# ============================================
# routes/api_routes.py
# نقاط نهاية API للعمليات AJAX
# ============================================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from database import Database
from services.finance_service import finance_service
from config import get_current_date

router = APIRouter(prefix="/api")


# ===== نماذج API =====

class LinkStudentTeacher(BaseModel):
    student_id: int
    teacher_id: int


class AddInstallment(BaseModel):
    student_id: int
    teacher_id: int
    amount: int = Field(..., gt=0)
    payment_date: str
    installment_type: str = "القسط الأول"
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
async def api_add_subject(subject: SubjectCreate):
    """إضافة مادة دراسية جديدة"""
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
async def api_update_subject(subject_id: int, subject: SubjectUpdate):
    """تحديث مادة دراسية"""
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
async def api_delete_subject(subject_id: int):
    """حذف مادة دراسية"""
    db = Database()
    try:
        db.execute_query("DELETE FROM subjects WHERE id = %s", (subject_id,))
        return {"success": True, "message": "تم حذف المادة"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


# ===== عمليات الطلاب =====

@router.get("/students/{student_id}")
async def api_get_student(student_id: int):
    """الحصول على بيانات طالب"""
    db = Database()
    query = "SELECT * FROM students WHERE id = %s"
    result = db.execute_query(query, (student_id,))
    
    if not result:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    return {"success": True, "data": dict(result[0])}


@router.get("/students/{student_id}/teachers")
async def api_get_student_teachers(student_id: int):
    """الحصول على قائمة مدرسي طالب"""
    teachers_summary = finance_service.get_student_all_teachers_summary(student_id)
    return {"success": True, "data": teachers_summary}


# ===== عمليات المدرسين =====

@router.get("/teachers")
async def api_get_all_teachers():
    """الحصول على قائمة جميع المدرسين"""
    db = Database()
    query = "SELECT id, name, subject, total_fee, notes FROM teachers ORDER BY name"
    results = db.execute_query(query)
    
    return {"success": True, "data": [dict(r) for r in results] if results else []}


@router.get("/teachers/{teacher_id}")
async def api_get_teacher(teacher_id: int):
    """الحصول على بيانات مدرس"""
    db = Database()
    query = "SELECT * FROM teachers WHERE id = %s"
    result = db.execute_query(query, (teacher_id,))
    
    if not result:
        raise HTTPException(status_code=404, detail="المدرس غير موجود")
    
    return {"success": True, "data": dict(result[0])}


@router.get("/teachers/{teacher_id}/balance")
async def api_get_teacher_balance(teacher_id: int):
    """الحصول على الرصيد المالي للمدرس"""
    balance = finance_service.calculate_teacher_balance(teacher_id)
    return {"success": True, "data": balance}


@router.get("/teachers/{teacher_id}/students")
async def api_get_teacher_students(teacher_id: int):
    """الحصول على قائمة طلاب مدرس"""
    students = finance_service.get_teacher_students_list(teacher_id)
    return {"success": True, "data": students}


# ===== ربط الطالب بمدرس =====

@router.post("/link-student-teacher")
async def api_link_student_teacher(link: LinkStudentTeacher):
    """ربط طالب بمدرس"""
    db = Database()
    
    try:
        student_check = db.execute_query("SELECT id FROM students WHERE id = %s", (link.student_id,))
        teacher_check = db.execute_query("SELECT id FROM teachers WHERE id = %s", (link.teacher_id,))
        
        if not student_check or not teacher_check:
            raise HTTPException(status_code=404, detail="الطالب أو المدرس غير موجود")
        
        existing = db.execute_query(
            "SELECT * FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
            (link.student_id, link.teacher_id)
        )
        
        if existing:
            return {"success": False, "message": "الربط موجود مسبقاً"}
        
        db.execute_query(
            "INSERT INTO student_teacher (student_id, teacher_id) VALUES (%s, %s)",
            (link.student_id, link.teacher_id)
        )
        
        return {"success": True, "message": "تم الربط بنجاح"}
        
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.post("/link-student-teachers")
async def api_link_student_teachers(data: dict):
    """ربط طالب بعدة مدرسين"""
    db = Database()
    student_id = data.get("student_id")
    teacher_ids = data.get("teacher_ids", [])
    
    if not student_id or not teacher_ids:
        return {"success": False, "message": "بيانات ناقصة"}
    
    try:
        linked = 0
        for teacher_id in teacher_ids:
            existing = db.execute_query(
                "SELECT * FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
                (student_id, int(teacher_id))
            )
            if not existing:
                db.execute_query(
                    "INSERT INTO student_teacher (student_id, teacher_id) VALUES (%s, %s)",
                    (student_id, int(teacher_id))
                )
                linked += 1
        
        return {"success": True, "message": f"تم ربط الطالب بـ {linked} مدرس"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.delete("/unlink-student-teacher/{student_id}/{teacher_id}")
async def api_unlink_student_teacher(student_id: int, teacher_id: int):
    """إلغاء ربط طالب بمدرس (مع حذف الأقساط)"""
    db = Database()
    
    try:
        db.execute_query(
            "DELETE FROM installments WHERE student_id = %s AND teacher_id = %s",
            (student_id, teacher_id)
        )
        
        db.execute_query(
            "DELETE FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
            (student_id, teacher_id)
        )
        
        return {"success": True, "message": "تم إلغاء الربط وحذف الأقساط"}
        
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


# ===== عمليات الأقساط =====

@router.post("/installments")
async def api_add_installment(installment: AddInstallment):
    """إضافة قسط جديد"""
    db = Database()
    
    try:
        link_check = db.execute_query(
            "SELECT * FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
            (installment.student_id, installment.teacher_id)
        )
        
        if not link_check:
            db.execute_query(
                "INSERT INTO student_teacher (student_id, teacher_id) VALUES (%s, %s)",
                (installment.student_id, installment.teacher_id)
            )
        
        insert_query = '''
            INSERT INTO installments (student_id, teacher_id, amount, payment_date, installment_type, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
        '''
        
        db.execute_query(insert_query, (
            installment.student_id,
            installment.teacher_id,
            installment.amount,
            installment.payment_date,
            installment.installment_type,
            installment.notes
        ))
        
        new_balance = finance_service.calculate_student_teacher_balance(
            installment.student_id, 
            installment.teacher_id
        )
        
        return {
            "success": True, 
            "message": "تم إضافة القسط بنجاح",
            "new_balance": new_balance
        }
        
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.get("/installments/student/{student_id}/teacher/{teacher_id}")
async def api_get_installments(student_id: int, teacher_id: int):
    """الحصول على أقساط طالب عند مدرس معين"""
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
async def api_get_recent_installments(limit: int = 20):
    """الحصول على آخر الأقساط المسجلة"""
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
async def api_delete_installment(installment_id: int):
    """حذف قسط"""
    db = Database()
    
    try:
        installment = db.execute_query("SELECT * FROM installments WHERE id = %s", (installment_id,))
        
        if not installment:
            return {"success": False, "message": "القسط غير موجود"}
        
        db.execute_query("DELETE FROM installments WHERE id = %s", (installment_id,))
        
        return {"success": True, "message": "تم حذف القسط"}
        
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


# ===== عمليات السحوبات =====

@router.post("/withdrawals")
async def api_add_withdrawal(withdrawal: AddWithdrawal):
    """تسجيل سحب جديد للمدرس"""
    db = Database()
    
    try:
        can_withdraw, message, balance = finance_service.can_teacher_withdraw(
            withdrawal.teacher_id, 
            withdrawal.amount
        )
        
        if not can_withdraw:
            return {"success": False, "message": message}
        
        insert_query = '''
            INSERT INTO teacher_withdrawals (teacher_id, amount, withdrawal_date, notes)
            VALUES (%s, %s, %s, %s)
        '''
        
        db.execute_query(insert_query, (
            withdrawal.teacher_id,
            withdrawal.amount,
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
async def api_get_withdrawals(teacher_id: int, limit: int = 10):
    """الحصول على سحوبات مدرس"""
    withdrawals = finance_service.get_teacher_recent_withdrawals(teacher_id, limit)
    total = finance_service.get_teacher_withdrawn_total(teacher_id)
    
    return {
        "success": True,
        "data": withdrawals,
        "total_withdrawn": total
    }


@router.delete("/withdrawals/{withdrawal_id}")
async def api_delete_withdrawal(withdrawal_id: int):
    """حذف سحب"""
    db = Database()
    
    try:
        db.execute_query("DELETE FROM teacher_withdrawals WHERE id = %s", (withdrawal_id,))
        return {"success": True, "message": "تم حذف السحب"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


# ===== إحصائيات =====

@router.get("/statistics")
async def api_get_statistics():
    """الحصول على إحصائيات النظام"""
    stats = finance_service.get_system_statistics()
    return {"success": True, "data": stats}


# ===== بحث شامل =====

@router.get("/search")
async def api_global_search(q: str = ""):
    """بحث شامل في النظام"""
    db = Database()
    results = {"students": [], "teachers": [], "subjects": []}
    
    if not q or len(q) < 1:
        return {"success": True, "data": results}
    
    try:
        # بحث الطلاب
        students = db.execute_query(
            '''SELECT id, name, barcode, study_type FROM students 
               WHERE name LIKE %s OR barcode LIKE %s ORDER BY name LIMIT 10''',
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
