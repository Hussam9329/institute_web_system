# ============================================
# routes/api_routes.py
# نقاط نهاية API للعمليات AJAX
# ============================================

from fastapi import APIRouter, HTTPException, Body, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from database import Database
from services.finance_service import finance_service, sync_student_status
from services.cache_service import cache_service
from services.teaching_types import get_fee_for_study_type, get_deduction_for_study_type, parse_custom_type_settings
from config import get_current_date, format_currency, get_client_timestamp
from auth import check_permission
from services.audit_service import log_action
from services.deletion_guard_service import _deletion_guard_service as deletion_guard

router = APIRouter(prefix="/api")


def _invalidate_dashboard_cache():
    """إلغاء التخزين المؤقت للوحة التحكم عند تغيير البيانات"""
    cache_service.invalidate_pattern('dashboard_')


# ===== نماذج API =====

class LinkStudentTeacher(BaseModel):
    student_id: int
    teacher_id: int
    study_type: str = "حضوري"
    status: str = "مستمر"


class AddInstallment(BaseModel):
    student_id: int
    teacher_id: int
    amount: int = Field(..., gt=0)
    payment_date: str
    installment_type: str = "القسط الأول"
    study_type: Optional[str] = "حضوري"
    notes: Optional[str] = ""
    for_installment: Optional[str] = ""  # للدفعات: يحدد القسط الذي تنتمي إليه (القسط الأول أو القسط الثاني)


class AddWithdrawal(BaseModel):
    teacher_id: int
    amount: int = Field(..., gt=0)
    withdrawal_date: str
    notes: Optional[str] = ""


class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class SubjectUpdate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


# ===== عمليات المواد الدراسية =====

@router.get("/subjects")
async def api_get_subjects():
    """الحصول على قائمة جميع المواد الدراسية"""
    db = Database()
    query = "SELECT * FROM subjects ORDER BY name"
    results = db.execute_query(query)
    return {"success": True, "data": [dict(r) for r in results] if results else []}


@router.post("/subjects")
async def api_add_subject(request: Request, subject: SubjectCreate):
    """إضافة مادة دراسية جديدة"""
    check_permission(request, 'add_subjects')
    db = Database()
    try:
        # التحقق من عدم وجود المادة
        existing = db.execute_query("SELECT id FROM subjects WHERE name = %s", (subject.name,))
        if existing:
            return {"success": False, "message": "هذه المادة موجودة مسبقاً"}
        
        result = db.execute_query(
            "INSERT INTO subjects (name, created_at) VALUES (%s, %s) RETURNING id",
            (subject.name, get_current_date(get_client_timestamp(request)))
        )
        subject_id = result[0]['id'] if result else ""
        log_action(
            request,
            action="create",
            entity="subject",
            entity_id=subject_id,
            description=f"إضافة مادة: {subject.name}"
        )
        _invalidate_dashboard_cache()
        return {"success": True, "message": "تم إضافة المادة بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.put("/subjects/{subject_id}")
async def api_update_subject(request: Request, subject_id: int, subject: SubjectUpdate):
    """تحديث مادة دراسية"""
    check_permission(request, 'edit_subjects')
    db = Database()
    try:
        existing = db.execute_query("SELECT id FROM subjects WHERE id = %s", (subject_id,))
        if not existing:
            return {"success": False, "message": "المادة غير موجودة"}
        
        dup = db.execute_query("SELECT id FROM subjects WHERE name = %s AND id != %s", (subject.name, subject_id))
        if dup:
            return {"success": False, "message": "اسم المادة موجود مسبقاً"}
        
        db.execute_query("UPDATE subjects SET name = %s WHERE id = %s", (subject.name, subject_id))
        _invalidate_dashboard_cache()
        return {"success": True, "message": "تم تحديث المادة بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.delete("/subjects/{subject_id}")
async def api_delete_subject(request: Request, subject_id: int):
    """حذف مادة دراسية"""
    check_permission(request, 'delete_subjects')
    try:
        guard = deletion_guard.can_delete_subject(subject_id)
        if not guard.allowed:
            return guard.to_dict()
        
        db = Database()
        subject_row = db.execute_query("SELECT name FROM subjects WHERE id = %s", (subject_id,))
        subject_name = subject_row[0]['name'] if subject_row else str(subject_id)
        db.execute_query("DELETE FROM subjects WHERE id = %s", (subject_id,))
        log_action(
            request,
            action="delete",
            entity="subject",
            entity_id=subject_id,
            description=f"حذف مادة: {subject_name}"
        )
        _invalidate_dashboard_cache()
        return {"success": True, "message": "تم حذف المادة"}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


# ===== عمليات الطلاب =====

@router.get("/students/{student_id}")
async def api_get_student(request: Request, student_id: int):
    """الحصول على بيانات طالب"""
    check_permission(request, 'preview_students')
    db = Database()
    query = "SELECT * FROM students WHERE id = %s"
    result = db.execute_query(query, (student_id,))
    
    if not result:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    return {"success": True, "data": dict(result[0])}


@router.get("/students/{student_id}/teachers")
async def api_get_student_teachers(request: Request, student_id: int):
    """الحصول على قائمة مدرسي طالب"""
    check_permission(request, 'preview_students')
    teachers_summary = finance_service.get_student_all_teachers_summary(student_id)
    return {"success": True, "data": teachers_summary}


# ===== عمليات المدرسين =====

@router.get("/teachers")
async def api_get_all_teachers(request: Request):
    """الحصول على قائمة جميع المدرسين"""
    check_permission(request, 'view_teachers_list')
    db = Database()
    query = "SELECT id, name, subject, total_fee, notes, teaching_types, fee_in_person, fee_electronic, fee_blended, custom_type_settings FROM teachers ORDER BY name"
    results = db.execute_query(query)
    
    return {"success": True, "data": [dict(r) for r in results] if results else []}


@router.get("/teachers/{teacher_id}")
async def api_get_teacher(request: Request, teacher_id: int):
    """الحصول على بيانات مدرس"""
    check_permission(request, 'preview_teachers')
    db = Database()
    query = "SELECT * FROM teachers WHERE id = %s"
    result = db.execute_query(query, (teacher_id,))
    
    if not result:
        raise HTTPException(status_code=404, detail="المدرس غير موجود")
    
    return {"success": True, "data": dict(result[0])}


@router.get("/teachers/{teacher_id}/balance")
async def api_get_teacher_balance(request: Request, teacher_id: int):
    """الحصول على الرصيد المالي للمدرس"""
    check_permission(request, 'view_teacher_balance')
    balance = finance_service.calculate_teacher_balance(teacher_id)
    return {"success": True, "data": balance}


@router.get("/teachers/{teacher_id}/balance-at-date")
async def api_get_teacher_balance_at_date(request: Request, teacher_id: int, date: str):
    """الحصول على رصيد المدرس المتاح بتاريخ محدد"""
    check_permission(request, 'view_teacher_balance')

    if not date:
        return {
            "success": False,
            "message": "يجب تحديد التاريخ"
        }

    balance = finance_service.calculate_teacher_balance_until(teacher_id, date)

    return {
        "success": True,
        "data": balance
    }


@router.get("/teachers/{teacher_id}/students")
async def api_get_teacher_students(request: Request, teacher_id: int):
    """الحصول على قائمة طلاب مدرس"""
    check_permission(request, 'preview_teachers')
    students = finance_service.get_teacher_students_list(teacher_id)
    return {"success": True, "data": students}


# ===== ربط الطالب بمدرس =====

@router.post("/link-student-teacher")
async def api_link_student_teacher(request: Request, link: LinkStudentTeacher):
    """ربط طالب بمدرس"""
    check_permission(request, 'link_students')
    db = Database()
    
    try:
        student_check = db.execute_query("SELECT id FROM students WHERE id = %s", (link.student_id,))
        teacher_check = db.execute_query("SELECT id, subject FROM teachers WHERE id = %s", (link.teacher_id,))
        
        if not student_check or not teacher_check:
            raise HTTPException(status_code=404, detail="الطالب أو المدرس غير موجود")
        
        existing = db.execute_query(
            "SELECT * FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
            (link.student_id, link.teacher_id)
        )
        
        if existing:
            return {"success": False, "message": "الربط موجود مسبقاً"}
        
        # Check if student is already linked to another teacher with the same subject
        teacher_subject = teacher_check[0]['subject']
        same_subject_links = db.execute_query('''
            SELECT st.teacher_id, t.name as teacher_name, st.status
            FROM student_teacher st
            JOIN teachers t ON st.teacher_id = t.id
            WHERE st.student_id = %s AND t.subject = %s
        ''', (link.student_id, teacher_subject))
        
        # بناء قائمة المواد المسجلة للتنبيه
        registered_subjects = []
        if same_subject_links:
            for link_row in same_subject_links:
                if link_row['teacher_id'] != link.teacher_id:
                    link_status = link_row.get('status', 'مستمر')
                    if link_status != 'منسحب':
                        registered_subjects.append(f"{teacher_subject} (المدرس: {link_row['teacher_name']})")
        
        if registered_subjects:
            subjects_str = ' - '.join(registered_subjects)
            return {"success": False, "message": f"الطالب مسجل بالمادة ({subjects_str}) ولا يمكن ربطه بأكثر من مدرس لنفس المادة"}
        
        db.execute_query(
            "INSERT INTO student_teacher (student_id, teacher_id, study_type, status) VALUES (%s, %s, %s, %s)",
            (link.student_id, link.teacher_id, link.study_type, link.status)
        )
        
        sync_student_status(link.student_id)
        _invalidate_dashboard_cache()

        log_action(
            request,
            action="link",
            entity="student_teacher",
            entity_id=f"{link.student_id}-{link.teacher_id}",
            description=f"ربط الطالب {link.student_id} بالمدرس {link.teacher_id}"
        )

        return {"success": True, "message": "تم الربط بنجاح"}
        
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.post("/link-student-teachers")
async def api_link_student_teachers(request: Request, data: dict):
    """ربط طالب بعدة مدرسين"""
    check_permission(request, 'link_students')
    db = Database()
    student_id = data.get("student_id")
    teacher_ids = data.get("teacher_ids", [])
    
    if not student_id or not teacher_ids:
        return {"success": False, "message": "بيانات ناقصة"}
    
    try:
        linked = 0
        for teacher_id in teacher_ids:
            tid = int(teacher_id)
            existing = db.execute_query(
                "SELECT * FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
                (student_id, tid)
            )
            if existing:
                continue
            
            # Check if student is already linked to another teacher with the same subject
            teacher_check = db.execute_query("SELECT subject FROM teachers WHERE id = %s", (tid,))
            if teacher_check:
                teacher_subject = teacher_check[0]['subject']
                same_subject_links = db.execute_query('''
                    SELECT st.teacher_id, st.status, t.name as teacher_name
                    FROM student_teacher st
                    JOIN teachers t ON st.teacher_id = t.id
                    WHERE st.student_id = %s AND t.subject = %s
                ''', (student_id, teacher_subject))
                
                if same_subject_links:
                    for link_row in same_subject_links:
                        if link_row['teacher_id'] != tid:
                            link_status = link_row.get('status', 'مستمر')
                            if link_status != 'منسحب':
                                return {"success": False, "message": f"الطالب مسجل بالمادة ({teacher_subject}) عند المدرس ({link_row['teacher_name']}) ولا يمكن ربطه بأكثر من مدرس لنفس المادة"}
            
            st_study_type = data.get("study_type", "حضوري")
            st_status = data.get("status", "مستمر")
            db.execute_query(
                "INSERT INTO student_teacher (student_id, teacher_id, study_type, status) VALUES (%s, %s, %s, %s)",
                (student_id, tid, st_study_type, st_status)
            )
            linked += 1
        
        sync_student_status(int(student_id))
        _invalidate_dashboard_cache()
        return {"success": True, "message": f"تم ربط الطالب بـ {linked} مدرس"}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.put("/update-student-discount/{student_id}/{teacher_id}")
async def api_update_student_discount(request: Request, student_id: int, teacher_id: int, data: dict):
    """تحديث خصم الطالب عند مدرس معين"""
    check_permission(request, 'add_payments')
    db = Database()
    
    try:
        discount_type = data.get('discount_type', 'none')
        discount_value = int(data.get('discount_value', 0))
        institute_waiver = int(data.get('institute_waiver', 0))
        
        # التحقق من صحة القيم
        if discount_type not in ('none', 'percentage', 'fixed', 'custom', 'free'):
            return {"success": False, "message": "نوع الخصم غير صالح"}
        
        if discount_type in ('percentage', 'custom') and (discount_value < 1 or discount_value > 99):
            return {"success": False, "message": "نسبة الخصم يجب أن تكون بين 1% و 99%. إذا كنت تريد خصم 100% اختر نوع 'مجاني'."}
        
        if discount_type == 'fixed' and discount_value <= 0:
            return {"success": False, "message": "قيمة الخصم الثابت يجب أن تكون أكبر من صفر"}
        
        # فحص حد الخصم الثابت: لا يمكن أن يتجاوز القسط الكلي للمدرس
        if discount_type == 'fixed' and discount_value > 0:
            teacher_row = db.execute_query(
                "SELECT fee_in_person, fee_electronic, fee_blended, total_fee, custom_type_settings FROM teachers WHERE id = %s",
                (teacher_id,)
            )
            if teacher_row:
                from services.teaching_types import get_fee_for_study_type
                link_row = db.execute_query(
                    "SELECT study_type FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
                    (student_id, teacher_id)
                )
                study_type = link_row[0]['study_type'] if link_row else 'حضوري'
                teacher_fee = get_fee_for_study_type(dict(teacher_row[0]), study_type)
                if teacher_fee > 0 and discount_value > teacher_fee:
                    return {"success": False, "message": f"مبلغ الخصم الثابت ({format_currency(discount_value)}) يتجاوز القسط الكلي ({format_currency(teacher_fee)}). الحد الأقصى المسموح: {format_currency(teacher_fee)}."}
        
        if discount_type == 'free' and institute_waiver not in (0, 1):
            return {"success": False, "message": "قيمة تنازل المعهد غير صالحة"}
        
        # التحقق من وجود الربط
        link = db.execute_query(
            "SELECT status, discount_type FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
            (student_id, teacher_id)
        )
        
        if not link:
            return {"success": False, "message": "الربط غير موجود"}
        
        # ===== فحص اكتمال الأقساط: لا يسمح بالخصم بعد اتمام جميع الأقساط =====
        current_balance = finance_service.calculate_student_teacher_balance(student_id, teacher_id)
        current_discount_type = link[0].get('discount_type', 'none') or 'none'
        
        # إذا كان الطالب أكمل جميع أقساطه (remaining_balance <= 0) وهناك محاولة لتغيير الخصم
        if current_balance['remaining_balance'] <= 0 and current_balance['paid_total'] > 0:
            # السماح فقط إذا لم يتغير شيء فعلياً
            value_changed = False
            if discount_type != current_discount_type:
                value_changed = True
            else:
                new_discount_value = int(data.get('discount_value', 0))
                old_discount_value = link[0].get('discount_value', 0) or 0
                if new_discount_value != old_discount_value:
                    value_changed = True
                new_waiver = int(data.get('institute_waiver', 0))
                old_waiver = link[0].get('institute_waiver', 0) or 0
                if new_waiver != old_waiver:
                    value_changed = True

            if value_changed:
                return {
                    "success": False,
                    "message": f"لا يمكن تعديل الخصم! الطالب أتمّ جميع أقساطه لدى هذا المدرس (المدفوع: {format_currency(current_balance['paid_total'])} من {format_currency(current_balance['total_fee'])})"
                }
        
        # ===== التحقق الشامل: لا يمكن تطبيق أي خصم يجعل المدفوع يتجاوز القسط الجديد =====
        if current_balance['paid_total'] > 0 and discount_type != 'none':
            original_fee = current_balance.get('original_fee', current_balance['total_fee'])
            
            # حساب القسط الجديد بعد الخصم المطلوب
            if discount_type == 'free':
                new_fee = 0
            elif discount_type in ('percentage', 'custom'):
                new_fee = original_fee - round(original_fee * discount_value / 100)
            elif discount_type == 'fixed':
                new_fee = original_fee - discount_value
            else:
                new_fee = original_fee
            
            if current_balance['paid_total'] > new_fee:
                if discount_type == 'free':
                    return {
                        "success": False, 
                        "message": f"لا يمكن تحويل الطالب إلى مجاني! الطالب لديه مدفوعات ({format_currency(current_balance['paid_total'])}) تتجاوز القسط بعد الخصم (0)"
                    }
                else:
                    return {
                        "success": False, 
                        "message": f"لا يمكن تطبيق هذا الخصم! المبلغ المدفوع ({format_currency(current_balance['paid_total'])}) يتجاوز القسط بعد الخصم ({format_currency(new_fee)})"
                    }
        
        # إذا كان الطالب "مجاني" - لا يمكن تسجيل أقساط مستقبلاً
        # لكن الأقساط السابقة تبقى محفوظة
        
        db.execute_query(
            """UPDATE student_teacher 
               SET discount_type = %s, discount_value = %s, institute_waiver = %s 
               WHERE student_id = %s AND teacher_id = %s""",
            (discount_type, discount_value, institute_waiver, student_id, teacher_id)
        )
        
        # حساب الرصيد الجديد
        new_balance = finance_service.calculate_student_teacher_balance(student_id, teacher_id)
        _invalidate_dashboard_cache()
        return {
            "success": True, 
            "message": "تم تحديث الخصم بنجاح",
            "new_balance": new_balance
        }
        
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.get("/student-discount/{student_id}/{teacher_id}")
async def api_get_student_discount(student_id: int, teacher_id: int):
    """الحصول على معلومات خصم الطالب عند مدرس"""
    discount_info = finance_service._get_discount_info(student_id, teacher_id)
    # إضافة معلومات الرصيد لفحص اكتمال الأقساط
    balance = finance_service.calculate_student_teacher_balance(student_id, teacher_id)
    discount_info['remaining_balance'] = balance['remaining_balance']
    discount_info['paid_total'] = balance['paid_total']
    discount_info['total_fee'] = balance['total_fee']
    return {"success": True, "data": discount_info}


@router.put("/update-student-teacher-link/{student_id}/{teacher_id}")
async def api_update_student_teacher_link(request: Request, student_id: int, teacher_id: int, data: dict):
    """تحديث نوع الدراسة والحالة لربط طالب بمدرس - مع منع تغيير نوع الدراسة أو التحويل لمنسحب إذا وُجدت مدفوعات"""
    check_permission(request, 'link_students')
    db = Database()
    
    try:
        new_study_type = data.get("study_type", "حضوري")
        status = data.get("status", "مستمر")
        
        # فحص وجود أقساط مدفوعة - يُمنع تغيير نوع الدراسة أو التحويل لمنسحب نهائياً
        payment_check = db.execute_query(
            "SELECT COUNT(*) as cnt FROM installments WHERE student_id = %s AND teacher_id = %s",
            (student_id, teacher_id)
        )
        has_payments = payment_check and payment_check[0]['cnt'] > 0
        
        if has_payments:
            # لا يمكن التحويل إلى منسحب إذا وُجدت أقساط
            if status == 'منسحب':
                return {"success": False, "message": f"لا يمكن تغيير الحالة إلى منسحب! يوجد {payment_check[0]['cnt']} قسط مسجل بين الطالب وهذا المدرس. يجب حذف جميع الأقساط أولاً."}
            
            # جلب نوع الدراسة الحالي والحفاظ عليه
            current_link = db.execute_query(
                "SELECT study_type FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
                (student_id, teacher_id)
            )
            current_study_type = current_link[0]['study_type'] if current_link else 'حضوري'
            # تحديث الحالة فقط مع الحفاظ على نوع الدراسة
            db.execute_query(
                "UPDATE student_teacher SET status = %s WHERE student_id = %s AND teacher_id = %s",
                (status, student_id, teacher_id)
            )
            return {"success": True, "message": "تم تحديث الحالة فقط. لا يمكن تغيير نوع الدراسة لوجود أقساط مسجلة."}
        else:
            # لا يمكن التحويل إلى منسحب عبر هذه الواجهة - يجب استخدام إلغاء الربط
            if status == 'منسحب':
                return {"success": False, "message": "لا يمكن تغيير الحالة إلى منسحب. استخدم زر إلغاء الربط بدلاً من ذلك."}
            
            # لا توجد مدفوعات - يمكن تحديث كل شيء
            db.execute_query(
                "UPDATE student_teacher SET study_type = %s, status = %s WHERE student_id = %s AND teacher_id = %s",
                (new_study_type, status, student_id, teacher_id)
            )
        
        sync_student_status(student_id)
        _invalidate_dashboard_cache()
        return {"success": True, "message": "تم التحديث بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.delete("/unlink-student-teacher/{student_id}/{teacher_id}")
async def api_unlink_student_teacher(request: Request, student_id: int, teacher_id: int):
    """إلغاء ربط طالب بمدرس - مسموح فقط في حالة عدم وجود أقساط بينهما"""
    check_permission(request, 'link_students')
    db = Database()
    
    try:
        # التحقق من وجود الربط
        link = db.execute_query(
            "SELECT status FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
            (student_id, teacher_id)
        )
        
        if not link:
            return {"success": False, "message": "الربط غير موجود"}
        
        current_status = link[0].get('status', 'مستمر')
        if current_status == 'منسحب':
            return {"success": False, "message": "الطالب بالفعل منسحب من هذا المدرس"}
        
        # فحص وجود أقساط بين الطالب والمدرس - لا يمكن إلغاء الربط إذا وُجدت أقساط
        installment_count = db.execute_query(
            "SELECT COUNT(*) as cnt FROM installments WHERE student_id = %s AND teacher_id = %s",
            (student_id, teacher_id)
        )
        count = installment_count[0]['cnt'] if installment_count else 0
        
        if count > 0:
            return {
                "success": False, 
                "message": f"لا يمكن إلغاء الربط! يوجد {count} قسط مسجل بين الطالب وهذا المدرس. يجب حذف جميع الأقساط أولاً قبل إلغاء الربط."
            }
        
        # لا توجد أقساط - يمكن إلغاء الربط
        # حذف الربط نهائياً بدلاً من تغيير الحالة (لأنه لا توجد سجلات مالية)
        db.execute_query(
            "DELETE FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
            (student_id, teacher_id)
        )
        
        sync_student_status(student_id)
        
        _invalidate_dashboard_cache()

        log_action(
            request,
            action="unlink",
            entity="student_teacher",
            entity_id=f"{student_id}-{teacher_id}",
            description=f"إلغاء ربط الطالب {student_id} من المدرس {teacher_id}"
        )

        return {"success": True, "message": "تم إلغاء الربط بنجاح", "preserved_installments": 0}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


# ===== عمليات الأقساط =====

@router.post("/installments")
async def api_add_installment(request: Request, installment: AddInstallment):
    """إضافة قسط جديد"""
    check_permission(request, 'add_payments')
    db = Database()
    
    try:
        link_check = db.execute_query(
            "SELECT * FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
            (installment.student_id, installment.teacher_id)
        )
        
        if link_check:
            # لا نسمح بتغيير نوع الدراسة عند وجود ربط - نحافظ على النوع المحدد مسبقاً
            # نوع الدراسة يُحدد عند الربط فقط ولا يمكن تغييره بعد ذلك
            pass
        else:
            # التحقق من أن الطالب ليس مربوطاً بمدرس آخر لنفس المادة
            teacher_check = db.execute_query("SELECT subject FROM teachers WHERE id = %s", (installment.teacher_id,))
            if teacher_check:
                teacher_subject = teacher_check[0]['subject']
                same_subject_links = db.execute_query('''
                    SELECT st.teacher_id, st.status, t.name as teacher_name
                    FROM student_teacher st
                    JOIN teachers t ON st.teacher_id = t.id
                    WHERE st.student_id = %s AND t.subject = %s
                ''', (installment.student_id, teacher_subject))
                
                if same_subject_links:
                    for link_row in same_subject_links:
                        if link_row['teacher_id'] != installment.teacher_id:
                            link_status = link_row.get('status', 'مستمر')
                            if link_status != 'منسحب':
                                return {
                                    "success": False,
                                    "message": f"لا يمكن تسجيل قسط لهذا المدرس! الطالب مسجل بالمادة ({teacher_subject}) عند المدرس ({link_row['teacher_name']})"
                                }
            
            # تحديد نوع الدراسة: من الطلب أو النوع الأول المتاح للمدرس
            auto_study_type = installment.study_type or 'حضوري'
            teacher_info = db.execute_query("SELECT teaching_types FROM teachers WHERE id = %s", (installment.teacher_id,))
            if teacher_info:
                tt_list = [t.strip() for t in (teacher_info[0].get('teaching_types') or 'حضوري').split(',') if t.strip()]
                if auto_study_type not in tt_list:
                    auto_study_type = tt_list[0] if tt_list else 'حضوري'
            
            db.execute_query(
                "INSERT INTO student_teacher (student_id, teacher_id, study_type, status) VALUES (%s, %s, %s, 'مستمر')",
                (installment.student_id, installment.teacher_id, auto_study_type)
            )
        
        # التحقق: هل الطالب مجاني؟
        discount_info = finance_service._get_discount_info(installment.student_id, installment.teacher_id)
        if discount_info.get('discount_type') == 'free':
            return {
                "success": False,
                "message": "الطالب مجاني - لا يمكن تسجيل أقساط له"
            }

        # ===== التحقق من نوع القسط والتعارض مع الأقساط الموجودة =====
        existing_types_query = db.execute_query(
            "SELECT DISTINCT installment_type FROM installments WHERE student_id = %s AND teacher_id = %s",
            (installment.student_id, installment.teacher_id)
        )
        existing_types = set()
        if existing_types_query:
            for row in existing_types_query:
                itype = row.get('installment_type', '')
                if itype:
                    existing_types.add(itype)
        
        has_existing_first = 'القسط الأول' in existing_types
        has_existing_second = 'القسط الثاني' in existing_types
        has_existing_full = 'دفع كامل' in existing_types
        has_existing_splits = 'دفعات' in existing_types
        has_any_existing = len(existing_types - {'دفعات'}) > 0  # الدفعات لا تمنع إضافة أقساط جديدة
        
        new_type = installment.installment_type
        
        # القواعد:
        # 1. "دفع كامل" → مسموح إذا لم توجد أي أقساط سابقة، أو إذا وُجد القسط الأول فقط، أو إذا كان المبلغ يغطي كامل المتبقي
        current_balance_preview = finance_service.calculate_student_teacher_balance(
            installment.student_id, installment.teacher_id
        )
        remaining_preview = current_balance_preview['total_fee'] - current_balance_preview['paid_total']
        will_close_balance = remaining_preview > 0 and installment.amount >= remaining_preview

        if new_type == 'دفع كامل' and has_any_existing and not will_close_balance:
            # السماح بتحويل القسط الأول إلى دفع كامل (الطالب دفع القسط الأول ويريد تحويله لدفع كامل)
            if has_existing_first and not has_existing_second and not has_existing_full:
                pass  # مسموح - تحويل من دفعات إلى دفع كامل
            else:
                return {
                    "success": False,
                    "message": "لا يمكن تسجيل دفع كامل! يوجد أقساط مسجلة مسبقاً لهذا الطالب عند هذا المدرس"
                }
        
        # 2. "القسط الثاني" → مسموح فقط إذا وُجد "القسط الأول" أو دفعات للقسط الأول ولم يُسجل "القسط الثاني" سابقاً
        if new_type == 'القسط الثاني':
            if not has_existing_first and not has_existing_splits:
                return {
                    "success": False,
                    "message": "لا يمكن تسجيل القسط الثاني! يجب تسجيل القسط الأول أولاً"
                }
            if has_existing_second:
                return {
                    "success": False,
                    "message": "لا يمكن تسجيل القسط الثاني مرتين! القسط الثاني مسجل مسبقاً"
                }
            if has_existing_full:
                return {
                    "success": False,
                    "message": "لا يمكن تسجيل القسط الثاني! يوجد دفع كامل مسجل مسبقاً"
                }
        
        # 3. "القسط الأول" → مسموح فقط إذا لم يُسجل مسبقاً ولم يُسجل "دفع كامل" أو "القسط الثاني"
        if new_type == 'القسط الأول':
            if has_existing_first:
                return {
                    "success": False,
                    "message": "لا يمكن تسجيل القسط الأول مرتين! القسط الأول مسجل مسبقاً. يمكنك استخدام 'دفعات' لتسجيل دفعات إضافية للقسط الأول"
                }
            if has_existing_full:
                return {
                    "success": False,
                    "message": "لا يمكن تسجيل القسط الأول! يوجد دفع كامل مسجل مسبقاً"
                }
            if has_existing_second:
                return {
                    "success": False,
                    "message": "لا يمكن تسجيل القسط الأول! يوجد قسط ثاني مسجل مسبقاً"
                }
        
        # 4. "دفعات" → مسموح دائماً إذا لم يُسجل "دفع كامل"
        if new_type == 'دفعات':
            if has_existing_full:
                return {
                    "success": False,
                    "message": "لا يمكن تسجيل دفعات! يوجد دفع كامل مسجل مسبقاً"
                }
            # التحقق من أن for_installment محدد وقيمته صحيحة
            for_inst = installment.for_installment or ''
            if for_inst and for_inst not in ('القسط الأول', 'القسط الثاني'):
                return {
                    "success": False,
                    "message": "قيمة for_installment غير صحيحة. يجب أن تكون 'القسط الأول' أو 'القسط الثاني'"
                }
            # إذا لم يتم تحديد for_installment، حدده تلقائياً
            if not for_inst:
                if has_existing_second:
                    # إذا وُجد القسط الثاني، الدفعات تنتمي له
                    installment.for_installment = 'القسط الثاني'
                else:
                    # افتراضي: الدفعات تنتمي للقسط الأول
                    installment.for_installment = 'القسط الأول'

        # التحقق: المبلغ المدفوع لا يتجاوز القسط الكلي
        current_balance = finance_service.calculate_student_teacher_balance(
            installment.student_id, installment.teacher_id
        )
        total_fee = current_balance['total_fee']
        already_paid = current_balance['paid_total']
        new_total = already_paid + installment.amount
        
        if total_fee <= 0:
            return {
                "success": False,
                "message": "لا يمكن تسجيل قسط - القسط الكلي صفر (طالب مجاني أو خصم كامل)"
            }

        if new_total > total_fee:
            remaining = total_fee - already_paid
            return {
                "success": False,
                "message": f"لا يمكن تسجيل دفعة أكبر من المتبقي. المتبقي الحالي هو {format_currency(remaining)} د.ع. (القسط الكلي {format_currency(total_fee)}، المدفوع {format_currency(already_paid)})"
            }

        # ===== حساب المتبقي قبل الدفع لتحديد ما إذا كان سيغلق الرصيد =====
        remaining_before_payment = total_fee - already_paid
        will_close_balance = remaining_before_payment > 0 and installment.amount >= remaining_before_payment

        # ===== تحويل تلقائي إلى دفع كامل عند تسديد كامل المتبقي =====
        # الهدف: إذا دفع الطالب كل المتبقي، لا يبقى القسط مسجل كـ قسط أول أو دفعات
        auto_converted = False
        if remaining_before_payment > 0 and installment.amount >= remaining_before_payment:
            installment.installment_type = 'دفع كامل'
            installment.for_installment = ''
            auto_converted = True

        from config import get_current_date as _get_current_date
        
        _client_ts = get_client_timestamp(request)

        insert_query = '''
            INSERT INTO installments (student_id, teacher_id, amount, payment_date, installment_type, for_installment, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        '''
        
        result = db.execute_query(insert_query, (
            installment.student_id,
            installment.teacher_id,
            installment.amount,
            installment.payment_date,
            installment.installment_type,
            installment.for_installment or '',
            installment.notes,
            _get_current_date(_client_ts)
        ))
        installment_id = result[0]['id'] if result else None
        
        new_balance = finance_service.calculate_student_teacher_balance(
            installment.student_id, 
            installment.teacher_id
        )
        
        message = "تم إضافة القسط بنجاح"
        if auto_converted:
            message = f"تم تسجيل الدفع كـ 'دفع كامل' لأن المبلغ المدفوع ({format_currency(installment.amount)}) يغطي كامل المتبقي."
        
        _invalidate_dashboard_cache()

        log_action(
            request,
            action="create",
            entity="installment",
            entity_id=installment_id,
            description=f"إضافة دفعة بمبلغ {installment.amount} للطالب {installment.student_id} عند المدرس {installment.teacher_id}"
        )

        return {
            "success": True, 
            "message": message,
            "new_balance": new_balance,
            "installment_id": installment_id,
            "auto_converted": auto_converted,
            "amount_warning": None
        }
        
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.get("/installments/student/{student_id}/teacher/{teacher_id}")
async def api_get_installments(request: Request, student_id: int, teacher_id: int):
    """الحصول على أقساط طالب عند مدرس معين"""
    check_permission(request, 'view_payments_list')
    db = Database()
    
    query = '''
        SELECT i.*, s.name as student_name, t.name as teacher_name
        FROM installments i
        JOIN students s ON i.student_id = s.id
        JOIN teachers t ON i.teacher_id = t.id
        WHERE i.student_id = %s AND i.teacher_id = %s
        ORDER BY i.payment_date DESC
    '''
    
    results = db.execute_query(query, (student_id, teacher_id))
    total_paid = finance_service.get_student_paid_total(student_id, teacher_id)
    
    # حساب أنواع الأقساط الموجودة للاستخدام في الواجهة
    existing_types = set()
    if results:
        for r in results:
            itype = r.get('installment_type', '')
            if itype:
                existing_types.add(itype)
    
    return {
        "success": True,
        "data": [dict(r) for r in results] if results else [],
        "total_paid": total_paid,
        "existing_types": list(existing_types)
    }


@router.get("/installments/allowed-types/{student_id}/{teacher_id}")
async def api_get_allowed_installment_types(request: Request, student_id: int, teacher_id: int):
    """الحصول على أنواع الأقساط المسموحة لطالب عند مدرس معين"""
    check_permission(request, 'view_payments_list')
    db = Database()
    
    try:
        existing_types_query = db.execute_query(
            "SELECT DISTINCT installment_type FROM installments WHERE student_id = %s AND teacher_id = %s",
            (student_id, teacher_id)
        )
        existing_types = set()
        if existing_types_query:
            for row in existing_types_query:
                itype = row.get('installment_type', '')
                if itype:
                    existing_types.add(itype)
        
        has_first = 'القسط الأول' in existing_types
        has_second = 'القسط الثاني' in existing_types
        has_full = 'دفع كامل' in existing_types
        has_splits = 'دفعات' in existing_types
        
        allowed = []
        
        # القسط الأول: مسموح فقط إذا لم يُسجل أي قسط من قبل (باستثناء الدفعات)
        if not has_first and not has_second and not has_full:
            allowed.append('القسط الأول')
        
        # القسط الثاني: مسموح فقط إذا وُجد القسط الأول أو دفعات ولم يُسجل القسط الثاني أو دفع كامل بعد
        if (has_first or has_splits) and not has_second and not has_full:
            allowed.append('القسط الثاني')
        
        # دفع كامل: مسموح إذا لم توجد أي أقساط رئيسية، أو إذا وُجد القسط الأول فقط (تحويل من دفعات إلى دفع كامل)
        if not existing_types or has_first and not has_second and not has_full:
            allowed.append('دفع كامل')
        
        # دفعات: مسموح دائماً إذا لم يُسجل "دفع كامل"
        # الدفعات تتيح تقسيم القسط الأول أو الثاني إلى دفعات أصغر
        if not has_full:
            # تحديد خيارات for_installment المتاحة
            split_options = []
            if not has_first and not has_second:
                # لا توجد أقساط بعد - يمكن عمل دفعات للقسط الأول
                split_options.append({'value': 'القسط الأول', 'label': 'دفعات للقسط الأول'})
            elif has_first and not has_second:
                # وُجد القسط الأول - يمكن عمل دفعات إضافية للقسط الأول أو الثاني
                split_options.append({'value': 'القسط الأول', 'label': 'دفعات إضافية للقسط الأول'})
                split_options.append({'value': 'القسط الثاني', 'label': 'دفعات للقسط الثاني'})
            elif has_second:
                # وُجد القسط الثاني - يمكن عمل دفعات إضافية
                split_options.append({'value': 'القسط الثاني', 'label': 'دفعات إضافية للقسط الثاني'})
            
            if split_options:
                allowed.append('دفعات')
        
        return {
            "success": True,
            "allowed_types": allowed,
            "existing_types": list(existing_types),
            "split_options": split_options if not has_full else []
        }
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.get("/installments/recent")
async def api_get_recent_installments(request: Request, limit: int = 20):
    """الحصول على آخر الأقساط المسجلة"""
    check_permission(request, 'view_payments_list')
    db = Database()
    query = '''
        SELECT i.*, s.name as student_name, t.name as teacher_name, t.subject as teacher_subject
        FROM installments i
        JOIN students s ON i.student_id = s.id
        JOIN teachers t ON i.teacher_id = t.id
        ORDER BY i.id DESC
        LIMIT %s
    '''
    results = db.execute_query(query, (limit,))
    return {"success": True, "data": [dict(r) for r in results] if results else []}


@router.delete("/installments/{installment_id}")
async def api_delete_installment(request: Request, installment_id: int):
    """حذف قسط - مسموح فقط لمدير النظام، مع إرجاع تفاصيل القسط المحذوف"""
    check_permission(request, 'delete_payments')
    
    try:
        user = getattr(request.state, 'user', None)
        guard = deletion_guard.can_delete_installment(installment_id, user)
        if not guard.allowed:
            return guard.to_dict()
        
        inst_data = guard.details.get('installment', {})
        db = Database()
        db.execute_query("DELETE FROM installments WHERE id = %s", (installment_id,))
        
        _invalidate_dashboard_cache()
        
        return {
            "success": True, 
            "message": "تم حذف القسط",
            "deleted_installment": inst_data
        }
        
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


# ===== فحص سلامة البيانات =====

@router.get("/data-integrity-check")
async def api_data_integrity_check(request: Request):
    """فحص السجلات التي تتنافى مع منطق النظام وشروطه"""
    check_permission(request, 'view_reports')
    db = Database()
    
    issues = []
    
    try:
        # 1. فحص: قسط أول مسجل لكن مبلغه يساوي القسط الكلي (كان يجب أن يكون "دفع كامل")
        query1 = '''
            SELECT i.id, i.student_id, i.teacher_id, i.amount, i.installment_type,
                   s.name as student_name, t.name as teacher_name,
                   st.discount_type, st.discount_value, st.institute_waiver,
                   t.total_fee, t.fee_in_person, t.fee_electronic, t.fee_blended,
                   t.custom_type_settings, st.study_type
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            JOIN student_teacher st ON st.student_id = i.student_id AND st.teacher_id = i.teacher_id
            WHERE i.installment_type = 'القسط الأول'
        '''
        first_installments = db.execute_query(query1)
        
        if first_installments:
            for inst in first_installments:
                # حساب القسط الفعلي
                study_type = inst.get('study_type', 'حضوري') or 'حضوري'
                original_fee = get_fee_for_study_type(inst, study_type)
                
                # تطبيق خصم الطالب
                discount_type = inst.get('discount_type', 'none') or 'none'
                discount_value = inst.get('discount_value', 0) or 0
                
                if discount_type == 'free':
                    effective_fee = 0
                elif discount_type in ('percentage', 'custom') and discount_value > 0:
                    effective_fee = original_fee - round(original_fee * discount_value / 100)
                elif discount_type == 'fixed' and discount_value > 0:
                    effective_fee = original_fee - discount_value
                else:
                    effective_fee = original_fee
                
                if effective_fee > 0 and inst['amount'] >= effective_fee:
                    issues.append({
                        'type': 'first_installment_equals_full',
                        'severity': 'high',
                        'installment_id': inst['id'],
                        'student_name': inst['student_name'],
                        'teacher_name': inst['teacher_name'],
                        'amount': inst['amount'],
                        'effective_fee': effective_fee,
                        'message': f"القسط الأول (#{inst['id']}) للطالب {inst['student_name']} عند المدرس {inst['teacher_name']}: المبلغ {format_currency(inst['amount'])} يساوي القسط الكلي {format_currency(effective_fee)} - كان يجب تسجيله كـ 'دفع كامل' بدلاً من 'القسط الأول' لضمان استقطاع نسبة المعهد كاملةً"
                    })
        
        # 2. فحص: مدفوعات تتجاوز القسط الكلي
        query2 = '''
            SELECT i.student_id, i.teacher_id, 
                   SUM(i.amount) as total_paid,
                   COUNT(*) as installment_count,
                   s.name as student_name, t.name as teacher_name,
                   st.discount_type, st.discount_value, st.institute_waiver,
                   t.total_fee, t.fee_in_person, t.fee_electronic, t.fee_blended,
                   t.custom_type_settings, st.study_type
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            JOIN student_teacher st ON st.student_id = i.student_id AND st.teacher_id = i.teacher_id
            GROUP BY i.student_id, i.teacher_id, s.name, t.name, 
                     st.discount_type, st.discount_value, st.institute_waiver,
                     t.total_fee, t.fee_in_person, t.fee_electronic, t.fee_blended,
                     t.custom_type_settings, st.study_type
            HAVING SUM(i.amount) > 0
        '''
        payment_totals = db.execute_query(query2)
        
        if payment_totals:
            for pt in payment_totals:
                study_type = pt.get('study_type', 'حضوري') or 'حضوري'
                original_fee = get_fee_for_study_type(pt, study_type)
                
                discount_type = pt.get('discount_type', 'none') or 'none'
                discount_value = pt.get('discount_value', 0) or 0
                
                if discount_type == 'free':
                    effective_fee = 0
                elif discount_type in ('percentage', 'custom') and discount_value > 0:
                    effective_fee = original_fee - round(original_fee * discount_value / 100)
                elif discount_type == 'fixed' and discount_value > 0:
                    effective_fee = original_fee - discount_value
                else:
                    effective_fee = original_fee
                
                if effective_fee > 0 and pt['total_paid'] > effective_fee:
                    overpayment = pt['total_paid'] - effective_fee
                    issues.append({
                        'type': 'overpayment',
                        'severity': 'medium',
                        'student_name': pt['student_name'],
                        'teacher_name': pt['teacher_name'],
                        'total_paid': pt['total_paid'],
                        'effective_fee': effective_fee,
                        'overpayment': overpayment,
                        'message': f"الطالب {pt['student_name']} عند المدرس {pt['teacher_name']}: المدفوع {format_currency(pt['total_paid'])} يتجاوز القسط الكلي {format_currency(effective_fee)} بمبلغ {format_currency(overpayment)}"
                    })
        
        # 3. فحص: طالب مجاني لديه أقساط مسجلة
        query3 = '''
            SELECT i.id, i.amount, i.installment_type,
                   s.name as student_name, t.name as teacher_name
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            JOIN student_teacher st ON st.student_id = i.student_id AND st.teacher_id = i.teacher_id
            WHERE st.discount_type = 'free'
        '''
        free_with_payments = db.execute_query(query3)
        if free_with_payments:
            for fwp in free_with_payments:
                issues.append({
                    'type': 'free_student_with_payment',
                    'severity': 'high',
                    'installment_id': fwp['id'],
                    'student_name': fwp['student_name'],
                    'teacher_name': fwp['teacher_name'],
                    'amount': fwp['amount'],
                    'message': f"الطالب {fwp['student_name']} مجاني لكن لديه قسط مسجل (#{fwp['id']}) بمبلغ {format_currency(fwp['amount'])} عند المدرس {fwp['teacher_name']}"
                })
        
        # 4. فحص: قسط ثاني بدون قسط أول
        query4 = '''
            SELECT i.id, i.amount, s.name as student_name, t.name as teacher_name
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            WHERE i.installment_type = 'القسط الثاني'
            AND NOT EXISTS (
                SELECT 1 FROM installments i2 
                WHERE i2.student_id = i.student_id 
                AND i2.teacher_id = i.teacher_id 
                AND i2.installment_type = 'القسط الأول'
            )
            AND NOT EXISTS (
                SELECT 1 FROM installments i3 
                WHERE i3.student_id = i.student_id 
                AND i3.teacher_id = i.teacher_id 
                AND i3.installment_type = 'دفعات'
            )
        '''
        second_without_first = db.execute_query(query4)
        if second_without_first:
            for swf in second_without_first:
                issues.append({
                    'type': 'second_without_first',
                    'severity': 'medium',
                    'installment_id': swf['id'],
                    'student_name': swf['student_name'],
                    'teacher_name': swf['teacher_name'],
                    'message': f"الطالب {swf['student_name']}: قسط ثاني مسجل (#{swf['id']}) بدون قسط أول عند المدرس {swf['teacher_name']}"
                })
        
        # 5. فحص: طلاب مربوطين بمدرسين بنفس المادة وحالة مستمر
        query5 = '''
            SELECT s.name as student_name, t1.name as teacher1_name, t2.name as teacher2_name, t1.subject
            FROM student_teacher st1
            JOIN student_teacher st2 ON st1.student_id = st2.student_id AND st1.teacher_id < st2.teacher_id
            JOIN students s ON st1.student_id = s.id
            JOIN teachers t1 ON st1.teacher_id = t1.id
            JOIN teachers t2 ON st2.teacher_id = t2.id
            WHERE t1.subject = t2.subject
            AND st1.status = 'مستمر' AND st2.status = 'مستمر'
        '''
        duplicate_subjects = db.execute_query(query5)
        if duplicate_subjects:
            for ds in duplicate_subjects:
                issues.append({
                    'type': 'duplicate_subject_link',
                    'severity': 'high',
                    'student_name': ds['student_name'],
                    'subject': ds['subject'],
                    'teacher1_name': ds['teacher1_name'],
                    'teacher2_name': ds['teacher2_name'],
                    'message': f"الطالب {ds['student_name']} مربوط بمدرسين لنفس المادة ({ds['subject']}): {ds['teacher1_name']} و {ds['teacher2_name']}"
                })
        
        return {
            "success": True,
            "total_issues": len(issues),
            "high_severity": len([i for i in issues if i.get('severity') == 'high']),
            "medium_severity": len([i for i in issues if i.get('severity') == 'medium']),
            "issues": issues
        }
        
    except Exception as e:
        return {"success": False, "message": f"خطأ في فحص البيانات: {str(e)}"}


@router.post("/fix-first-installment-to-full")
async def api_fix_first_to_full(request: Request):
    """إصلاح: تحويل الأقساط الأولى التي يساوي مبلغها القسط الكلي إلى 'دفع كامل'"""
    check_permission(request, 'delete_payments')  # يتطلب صلاحية عالية
    db = Database()
    
    try:
        user = getattr(request.state, 'user', None)
        if not user or user.get('role_name', '') != 'مدير عام':
            return {"success": False, "message": "فقط مدير النظام يمكنه تنفيذ هذا الإصلاح"}
        
        # البحث عن الأقساط الأولى التي يساوي مبلغها القسط الكلي
        query = '''
            SELECT i.id, i.student_id, i.teacher_id, i.amount,
                   s.name as student_name, t.name as teacher_name,
                   st.discount_type, st.discount_value, st.institute_waiver,
                   t.total_fee, t.fee_in_person, t.fee_electronic, t.fee_blended,
                   t.custom_type_settings, st.study_type
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            JOIN student_teacher st ON st.student_id = i.student_id AND st.teacher_id = i.teacher_id
            WHERE i.installment_type = 'القسط الأول'
        '''
        first_installments = db.execute_query(query)
        
        fixed = []
        if first_installments:
            for inst in first_installments:
                study_type = inst.get('study_type', 'حضوري') or 'حضوري'
                original_fee = get_fee_for_study_type(inst, study_type)
                
                discount_type = inst.get('discount_type', 'none') or 'none'
                discount_value = inst.get('discount_value', 0) or 0
                
                if discount_type == 'free':
                    effective_fee = 0
                elif discount_type in ('percentage', 'custom') and discount_value > 0:
                    effective_fee = original_fee - round(original_fee * discount_value / 100)
                elif discount_type == 'fixed' and discount_value > 0:
                    effective_fee = original_fee - discount_value
                else:
                    effective_fee = original_fee
                
                if effective_fee > 0 and inst['amount'] >= effective_fee:
                    # تحويل إلى دفع كامل
                    db.execute_query(
                        "UPDATE installments SET installment_type = 'دفع كامل', for_installment = '' WHERE id = %s",
                        (inst['id'],)
                    )
                    fixed.append({
                        'installment_id': inst['id'],
                        'student_name': inst['student_name'],
                        'teacher_name': inst['teacher_name'],
                        'amount': inst['amount'],
                        'effective_fee': effective_fee
                    })
        
        return {
            "success": True,
            "message": f"تم إصلاح {len(fixed)} قسط: تحويل من 'القسط الأول' إلى 'دفع كامل'",
            "fixed_count": len(fixed),
            "fixed_records": fixed
        }
        
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


# ===== عمليات السحوبات =====

@router.post("/withdrawals")
async def api_add_withdrawal(request: Request, withdrawal: AddWithdrawal):
    """تسجيل سحب جديد للمدرس"""
    check_permission(request, 'add_withdrawals')
    db = Database()
    
    try:
        amount = withdrawal.amount

        if not withdrawal.withdrawal_date:
            return {"success": False, "message": "يجب تحديد تاريخ السحب"}

        # ===== التحقق: لا يمكن سحب مبلغ أكبر من مستحق المدرس المتاح =====
        can_withdraw, message, balance = finance_service.can_teacher_withdraw_on_date(
            withdrawal.teacher_id,
            amount,
            withdrawal.withdrawal_date
        )
        
        if not can_withdraw:
            return {"success": False, "message": f"لا يمكن تسجيل السحب. الرصيد المتاح للمدرس هو {format_currency(balance)} فقط. {message}"}
        
        insert_query = '''
            INSERT INTO teacher_withdrawals (teacher_id, amount, withdrawal_date, notes)
            VALUES (%s, %s, %s, %s)
        '''
        
        db.execute_query(insert_query, (
            withdrawal.teacher_id,
            amount,
            withdrawal.withdrawal_date,
            withdrawal.notes
        ))
        
        new_balance = finance_service.calculate_teacher_balance(withdrawal.teacher_id)
        _invalidate_dashboard_cache()

        log_action(
            request,
            action="create",
            entity="teacher_withdrawal",
            entity_id="",
            description=f"إضافة سحب بمبلغ {amount} للمدرس {withdrawal.teacher_id}"
        )
        
        return {
            "success": True, 
            "message": "تم تسجيل السحب بنجاح",
            "new_balance": new_balance
        }
        
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.get("/withdrawals/teacher/{teacher_id}")
async def api_get_withdrawals(request: Request, teacher_id: int, limit: int = 10):
    """الحصول على سحوبات مدرس"""
    check_permission(request, 'view_withdrawals_list')
    withdrawals = finance_service.get_teacher_recent_withdrawals(teacher_id, limit)
    total = finance_service.get_teacher_withdrawn_total(teacher_id)
    
    return {
        "success": True,
        "data": withdrawals,
        "total_withdrawn": total
    }


@router.delete("/withdrawals/{withdrawal_id}")
async def api_delete_withdrawal(request: Request, withdrawal_id: int):
    """حذف سحب"""
    check_permission(request, 'delete_withdrawals')
    
    try:
        guard = deletion_guard.can_delete_withdrawal(withdrawal_id)
        if not guard.allowed:
            return guard.to_dict()
        
        db = Database()
        db.execute_query("DELETE FROM teacher_withdrawals WHERE id = %s", (withdrawal_id,))
        _invalidate_dashboard_cache()
        return {"success": True, "message": "تم حذف السحب"}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.put("/withdrawals/{withdrawal_id}")
async def api_edit_withdrawal(request: Request, withdrawal_id: int, data: dict = Body(...)):
    """تعديل سحب"""
    check_permission(request, 'add_withdrawals')
    db = Database()
    
    try:
        amount = int(data.get('amount', 0))
        withdrawal_date = data.get('withdrawal_date', '')
        notes = data.get('notes', '')
        
        if amount <= 0:
            return {"success": False, "message": "المبلغ يجب أن يكون أكبر من صفر"}
        
        old = db.execute_query("SELECT teacher_id, amount FROM teacher_withdrawals WHERE id = %s", (withdrawal_id,))
        if not old:
            return {"success": False, "message": "السحب غير موجود"}
        
        teacher_id = old[0]['teacher_id']

        if not withdrawal_date:
            return {"success": False, "message": "يجب تحديد تاريخ السحب"}

        # ===== التحقق: لا يمكن سحب مبلغ أكبر من مستحق المدرس المتاح =====
        can_withdraw, message, balance = finance_service.can_teacher_withdraw_on_date(
            teacher_id,
            amount,
            withdrawal_date,
            exclude_withdrawal_id=withdrawal_id
        )

        if not can_withdraw:
            return {"success": False, "message": f"لا يمكن تعديل السحب. الرصيد المتاح للمدرس هو {format_currency(balance)} فقط. {message}"}
        
        db.execute_query(
            "UPDATE teacher_withdrawals SET amount = %s, withdrawal_date = %s, notes = %s WHERE id = %s",
            (amount, withdrawal_date, notes, withdrawal_id)
        )
        _invalidate_dashboard_cache()
        return {"success": True, "message": "تم تعديل السحب بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


# ===== إحصائيات =====

@router.get("/statistics")
async def api_get_statistics(request: Request):
    """الحصول على إحصائيات النظام"""
    check_permission(request, 'view_dashboard')
    stats = finance_service.get_system_statistics()
    return {"success": True, "data": stats}


@router.get("/financial-warnings")
async def api_get_financial_warnings(request: Request):
    """الحصول على تنبيهات مالية للبيانات القديمة"""
    check_permission(request, 'view_reports')
    warnings = finance_service.get_financial_warnings()
    return {"success": True, "data": warnings, "count": len(warnings)}


# ===== فحص سلامة قاعدة البيانات =====

@router.get("/database-integrity-check")
async def api_database_integrity_check(request: Request):
    """
    فحص شامل لسلامة البيانات في قاعدة البيانات
    يكتشف أي سجلات تتنافى مع منطق النظام وشروطه
    """
    check_permission(request, 'system_settings')
    db = Database()
    issues = []
    
    try:
        # ===== 1. طلاب لديهم أقساط بدون رابط student_teacher =====
        orphan_installments = db.execute_query('''
            SELECT i.student_id, i.teacher_id, s.name as student_name, t.name as teacher_name,
                   COUNT(i.id) as installment_count, SUM(i.amount) as total_amount
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            LEFT JOIN student_teacher st ON st.student_id = i.student_id AND st.teacher_id = i.teacher_id
            WHERE st.student_id IS NULL
            GROUP BY i.student_id, i.teacher_id, s.name, t.name
        ''')
        if orphan_installments:
            for row in orphan_installments:
                issues.append({
                    'type': 'orphan_installments',
                    'severity': 'critical',
                    'message': f"أقساط بدون رابط طالب-مدرس: الطالب '{row['student_name']}' والمدرس '{row['teacher_name']}' لديهما {row['installment_count']} قسط (مجموع {format_currency(row['total_amount'])}) بدون رابط في جدول student_teacher",
                    'data': dict(row)
                })
        
        # ===== 2. طلاب دفعوا أكثر من القسط الكلي (overpayment) =====
        all_links = db.execute_query('''
            SELECT st.student_id, st.teacher_id, s.name as student_name, t.name as teacher_name,
                   st.discount_type, st.discount_value, st.study_type
            FROM student_teacher st
            JOIN students s ON st.student_id = s.id
            JOIN teachers t ON st.teacher_id = t.id
            WHERE st.status = 'مستمر'
        ''')
        if all_links:
            for link in all_links:
                try:
                    balance = finance_service.calculate_student_teacher_balance(link['student_id'], link['teacher_id'])
                    if balance.get('has_overpayment', False):
                        issues.append({
                            'type': 'overpayment',
                            'severity': 'critical',
                            'message': f"مدفوع يتجاوز القسط: الطالب '{link['student_name']}' عند المدرس '{link['teacher_name']}' - المدفوع {format_currency(balance['paid_total'])} يتجاوز القسط {format_currency(balance['total_fee'])} بمبلغ {format_currency(balance['overpayment_amount'])}",
                            'data': {
                                'student_id': link['student_id'],
                                'teacher_id': link['teacher_id'],
                                'student_name': link['student_name'],
                                'teacher_name': link['teacher_name'],
                                'paid_total': balance['paid_total'],
                                'total_fee': balance['total_fee'],
                                'overpayment': balance['overpayment_amount']
                            }
                        })
                except Exception:
                    pass
        
        # ===== 3. طلاب مجانيون لديهم أقساط مسجلة =====
        free_with_installments = db.execute_query('''
            SELECT i.student_id, i.teacher_id, s.name as student_name, t.name as teacher_name,
                   COUNT(i.id) as installment_count, SUM(i.amount) as total_amount
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            JOIN student_teacher st ON st.student_id = i.student_id AND st.teacher_id = i.teacher_id
            WHERE st.discount_type = 'free'
            GROUP BY i.student_id, i.teacher_id, s.name, t.name
        ''')
        if free_with_installments:
            for row in free_with_installments:
                issues.append({
                    'type': 'free_with_installments',
                    'severity': 'high',
                    'message': f"طالب مجاني لديه أقساط: الطالب '{row['student_name']}' عند المدرس '{row['teacher_name']}' مسجل كمجاني لكن لديه {row['installment_count']} قسط (مجموع {format_currency(row['total_amount'])})",
                    'data': dict(row)
                })
        
        # ===== 4. قسط ثاني بدون قسط أول =====
        second_without_first = db.execute_query('''
            SELECT i.student_id, i.teacher_id, s.name as student_name, t.name as teacher_name
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            WHERE i.installment_type = 'القسط الثاني'
            AND NOT EXISTS (
                SELECT 1 FROM installments i2 
                WHERE i2.student_id = i.student_id AND i2.teacher_id = i.teacher_id 
                AND i2.installment_type = 'القسط الأول'
            )
        ''')
        if second_without_first:
            for row in second_without_first:
                issues.append({
                    'type': 'second_without_first',
                    'severity': 'critical',
                    'message': f"قسط ثاني بدون قسط أول: الطالب '{row['student_name']}' عند المدرس '{row['teacher_name']}' لديه قسط ثاني بدون قسط أول",
                    'data': dict(row)
                })
        
        # ===== 5. دفع كامل مع أقساط أخرى (بعد التحديث الجديد يُسمح بدفع كامل + قسط أول فقط) =====
        invalid_combinations = db.execute_query('''
            SELECT i.student_id, i.teacher_id, s.name as student_name, t.name as teacher_name,
                   STRING_AGG(DISTINCT i.installment_type, ', ') as installment_types
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            WHERE i.installment_type = 'دفع كامل'
            GROUP BY i.student_id, i.teacher_id, s.name, t.name
            HAVING COUNT(DISTINCT i.installment_type) > 1
        ''')
        if invalid_combinations:
            for row in invalid_combinations:
                types = row['installment_types'] or ''
                # مسموح فقط: دفع كامل + القسط الأول (تحويل من دفعات إلى كامل)
                if 'القسط الثاني' in types:
                    issues.append({
                        'type': 'invalid_installment_combo',
                        'severity': 'critical',
                        'message': f"تركيب أقساط غير صالح: الطالب '{row['student_name']}' عند المدرس '{row['teacher_name']}' لديه الأنواع: {types} - لا يمكن وجود قسط ثاني مع دفع كامل",
                        'data': dict(row)
                    })
        
        # ===== 6. طلاب بحالة غير متسقة =====
        inconsistent_status = db.execute_query('''
            SELECT s.id, s.name, s.status as student_status,
                   CASE 
                       WHEN NOT EXISTS (SELECT 1 FROM student_teacher st WHERE st.student_id = s.id) THEN 'no_links'
                       WHEN (SELECT COUNT(*) FROM student_teacher st WHERE st.student_id = s.id) = 
                            (SELECT COUNT(*) FROM student_teacher st WHERE st.student_id = s.id AND st.status = 'منسحب') THEN 'all_withdrawn'
                       ELSE 'has_active'
                   END as computed_status
            FROM students s
            WHERE 
                (s.status = 'مستمر' AND NOT EXISTS (SELECT 1 FROM student_teacher st WHERE st.student_id = s.id AND st.status = 'مستمر'))
                OR
                (s.status = 'منسحب' AND EXISTS (SELECT 1 FROM student_teacher st WHERE st.student_id = s.id AND st.status = 'مستمر'))
                OR
                (s.status = 'غير مربوط' AND EXISTS (SELECT 1 FROM student_teacher st WHERE st.student_id = s.id))
        ''')
        if inconsistent_status:
            for row in inconsistent_status:
                issues.append({
                    'type': 'inconsistent_status',
                    'severity': 'medium',
                    'message': f"حالة طالب غير متسقة: الطالب '{row['name']}' حالته '{row['student_status']}' لكن الوضع الفعلي '{row['computed_status']}'",
                    'data': dict(row)
                })
        
        # ===== 7. سحوبات تتجاوز المستحق =====
        teachers_list = db.execute_query("SELECT id, name FROM teachers")
        if teachers_list:
            for teacher in teachers_list:
                try:
                    balance = finance_service.calculate_teacher_balance(teacher['id'])
                    if balance.get('has_over_withdrawal', False):
                        issues.append({
                            'type': 'over_withdrawal',
                            'severity': 'critical',
                            'message': f"سحوبات تتجاوز المستحق: المدرس '{teacher['name']}' - المسحوب {format_currency(balance['withdrawn_total'])} يتجاوز المستحق {format_currency(balance['teacher_due'])} بمبلغ {format_currency(balance['over_withdrawal_amount'])}",
                            'data': {
                                'teacher_id': teacher['id'],
                                'teacher_name': teacher['name'],
                                'teacher_due': balance['teacher_due'],
                                'withdrawn_total': balance['withdrawn_total'],
                                'over_withdrawal': balance['over_withdrawal_amount']
                            }
                        })
                except Exception:
                    pass
        
        # ===== 8. روابط مكررة لنفس المادة =====
        duplicate_subjects = db.execute_query('''
            SELECT st.student_id, s.name as student_name, t.subject,
                   COUNT(*) as link_count,
                   STRING_AGG(t.name, ', ') as teacher_names
            FROM student_teacher st
            JOIN students s ON st.student_id = s.id
            JOIN teachers t ON st.teacher_id = t.id
            WHERE st.status = 'مستمر'
            GROUP BY st.student_id, s.name, t.subject
            HAVING COUNT(*) > 1
        ''')
        if duplicate_subjects:
            for row in duplicate_subjects:
                issues.append({
                    'type': 'duplicate_subject_link',
                    'severity': 'high',
                    'message': f"ربط مكرر بنفس المادة: الطالب '{row['student_name']}' مربوط بـ {row['link_count']} مدرسين للمادة '{row['subject']}' ({row['teacher_names']})",
                    'data': dict(row)
                })
        
        # ===== ملخص =====
        critical_count = sum(1 for i in issues if i['severity'] == 'critical')
        high_count = sum(1 for i in issues if i['severity'] == 'high')
        medium_count = sum(1 for i in issues if i['severity'] == 'medium')
        
        return {
            "success": True,
            "total_issues": len(issues),
            "critical": critical_count,
            "high": high_count,
            "medium": medium_count,
            "is_clean": len(issues) == 0,
            "issues": issues
        }
        
    except Exception as e:
        return {"success": False, "message": f"خطأ في فحص السلامة: {str(e)}"}


# ===== تصدير شامل =====

@router.get("/export-all")
async def api_export_all(request: Request):
    """تصدير شامل لجميع بيانات النظام"""
    check_permission(request, 'system_settings')
    db = Database()
    export_data = {}
    
    try:
        # الطلاب
        students = db.execute_query('''
            SELECT s.id, s.name, s.barcode, s.notes, s.created_at,
                (SELECT CASE WHEN COUNT(*) = 0 THEN 'غير مربوط' WHEN SUM(CASE WHEN st.status = 'منسحب' THEN 1 ELSE 0 END) = COUNT(*) THEN 'منسحب' ELSE 'مستمر' END 
                 FROM student_teacher st WHERE st.student_id = s.id) as status
            FROM students s ORDER BY s.name
        ''')
        export_data['students'] = [dict(r) for r in students] if students else []
        
        # المدرسين
        teachers = db.execute_query("SELECT * FROM teachers ORDER BY name")
        export_data['teachers'] = [dict(r) for r in teachers] if teachers else []
        
        # المواد
        subjects = db.execute_query("SELECT * FROM subjects ORDER BY name")
        export_data['subjects'] = [dict(r) for r in subjects] if subjects else []
        
        # الأقساط
        installments = db.execute_query('''
            SELECT i.id, i.student_id, s.name as student_name, i.teacher_id, t.name as teacher_name,
                   t.subject, i.amount, i.payment_date, i.installment_type, i.notes
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            ORDER BY i.id DESC
        ''')
        export_data['installments'] = [dict(r) for r in installments] if installments else []
        
        # السحوبات
        withdrawals = db.execute_query('''
            SELECT w.id, w.teacher_id, t.name as teacher_name, w.amount, w.withdrawal_date, w.notes
            FROM teacher_withdrawals w
            JOIN teachers t ON w.teacher_id = t.id
            ORDER BY w.id DESC
        ''')
        export_data['withdrawals'] = [dict(r) for r in withdrawals] if withdrawals else []
        
        # روابط الطلاب بالمدرسين
        links = db.execute_query('''
            SELECT st.student_id, s.name as student_name, st.teacher_id, t.name as teacher_name,
                   t.subject, st.study_type, st.status
            FROM student_teacher st
            JOIN students s ON st.student_id = s.id
            JOIN teachers t ON st.teacher_id = t.id
            ORDER BY s.name
        ''')
        export_data['student_teacher_links'] = [dict(r) for r in links] if links else []
        
        # الإحصائيات
        export_data['statistics'] = finance_service.get_system_statistics()
        
    except Exception as e:
        return {"success": False, "message": f"خطأ في التصدير: {str(e)}"}
    
    return {"success": True, "data": export_data}


# ===== بحث شامل =====

@router.get("/search")
async def api_global_search(request: Request, q: str = ""):
    """بحث شامل في النظام"""
    # البحث متاح لكل مستخدم مسجل الدخول
    db = Database()
    results = {"students": [], "teachers": [], "subjects": []}
    
    if not q or len(q) < 1:
        return {"success": True, "data": results}
    
    try:
        # بحث الطلاب - عرض نوع الدراسة الفعلي من جدول student_teacher
        students = db.execute_query(
            '''SELECT s.id, s.name, s.barcode, 
               COALESCE(
                   STRING_AGG(DISTINCT st.study_type, ' / '),
                   s.study_type
               ) as study_type
               FROM students s
               LEFT JOIN student_teacher st ON st.student_id = s.id
               WHERE s.name LIKE %s OR s.barcode LIKE %s
               GROUP BY s.id, s.name, s.barcode, s.study_type
               ORDER BY s.name LIMIT 10''',
            (f'%{q}%', f'%{q}%')
        )
        results["students"] = [dict(r) for r in students] if students else []
        
        # بحث المدرسين
        teachers = db.execute_query(
            '''SELECT id, name, subject, total_fee FROM teachers 
               WHERE name LIKE %s OR subject LIKE %s ORDER BY name LIMIT 10''',
            (f'%{q}%', f'%{q}%')
        )
        results["teachers"] = [dict(r) for r in teachers] if teachers else []
        
        # بحث المواد
        subjects = db.execute_query(
            '''SELECT id, name FROM subjects WHERE name LIKE %s ORDER BY name LIMIT 10''',
            (f'%{q}%',)
        )
        results["subjects"] = [dict(r) for r in subjects] if subjects else []
        
    except Exception as e:
        print(f"Search error: {e}")
    
    return {"success": True, "data": results}


# ===== التنبيهات الذكية =====

@router.get("/smart-alerts")
async def api_smart_alerts(request: Request):
    """الحصول على التنبيهات الذكية للوحة التحكم"""
    check_permission(request, 'view_dashboard')
    db = Database()
    alerts = []
    
    try:
        # 1. الطلاب الذين لم يسددوا بالكامل (لديهم رصيد متبقي > 0) - مع تطبيق الخصم
        active_links = db.execute_query('''
            SELECT DISTINCT st.student_id, s.name
            FROM student_teacher st
            INNER JOIN students s ON st.student_id = s.id
            WHERE st.status = 'مستمر'
        ''')
        
        unpaid_students = []
        if active_links:
            for link in active_links:
                summary = finance_service.get_student_all_teachers_summary(link['student_id'])
                total_remaining = sum(ts['remaining_balance'] for ts in summary) if summary else 0
                if total_remaining > 0:
                    unpaid_students.append({'id': link['student_id'], 'name': link['name'], 'remaining': total_remaining})
        
        if unpaid_students:
            alerts.append({
                'type': 'warning',
                'icon': 'fa-exclamation-triangle',
                'title': 'طلاب لم يسددوا بالكامل',
                'message': f'يوجد {len(unpaid_students)} طالب لديهم أرصدة متبقية لم تسدد بالكامل',
                'link': '/students'
            })
        
        # 2. المدرسين الذين لديهم أرصدة متاحة للسحب
        teachers_with_balance = []
        all_teachers = db.execute_query("SELECT id FROM teachers")
        if all_teachers:
            for t in all_teachers:
                try:
                    balance = finance_service.calculate_teacher_balance(t['id'])
                    if balance.get('remaining_balance', 0) > 0:
                        teachers_with_balance.append(t['id'])
                except:
                    pass
        
        if teachers_with_balance:
            alerts.append({
                'type': 'info',
                'icon': 'fa-wallet',
                'title': 'أرصدة متاحة للسحب',
                'message': f'يوجد {len(teachers_with_balance)} مدرس لديهم أرصدة قابلة للسحب',
                'link': '/accounting'
            })
        
        # 3. طلاب غير مربوطين بمدرسين
        unlinked = db.execute_query('''
            SELECT COUNT(*) as cnt FROM students s
            WHERE NOT EXISTS (SELECT 1 FROM student_teacher st WHERE st.student_id = s.id)
        ''')
        unlinked_count = unlinked[0]['cnt'] if unlinked else 0
        if unlinked_count > 0:
            alerts.append({
                'type': 'danger',
                'icon': 'fa-unlink',
                'title': 'طلاب غير مربوطين',
                'message': f'يوجد {unlinked_count} طالب غير مربوط بأي مدرس',
                'link': '/students'
            })
        
        # 4. طلاب دفعوا القسط الأول فقط (لم يسددوا القسط الثاني)
        first_only = db.execute_query('''
            SELECT COUNT(DISTINCT i.student_id) as cnt
            FROM installments i
            WHERE i.installment_type = 'القسط الأول'
            AND NOT EXISTS (
                SELECT 1 FROM installments i2 
                WHERE i2.student_id = i.student_id 
                AND i2.teacher_id = i.teacher_id
                AND i2.installment_type IN ('القسط الثاني', 'دفع كامل')
            )
        ''')
        first_only_count = first_only[0]['cnt'] if first_only else 0
        if first_only_count > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'fa-clock',
                'title': 'لم يسددوا القسط الثاني',
                'message': f'يوجد {first_only_count} طالب دفعوا القسط الأول فقط ولم يسددوا القسط الثاني',
                'link': '/payments'
            })
        
        # 5. أرصدة كبيرة غير مسحوبة (> 500,000 د.ع)
        large_balance_teachers = []
        if all_teachers:
            for t in all_teachers:
                try:
                    balance = finance_service.calculate_teacher_balance(t['id'])
                    if balance.get('remaining_balance', 0) > 500000:
                        large_balance_teachers.append(t['id'])
                except:
                    pass
        
        if large_balance_teachers:
            alerts.append({
                'type': 'info',
                'icon': 'fa-coins',
                'title': 'أرصدة كبيرة غير مسحوبة',
                'message': f'يوجد {len(large_balance_teachers)} مدرس لديهم أرصدة غير مسحوبة تتجاوز 500,000 د.ع',
                'link': '/accounting'
            })
    
    except Exception as e:
        print(f"Smart alerts error: {e}")

    return {"success": True, "data": alerts}


# ===== عمليات القاعات =====

@router.get("/rooms")
async def api_get_rooms():
    """الحصول على قائمة جميع القاعات"""
    db = Database()
    try:
        rooms = db.execute_query("SELECT * FROM rooms ORDER BY name")
        return {"success": True, "data": [dict(r) for r in rooms] if rooms else []}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.post("/rooms")
async def api_add_room(request: Request, data: dict = Body(...)):
    """إضافة قاعة جديدة"""
    check_permission(request, 'add_subjects')
    db = Database()
    try:
        name = data.get('name', '').strip()
        capacity = int(data.get('capacity', 0))
        notes = data.get('notes', '')
        
        if not name:
            return {"success": False, "message": "اسم القاعة مطلوب"}
        
        existing = db.execute_query("SELECT id FROM rooms WHERE name = %s", (name,))
        if existing:
            return {"success": False, "message": "اسم القاعة موجود مسبقاً"}
        
        result = db.execute_query(
            "INSERT INTO rooms (name, capacity, notes, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
            (name, capacity, notes, get_current_date(get_client_timestamp(request)))
        )
        new_id = result[0]['id'] if result else None
        return {"success": True, "message": "تم إضافة القاعة بنجاح", "id": new_id}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.put("/rooms/{room_id}")
async def api_update_room(request: Request, room_id: int, data: dict = Body(...)):
    """تحديث قاعة"""
    check_permission(request, 'edit_subjects')
    db = Database()
    try:
        name = data.get('name', '').strip()
        capacity = int(data.get('capacity', 0))
        notes = data.get('notes', '')
        
        if not name:
            return {"success": False, "message": "اسم القاعة مطلوب"}
        
        existing = db.execute_query("SELECT id FROM rooms WHERE id = %s", (room_id,))
        if not existing:
            return {"success": False, "message": "القاعة غير موجودة"}
        
        dup = db.execute_query("SELECT id FROM rooms WHERE name = %s AND id != %s", (name, room_id))
        if dup:
            return {"success": False, "message": "اسم القاعة موجود مسبقاً"}
        
        db.execute_query(
            "UPDATE rooms SET name = %s, capacity = %s, notes = %s WHERE id = %s",
            (name, capacity, notes, room_id)
        )
        return {"success": True, "message": "تم تحديث القاعة بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.delete("/rooms/{room_id}")
async def api_delete_room(request: Request, room_id: int):
    """حذف قاعة"""
    check_permission(request, 'delete_subjects')
    try:
        guard = deletion_guard.can_delete_room(room_id)
        if not guard.allowed:
            return guard.to_dict()
        
        db = Database()
        db.execute_query("DELETE FROM rooms WHERE id = %s", (room_id,))
        return {"success": True, "message": "تم حذف القاعة"}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


# ===== عمليات الجدول الأسبوعي =====

@router.get("/weekly-schedule")
async def api_get_weekly_schedule(room_id: int = None):
    """الحصول على الجدول الأسبوعي كاملاً أو لقاعة محددة"""
    db = Database()
    try:
        if room_id:
            query = '''
                SELECT ws.*, r.name as room_name, t.name as teacher_name, t.subject as teacher_subject
                FROM weekly_schedule ws
                JOIN rooms r ON ws.room_id = r.id
                JOIN teachers t ON ws.teacher_id = t.id
                WHERE ws.room_id = %s
                ORDER BY ws.day_of_week, ws.start_time
            '''
            results = db.execute_query(query, (room_id,))
        else:
            query = '''
                SELECT ws.*, r.name as room_name, t.name as teacher_name, t.subject as teacher_subject
                FROM weekly_schedule ws
                JOIN rooms r ON ws.room_id = r.id
                JOIN teachers t ON ws.teacher_id = t.id
                ORDER BY r.name, ws.day_of_week, ws.start_time
            '''
            results = db.execute_query(query)
        
        return {"success": True, "data": [dict(r) for r in results] if results else []}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.post("/weekly-schedule")
async def api_add_weekly_lecture(request: Request, data: dict = Body(...)):
    """إضافة محاضرة أو امتحان للجدول الأسبوعي مع فحص التعارضات"""
    check_permission(request, 'add_subjects')
    db = Database()
    try:
        room_id = int(data.get('room_id', 0))
        teacher_id = int(data.get('teacher_id', 0))
        subject = data.get('subject', '').strip()
        day_of_week = data.get('day_of_week', '').strip()
        start_time = data.get('start_time', '').strip()
        end_time = data.get('end_time', '').strip()
        event_type = data.get('event_type', 'محاضرة').strip()
        notes = data.get('notes', '')
        duration = data.get('duration', None)
        
        if not all([room_id, teacher_id, day_of_week, start_time, end_time]):
            return {"success": False, "message": "جميع الحقول مطلوبة: القاعة، المدرس، اليوم، وقت البداية، وقت النهاية"}
        
        valid_days = ['الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
        if day_of_week not in valid_days:
            return {"success": False, "message": f"اليوم يجب أن يكون من: {', '.join(valid_days)}"}
        
        # حساب وقت النهاية من المدة إذا تم تحديدها
        if duration and not end_time:
            try:
                duration_minutes = int(duration)
                sh, sm = map(int, start_time.split(':'))
                total_minutes = sh * 60 + sm + duration_minutes
                eh = total_minutes // 60
                em = total_minutes % 60
                end_time = f"{eh:02d}:{em:02d}"
            except (ValueError, TypeError):
                return {"success": False, "message": "قيمة المدة غير صالحة"}
        
        if not end_time:
            return {"success": False, "message": "يرجى تحديد المدة أو وقت النهاية"}
        
        if start_time >= end_time:
            return {"success": False, "message": "وقت البداية يجب أن يكون قبل وقت النهاية"}
        
        # التحقق من نوع الحدث
        if event_type not in ('محاضرة', 'امتحان'):
            event_type = 'محاضرة'
        
        # فحص تعارض القاعة: لا يمكن إضافة حدثين في نفس القاعة بنفس اليوم والوقت المتداخل
        room_conflict = db.execute_query('''
            SELECT ws.*, t.name as teacher_name, t.subject as teacher_subject
            FROM weekly_schedule ws
            JOIN teachers t ON ws.teacher_id = t.id
            WHERE ws.room_id = %s AND ws.day_of_week = %s
            AND NOT (ws.end_time <= %s OR ws.start_time >= %s)
        ''', (room_id, day_of_week, start_time, end_time))
        
        if room_conflict:
            conflict = room_conflict[0]
            conflict_type = conflict.get('event_type', 'محاضرة')
            conflict_label = 'امتحان' if conflict_type == 'امتحان' else 'محاضرة'
            return {
                "success": False,
                "message": f"تعارض في القاعة! يوجد {conflict_label} للمدرس {conflict['teacher_name']} ({conflict['teacher_subject']}) من {conflict['start_time']} إلى {conflict['end_time']}"
            }
        
        # فحص تعارض المدرس: لا يمكن للمدرس التدريس في مكانين بنفس الوقت
        teacher_conflict = db.execute_query('''
            SELECT ws.*, r.name as room_name
            FROM weekly_schedule ws
            JOIN rooms r ON ws.room_id = r.id
            WHERE ws.teacher_id = %s AND ws.day_of_week = %s
            AND NOT (ws.end_time <= %s OR ws.start_time >= %s)
        ''', (teacher_id, day_of_week, start_time, end_time))
        
        if teacher_conflict:
            conflict = teacher_conflict[0]
            return {
                "success": False,
                "message": f"تعارض في جدول المدرس! المدرس لديه محاضرة في قاعة {conflict['room_name']} من {conflict['start_time']} إلى {conflict['end_time']}"
            }
        
        if not subject:
            teacher_info = db.execute_query("SELECT subject FROM teachers WHERE id = %s", (teacher_id,))
            subject = teacher_info[0]['subject'] if teacher_info else ''
        
        result = db.execute_query(
            '''INSERT INTO weekly_schedule (room_id, teacher_id, subject, day_of_week, start_time, end_time, event_type, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
            (room_id, teacher_id, subject, day_of_week, start_time, end_time, event_type, notes)
        )
        new_id = result[0]['id'] if result else None
        
        event_label = 'الامتحان' if event_type == 'امتحان' else 'المحاضرة'
        return {"success": True, "message": f"تم إضافة {event_label} بنجاح", "id": new_id}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.put("/weekly-schedule/{lecture_id}")
async def api_update_weekly_lecture(request: Request, lecture_id: int, data: dict = Body(...)):
    """تحديث محاضرة أو امتحان في الجدول الأسبوعي مع فحص التعارضات"""
    check_permission(request, 'edit_subjects')
    db = Database()
    try:
        room_id = int(data.get('room_id', 0))
        teacher_id = int(data.get('teacher_id', 0))
        subject = data.get('subject', '').strip()
        day_of_week = data.get('day_of_week', '').strip()
        start_time = data.get('start_time', '').strip()
        end_time = data.get('end_time', '').strip()
        event_type = data.get('event_type', 'محاضرة').strip()
        notes = data.get('notes', '')
        duration = data.get('duration', None)
        
        if not all([room_id, teacher_id, day_of_week, start_time, end_time]):
            return {"success": False, "message": "جميع الحقول مطلوبة: القاعة، المدرس، اليوم، وقت البداية، وقت النهاية"}
        
        # حساب وقت النهاية من المدة إذا تم تحديدها
        if duration and not end_time:
            try:
                duration_minutes = int(duration)
                sh, sm = map(int, start_time.split(':'))
                total_minutes = sh * 60 + sm + duration_minutes
                eh = total_minutes // 60
                em = total_minutes % 60
                end_time = f"{eh:02d}:{em:02d}"
            except (ValueError, TypeError):
                return {"success": False, "message": "قيمة المدة غير صالحة"}
        
        if not end_time:
            return {"success": False, "message": "يرجى تحديد المدة أو وقت النهاية"}
        
        if start_time >= end_time:
            return {"success": False, "message": "وقت البداية يجب أن يكون قبل وقت النهاية"}
        
        # التحقق من نوع الحدث
        if event_type not in ('محاضرة', 'امتحان'):
            event_type = 'محاضرة'
        
        # فحص تعارض القاعة (باستثناء المحاضرة الحالية)
        room_conflict = db.execute_query('''
            SELECT ws.*, t.name as teacher_name, t.subject as teacher_subject
            FROM weekly_schedule ws
            JOIN teachers t ON ws.teacher_id = t.id
            WHERE ws.room_id = %s AND ws.day_of_week = %s AND ws.id != %s
            AND NOT (ws.end_time <= %s OR ws.start_time >= %s)
        ''', (room_id, day_of_week, lecture_id, start_time, end_time))
        
        if room_conflict:
            conflict = room_conflict[0]
            conflict_type = conflict.get('event_type', 'محاضرة')
            conflict_label = 'امتحان' if conflict_type == 'امتحان' else 'محاضرة'
            return {
                "success": False,
                "message": f"تعارض في القاعة! يوجد {conflict_label} للمدرس {conflict['teacher_name']} ({conflict['teacher_subject']}) من {conflict['start_time']} إلى {conflict['end_time']}"
            }
        
        # فحص تعارض المدرس (باستثناء المحاضرة الحالية)
        teacher_conflict = db.execute_query('''
            SELECT ws.*, r.name as room_name
            FROM weekly_schedule ws
            JOIN rooms r ON ws.room_id = r.id
            WHERE ws.teacher_id = %s AND ws.day_of_week = %s AND ws.id != %s
            AND NOT (ws.end_time <= %s OR ws.start_time >= %s)
        ''', (teacher_id, day_of_week, lecture_id, start_time, end_time))
        
        if teacher_conflict:
            conflict = teacher_conflict[0]
            return {
                "success": False,
                "message": f"تعارض في جدول المدرس! المدرس لديه محاضرة في قاعة {conflict['room_name']} من {conflict['start_time']} إلى {conflict['end_time']}"
            }
        
        if not subject:
            teacher_info = db.execute_query("SELECT subject FROM teachers WHERE id = %s", (teacher_id,))
            subject = teacher_info[0]['subject'] if teacher_info else ''
        
        db.execute_query(
            '''UPDATE weekly_schedule SET room_id=%s, teacher_id=%s, subject=%s, day_of_week=%s, 
               start_time=%s, end_time=%s, event_type=%s, notes=%s WHERE id=%s''',
            (room_id, teacher_id, subject, day_of_week, start_time, end_time, event_type, notes, lecture_id)
        )
        
        event_label = 'الامتحان' if event_type == 'امتحان' else 'المحاضرة'
        return {"success": True, "message": f"تم تحديث {event_label} بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


@router.delete("/weekly-schedule/{lecture_id}")
async def api_delete_weekly_lecture(request: Request, lecture_id: int):
    """حذف محاضرة من الجدول الأسبوعي"""
    check_permission(request, 'delete_subjects')
    try:
        guard = deletion_guard.can_delete_weekly_schedule(lecture_id)
        if not guard.allowed:
            return guard.to_dict()
        
        db = Database()
        db.execute_query("DELETE FROM weekly_schedule WHERE id = %s", (lecture_id,))
        return {"success": True, "message": "تم حذف المحاضرة"}
    except Exception as e:
        return {"success": False, "message": f"خطأ في المعالجة: {str(e)}"}


# ===== بحث بالباركود / QR =====

@router.get("/lookup")
async def api_lookup_barcode(request: Request, code: str = ""):
    """
    بحث سريع بالباركود أو الرمز - يبحث في الطلاب والمدرسين
    يُستخدم للماسح الضوئي (QR Scanner) أو إدخال الرمز يدوياً
    
    Returns:
        - found: هل وُجد نتيجة؟
        - type: 'student' أو 'teacher' أو 'none'
        - id: رقم السجل
        - name: الاسم
        - url: رابط الصفحة
    """
    if not code or len(code.strip()) < 1:
        return {"found": False, "type": "none", "message": "لم يتم إدخال رمز"}
    
    code = code.strip()
    db = Database()
    
    try:
        # 1. بحث في الطلاب بالباركود (مطابقة تامة أو جزئية)
        student = db.execute_query(
            "SELECT id, name, barcode FROM students WHERE barcode = %s LIMIT 1",
            (code,)
        )
        if not student:
            # محاولة بحث جزئي
            student = db.execute_query(
                "SELECT id, name, barcode FROM students WHERE barcode LIKE %s LIMIT 1",
                (f'%{code}%',)
            )
        if not student:
            # بحث بالرقم التسلسلي (id)
            try:
                sid = int(code.replace('STU-', '').split('-')[-1])
                student = db.execute_query(
                    "SELECT id, name, barcode FROM students WHERE id = %s LIMIT 1",
                    (sid,)
                )
            except (ValueError, IndexError):
                pass
        
        if student:
            s = student[0]
            return {
                "found": True,
                "type": "student",
                "id": s['id'],
                "name": s['name'],
                "barcode": s['barcode'],
                "url": f"/students/{s['id']}"
            }
        
        # 2. بحث في المدرسين بالاسم أو الرقم
        try:
            tid = int(code)
            teacher = db.execute_query(
                "SELECT id, name, subject FROM teachers WHERE id = %s LIMIT 1",
                (tid,)
            )
        except ValueError:
            teacher = db.execute_query(
                "SELECT id, name, subject FROM teachers WHERE name LIKE %s LIMIT 1",
                (f'%{code}%',)
            )
        
        if teacher:
            t = teacher[0]
            return {
                "found": True,
                "type": "teacher",
                "id": t['id'],
                "name": t['name'],
                "subject": t['subject'],
                "url": f"/teachers/{t['id']}"
            }
        
        return {"found": False, "type": "none", "message": "لم يتم العثور على نتائج"}
        
    except Exception as e:
        return {"found": False, "type": "none", "message": f"خطأ في البحث: {str(e)}"}


# ===== عمليات الثيم =====

class ThemeUpdate(BaseModel):
    """نموذج تحديث ثيم المستخدم"""
    theme: str = Field(..., pattern="^(light|dark)$", description="الثيم: light أو dark")


@router.post("/user/theme")
async def api_update_user_theme(request: Request, data: ThemeUpdate):
    """حفظ تفضيل الثيم للمستخدم الحالي"""
    try:
        # محاولة الحصول على المستخدم الحالي
        from auth import get_current_user
        user = get_current_user(request)

        if user:
            db = Database()
            # التحقق من وجود عمود theme في جدول users
            try:
                db.execute_query(
                    "UPDATE users SET theme = %s WHERE id = %s",
                    (data.theme, user['id'])
                )
            except Exception:
                # إذا لم يكن عمود theme موجوداً بعد، نتجاهل الخطأ
                # localStorage يكفي كخطة بديلة
                pass

        return {"success": True, "theme": data.theme}

    except Exception as e:
        # لا نعرض خطأ للمستخدم - localStorage يكفي
        return {"success": True, "theme": data.theme}


# ===== فحص وتنظيف قاعدة البيانات (مؤقت) =====

@router.post("/admin/inspect-and-clean-db")
async def api_inspect_and_clean_db(request: Request):
    """فحص شامل لقاعدة البيانات وتنظيف أي بيانات متضاربة أو عشوائية أو يتيمة"""
    db = Database()
    issues = {}
    cleaned = {}
    
    # ===== 1. فحص عدد السجلات =====
    tables = ['subjects', 'students', 'teachers', 'student_teacher', 'installments', 
              'teacher_withdrawals', 'weekly_schedule', 'rooms', 'roles', 'permissions', 
              'role_permissions', 'users']
    counts = {}
    for t in tables:
        try:
            r = db.execute_query(f"SELECT COUNT(*) as cnt FROM {t}")
            counts[t] = r[0]['cnt'] if r else 0
        except Exception as e:
            counts[t] = str(e)
    issues['table_counts'] = counts
    
    # ===== 2. روابط يتيمة (طالب أو مدرس محذوف) =====
    try:
        orphan_links = db.execute_query("""
            SELECT st.student_id, st.teacher_id 
            FROM student_teacher st
            LEFT JOIN students s ON st.student_id = s.id
            LEFT JOIN teachers t ON st.teacher_id = t.id
            WHERE s.id IS NULL OR t.id IS NULL
        """) or []
        issues['orphan_links'] = len(orphan_links)
        if orphan_links:
            for ol in orphan_links:
                db.execute_query("DELETE FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
                               (ol['student_id'], ol['teacher_id']))
            cleaned['orphan_links_deleted'] = len(orphan_links)
    except Exception as e:
        issues['orphan_links_error'] = str(e)
    
    # ===== 3. أقساط يتيمة (طالب أو مدرس محذوف) =====
    try:
        orphan_inst = db.execute_query("""
            SELECT i.id FROM installments i
            LEFT JOIN students s ON i.student_id = s.id
            LEFT JOIN teachers t ON i.teacher_id = t.id
            WHERE s.id IS NULL OR t.id IS NULL
        """) or []
        issues['orphan_installments'] = len(orphan_inst)
        if orphan_inst:
            ids = [str(oi['id']) for oi in orphan_inst]
            db.execute_query(f"DELETE FROM installments WHERE id IN ({','.join(ids)})")
            cleaned['orphan_installments_deleted'] = len(orphan_inst)
    except Exception as e:
        issues['orphan_installments_error'] = str(e)
    
    # ===== 4. أقساط بدون رابط طالب-مدرس =====
    try:
        no_link_inst = db.execute_query("""
            SELECT i.id FROM installments i
            LEFT JOIN student_teacher st ON i.student_id = st.student_id AND i.teacher_id = st.teacher_id
            WHERE st.student_id IS NULL
        """) or []
        issues['installments_no_link'] = len(no_link_inst)
        if no_link_inst:
            ids = [str(ni['id']) for ni in no_link_inst]
            db.execute_query(f"DELETE FROM installments WHERE id IN ({','.join(ids)})")
            cleaned['installments_no_link_deleted'] = len(no_link_inst)
    except Exception as e:
        issues['installments_no_link_error'] = str(e)
    
    # ===== 5. أقساط بمبلغ <= 0 =====
    try:
        bad_amount = db.execute_query("SELECT id FROM installments WHERE amount <= 0") or []
        issues['bad_amount_installments'] = len(bad_amount)
        if bad_amount:
            ids = [str(ba['id']) for ba in bad_amount]
            db.execute_query(f"DELETE FROM installments WHERE id IN ({','.join(ids)})")
            cleaned['bad_amount_installments_deleted'] = len(bad_amount)
    except Exception as e:
        issues['bad_amount_installments_error'] = str(e)
    
    # ===== 6. أقساط بنوع غير صالح =====
    try:
        bad_type = db.execute_query("""
            SELECT id FROM installments 
            WHERE installment_type NOT IN ('القسط الأول', 'القسط الثاني', 'دفع كامل', 'دفعات')
        """) or []
        issues['bad_type_installments'] = len(bad_type)
        if bad_type:
            ids = [str(bt['id']) for bt in bad_type]
            db.execute_query(f"DELETE FROM installments WHERE id IN ({','.join(ids)})")
            cleaned['bad_type_installments_deleted'] = len(bad_type)
    except Exception as e:
        issues['bad_type_installments_error'] = str(e)
    
    # ===== 7. دفعات بدون for_installment =====
    try:
        bad_splits = db.execute_query("""
            SELECT id FROM installments 
            WHERE installment_type = 'دفعات' AND (for_installment IS NULL OR for_installment = '')
        """) or []
        issues['splits_no_for'] = len(bad_splits)
        if bad_splits:
            ids = [str(bs['id']) for bs in bad_splits]
            db.execute_query(f"DELETE FROM installments WHERE id IN ({','.join(ids)})")
            cleaned['splits_no_for_deleted'] = len(bad_splits)
    except Exception as e:
        issues['splits_no_for_error'] = str(e)
    
    # ===== 8. تكرار أنواع أقساط رئيسية =====
    try:
        dup_types = db.execute_query("""
            SELECT student_id, teacher_id, installment_type, COUNT(*) as cnt
            FROM installments
            WHERE installment_type IN ('القسط الأول', 'القسط الثاني', 'دفع كامل')
            GROUP BY student_id, teacher_id, installment_type
            HAVING COUNT(*) > 1
        """) or []
        issues['dup_installment_types'] = len(dup_types)
        if dup_types:
            for dt in dup_types:
                db.execute_query("""
                    DELETE FROM installments WHERE id IN (
                        SELECT id FROM installments 
                        WHERE student_id = %s AND teacher_id = %s AND installment_type = %s
                        ORDER BY id DESC OFFSET 1
                    )
                """, (dt['student_id'], dt['teacher_id'], dt['installment_type']))
            cleaned['dup_installment_types_fixed'] = len(dup_types)
    except Exception as e:
        issues['dup_installment_types_error'] = str(e)
    
    # ===== 9. سحوبات يتيمة =====
    try:
        orphan_with = db.execute_query("""
            SELECT tw.id FROM teacher_withdrawals tw
            LEFT JOIN teachers t ON tw.teacher_id = t.id
            WHERE t.id IS NULL
        """) or []
        issues['orphan_withdrawals'] = len(orphan_with)
        if orphan_with:
            ids = [str(ow['id']) for ow in orphan_with]
            db.execute_query(f"DELETE FROM teacher_withdrawals WHERE id IN ({','.join(ids)})")
            cleaned['orphan_withdrawals_deleted'] = len(orphan_with)
    except Exception as e:
        issues['orphan_withdrawals_error'] = str(e)
    
    # ===== 10. سحوبات بمبلغ <= 0 =====
    try:
        bad_with = db.execute_query("SELECT id FROM teacher_withdrawals WHERE amount <= 0") or []
        issues['bad_withdrawals'] = len(bad_with)
        if bad_with:
            ids = [str(bw['id']) for bw in bad_with]
            db.execute_query(f"DELETE FROM teacher_withdrawals WHERE id IN ({','.join(ids)})")
            cleaned['bad_withdrawals_deleted'] = len(bad_with)
    except Exception as e:
        issues['bad_withdrawals_error'] = str(e)
    
    # ===== 11. جداول أسبوعية يتيمة =====
    try:
        orphan_sched = db.execute_query("""
            SELECT ws.id FROM weekly_schedule ws
            LEFT JOIN teachers t ON ws.teacher_id = t.id
            LEFT JOIN rooms r ON ws.room_id = r.id
            WHERE t.id IS NULL OR r.id IS NULL
        """) or []
        issues['orphan_schedule'] = len(orphan_sched)
        if orphan_sched:
            ids_to_del = [str(sch['id']) for sch in orphan_sched]
            db.execute_query(f"DELETE FROM weekly_schedule WHERE id IN ({','.join(ids_to_del)})")
            cleaned['orphan_schedule_deleted'] = len(orphan_sched)
    except Exception as e:
        issues['orphan_schedule_error'] = str(e)
    
    # ===== 12. أساتذة بمادة غير موجودة في جدول المواد =====
    try:
        no_subject = db.execute_query("""
            SELECT t.id, t.name, t.subject FROM teachers t
            LEFT JOIN subjects s ON t.subject = s.name
            WHERE s.name IS NULL
        """) or []
        issues['teachers_no_subject'] = len(no_subject)
        # إضافة المادة تلقائياً إذا لم تكن موجودة
        if no_subject:
            for ns in no_subject:
                try:
                    db.execute_query("INSERT INTO subjects (name, created_at) VALUES (%s, %s)", 
                                   (ns['subject'], get_current_date(get_client_timestamp(request))))
                except Exception:
                    pass  # قد تكون المادة موجودة فعلاً
            cleaned['teachers_missing_subjects_added'] = len(no_subject)
    except Exception as e:
        issues['teachers_no_subject_error'] = str(e)
    
    # ===== 13. مواد بدون أساتذة (يتيمة) =====
    try:
        subjects_no_teachers = db.execute_query("""
            SELECT s.id, s.name FROM subjects s
            LEFT JOIN teachers t ON s.name = t.subject
            WHERE t.id IS NULL
        """) or []
        issues['subjects_no_teachers'] = len(subjects_no_teachers)
        # حذف المواد بدون أساتذة (بيانات يتيمة)
        if subjects_no_teachers:
            for sn in subjects_no_teachers:
                db.execute_query("DELETE FROM subjects WHERE id = %s", (sn['id'],))
            cleaned['orphan_subjects_deleted'] = len(subjects_no_teachers)
    except Exception as e:
        issues['subjects_no_teachers_error'] = str(e)
    
    # ===== 14. طلاب بدون أي رابط =====
    try:
        orphan_students = db.execute_query("""
            SELECT s.id, s.name FROM students s 
            LEFT JOIN student_teacher st ON s.id = st.student_id 
            WHERE st.student_id IS NULL
        """) or []
        issues['students_no_links'] = len(orphan_students)
    except Exception as e:
        issues['students_no_links_error'] = str(e)
    
    # ===== 15. تصحيح حالة الطلاب =====
    try:
        status_mismatch = db.execute_query("""
            SELECT s.id, s.status as declared_status,
                CASE 
                    WHEN (SELECT COUNT(*) FROM student_teacher st WHERE st.student_id = s.id) = 0 THEN 'غير مربوط'
                    WHEN (SELECT SUM(CASE WHEN st.status = 'منسحب' THEN 1 ELSE 0 END) FROM student_teacher st WHERE st.student_id = s.id) = 
                         (SELECT COUNT(*) FROM student_teacher st WHERE st.student_id = s.id) THEN 'منسحب'
                    WHEN (SELECT SUM(CASE WHEN st.status = 'منسحب' THEN 1 ELSE 0 END) FROM student_teacher st WHERE st.student_id = s.id) > 0 THEN 'مدمج'
                    ELSE 'مستمر'
                END as actual_status
            FROM students s
            WHERE s.status != CASE 
                    WHEN (SELECT COUNT(*) FROM student_teacher st WHERE st.student_id = s.id) = 0 THEN 'غير مربوط'
                    WHEN (SELECT SUM(CASE WHEN st.status = 'منسحب' THEN 1 ELSE 0 END) FROM student_teacher st WHERE st.student_id = s.id) = 
                         (SELECT COUNT(*) FROM student_teacher st WHERE st.student_id = s.id) THEN 'منسحب'
                    WHEN (SELECT SUM(CASE WHEN st.status = 'منسحب' THEN 1 ELSE 0 END) FROM student_teacher st WHERE st.student_id = s.id) > 0 THEN 'مدمج'
                    ELSE 'مستمر'
                END
        """) or []
        issues['status_mismatch'] = len(status_mismatch)
        if status_mismatch:
            for sm in status_mismatch:
                actual = sm['actual_status']
                db.execute_query("UPDATE students SET status = %s WHERE id = %s", (actual, sm['id']))
            cleaned['status_fixed'] = len(status_mismatch)
    except Exception as e:
        issues['status_mismatch_error'] = str(e)
    
    # ===== 16. روابط بحالة دراسة غير صالحة =====
    try:
        bad_link_types = db.execute_query("""
            SELECT student_id, teacher_id, study_type, status 
            FROM student_teacher 
            WHERE study_type NOT IN ('حضوري', 'الكتروني', 'مدمج')
               OR status NOT IN ('مستمر', 'منسحب')
        """) or []
        issues['bad_link_types'] = len(bad_link_types)
        if bad_link_types:
            for blt in bad_link_types:
                fix_study = blt['study_type'] if blt['study_type'] in ('حضوري', 'الكتروني', 'مدمج') else 'حضوري'
                fix_status = blt['status'] if blt['status'] in ('مستمر', 'منسحب') else 'مستمر'
                db.execute_query("""
                    UPDATE student_teacher SET study_type = %s, status = %s 
                    WHERE student_id = %s AND teacher_id = %s
                """, (fix_study, fix_status, blt['student_id'], blt['teacher_id']))
            cleaned['bad_link_types_fixed'] = len(bad_link_types)
    except Exception as e:
        issues['bad_link_types_error'] = str(e)
    
    # ===== 17. مستخدمون بدون دور =====
    try:
        users_no_role = db.execute_query("""
            SELECT u.id FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE r.id IS NULL
        """) or []
        issues['users_no_role'] = len(users_no_role)
    except Exception as e:
        issues['users_no_role_error'] = str(e)
    
    # ===== 18. طلاب بدون باركود صحيح =====
    try:
        bad_barcode = db.execute_query("""
            SELECT id, name FROM students 
            WHERE barcode IS NULL OR barcode = '' OR barcode LIKE 'TEMP-%'
        """) or []
        issues['bad_barcode'] = len(bad_barcode)
        if bad_barcode:
            for bb in bad_barcode:
                new_barcode = generate_barcode(bb['id'])
                db.execute_query("UPDATE students SET barcode = %s WHERE id = %s", (new_barcode, bb['id']))
            cleaned['bad_barcode_fixed'] = len(bad_barcode)
    except Exception as e:
        issues['bad_barcode_error'] = str(e)
    
    # ===== 19. إعادة حساب حالة جميع الطلاب =====
    try:
        all_students = db.execute_query("SELECT id FROM students") or []
        synced = 0
        for s in all_students:
            try:
                sync_student_status(s['id'])
                synced += 1
            except Exception:
                pass
        cleaned['students_status_synced'] = synced
    except Exception as e:
        issues['sync_error'] = str(e)
    
    # إلغاء التخزين المؤقت
    try:
        cache_service.invalidate_pattern('dashboard_')
        cache_service.invalidate_pattern('finance_')
    except Exception:
        pass
    
    return {
        "success": True,
        "issues_found": issues,
        "cleaning_done": cleaned
    }
