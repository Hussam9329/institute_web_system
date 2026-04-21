# ============================================
# routes/main_routes.py
# المسارات الرئيسية للصفحات HTML
# ============================================

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import Database
from services.finance_service import finance_service
from config import get_current_date, format_currency

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """الصفحة الرئيسية - Dashboard"""
    # الحصول على الإحصائيات
    stats = finance_service.get_system_statistics()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "format_currency": format_currency
    })


@router.get("/students", response_class=HTMLResponse)
async def students_list(request: Request, search: str = ""):
    """صفحة قائمة الطلاب"""
    db = Database()
    
    if search:
        query = '''
            SELECT * FROM students 
            WHERE name LIKE ? OR barcode LIKE ?
            ORDER BY name
        '''
        students = db.execute_query(query, (f'%{search}%', f'%{search}%'))
    else:
        query = "SELECT * FROM students ORDER BY name"
        students = db.execute_query(query)
    
    return templates.TemplateResponse("students/list.html", {
        "request": request,
        "students": students,
        "search": search,
        "format_currency": format_currency
    })


@router.get("/students/add", response_class=HTMLResponse)
async def student_form(request: Request):
    """نموذج إضافة طالب جديد"""
    return templates.TemplateResponse("students/form.html", {
        "request": request,
        "student": None,
        "mode": "add"
    })


@router.post("/students/add")
async def student_add(
    request: Request,
    name: str = Form(...),
    study_type: str = Form("حضوري"),
    has_card: bool = Form(False),
    has_badge: bool = Form(False),
    status: str = Form("مستمر"),
    notes: str = Form("")
):
    """حفظ طالب جديد"""
    db = Database()
    
    # توليد باركود
    barcode_query = "SELECT MAX(id) as max_id FROM students"
    result = db.execute_query(barcode_query)
    next_id = (result[0]['max_id'] or 0) + 1
    barcode = f"STU-2024-{str(next_id).zfill(6)}"
    
    # إدخال الطالب
    insert_query = '''
        INSERT INTO students (name, study_type, has_card, has_badge, status, barcode, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    '''
    
    db.execute_query(insert_query, (
        name, study_type, 
        1 if has_card else 0, 
        1 if has_badge else 0, 
        status, barcode, notes, 
        get_current_date()
    ))
    
    return RedirectResponse(url="/students?msg=added", status_code=303)


@router.get("/students/{student_id}/edit", response_class=HTMLResponse)
async def student_edit_form(request: Request, student_id: int):
    """نموذج تعديل طالب"""
    db = Database()
    
    query = "SELECT * FROM students WHERE id = ?"
    result = db.execute_query(query, (student_id,))
    
    if not result:
        return RedirectResponse(url="/students?error=not_found", status_code=303)
    
    return templates.TemplateResponse("students/form.html", {
        "request": request,
        "student": dict(result[0]),
        "mode": "edit"
    })


@router.post("/students/{student_id}/edit")
async def student_update(
    request: Request,
    student_id: int,
    name: str = Form(...),
    study_type: str = Form("حضوري"),
    has_card: bool = Form(False),
    has_badge: bool = Form(False),
    status: str = Form("مستمر"),
    notes: str = Form("")
):
    """تحديث بيانات طالب"""
    db = Database()
    
    update_query = '''
        UPDATE students 
        SET name=?, study_type=?, has_card=?, has_badge=?, status=?, notes=?
        WHERE id = ?
    '''
    
    db.execute_query(update_query, (
        name, study_type,
        1 if has_card else 0,
        1 if has_badge else 0,
        status, notes, student_id
    ))
    
    return RedirectResponse(url="/students?msg=updated", status_code=303)


@router.get("/students/{student_id}", response_class=HTMLResponse)
async def student_profile(request: Request, student_id: int):
    """بروفايل الطالب"""
    db = Database()
    
    # بيانات الطالب
    student_query = "SELECT * FROM students WHERE id = ?"
    student_result = db.execute_query(student_query, (student_id,))
    
    if not student_result:
        return RedirectResponse(url="/students?error=not_found", status_code=303)
    
    student = dict(student_result[0])
    
    # ملخص المالي مع المدرسين
    teachers_summary = finance_service.get_student_all_teachers_summary(student_id)
    
    return templates.TemplateResponse("students/profile.html", {
        "request": request,
        "student": student,
        "teachers_summary": teachers_summary,
        "format_currency": format_currency
    })


@router.post("/students/{student_id}/delete")
async def student_delete(request: Request, student_id: int):
    """حذف طالب"""
    db = Database()
    
    # حذف الأقساط المرتبطة
    db.execute_query("DELETE FROM installments WHERE student_id = ?", (student_id,))
    
    # حذف الروابط مع المدرسين
    db.execute_query("DELETE FROM student_teacher WHERE student_id = ?", (student_id,))
    
    # حذف الطالب
    db.execute_query("DELETE FROM students WHERE id = ?", (student_id,))
    
    return RedirectResponse(url="/students?msg=deleted", status_code=303)


@router.get("/teachers", response_class=HTMLResponse)
async def teachers_list(request: Request, subject: str = ""):
    """صفحة قائمة المدرسين"""
    db = Database()
    
    if subject:
        query = "SELECT * FROM teachers WHERE subject = ? ORDER BY name"
        teachers = db.execute_query(query, (subject,))
    else:
        query = "SELECT * FROM teachers ORDER BY subject, name"
        teachers = db.execute_query(query)
    
    # الحصول على قائمة المواد الفريدة
    subjects_query = "SELECT DISTINCT subject FROM teachers ORDER BY subject"
    subjects = db.execute_query(subjects_query)
    
    return templates.TemplateResponse("teachers/list.html", {
        "request": request,
        "teachers": teachers,
        "subjects": subjects,
        "selected_subject": subject,
        "format_currency": format_currency
    })


@router.get("/teachers/add", response_class=HTMLResponse)
async def teacher_form(request: Request):
    """نموذج إضافة مدرس جديد"""
    return templates.TemplateResponse("teachers/form.html", {
        "request": request,
        "teacher": None,
        "mode": "add"
    })


@router.post("/teachers/add")
async def teacher_add(
    request: Request,
    name: str = Form(...),
    subject: str = Form(...),
    total_fee: int = Form(0),
    notes: str = Form("")
):
    """حفظ مدرس جديد"""
    db = Database()
    
    insert_query = '''
        INSERT INTO teachers (name, subject, total_fee, notes, created_at)
        VALUES (?, ?, ?, ?, ?)
    '''
    
    db.execute_query(insert_query, (name, subject, total_fee, notes, get_current_date()))
    
    return RedirectResponse(url="/teachers?msg=added", status_code=303)


@router.get("/teachers/{teacher_id}/edit", response_class=HTMLResponse)
async def teacher_edit_form(request: Request, teacher_id: int):
    """نموذج تعديل مدرس"""
    db = Database()
    
    query = "SELECT * FROM teachers WHERE id = ?"
    result = db.execute_query(query, (teacher_id,))
    
    if not result:
        return RedirectResponse(url="/teachers?error=not_found", status_code=303)
    
    return templates.TemplateResponse("teachers/form.html", {
        "request": request,
        "teacher": dict(result[0]),
        "mode": "edit"
    })


@router.post("/teachers/{teacher_id}/edit")
async def teacher_update(
    request: Request,
    teacher_id: int,
    name: str = Form(...),
    subject: str = Form(...),
    total_fee: int = Form(0),
    notes: str = Form("")
):
    """تحديث بيانات مدرس"""
    db = Database()
    
    update_query = '''
        UPDATE teachers 
        SET name=?, subject=?, total_fee=?, notes=?
        WHERE id = ?
    '''
    
    db.execute_query(update_query, (name, subject, total_fee, notes, teacher_id))
    
    return RedirectResponse(url="/teachers?msg=updated", status_code=303)


@router.get("/teachers/{teacher_id}", response_class=HTMLResponse)
async def teacher_detail(request: Request, teacher_id: int):
    """تفاصيل المدرس"""
    db = Database()
    
    # بيانات المدرس
    teacher_query = "SELECT * FROM teachers WHERE id = ?"
    teacher_result = db.execute_query(teacher_query, (teacher_id,))
    
    if not teacher_result:
        return RedirectResponse(url="/teachers?error=not_found", status_code=303)
    
    teacher = dict(teacher_result[0])
    
    # قائمة الطلاب
    students_list = finance_service.get_teacher_students_list(teacher_id)
    
    # معلومات مالية
    financial_info = finance_service.calculate_teacher_balance(teacher_id)
    
    return templates.TemplateResponse("teachers/detail.html", {
        "request": request,
        "teacher": teacher,
        "students_list": students_list,
        "financial_info": financial_info,
        "format_currency": format_currency
    })


@router.post("/teachers/{teacher_id}/delete")
async def teacher_delete(request: Request, teacher_id: int):
    """حذف مدرس"""
    db = Database()
    
    # حذف السحوبات
    db.execute_query("DELETE FROM teacher_withdrawals WHERE teacher_id = ?", (teacher_id,))
    
    # حذف الأقساط
    db.execute_query("DELETE FROM installments WHERE teacher_id = ?", (teacher_id,))
    
    # حذف الروابط
    db.execute_query("DELETE FROM student_teacher WHERE teacher_id = ?", (teacher_id,))
    
    # حذف المدرس
    db.execute_query("DELETE FROM teachers WHERE id = ?", (teacher_id,))
    
    return RedirectResponse(url="/teachers?msg=deleted", status_code=303)


@router.get("/accounting", response_class=HTMLResponse)
async def accounting_page(request: Request, search: str = ""):
    """صفحة محاسبة المدرسين"""
    db = Database()
    
    if search:
        query = '''
            SELECT t.*,
                   (SELECT COUNT(*) FROM student_teacher st WHERE st.teacher_id = t.id) as students_count
            FROM teachers t
            WHERE t.name LIKE ? OR t.subject LIKE ?
            ORDER BY t.name
        '''
        teachers = db.execute_query(query, (f'%{search}%', f'%{search}%'))
    else:
        query = '''
            SELECT t.*,
                   (SELECT COUNT(*) FROM student_teacher st WHERE st.teacher_id = t.id) as students_count
            FROM teachers t
            ORDER BY t.name
        '''
        teachers = db.execute_query(query)
    
    # إضافة المعلومات المالية لكل مدرس
    teachers_with_finance = []
    for teacher in teachers:
        teacher_dict = dict(teacher)
        teacher_dict['financial'] = finance_service.calculate_teacher_balance(teacher_dict['id'])
        teachers_with_finance.append(teacher_dict)
    
    return templates.TemplateResponse("accounting/index.html", {
        "request": request,
        "teachers": teachers_with_finance,
        "search": search,
        "format_currency": format_currency
    })


@router.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    """صفحة الإحصائيات"""
    stats = finance_service.get_system_statistics()
    
    return templates.TemplateResponse("stats/index.html", {
        "request": request,
        "stats": stats,
        "format_currency": format_currency
    })