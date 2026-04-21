# ============================================
# routes/main_routes.py
# المسارات الرئيسية للصفحات HTML
# ============================================

import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import Database
from services.finance_service import finance_service
from config import get_current_date, format_currency, BASE_DIR

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """الصفحة الرئيسية - Dashboard"""
    stats = finance_service.get_system_statistics()
    
    # آخر الأقساط
    db = Database()
    try:
        recent_installments = db.execute_query('''
            SELECT i.*, s.name as student_name, t.name as teacher_name, t.subject
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            ORDER BY i.id DESC LIMIT 5
        ''')
    except:
        recent_installments = []
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "recent_installments": recent_installments,
        "format_currency": format_currency
    })


# ===== المواد الدراسية =====

@router.get("/subjects", response_class=HTMLResponse)
async def subjects_list(request: Request):
    """صفحة إدارة المواد الدراسية"""
    db = Database()
    try:
        subjects = db.execute_query("SELECT * FROM subjects ORDER BY name")
        # عد المدرسين لكل مادة
        subjects_with_count = []
        for s in subjects:
            sd = dict(s)
            teachers = db.execute_query("SELECT COUNT(*) as cnt FROM teachers WHERE subject = %s", (sd['name'],))
            sd['teachers_count'] = teachers[0]['cnt'] if teachers else 0
            subjects_with_count.append(sd)
    except:
        subjects_with_count = []
    
    return templates.TemplateResponse("subjects/list.html", {
        "request": request,
        "subjects": subjects_with_count
    })


@router.post("/subjects/add")
async def subject_add(request: Request, name: str = Form(...)):
    """إضافة مادة جديدة"""
    db = Database()
    try:
        existing = db.execute_query("SELECT id FROM subjects WHERE name = %s", (name,))
        if existing:
            return RedirectResponse(url="/subjects?error=exists", status_code=303)
        db.execute_query("INSERT INTO subjects (name, created_at) VALUES (%s, %s)", (name, get_current_date()))
    except:
        pass
    return RedirectResponse(url="/subjects?msg=added", status_code=303)


@router.post("/subjects/{subject_id}/delete")
async def subject_delete(request: Request, subject_id: int):
    """حذف مادة"""
    db = Database()
    db.execute_query("DELETE FROM subjects WHERE id = %s", (subject_id,))
    return RedirectResponse(url="/subjects?msg=deleted", status_code=303)


# ===== الطلاب =====

@router.get("/students", response_class=HTMLResponse)
async def students_list(request: Request, search: str = "", msg: str = "", error: str = ""):
    """صفحة قائمة الطلاب"""
    db = Database()
    
    try:
        if search:
            query = '''
                SELECT s.*, 
                    (SELECT COUNT(*) FROM student_teacher st WHERE st.student_id = s.id) as teachers_count
                FROM students s
                WHERE s.name LIKE %s OR s.barcode LIKE %s
                ORDER BY s.name
            '''
            students = db.execute_query(query, (f'%{search}%', f'%{search}%'))
        else:
            query = '''
                SELECT s.*, 
                    (SELECT COUNT(*) FROM student_teacher st WHERE st.student_id = s.id) as teachers_count
                FROM students s
                ORDER BY s.name
            '''
            students = db.execute_query(query)
    except Exception as e:
        students = []
        print(f"Error loading students: {e}")
    
    return templates.TemplateResponse("students/list.html", {
        "request": request,
        "students": students,
        "search": search,
        "msg": msg,
        "error": error,
        "format_currency": format_currency
    })


@router.get("/students/add", response_class=HTMLResponse)
async def student_form(request: Request):
    """نموذج إضافة طالب جديد"""
    db = Database()
    teachers = db.execute_query("SELECT id, name, subject FROM teachers ORDER BY name")
    return templates.TemplateResponse("students/form.html", {
        "request": request,
        "student": None,
        "mode": "add",
        "teachers": teachers
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
    
    insert_query = '''
        INSERT INTO students (name, study_type, has_card, has_badge, status, barcode, notes, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    '''
    
    db.execute_query(insert_query, (
        name, study_type, 
        1 if has_card else 0, 
        1 if has_badge else 0, 
        status, barcode, notes, 
        get_current_date()
    ))
    
    # ربط الطالب بالمدرسين المحددين
    form_data = await request.form()
    teacher_ids = form_data.getlist("teacher_ids")
    
    if teacher_ids:
        # الحصول على آخر ID
        new_student = db.execute_query("SELECT MAX(id) as max_id FROM students")
        student_id = new_student[0]['max_id']
        
        for tid in teacher_ids:
            if tid:
                try:
                    db.execute_query(
                        "INSERT INTO student_teacher (student_id, teacher_id) VALUES (%s, %s)",
                        (student_id, int(tid))
                    )
                except:
                    pass
    
    return RedirectResponse(url="/students?msg=added", status_code=303)


@router.get("/students/{student_id}/edit", response_class=HTMLResponse)
async def student_edit_form(request: Request, student_id: int):
    """نموذج تعديل طالب"""
    db = Database()
    
    query = "SELECT * FROM students WHERE id = %s"
    result = db.execute_query(query, (student_id,))
    
    if not result:
        return RedirectResponse(url="/students?error=not_found", status_code=303)
    
    student = dict(result[0])
    teachers = db.execute_query("SELECT id, name, subject FROM teachers ORDER BY name")
    
    # المدرسين المرتبطين بالطالب
    linked = db.execute_query(
        "SELECT teacher_id FROM student_teacher WHERE student_id = %s",
        (student_id,)
    )
    linked_ids = [r['teacher_id'] for r in linked] if linked else []
    
    return templates.TemplateResponse("students/form.html", {
        "request": request,
        "student": student,
        "mode": "edit",
        "teachers": teachers,
        "linked_teacher_ids": linked_ids
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
        SET name=%s, study_type=%s, has_card=%s, has_badge=%s, status=%s, notes=%s
        WHERE id = %s
    '''
    
    db.execute_query(update_query, (
        name, study_type,
        1 if has_card else 0,
        1 if has_badge else 0,
        status, notes, student_id
    ))
    
    # تحديث ربط المدرسين
    form_data = await request.form()
    teacher_ids = form_data.getlist("teacher_ids")
    
    # حذف الروابط القديمة (بدون حذف الأقساط)
    db.execute_query("DELETE FROM student_teacher WHERE student_id = %s AND teacher_id NOT IN %s" % ('%s', ), 
                     () if not teacher_ids else (student_id, tuple(int(t) for t in teacher_ids if t)))
    
    # إعادة الربط بطريقة صحيحة
    # حذف كل الروابط القديمة أولاً
    old_links = db.execute_query("SELECT teacher_id FROM student_teacher WHERE student_id = %s", (student_id,))
    old_teacher_ids = set(r['teacher_id'] for r in old_links) if old_links else set()
    new_teacher_ids = set(int(t) for t in teacher_ids if t)
    
    # إضافة روابط جديدة فقط
    for tid in new_teacher_ids - old_teacher_ids:
        try:
            db.execute_query(
                "INSERT INTO student_teacher (student_id, teacher_id) VALUES (%s, %s)",
                (student_id, tid)
            )
        except:
            pass
    
    # حذف الروابط التي أزيلت (مع حذف الأقساط المرتبطة)
    for tid in old_teacher_ids - new_teacher_ids:
        db.execute_query("DELETE FROM installments WHERE student_id = %s AND teacher_id = %s", (student_id, tid))
        db.execute_query("DELETE FROM student_teacher WHERE student_id = %s AND teacher_id = %s", (student_id, tid))
    
    return RedirectResponse(url="/students?msg=updated", status_code=303)


@router.get("/students/{student_id}", response_class=HTMLResponse)
async def student_profile(request: Request, student_id: int):
    """بروفايل الطالب"""
    db = Database()
    
    student_query = "SELECT * FROM students WHERE id = %s"
    student_result = db.execute_query(student_query, (student_id,))
    
    if not student_result:
        return RedirectResponse(url="/students?error=not_found", status_code=303)
    
    student = dict(student_result[0])
    teachers_summary = finance_service.get_student_all_teachers_summary(student_id)
    
    # جميع الأقساط
    try:
        all_installments = db.execute_query('''
            SELECT i.*, t.name as teacher_name, t.subject
            FROM installments i
            JOIN teachers t ON i.teacher_id = t.id
            WHERE i.student_id = %s
            ORDER BY i.payment_date DESC
        ''', (student_id,))
    except:
        all_installments = []
    
    return templates.TemplateResponse("students/profile.html", {
        "request": request,
        "student": student,
        "teachers_summary": teachers_summary,
        "all_installments": all_installments,
        "format_currency": format_currency
    })


@router.post("/students/{student_id}/delete")
async def student_delete(request: Request, student_id: int):
    """حذف طالب"""
    db = Database()
    db.execute_query("DELETE FROM installments WHERE student_id = %s", (student_id,))
    db.execute_query("DELETE FROM student_teacher WHERE student_id = %s", (student_id,))
    db.execute_query("DELETE FROM students WHERE id = %s", (student_id,))
    return RedirectResponse(url="/students?msg=deleted", status_code=303)


# ===== المدرسين =====

@router.get("/teachers", response_class=HTMLResponse)
async def teachers_list(request: Request, subject: str = "", search: str = ""):
    """صفحة قائمة المدرسين"""
    db = Database()
    
    try:
        if search:
            query = "SELECT * FROM teachers WHERE name LIKE %s OR subject LIKE %s ORDER BY name"
            teachers = db.execute_query(query, (f'%{search}%', f'%{search}%'))
        elif subject:
            query = "SELECT * FROM teachers WHERE subject = %s ORDER BY name"
            teachers = db.execute_query(query, (subject,))
        else:
            query = "SELECT * FROM teachers ORDER BY subject, name"
            teachers = db.execute_query(query)
        
        # عدد الطلاب لكل مدرس
        for t in teachers:
            cnt = db.execute_query("SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],))
            t['students_count'] = cnt[0]['cnt'] if cnt else 0
    except:
        teachers = []
    
    # الحصول على المواد من جدول المواد + المواد الموجودة في المدرسين
    subjects_from_table = db.execute_query("SELECT name FROM subjects ORDER BY name")
    subjects_from_teachers = db.execute_query("SELECT DISTINCT subject as name FROM teachers ORDER BY subject")
    
    all_subjects = set()
    if subjects_from_table:
        all_subjects.update(s['name'] for s in subjects_from_table)
    if subjects_from_teachers:
        all_subjects.update(s['name'] for s in subjects_from_teachers)
    
    subjects_list = sorted(all_subjects)
    
    return templates.TemplateResponse("teachers/list.html", {
        "request": request,
        "teachers": teachers,
        "subjects": subjects_list,
        "selected_subject": subject,
        "search": search,
        "format_currency": format_currency
    })


@router.get("/teachers/add", response_class=HTMLResponse)
async def teacher_form(request: Request):
    """نموذج إضافة مدرس جديد"""
    db = Database()
    subjects = db.execute_query("SELECT name FROM subjects ORDER BY name")
    return templates.TemplateResponse("teachers/form.html", {
        "request": request,
        "teacher": None,
        "mode": "add",
        "subjects": subjects
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
    
    # إضافة المادة لجدول المواد إذا لم تكن موجودة
    existing_subject = db.execute_query("SELECT id FROM subjects WHERE name = %s", (subject,))
    if not existing_subject:
        try:
            db.execute_query("INSERT INTO subjects (name, created_at) VALUES (%s, %s)", (subject, get_current_date()))
        except:
            pass
    
    insert_query = '''
        INSERT INTO teachers (name, subject, total_fee, notes, created_at)
        VALUES (%s, %s, %s, %s, %s)
    '''
    
    db.execute_query(insert_query, (name, subject, total_fee, notes, get_current_date()))
    
    return RedirectResponse(url="/teachers?msg=added", status_code=303)


@router.get("/teachers/{teacher_id}/edit", response_class=HTMLResponse)
async def teacher_edit_form(request: Request, teacher_id: int):
    """نموذج تعديل مدرس"""
    db = Database()
    
    query = "SELECT * FROM teachers WHERE id = %s"
    result = db.execute_query(query, (teacher_id,))
    
    if not result:
        return RedirectResponse(url="/teachers?error=not_found", status_code=303)
    
    subjects = db.execute_query("SELECT name FROM subjects ORDER BY name")
    
    return templates.TemplateResponse("teachers/form.html", {
        "request": request,
        "teacher": dict(result[0]),
        "mode": "edit",
        "subjects": subjects
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
    
    # إضافة المادة لجدول المواد إذا لم تكن موجودة
    existing_subject = db.execute_query("SELECT id FROM subjects WHERE name = %s", (subject,))
    if not existing_subject:
        try:
            db.execute_query("INSERT INTO subjects (name, created_at) VALUES (%s, %s)", (subject, get_current_date()))
        except:
            pass
    
    update_query = '''
        UPDATE teachers 
        SET name=%s, subject=%s, total_fee=%s, notes=%s
        WHERE id = %s
    '''
    
    db.execute_query(update_query, (name, subject, total_fee, notes, teacher_id))
    
    return RedirectResponse(url="/teachers?msg=updated", status_code=303)


@router.get("/teachers/{teacher_id}", response_class=HTMLResponse)
async def teacher_detail(request: Request, teacher_id: int):
    """تفاصيل المدرس"""
    db = Database()
    
    teacher_query = "SELECT * FROM teachers WHERE id = %s"
    teacher_result = db.execute_query(teacher_query, (teacher_id,))
    
    if not teacher_result:
        return RedirectResponse(url="/teachers?error=not_found", status_code=303)
    
    teacher = dict(teacher_result[0])
    students_list = finance_service.get_teacher_students_list(teacher_id)
    financial_info = finance_service.calculate_teacher_balance(teacher_id)
    recent_withdrawals = finance_service.get_teacher_recent_withdrawals(teacher_id, limit=20)
    
    return templates.TemplateResponse("teachers/detail.html", {
        "request": request,
        "teacher": teacher,
        "students_list": students_list,
        "financial_info": financial_info,
        "recent_withdrawals": recent_withdrawals,
        "format_currency": format_currency
    })


@router.post("/teachers/{teacher_id}/delete")
async def teacher_delete(request: Request, teacher_id: int):
    """حذف مدرس"""
    db = Database()
    db.execute_query("DELETE FROM teacher_withdrawals WHERE teacher_id = %s", (teacher_id,))
    db.execute_query("DELETE FROM installments WHERE teacher_id = %s", (teacher_id,))
    db.execute_query("DELETE FROM student_teacher WHERE teacher_id = %s", (teacher_id,))
    db.execute_query("DELETE FROM teachers WHERE id = %s", (teacher_id,))
    return RedirectResponse(url="/teachers?msg=deleted", status_code=303)


# ===== المحاسبة =====

@router.get("/accounting", response_class=HTMLResponse)
async def accounting_page(request: Request, search: str = ""):
    """صفحة محاسبة المدرسين"""
    db = Database()
    
    try:
        if search:
            query = '''
                SELECT t.*,
                       (SELECT COUNT(*) FROM student_teacher st WHERE st.teacher_id = t.id) as students_count
                FROM teachers t
                WHERE t.name LIKE %s OR t.subject LIKE %s
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
        
        teachers_with_finance = []
        for teacher in teachers:
            teacher_dict = dict(teacher)
            try:
                teacher_dict['financial'] = finance_service.calculate_teacher_balance(teacher_dict['id'])
            except Exception as e:
                print(f"Error calculating balance for teacher {teacher_dict['id']}: {e}")
                teacher_dict['financial'] = {
                    'total_received': 0,
                    'institute_deduction': 0,
                    'paying_students_count': 0,
                    'teacher_due': 0,
                    'withdrawn_total': 0,
                    'remaining_balance': 0,
                    'can_withdraw': False
                }
            teachers_with_finance.append(teacher_dict)
    except Exception as e:
        print(f"Error loading accounting page: {e}")
        teachers_with_finance = []
    
    return templates.TemplateResponse("accounting/index.html", {
        "request": request,
        "teachers": teachers_with_finance,
        "search": search,
        "format_currency": format_currency
    })


# ===== الأقساط والمدفوعات =====

@router.get("/payments", response_class=HTMLResponse)
async def payments_page(request: Request, search: str = ""):
    """صفحة إدارة الأقساط والمدفوعات"""
    db = Database()
    
    try:
        if search:
            query = '''
                SELECT i.*, s.name as student_name, s.barcode, t.name as teacher_name, t.subject
                FROM installments i
                JOIN students s ON i.student_id = s.id
                JOIN teachers t ON i.teacher_id = t.id
                WHERE s.name LIKE %s OR t.name LIKE %s OR t.subject LIKE %s
                ORDER BY i.id DESC
            '''
            installments = db.execute_query(query, (f'%{search}%', f'%{search}%', f'%{search}%'))
        else:
            query = '''
                SELECT i.*, s.name as student_name, s.barcode, t.name as teacher_name, t.subject
                FROM installments i
                JOIN students s ON i.student_id = s.id
                JOIN teachers t ON i.teacher_id = t.id
                ORDER BY i.id DESC
            '''
            installments = db.execute_query(query)
    except:
        installments = []
    
    teachers = db.execute_query("SELECT id, name, subject, total_fee FROM teachers ORDER BY name")
    students = db.execute_query("SELECT id, name, barcode FROM students ORDER BY name")
    
    # إجماليات
    try:
        total_result = db.execute_query("SELECT COALESCE(SUM(amount), 0) as total FROM installments")
        total_amount = total_result[0]['total'] if total_result else 0
    except:
        total_amount = 0
    
    return templates.TemplateResponse("payments/index.html", {
        "request": request,
        "installments": installments,
        "teachers": teachers,
        "students": students,
        "search": search,
        "total_amount": total_amount,
        "format_currency": format_currency
    })


# ===== التقارير =====

@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    """صفحة التقارير"""
    db = Database()
    stats = finance_service.get_system_statistics()
    
    # ملخص المدرسين
    try:
        teachers = db.execute_query("SELECT id, name, subject FROM teachers ORDER BY name")
        teachers_report = []
        for t in teachers:
            td = dict(t)
            try:
                td['financial'] = finance_service.calculate_teacher_balance(td['id'])
                td['students_count'] = finance_service.get_teacher_total_students_count(td['id'])
            except:
                td['financial'] = {'teacher_due': 0, 'withdrawn_total': 0, 'remaining_balance': 0}
                td['students_count'] = 0
            teachers_report.append(td)
    except:
        teachers_report = []
    
    # ملخص الطلاب
    try:
        students = db.execute_query('''
            SELECT s.id, s.name, s.study_type, s.status, s.barcode,
                   (SELECT COUNT(*) FROM student_teacher st WHERE st.student_id = s.id) as teachers_count
            FROM students s ORDER BY s.name
        ''')
        students_report = []
        for s in students:
            sd = dict(s)
            summary = finance_service.get_student_all_teachers_summary(sd['id'])
            sd['total_fee'] = sum(t['total_fee'] for t in summary)
            sd['total_paid'] = sum(t['paid_total'] for t in summary)
            sd['total_remaining'] = sum(t['remaining_balance'] for t in summary)
            students_report.append(sd)
    except:
        students_report = []
    
    return templates.TemplateResponse("reports/index.html", {
        "request": request,
        "stats": stats,
        "teachers_report": teachers_report,
        "students_report": students_report,
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
