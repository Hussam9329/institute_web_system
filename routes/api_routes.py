# ============================================
# routes/api_routes.py
# نقاط نهاية API للعمليات AJAX
# ============================================

from fastapi import APIRouter, HTTPException, Body, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from database import Database
from services.finance_service import finance_service, sync_student_status
from config import get_current_date, format_currency
from auth import check_permission

router = APIRouter(prefix="/api")


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
        
        db.execute_query(
            "INSERT INTO subjects (name, created_at) VALUES (%s, %s)",
            (subject.name, get_current_date())
        )
        return {"success": True, "message": "تم إضافة المادة بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
        return {"success": True, "message": "تم تحديث المادة بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.delete("/subjects/{subject_id}")
async def api_delete_subject(request: Request, subject_id: int):
    """حذف مادة دراسية"""
    check_permission(request, 'delete_subjects')
    db = Database()
    try:
        # فحص وجود مدرسين مرتبطين بالمادة
        subject_info = db.execute_query("SELECT name FROM subjects WHERE id = %s", (subject_id,))
        if not subject_info:
            return {"success": False, "message": "المادة غير موجودة"}
        
        teachers_count = db.execute_query(
            "SELECT COUNT(*) as cnt FROM teachers WHERE subject = %s",
            (subject_info[0]['name'],)
        )
        if teachers_count and teachers_count[0]['cnt'] > 0:
            return {"success": False, "message": f"لا يمكن حذف المادة - يوجد {teachers_count[0]['cnt']} مدرس مرتبط بها"}
        
        db.execute_query("DELETE FROM subjects WHERE id = %s", (subject_id,))
        return {"success": True, "message": "تم حذف المادة"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
    query = "SELECT id, name, subject, total_fee, notes, teaching_types, fee_in_person, fee_electronic, fee_blended FROM teachers ORDER BY name"
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
        
        return {"success": True, "message": "تم الربط بنجاح"}
        
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
        
        return {"success": True, "message": f"تم ربط الطالب بـ {linked} مدرس"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
        
        if discount_type in ('percentage', 'custom') and (discount_value < 0 or discount_value > 100):
            return {"success": False, "message": "نسبة الخصم يجب أن تكون بين 0 و 100"}
        
        if discount_type == 'fixed' and discount_value <= 0:
            return {"success": False, "message": "قيمة الخصم الثابت يجب أن تكون أكبر من صفر"}
        
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
        
        return {
            "success": True, 
            "message": "تم تحديث الخصم بنجاح",
            "new_balance": new_balance
        }
        
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
    """تحديث نوع الدراسة والحالة لربط طالب بمدرس - مع منع تغيير نوع الدراسة إذا وُجدت مدفوعات"""
    check_permission(request, 'link_students')
    db = Database()
    
    try:
        new_study_type = data.get("study_type", "حضوري")
        status = data.get("status", "مستمر")
        
        # فحص وجود أقساط مدفوعة - يُمنع تغيير نوع الدراسة نهائياً
        payment_check = db.execute_query(
            "SELECT COUNT(*) as cnt FROM installments WHERE student_id = %s AND teacher_id = %s",
            (student_id, teacher_id)
        )
        has_payments = payment_check and payment_check[0]['cnt'] > 0
        
        if has_payments:
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
            # لا توجد مدفوعات - يمكن تحديث كل شيء
            db.execute_query(
                "UPDATE student_teacher SET study_type = %s, status = %s WHERE student_id = %s AND teacher_id = %s",
                (new_study_type, status, student_id, teacher_id)
            )
        
        sync_student_status(student_id)
        
        return {"success": True, "message": "تم التحديث بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.delete("/unlink-student-teacher/{student_id}/{teacher_id}")
async def api_unlink_student_teacher(request: Request, student_id: int, teacher_id: int):
    """إلغاء ربط طالب بمدرس - تغيير الحالة إلى منسحب مع الحفاظ على السجلات المالية"""
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
        
        # تغيير حالة الربط إلى "منسحب" بدلاً من حذفه
        # هذا يحافظ على السجلات المالية (الأقساط) ويسمح بتتبع تاريخ الطالب
        db.execute_query(
            "UPDATE student_teacher SET status = 'منسحب' WHERE student_id = %s AND teacher_id = %s",
            (student_id, teacher_id)
        )
        
        sync_student_status(student_id)
        
        # فحص عدد الأقساط المحفوظة للإبلاغ
        installment_count = db.execute_query(
            "SELECT COUNT(*) as cnt FROM installments WHERE student_id = %s AND teacher_id = %s",
            (student_id, teacher_id)
        )
        count = installment_count[0]['cnt'] if installment_count else 0
        
        msg = "تم إلغاء الربط وتغيير حالة الطالب إلى منسحب"
        if count > 0:
            msg = f"تم إلغاء الربط مع الحفاظ على {count} سجل مالي (قسط)"
        
        return {"success": True, "message": msg, "preserved_installments": count}
        
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
                "message": f"المبلغ يتجاوز القسط الكلي! القسط الكلي {format_currency(total_fee)}، المدفوع {format_currency(already_paid)}، المتبقي {format_currency(remaining)}"
            }

        insert_query = '''
            INSERT INTO installments (student_id, teacher_id, amount, payment_date, installment_type, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        '''
        
        result = db.execute_query(insert_query, (
            installment.student_id,
            installment.teacher_id,
            installment.amount,
            installment.payment_date,
            installment.installment_type,
            installment.notes
        ))
        installment_id = result[0]['id'] if result else None
        
        new_balance = finance_service.calculate_student_teacher_balance(
            installment.student_id, 
            installment.teacher_id
        )
        
        return {
            "success": True, 
            "message": "تم إضافة القسط بنجاح",
            "new_balance": new_balance,
            "installment_id": installment_id
        }
        
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
    
    return {
        "success": True,
        "data": [dict(r) for r in results] if results else [],
        "total_paid": total_paid
    }


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
    """حذف قسط - مع إرجاع تفاصيل القسط المحذوف"""
    check_permission(request, 'delete_payments')
    db = Database()
    
    try:
        installment = db.execute_query("SELECT * FROM installments WHERE id = %s", (installment_id,))
        
        if not installment:
            return {"success": False, "message": "القسط غير موجود"}
        
        inst_data = dict(installment[0])
        db.execute_query("DELETE FROM installments WHERE id = %s", (installment_id,))
        
        return {
            "success": True, 
            "message": "تم حذف القسط",
            "deleted_installment": inst_data
        }
        
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


# ===== عمليات السحوبات =====

@router.post("/withdrawals")
async def api_add_withdrawal(request: Request, withdrawal: AddWithdrawal):
    """تسجيل سحب جديد للمدرس"""
    check_permission(request, 'add_withdrawals')
    db = Database()
    
    try:
        amount = withdrawal.amount
        balance_info = finance_service.calculate_teacher_balance(withdrawal.teacher_id)
        available = balance_info['remaining_balance']

        can_withdraw, message, balance = finance_service.can_teacher_withdraw(
            withdrawal.teacher_id, 
            amount
        )
        
        if not can_withdraw:
            return {"success": False, "message": message}
        
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
        
        return {
            "success": True, 
            "message": "تم تسجيل السحب بنجاح",
            "new_balance": new_balance
        }
        
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
    db = Database()
    
    try:
        # فحص وجود السحب قبل الحذف
        existing = db.execute_query("SELECT id FROM teacher_withdrawals WHERE id = %s", (withdrawal_id,))
        if not existing:
            return {"success": False, "message": "السحب غير موجود"}
        
        db.execute_query("DELETE FROM teacher_withdrawals WHERE id = %s", (withdrawal_id,))
        return {"success": True, "message": "تم حذف السحب"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
        balance_info = finance_service.calculate_teacher_balance(teacher_id)
        other_withdrawn = balance_info['withdrawn_total'] - old[0]['amount']
        max_allowed = balance_info['teacher_due'] - other_withdrawn
        
        if amount > max_allowed:
            return {"success": False, "message": f"المبلغ يتجاوز الرصيد المتاح ({format_currency(max_allowed)})"}
        
        db.execute_query(
            "UPDATE teacher_withdrawals SET amount = %s, withdrawal_date = %s, notes = %s WHERE id = %s",
            (amount, withdrawal_date, notes, withdrawal_id)
        )
        return {"success": True, "message": "تم تعديل السحب بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


# ===== إحصائيات =====

@router.get("/statistics")
async def api_get_statistics(request: Request):
    """الحصول على إحصائيات النظام"""
    check_permission(request, 'view_dashboard')
    stats = finance_service.get_system_statistics()
    return {"success": True, "data": stats}


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
                (SELECT CASE WHEN COUNT(*) = 0 THEN 'غير مربوط' WHEN COUNT(*) FILTER (WHERE st.status = 'منسحب') = COUNT(*) THEN 'منسحب' ELSE 'مستمر' END 
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
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
            (name, capacity, notes, get_current_date())
        )
        new_id = result[0]['id'] if result else None
        return {"success": True, "message": "تم إضافة القاعة بنجاح", "id": new_id}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.delete("/rooms/{room_id}")
async def api_delete_room(request: Request, room_id: int):
    """حذف قاعة"""
    check_permission(request, 'delete_subjects')
    db = Database()
    try:
        # فحص وجود محاضرات مرتبطة
        schedule_count = db.execute_query(
            "SELECT COUNT(*) as cnt FROM weekly_schedule WHERE room_id = %s", (room_id,)
        )
        cnt = schedule_count[0]['cnt'] if schedule_count else 0
        if cnt > 0:
            # حذف المحاضرات المرتبطة أولاً
            db.execute_query("DELETE FROM weekly_schedule WHERE room_id = %s", (room_id,))
        
        db.execute_query("DELETE FROM rooms WHERE id = %s", (room_id,))
        return {"success": True, "message": "تم حذف القاعة وما يتعلق بها من محاضرات"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
        
        if not all([room_id, teacher_id, day_of_week, start_time]):
            return {"success": False, "message": "جميع الحقول مطلوبة (القاعة، المدرس، اليوم، وقت البداية)"}
        
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
        return {"success": False, "message": f"خطأ: {str(e)}"}


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
        
        if not all([room_id, teacher_id, day_of_week, start_time]):
            return {"success": False, "message": "جميع الحقول مطلوبة"}
        
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
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.delete("/weekly-schedule/{lecture_id}")
async def api_delete_weekly_lecture(request: Request, lecture_id: int):
    """حذف محاضرة من الجدول الأسبوعي"""
    check_permission(request, 'delete_subjects')
    db = Database()
    try:
        db.execute_query("DELETE FROM weekly_schedule WHERE id = %s", (lecture_id,))
        return {"success": True, "message": "تم حذف المحاضرة"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}
