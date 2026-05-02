# ============================================
# routes/main_routes.py
# المسارات الرئيسية للصفحات HTML
# ============================================

import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import Database
from services.finance_service import finance_service, sync_student_status
from config import get_current_date, format_currency, format_date, BASE_DIR, generate_barcode

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# إضافة دوال عامة للقوالب
templates.env.globals['format_date'] = format_date


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
    error_msg = ""
    error_detail = ""
    try:
        subjects = db.execute_query("SELECT * FROM subjects ORDER BY name")
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
        "subjects": subjects_with_count,
        "error_msg": error_msg,
        "error_detail": error_detail
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
    """حذف مادة - مع حماية إذا كان فيها أساتذة"""
    db = Database()
    teachers_count = db.execute_query("SELECT COUNT(*) as cnt FROM teachers WHERE subject = (SELECT name FROM subjects WHERE id = %s)", (subject_id,))
    if teachers_count and teachers_count[0]['cnt'] > 0:
        cnt = teachers_count[0]['cnt']
        return RedirectResponse(url=f"/subjects?error=has_teachers&count={cnt}", status_code=303)
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
                    (SELECT COUNT(*) FROM student_teacher st WHERE st.student_id = s.id) as teachers_count,
                    (SELECT COALESCE(SUM(i.amount), 0) FROM installments i WHERE i.student_id = s.id) as total_paid,
                    (SELECT COALESCE(SUM(
                        CASE 
                            WHEN st2.study_type = 'الكتروني' AND t2.fee_electronic > 0 THEN t2.fee_electronic
                            WHEN st2.study_type = 'مدمج' AND t2.fee_blended > 0 THEN t2.fee_blended
                            WHEN st2.study_type = 'حضوري' AND t2.fee_in_person > 0 THEN t2.fee_in_person
                            ELSE t2.total_fee
                        END
                    ), 0) FROM student_teacher st2 JOIN teachers t2 ON st2.teacher_id = t2.id WHERE st2.student_id = s.id) as total_fees,
                    (SELECT CASE WHEN COUNT(*) = 0 THEN 'غير مربوط' WHEN COUNT(*) FILTER (WHERE st3.status = 'منسحب') = COUNT(*) THEN 'منسحب' WHEN COUNT(*) FILTER (WHERE st3.status = 'منسحب') > 0 THEN 'مدمج' ELSE 'مستمر' END FROM student_teacher st3 WHERE st3.student_id = s.id) as status
                FROM students s
                WHERE s.name LIKE %s OR s.barcode LIKE %s
                ORDER BY s.name
            '''
            students = db.execute_query(query, (f'%{search}%', f'%{search}%'))
        else:
            query = '''
                SELECT s.*,
                    (SELECT COUNT(*) FROM student_teacher st WHERE st.student_id = s.id) as teachers_count,
                    (SELECT COALESCE(SUM(i.amount), 0) FROM installments i WHERE i.student_id = s.id) as total_paid,
                    (SELECT COALESCE(SUM(
                        CASE 
                            WHEN st2.study_type = 'الكتروني' AND t2.fee_electronic > 0 THEN t2.fee_electronic
                            WHEN st2.study_type = 'مدمج' AND t2.fee_blended > 0 THEN t2.fee_blended
                            WHEN st2.study_type = 'حضوري' AND t2.fee_in_person > 0 THEN t2.fee_in_person
                            ELSE t2.total_fee
                        END
                    ), 0) FROM student_teacher st2 JOIN teachers t2 ON st2.teacher_id = t2.id WHERE st2.student_id = s.id) as total_fees,
                    (SELECT CASE WHEN COUNT(*) = 0 THEN 'غير مربوط' WHEN COUNT(*) FILTER (WHERE st3.status = 'منسحب') = COUNT(*) THEN 'منسحب' WHEN COUNT(*) FILTER (WHERE st3.status = 'منسحب') > 0 THEN 'مدمج' ELSE 'مستمر' END FROM student_teacher st3 WHERE st3.student_id = s.id) as status
                FROM students s
                ORDER BY s.name
            '''
            students = db.execute_query(query)
    except Exception as e:
        students = []
        print(f"Error loading students: {e}")

    # حساب المتبقي لكل طالب
    for s in students:
        fees = s.get('total_fees', 0) or 0
        paid = s.get('total_paid', 0) or 0
        s['total_remaining'] = fees - paid

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
    teachers = db.execute_query("SELECT id, name, subject, teaching_types FROM teachers ORDER BY name")
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
    notes: str = Form("")
):
    """حفظ طالب جديد"""
    db = Database()

    # توليد باركود حقيقي مباشرة باستخدام RETURNING
    # أولاً ندرج بدون باركود ثم نحدثه
    insert_query = '''
        INSERT INTO students (name, barcode, notes, created_at)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    '''
    
    temp_barcode = f"TEMP-{get_current_date()}"
    result = db.execute_query(insert_query, (name, temp_barcode, notes, get_current_date()))
    student_id = result[0]['id'] if result else None
    
    if student_id:
        real_barcode = generate_barcode(student_id)
        db.execute_query("UPDATE students SET barcode = %s WHERE id = %s", (real_barcode, student_id))

    # ربط الطالب بالمدرسين المحددين
    form_data = await request.form()
    teacher_ids = form_data.getlist("teacher_ids")

    if teacher_ids:
        for tid in teacher_ids:
            if tid:
                study_type = form_data.get(f"study_type_{tid}", "حضوري")
                status = form_data.get(f"status_{tid}", "مستمر")
                try:
                    db.execute_query(
                        "INSERT INTO student_teacher (student_id, teacher_id, study_type, status) VALUES (%s, %s, %s, %s)",
                        (student_id, int(tid), study_type, status)
                    )
                except:
                    pass

        sync_student_status(student_id)

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
    teachers = db.execute_query("SELECT id, name, subject, teaching_types FROM teachers ORDER BY name")

    # المدرسين المرتبطين بالطالب مع بيانات الربط
    linked = db.execute_query(
        "SELECT teacher_id, study_type, status FROM student_teacher WHERE student_id = %s",
        (student_id,)
    )
    linked_ids = [r['teacher_id'] for r in linked] if linked else []
    linked_data = {r['teacher_id']: r for r in linked} if linked else {}

    return templates.TemplateResponse("students/form.html", {
        "request": request,
        "student": student,
        "mode": "edit",
        "teachers": teachers,
        "linked_teacher_ids": linked_ids,
        "linked_data": linked_data
    })


@router.post("/students/{student_id}/edit")
async def student_update(
    request: Request,
    student_id: int,
    name: str = Form(...),
    notes: str = Form("")
):
    """تحديث بيانات طالب"""
    db = Database()

    update_query = '''
        UPDATE students
        SET name=%s, notes=%s
        WHERE id = %s
    '''

    db.execute_query(update_query, (
        name,
        notes, student_id
    ))

    # تحديث ربط المدرسين مع نوع الدراسة والحالة
    form_data = await request.form()
    teacher_ids = form_data.getlist("teacher_ids")

    # حذف كل الروابط القديمة أولاً
    old_links = db.execute_query("SELECT teacher_id FROM student_teacher WHERE student_id = %s", (student_id,))
    old_teacher_ids = set(r['teacher_id'] for r in old_links) if old_links else set()
    new_teacher_ids = set(int(t) for t in teacher_ids if t)

    # تحديث الروابط الموجودة
    for tid in new_teacher_ids & old_teacher_ids:
        study_type = form_data.get(f"study_type_{tid}", "حضوري")
        status = form_data.get(f"status_{tid}", "مستمر")
        try:
            db.execute_query(
                "UPDATE student_teacher SET study_type=%s, status=%s WHERE student_id=%s AND teacher_id=%s",
                (study_type, status, student_id, tid)
            )
        except:
            pass

    # إضافة روابط جديدة فقط
    for tid in new_teacher_ids - old_teacher_ids:
        study_type = form_data.get(f"study_type_{tid}", "حضوري")
        status = form_data.get(f"status_{tid}", "مستمر")
        try:
            db.execute_query(
                "INSERT INTO student_teacher (student_id, teacher_id, study_type, status) VALUES (%s, %s, %s, %s)",
                (student_id, tid, study_type, status)
            )
        except:
            pass

    # حذف الروابط التي أزيلت (مع حذف الأقساط المرتبطة)
    for tid in old_teacher_ids - new_teacher_ids:
        db.execute_query("DELETE FROM installments WHERE student_id = %s AND teacher_id = %s", (student_id, tid))
        db.execute_query("DELETE FROM student_teacher WHERE student_id = %s AND teacher_id = %s", (student_id, tid))

    sync_student_status(student_id)

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

def _build_institute_rate_display(teacher: dict) -> str:
    """عرض نسبة/مبلغ خصم المعهد - يدعم العرض حسب أنواع التدريس المختلفة"""
    # محاولة عرض معلومات الخصم حسب نوع التدريس
    teaching_types = (teacher.get('teaching_types') or 'حضوري').split(',')
    teaching_types = [t.strip() for t in teaching_types if t.strip()]
    
    type_map = {
        'حضوري': ('institute_pct_in_person', 'inst_ded_type_in_person', 'inst_ded_manual_in_person'),
        'الكتروني': ('institute_pct_electronic', 'inst_ded_type_electronic', 'inst_ded_manual_electronic'),
        'مدمج': ('institute_pct_blended', 'inst_ded_type_blended', 'inst_ded_manual_blended'),
    }
    
    displays = []
    for tt in teaching_types:
        if tt in type_map:
            pct_key, ded_type_key, manual_key = type_map[tt]
            ded_type = teacher.get(ded_type_key, 'percentage')
            
            if ded_type == 'manual':
                manual_val = teacher.get(manual_key, 0) or 0
                if manual_val > 0:
                    displays.append(f"{tt}: {format_currency(manual_val)}")
            else:
                pct_val = teacher.get(pct_key, 0) or 0
                if pct_val > 0:
                    displays.append(f"{tt}: {pct_val}%")
    
    if displays:
        return ' | '.join(displays)
    
    # fallback للحقول الأساسية
    ded_type = teacher.get('institute_deduction_type', 'percentage')
    ded_value = teacher.get('institute_deduction_value', 0) or 0

    if ded_type == 'manual' and ded_value > 0:
        return format_currency(ded_value)
    elif ded_value > 0:
        return f"{ded_value}%"
    return '-'


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

        # عدد الطلاب لكل مدرس + البيانات المالية الكاملة
        for t in teachers:
            cnt = db.execute_query("SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],))
            t['students_count'] = cnt[0]['cnt'] if cnt else 0
            try:
                balance_info = finance_service.calculate_teacher_balance(t['id'])
                t['total_received'] = balance_info.get('total_received', 0)
                t['total_remaining'] = balance_info.get('remaining_balance', 0)
                t['institute_deduction'] = balance_info.get('institute_deduction', 0)
                t['teacher_due'] = balance_info.get('teacher_due', 0)
                t['withdrawn_total'] = balance_info.get('withdrawn_total', 0)
                t['remaining_balance'] = balance_info.get('remaining_balance', 0)
                # حساب المطلوب الكلي - مجموع أقساط المدرس حسب نوع الدراسة لكل طالب
                try:
                    all_fees = db.execute_query(
                        '''SELECT COALESCE(SUM(
                               CASE 
                                   WHEN st.study_type = 'الكتروني' AND t.fee_electronic > 0 THEN t.fee_electronic
                                   WHEN st.study_type = 'مدمج' AND t.fee_blended > 0 THEN t.fee_blended
                                   WHEN st.study_type = 'حضوري' AND t.fee_in_person > 0 THEN t.fee_in_person
                                   ELSE t.total_fee
                               END
                           ), 0) as total 
                           FROM student_teacher st 
                           JOIN teachers t ON st.teacher_id = t.id
                           WHERE st.teacher_id = %s''',
                        (t['id'],)
                    )
                    total_fees = all_fees[0]['total'] if all_fees else 0
                    t['total_fees'] = total_fees
                except:
                    t['total_fees'] = 0
                # حساب عرض نسبة المعهد حسب أنواع التدريس
                t['institute_rate_display'] = _build_institute_rate_display(t)
            except:
                t['total_received'] = 0
                t['total_remaining'] = 0
                t['institute_deduction'] = 0
                t['teacher_due'] = 0
                t['withdrawn_total'] = 0
                t['remaining_balance'] = 0
                t['total_fees'] = 0
                t['institute_rate_display'] = ''
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
async def teacher_form(request: Request, error: str = ""):
    """نموذج إضافة مدرس جديد"""
    db = Database()
    subjects = db.execute_query("SELECT name FROM subjects ORDER BY name")
    return templates.TemplateResponse("teachers/form.html", {
        "request": request,
        "teacher": None,
        "mode": "add",
        "subjects": subjects,
        "error": error
    })


@router.post("/teachers/add")
async def teacher_add(
    request: Request,
    name: str = Form(...),
    subject: str = Form(...),
    total_fee: int = Form(0),
    institute_deduction_type: str = Form("percentage"),
    institute_deduction_value: int = Form(0),
    notes: str = Form(""),
    teaching_types: str = Form("حضوري"),
    fee_in_person: int = Form(0),
    fee_electronic: int = Form(0),
    fee_blended: int = Form(0),
    institute_pct_in_person: int = Form(0),
    institute_pct_electronic: int = Form(0),
    institute_pct_blended: int = Form(0),
    inst_ded_type_in_person: str = Form("percentage"),
    inst_ded_type_electronic: str = Form("percentage"),
    inst_ded_type_blended: str = Form("percentage"),
    inst_ded_manual_in_person: int = Form(0),
    inst_ded_manual_electronic: int = Form(0),
    inst_ded_manual_blended: int = Form(0)
):
    """حفظ مدرس جديد"""
    if not teaching_types or teaching_types.strip() == '':
        return RedirectResponse(url="/teachers/add?error=no_teaching_type", status_code=303)

    db = Database()

    existing_subject = db.execute_query("SELECT id FROM subjects WHERE name = %s", (subject,))
    if not existing_subject:
        try:
            db.execute_query("INSERT INTO subjects (name, created_at) VALUES (%s, %s)", (subject, get_current_date()))
        except:
            pass

    insert_query = '''
        INSERT INTO teachers (name, subject, total_fee, institute_deduction_type, institute_deduction_value, notes, created_at,
            teaching_types, fee_in_person, fee_electronic, fee_blended,
            institute_pct_in_person, institute_pct_electronic, institute_pct_blended,
            inst_ded_type_in_person, inst_ded_type_electronic, inst_ded_type_blended,
            inst_ded_manual_in_person, inst_ded_manual_electronic, inst_ded_manual_blended)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    '''

    db.execute_query(insert_query, (name, subject, total_fee, institute_deduction_type, institute_deduction_value, notes, get_current_date(),
        teaching_types, fee_in_person, fee_electronic, fee_blended,
        institute_pct_in_person, institute_pct_electronic, institute_pct_blended,
        inst_ded_type_in_person, inst_ded_type_electronic, inst_ded_type_blended,
        inst_ded_manual_in_person, inst_ded_manual_electronic, inst_ded_manual_blended))

    return RedirectResponse(url="/teachers?msg=added", status_code=303)


@router.get("/teachers/{teacher_id}/edit", response_class=HTMLResponse)
async def teacher_edit_form(request: Request, teacher_id: int, error: str = ""):
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
        "subjects": subjects,
        "error": error
    })


@router.post("/teachers/{teacher_id}/edit")
async def teacher_update(
    request: Request,
    teacher_id: int,
    name: str = Form(...),
    subject: str = Form(...),
    total_fee: int = Form(0),
    institute_deduction_type: str = Form("percentage"),
    institute_deduction_value: int = Form(0),
    notes: str = Form(""),
    teaching_types: str = Form("حضوري"),
    fee_in_person: int = Form(0),
    fee_electronic: int = Form(0),
    fee_blended: int = Form(0),
    institute_pct_in_person: int = Form(0),
    institute_pct_electronic: int = Form(0),
    institute_pct_blended: int = Form(0),
    inst_ded_type_in_person: str = Form("percentage"),
    inst_ded_type_electronic: str = Form("percentage"),
    inst_ded_type_blended: str = Form("percentage"),
    inst_ded_manual_in_person: int = Form(0),
    inst_ded_manual_electronic: int = Form(0),
    inst_ded_manual_blended: int = Form(0)
):
    """تحديث بيانات مدرس"""
    if not teaching_types or teaching_types.strip() == '':
        return RedirectResponse(url=f"/teachers/{teacher_id}/edit?error=no_teaching_type", status_code=303)

    db = Database()

    existing_subject = db.execute_query("SELECT id FROM subjects WHERE name = %s", (subject,))
    if not existing_subject:
        try:
            db.execute_query("INSERT INTO subjects (name, created_at) VALUES (%s, %s)", (subject, get_current_date()))
        except:
            pass

    update_query = '''
        UPDATE teachers
        SET name=%s, subject=%s, total_fee=%s, institute_deduction_type=%s, institute_deduction_value=%s, notes=%s,
            teaching_types=%s, fee_in_person=%s, fee_electronic=%s, fee_blended=%s,
            institute_pct_in_person=%s, institute_pct_electronic=%s, institute_pct_blended=%s,
            inst_ded_type_in_person=%s, inst_ded_type_electronic=%s, inst_ded_type_blended=%s,
            inst_ded_manual_in_person=%s, inst_ded_manual_electronic=%s, inst_ded_manual_blended=%s
        WHERE id = %s
    '''

    db.execute_query(update_query, (name, subject, total_fee, institute_deduction_type, institute_deduction_value, notes,
        teaching_types, fee_in_person, fee_electronic, fee_blended,
        institute_pct_in_person, institute_pct_electronic, institute_pct_blended,
        inst_ded_type_in_person, inst_ded_type_electronic, inst_ded_type_blended,
        inst_ded_manual_in_person, inst_ded_manual_electronic, inst_ded_manual_blended,
        teacher_id))

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

    counts_query = '''
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE study_type = 'حضوري') as in_person,
            COUNT(*) FILTER (WHERE study_type = 'الكتروني') as electronic,
            COUNT(*) FILTER (WHERE study_type = 'مدمج') as blended
        FROM student_teacher WHERE teacher_id = %s
    '''
    counts_result = db.execute_query(counts_query, (teacher_id,))
    study_counts = dict(counts_result[0]) if counts_result else {'total': 0, 'in_person': 0, 'electronic': 0, 'blended': 0}

    return templates.TemplateResponse("teachers/detail.html", {
        "request": request,
        "teacher": teacher,
        "students_list": students_list,
        "financial_info": financial_info,
        "study_counts": study_counts,
        "format_currency": format_currency
    })


@router.post("/teachers/{teacher_id}/delete")
async def teacher_delete(request: Request, teacher_id: int):
    """حذف مدرس - مع حماية إذا كان مرتبط بطلاب"""
    db = Database()
    students_count = db.execute_query("SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (teacher_id,))
    if students_count and students_count[0]['cnt'] > 0:
        cnt = students_count[0]['cnt']
        teacher = db.execute_query("SELECT name FROM teachers WHERE id = %s", (teacher_id,))
        teacher_name = teacher[0]['name'] if teacher else ''
        return RedirectResponse(url=f"/teachers?error=has_students&count={cnt}&name={teacher_name}", status_code=303)
    db.execute_query("DELETE FROM teacher_withdrawals WHERE teacher_id = %s", (teacher_id,))
    db.execute_query("DELETE FROM installments WHERE teacher_id = %s", (teacher_id,))
    db.execute_query("DELETE FROM student_teacher WHERE teacher_id = %s", (teacher_id,))
    db.execute_query("DELETE FROM teachers WHERE id = %s", (teacher_id,))
    return RedirectResponse(url="/teachers?msg=deleted", status_code=303)


# ===== المحاسبة =====

@router.get("/accounting", response_class=HTMLResponse)
async def accounting_page(request: Request, search: str = "", date_from: str = "", date_to: str = ""):
    """صفحة محاسبة المدرسين"""
    db = Database()

    try:
        if search:
            query = '''
                SELECT t.*,
                       (SELECT COUNT(*) FROM student_teacher st WHERE st.teacher_id = t.id) as students_count,
                       (SELECT COUNT(*) FROM student_teacher st WHERE st.teacher_id = t.id AND st.study_type = 'حضوري') as students_in_person,
                       (SELECT COUNT(*) FROM student_teacher st WHERE st.teacher_id = t.id AND st.study_type = 'الكتروني') as students_electronic,
                       (SELECT COUNT(*) FROM student_teacher st WHERE st.teacher_id = t.id AND st.study_type = 'مدمج') as students_blended
                FROM teachers t
                WHERE t.name LIKE %s OR t.subject LIKE %s
                ORDER BY t.name
            '''
            teachers = db.execute_query(query, (f'%{search}%', f'%{search}%'))
        else:
            query = '''
                SELECT t.*,
                       (SELECT COUNT(*) FROM student_teacher st WHERE st.teacher_id = t.id) as students_count,
                       (SELECT COUNT(*) FROM student_teacher st WHERE st.teacher_id = t.id AND st.study_type = 'حضوري') as students_in_person,
                       (SELECT COUNT(*) FROM student_teacher st WHERE st.teacher_id = t.id AND st.study_type = 'الكتروني') as students_electronic,
                       (SELECT COUNT(*) FROM student_teacher st WHERE st.teacher_id = t.id AND st.study_type = 'مدمج') as students_blended
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
        "date_from": date_from,
        "date_to": date_to,
        "format_currency": format_currency
    })


# ===== السحوبات =====

@router.get("/withdrawals", response_class=HTMLResponse)
async def withdrawals_page(request: Request, date_from: str = "", date_to: str = ""):
    """صفحة إدارة السحوبات"""
    db = Database()

    try:
        all_withdrawals = finance_service.get_all_withdrawals(limit=200)
        # فلترة بالتاريخ إذا تم تحديده
        if date_from:
            all_withdrawals = [w for w in all_withdrawals if w.get('withdrawal_date', '') >= date_from]
        if date_to:
            all_withdrawals = [w for w in all_withdrawals if w.get('withdrawal_date', '') <= date_to]
        teachers = db.execute_query("SELECT id, name, subject FROM teachers ORDER BY name")
    except Exception as e:
        all_withdrawals = []
        teachers = []
        print(f"Error loading withdrawals page: {e}")

    # حساب الإجمالي
    total_withdrawn = sum(w.get('amount', 0) for w in all_withdrawals)

    return templates.TemplateResponse("withdrawals/index.html", {
        "request": request,
        "withdrawals": all_withdrawals,
        "teachers": teachers,
        "total_withdrawn": total_withdrawn,
        "date_from": date_from,
        "date_to": date_to,
        "format_currency": format_currency
    })


# ===== الأقساط والمدفوعات =====

@router.get("/payments", response_class=HTMLResponse)
async def payments_page(request: Request, search: str = "", date_from: str = "", date_to: str = ""):
    """صفحة إدارة الأقساط والمدفوعات"""
    db = Database()

    try:
        conditions = []
        params = []

        if search:
            conditions.append("(s.name LIKE %s OR t.name LIKE %s OR t.subject LIKE %s)")
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

        if date_from:
            conditions.append("i.payment_date >= %s")
            params.append(date_from)

        if date_to:
            conditions.append("i.payment_date <= %s")
            params.append(date_to)

        where_clause = ''
        if conditions:
            where_clause = 'WHERE ' + ' AND '.join(conditions)

        query = f'''
            SELECT i.*, s.name as student_name, s.barcode, t.name as teacher_name, t.subject
            FROM installments i
            JOIN students s ON i.student_id = s.id
            JOIN teachers t ON i.teacher_id = t.id
            {where_clause}
            ORDER BY i.id DESC
        '''
        installments = db.execute_query(query, tuple(params))
    except:
        installments = []

    # حساب المتبقي لكل قسط (المتبقي = قسط المدرس - مجموع المدفوعات)
    for inst in installments:
        balance = finance_service.calculate_student_teacher_balance(inst['student_id'], inst['teacher_id'])
        inst['remaining'] = balance['remaining_balance']
        inst['total_fee'] = balance['total_fee']

    teachers = db.execute_query("SELECT id, name, subject, total_fee FROM teachers ORDER BY name")
    students = db.execute_query("SELECT id, name, barcode FROM students ORDER BY name")

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
        "date_from": date_from,
        "date_to": date_to,
        "total_amount": total_amount,
        "format_currency": format_currency
    })


# ===== الإحصائيات =====

@router.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    """صفحة الإحصائيات التفصيلية"""
    db = Database()
    stats = finance_service.get_system_statistics()

    stat_rows = []
    try:
        total_students = db.execute_query("SELECT COUNT(*) as cnt FROM students")
        total_students_count = total_students[0]['cnt'] if total_students else 0
        stat_rows.append({"label": "إجمالي الطلاب", "value": total_students_count, "icon": "fa-user-graduate", "color": "blue"})

        active_students = db.execute_query("SELECT COUNT(DISTINCT student_id) as cnt FROM student_teacher WHERE status = 'مستمر'")
        active_count = active_students[0]['cnt'] if active_students else 0
        stat_rows.append({"label": "الطلاب النشطين (مستمر)", "value": active_count, "icon": "fa-user-check", "color": "emerald"})

        withdrawn_students = db.execute_query("SELECT COUNT(DISTINCT student_id) as cnt FROM student_teacher WHERE status = 'منسحب'")
        withdrawn_count = withdrawn_students[0]['cnt'] if withdrawn_students else 0
        stat_rows.append({"label": "الطلاب المنسحبين", "value": withdrawn_count, "icon": "fa-user-minus", "color": "danger"})

        unlinked_students = db.execute_query("SELECT COUNT(*) as cnt FROM students s WHERE NOT EXISTS (SELECT 1 FROM student_teacher st WHERE st.student_id = s.id)")
        unlinked_count = unlinked_students[0]['cnt'] if unlinked_students else 0
        stat_rows.append({"label": "طلاب غير مربوطين", "value": unlinked_count, "icon": "fa-unlink", "color": "warning"})

        total_teachers = db.execute_query("SELECT COUNT(*) as cnt FROM teachers")
        total_teachers_count = total_teachers[0]['cnt'] if total_teachers else 0
        stat_rows.append({"label": "إجمالي المدرسين", "value": total_teachers_count, "icon": "fa-chalkboard-teacher", "color": "purple"})

        total_subjects = db.execute_query("SELECT COUNT(*) as cnt FROM subjects")
        total_subjects_count = total_subjects[0]['cnt'] if total_subjects else 0
        stat_rows.append({"label": "المواد الدراسية", "value": total_subjects_count, "icon": "fa-book-open", "color": "orange"})

        total_payments = db.execute_query("SELECT COUNT(*) as cnt FROM installments")
        total_payments_count = total_payments[0]['cnt'] if total_payments else 0
        stat_rows.append({"label": "عدد عمليات الدفع", "value": total_payments_count, "icon": "fa-money-check-alt", "color": "blue"})

        total_paid = db.execute_query("SELECT COALESCE(SUM(amount), 0) as total FROM installments")
        total_paid_amount = total_paid[0]['total'] if total_paid else 0
        stat_rows.append({"label": "إجمالي المدفوعات", "value": format_currency(total_paid_amount), "icon": "fa-coins", "color": "emerald"})

        total_withdrawn = db.execute_query("SELECT COALESCE(SUM(amount), 0) as total FROM teacher_withdrawals")
        total_withdrawn_amount = total_withdrawn[0]['total'] if total_withdrawn else 0
        stat_rows.append({"label": "إجمالي المسحوبات", "value": format_currency(total_withdrawn_amount), "icon": "fa-hand-holding-usd", "color": "orange"})

        net_revenue = stats.get('total_institute_deduction', 0)
        stat_rows.append({"label": "صافي الإيرادات", "value": format_currency(net_revenue), "icon": "fa-chart-line", "color": "purple"})
    except:
        pass

    return templates.TemplateResponse("stats/index.html", {
        "request": request,
        "stats": stats,
        "stat_rows": stat_rows,
        "format_currency": format_currency
    })
