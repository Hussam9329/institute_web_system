# ============================================
# routes/main_routes.py
# المسارات الرئيسية للصفحات HTML
# ============================================

import os
import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import Database
from services.finance_service import finance_service, sync_student_status
from services.cache_service import cache_service
from services.teaching_types import (
    parse_custom_type_settings, dump_custom_type_settings,
    get_fee_for_study_type, get_deduction_for_study_type,
    get_all_teaching_types, validate_custom_type_data,
    build_custom_type_settings_from_form
)
from config import get_current_date, format_currency, format_date, BASE_DIR, generate_barcode
from services.audit_service import log_action
from auth import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# إضافة دوال عامة للقوالب
templates.env.globals['format_date'] = format_date
templates.env.globals['format_currency'] = format_currency


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """الصفحة الرئيسية - Dashboard مع التخزين المؤقت ومعالجة الأخطاء"""
    
    # محاولة الحصول على الإحصائيات من التخزين المؤقت
    stats = cache_service.get('dashboard_stats')
    if stats is None:
        try:
            stats = finance_service.get_system_statistics()
            cache_service.set('dashboard_stats', stats, ttl=30)
        except Exception as e:
            logger.error(f"خطأ في تحميل إحصائيات لوحة التحكم: {e}")
            # بيانات افتراضية عند الفشل - عرض جزئي
            stats = {
                'total_students': 0, 'active_students': 0, 'withdrawn_students': 0,
                'unlinked_students': 0, 'total_teachers': 0, 'total_subjects': 0,
                'total_installments': 0, 'total_amount_paid': 0, 'total_withdrawals': 0,
                'total_institute_deduction': 0, '_error': True
            }

    # آخر الأقساط - مع معالجة الأخطاء والتحميل الجزئي
    recent_installments = cache_service.get('dashboard_recent_installments')
    if recent_installments is None:
        db = Database()
        try:
            recent_installments = db.execute_query('''
                SELECT i.*, s.name as student_name, t.name as teacher_name, t.subject
                FROM installments i
                JOIN students s ON i.student_id = s.id
                JOIN teachers t ON i.teacher_id = t.id
                ORDER BY i.id DESC LIMIT 5
            ''')
            cache_service.set('dashboard_recent_installments', recent_installments or [], ttl=30)
        except Exception as e:
            logger.error(f"خطأ في تحميل آخر الأقساط: {e}")
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
    check_permission(request, 'view_subjects')
    db = Database()
    try:
        # استعلام واحد يجلب المواد مع عدد المدرسين لكل مادة (بدلاً من N+1 استعلام)
        subjects = db.execute_query('''
            SELECT s.*, COALESCE(t.cnt, 0) as teachers_count
            FROM subjects s
            LEFT JOIN (SELECT subject, COUNT(*) as cnt FROM teachers GROUP BY subject) t ON s.name = t.subject
            ORDER BY s.name
        ''')
        subjects_with_count = [dict(s) for s in subjects] if subjects else []
    except:
        subjects_with_count = []

    return templates.TemplateResponse("subjects/list.html", {
        "request": request,
        "subjects": subjects_with_count
    })


@router.post("/subjects/add")
async def subject_add(request: Request, name: str = Form(...)):
    """إضافة مادة جديدة"""
    check_permission(request, 'add_subjects')
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
    check_permission(request, 'delete_subjects')
    db = Database()
    teachers_count = db.execute_query("SELECT COUNT(*) as cnt FROM teachers WHERE subject = (SELECT name FROM subjects WHERE id = %s)", (subject_id,))
    if teachers_count and teachers_count[0]['cnt'] > 0:
        cnt = teachers_count[0]['cnt']
        return RedirectResponse(url=f"/subjects?error=has_teachers&count={cnt}", status_code=303)
    db.execute_query("DELETE FROM subjects WHERE id = %s", (subject_id,))
    return RedirectResponse(url="/subjects?msg=deleted", status_code=303)


# ===== الطلاب =====

@router.get("/students", response_class=HTMLResponse)
async def students_list(request: Request, search: str = "", msg: str = "", error: str = "",
                        status_filter: str = "", payment_filter: str = "", teacher_filter: str = "",
                        study_type_filter: str = ""):
    """صفحة قائمة الطلاب مع فلاتر متقدمة"""
    check_permission(request, 'view_students_list')
    db = Database()

    try:
        # بناء الاستعلام مع الفلاتر
        where_clauses = []
        params = []

        if search:
            where_clauses.append("(s.name LIKE %s OR s.barcode LIKE %s)")
            params.extend([f'%{search}%', f'%{search}%'])

        # فلتر الحالة (مستمر/منسحب/مدمج/غير مربوط)
        if status_filter:
            if status_filter == 'مستمر':
                where_clauses.append("(SELECT COUNT(*) FROM student_teacher st3 WHERE st3.student_id = s.id) > 0 AND (SELECT SUM(CASE WHEN st3.status = 'منسحب' THEN 1 ELSE 0 END) FROM student_teacher st3 WHERE st3.student_id = s.id) = 0")
            elif status_filter == 'منسحب':
                where_clauses.append("(SELECT COUNT(*) FROM student_teacher st3 WHERE st3.student_id = s.id) > 0 AND (SELECT SUM(CASE WHEN st3.status = 'منسحب' THEN 1 ELSE 0 END) FROM student_teacher st3 WHERE st3.student_id = s.id) = (SELECT COUNT(*) FROM student_teacher st3 WHERE st3.student_id = s.id)")
            elif status_filter == 'مدمج':
                where_clauses.append("(SELECT SUM(CASE WHEN st3.status = 'منسحب' THEN 1 ELSE 0 END) FROM student_teacher st3 WHERE st3.student_id = s.id) > 0 AND (SELECT SUM(CASE WHEN st3.status = 'منسحب' THEN 1 ELSE 0 END) FROM student_teacher st3 WHERE st3.student_id = s.id) < (SELECT COUNT(*) FROM student_teacher st3 WHERE st3.student_id = s.id)")
            elif status_filter == 'غير مربوط':
                where_clauses.append("(SELECT COUNT(*) FROM student_teacher st3 WHERE st3.student_id = s.id) = 0")

        # فلتر المدرس
        if teacher_filter:
            try:
                tid = int(teacher_filter)
                where_clauses.append("s.id IN (SELECT st2.student_id FROM student_teacher st2 WHERE st2.teacher_id = %s)")
                params.append(tid)
            except ValueError:
                pass

        # فلتر نوع الدراسة
        if study_type_filter:
            where_clauses.append("s.id IN (SELECT st2.student_id FROM student_teacher st2 WHERE st2.study_type = %s)")
            params.append(study_type_filter)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        query = f'''
            SELECT s.*,
                (SELECT COUNT(*) FROM student_teacher st WHERE st.student_id = s.id) as teachers_count,
                (SELECT COUNT(*) FROM student_teacher st2 WHERE st2.student_id = s.id AND st2.status = 'مستمر') as active_links_count,
                (SELECT CASE WHEN COUNT(*) = 0 THEN 'غير مربوط' WHEN SUM(CASE WHEN st3.status = 'منسحب' THEN 1 ELSE 0 END) = COUNT(*) THEN 'منسحب' WHEN SUM(CASE WHEN st3.status = 'منسحب' THEN 1 ELSE 0 END) > 0 THEN 'مدمج' ELSE 'مستمر' END FROM student_teacher st3 WHERE st3.student_id = s.id) as status
            FROM students s
            {where_sql}
            ORDER BY s.name
        '''
        students = db.execute_query(query, tuple(params) if params else None)
    except Exception as e:
        students = []
        print(f"Error loading students: {e}")

    # حساب المتبقي لكل طالب - استعلام مجمّع بدلاً من N+1
    if students:
        try:
            student_ids = [s['id'] for s in students]
            balances_map = finance_service.get_students_balances_batch(student_ids)
            for s in students:
                bal = balances_map.get(s['id'], {'total_fees': 0, 'total_paid': 0, 'total_remaining': 0})
                s['total_fees'] = bal['total_fees']
                s['total_paid'] = bal['total_paid']
                s['total_remaining'] = bal['total_remaining']
        except Exception:
            for s in students:
                s['total_fees'] = 0
                s['total_paid'] = 0
                s['total_remaining'] = 0

    # فلتر حالة الدفع (بعد حساب المبالغ)
    if payment_filter:
        if payment_filter == 'paid':
            students = [s for s in students if (s.get('total_remaining') or 0) <= 0 and (s.get('total_fees') or 0) > 0]
        elif payment_filter == 'unpaid':
            students = [s for s in students if (s.get('total_remaining') or 0) > 0]
        elif payment_filter == 'partial':
            students = [s for s in students if (s.get('total_paid') or 0) > 0 and (s.get('total_remaining') or 0) > 0]
        elif payment_filter == 'no_payment':
            students = [s for s in students if (s.get('total_paid') or 0) == 0 and (s.get('total_fees') or 0) > 0]
        elif payment_filter == 'free':
            students = [s for s in students if (s.get('total_fees') or 0) == 0 and (s.get('teachers_count') or 0) > 0]

    # إحصائيات سريعة (محسوبة في Python بدل Jinja2 لتجنب أخطاء القوالب)
    stats_counts = {
        'paid': sum(1 for s in students if (s.get('total_remaining') or 0) <= 0 and (s.get('total_fees') or 0) > 0),
        'unpaid': sum(1 for s in students if (s.get('total_remaining') or 0) > 0),
        'no_payment': sum(1 for s in students if (s.get('total_paid') or 0) == 0 and (s.get('total_fees') or 0) > 0),
    }

    # جلب قائمة المدرسين للفلتر
    try:
        teachers_list = db.execute_query("SELECT id, name, subject FROM teachers ORDER BY name")
    except Exception:
        teachers_list = []

    return templates.TemplateResponse("students/list.html", {
        "request": request,
        "students": students,
        "search": search,
        "msg": msg,
        "error": error,
        "status_filter": status_filter,
        "payment_filter": payment_filter,
        "teacher_filter": teacher_filter,
        "study_type_filter": study_type_filter,
        "teachers_list": [dict(t) for t in teachers_list] if teachers_list else [],
        "stats_counts": stats_counts,
        "format_currency": format_currency
    })


@router.get("/students/add", response_class=HTMLResponse)
async def student_form(request: Request, error: str = "", detail: str = ""):
    """نموذج إضافة طالب جديد"""
    check_permission(request, 'add_students')
    db = Database()
    teachers = db.execute_query("SELECT id, name, subject, teaching_types, custom_type_settings FROM teachers ORDER BY name")
    # جلب قائمة المواد الدراسية للفرز
    subjects_from_table = db.execute_query("SELECT name FROM subjects ORDER BY name")
    subjects_from_teachers = db.execute_query("SELECT DISTINCT subject as name FROM teachers ORDER BY subject")
    all_subjects = set()
    if subjects_from_table:
        all_subjects.update(s['name'] for s in subjects_from_table)
    if subjects_from_teachers:
        all_subjects.update(s['name'] for s in subjects_from_teachers)
    subjects_list = sorted(all_subjects)
    return templates.TemplateResponse("students/form.html", {
        "request": request,
        "student": None,
        "mode": "add",
        "teachers": teachers,
        "subjects": subjects_list,
        "error": error,
        "error_detail": detail
    })


@router.post("/students/add")
async def student_add(
    request: Request,
    name: str = Form(...),
    notes: str = Form("")
):
    """حفظ طالب جديد"""
    check_permission(request, 'add_students')
    db = Database()

    form_data = await request.form()
    force_duplicate = form_data.get("force_duplicate") == "1"

    # فحص الاسم المشابه
    normalized_name = " ".join(name.strip().split())
    similar_students = db.execute_query("""
        SELECT 
            s.id,
            s.name,
            COALESCE(
                STRING_AGG(t.name || ' - ' || t.subject, '، '),
                'غير مربوط بأي مدرس'
            ) AS teachers_info
        FROM students s
        LEFT JOIN student_teacher st ON st.student_id = s.id
        LEFT JOIN teachers t ON t.id = st.teacher_id
        WHERE LOWER(TRIM(s.name)) = LOWER(TRIM(%s))
           OR LOWER(TRIM(s.name)) LIKE LOWER(TRIM(%s))
           OR LOWER(TRIM(%s)) LIKE LOWER(TRIM(s.name))
        GROUP BY s.id, s.name
        LIMIT 5
    """, (
        normalized_name,
        f"%{normalized_name}%",
        normalized_name
    ))

    if similar_students and not force_duplicate:
        details = []
        for s in similar_students:
            details.append(f"{s['name']} عند: {s['teachers_info']}")

        warning_text = " | ".join(details)

        return RedirectResponse(
            url=f"/students/add?error=similar_name&detail={warning_text}",
            status_code=303
        )

    # توليد باركود حقيقي مباشرة باستخدام RETURNING
    import time
    import random

    current_user_id = getattr(request.state, "user", {}).get("id")

    insert_query = '''
        INSERT INTO students (name, barcode, notes, created_at, created_by)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    '''

    temp_barcode = f"TEMP-{int(time.time()*1000)}-{random.randint(1000,9999)}"
    result = db.execute_query(insert_query, (name, temp_barcode, notes, get_current_date(), current_user_id))
    student_id = result[0]['id'] if result else None

    if student_id:
        real_barcode = generate_barcode(student_id)
        db.execute_query("UPDATE students SET barcode = %s WHERE id = %s", (real_barcode, student_id))
        log_action(request, action="create", entity="student", entity_id=student_id, description=f"إضافة الطالب: {name}")

    # ربط الطالب بالمدرسين المحددين
    form_data = await request.form()
    teacher_ids = form_data.getlist("teacher_ids")

    if teacher_ids:
        # ===== فحص تكرار المادة: لا يسمح بربط الطالب بأكثر من مدرس لنفس المادة =====
        # (إلا إذا كانت حالة الطالب مع المدرس الأول "منسحب")
        selected_teachers = []
        for tid in teacher_ids:
            if tid:
                teacher_info = db.execute_query("SELECT id, name, subject FROM teachers WHERE id = %s", (int(tid),))
                if teacher_info:
                    selected_teachers.append(dict(teacher_info[0]))

        # فحص تكرار المادة بين المدرسين المختارين
        subject_teachers = {}  # {المادة: [قائمة المدرسين]}
        for t in selected_teachers:
            subj = t['subject']
            if subj not in subject_teachers:
                subject_teachers[subj] = []
            subject_teachers[subj].append(t)

        duplicate_subjects = []
        for subj, teachers_list in subject_teachers.items():
            if len(teachers_list) > 1:
                teacher_names = ' و '.join([t['name'] for t in teachers_list])
                duplicate_subjects.append(f"{subj} ({teacher_names})")

        if duplicate_subjects:
            # حذف الطالب الذي تم إنشاؤه لأن الربط غير صالح
            db.execute_query("DELETE FROM students WHERE id = %s", (student_id,))
            dup_str = ' - '.join(duplicate_subjects)
            return RedirectResponse(
                url=f"/students/add?error=duplicate_subject&detail={dup_str}",
                status_code=303
            )

        for t in selected_teachers:
            tid = t['id']
            study_type = form_data.get(f"study_type_{tid}", "حضوري")
            status = form_data.get(f"status_{tid}", "مستمر")
            discount_type = form_data.get(f"discount_type_{tid}", "none")
            discount_value = int(form_data.get(f"discount_value_{tid}", 0) or 0)
            institute_waiver = int(form_data.get(f"institute_waiver_{tid}", 0) or 0)
            discount_notes = form_data.get(f"discount_notes_{tid}", "")
            try:
                db.execute_query(
                    "INSERT INTO student_teacher (student_id, teacher_id, study_type, status, discount_type, discount_value, institute_waiver, discount_notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (student_id, tid, study_type, status, discount_type, discount_value, institute_waiver, discount_notes)
                )
            except:
                pass

        sync_student_status(student_id)

    return RedirectResponse(url="/students?msg=added", status_code=303)


@router.get("/students/{student_id}/edit", response_class=HTMLResponse)
async def student_edit_form(request: Request, student_id: int, error: str = "", detail: str = ""):
    """نموذج تعديل طالب"""
    check_permission(request, 'edit_students')
    db = Database()

    query = "SELECT * FROM students WHERE id = %s"
    result = db.execute_query(query, (student_id,))

    if not result:
        return RedirectResponse(url="/students?error=not_found", status_code=303)

    student = dict(result[0])
    teachers = db.execute_query("SELECT id, name, subject, teaching_types, custom_type_settings FROM teachers ORDER BY name")

    # المدرسين المرتبطين بالطالب مع بيانات الربط
    linked = db.execute_query(
        "SELECT teacher_id, study_type, status, discount_type, discount_value, institute_waiver, discount_notes FROM student_teacher WHERE student_id = %s",
        (student_id,)
    )
    linked_ids = [r['teacher_id'] for r in linked] if linked else []
    linked_data = {r['teacher_id']: r for r in linked} if linked else {}

    # عدد الأقساط المدفوعة لكل مدرس مرتبط (لمنع تغيير نوع الدراسة إذا وُجدت مدفوعات)
    installment_counts = {}
    # المدرسين الذين أكمل الطالب جميع أقساطهم (لمنع تطبيق/تعديل الخصم)
    completed_teachers = set()
    if linked_ids:
        counts = db.execute_query(
            "SELECT teacher_id, COUNT(*) as cnt FROM installments WHERE student_id = %s GROUP BY teacher_id",
            (student_id,)
        )
        if counts:
            for c in counts:
                installment_counts[c['teacher_id']] = c['cnt']
        
        # فحص اكتمال الأقساط لكل مدرس مرتبط
        for tid in linked_ids:
            balance = finance_service.calculate_student_teacher_balance(student_id, tid)
            if balance['remaining_balance'] <= 0 and balance['paid_total'] > 0:
                completed_teachers.add(tid)

    # جلب قائمة المواد الدراسية للفرز
    subjects_from_table = db.execute_query("SELECT name FROM subjects ORDER BY name")
    subjects_from_teachers = db.execute_query("SELECT DISTINCT subject as name FROM teachers ORDER BY subject")
    all_subjects = set()
    if subjects_from_table:
        all_subjects.update(s['name'] for s in subjects_from_table)
    if subjects_from_teachers:
        all_subjects.update(s['name'] for s in subjects_from_teachers)
    subjects_list = sorted(all_subjects)

    return templates.TemplateResponse("students/form.html", {
        "request": request,
        "student": student,
        "mode": "edit",
        "teachers": teachers,
        "subjects": subjects_list,
        "linked_teacher_ids": linked_ids,
        "linked_data": linked_data,
        "installment_counts": installment_counts,
        "completed_teachers": completed_teachers,
        "error": error,
        "error_detail": detail
    })


@router.post("/students/{student_id}/edit")
async def student_update(
    request: Request,
    student_id: int,
    name: str = Form(...),
    notes: str = Form("")
):
    """تحديث بيانات طالب"""
    check_permission(request, 'edit_students')
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
        new_study_type = form_data.get(f"study_type_{tid}", "حضوري")
        status = form_data.get(f"status_{tid}", "مستمر")
        new_discount_type = form_data.get(f"discount_type_{tid}", "none")
        new_discount_value = int(form_data.get(f"discount_value_{tid}", 0) or 0)
        new_institute_waiver = int(form_data.get(f"institute_waiver_{tid}", 0) or 0)
        new_discount_notes = form_data.get(f"discount_notes_{tid}", "")
        
        # جلب البيانات الحالية للربط
        current_link = db.execute_query(
            "SELECT study_type, discount_type, discount_value, institute_waiver FROM student_teacher WHERE student_id = %s AND teacher_id = %s",
            (student_id, tid)
        )
        current_data = dict(current_link[0]) if current_link else {}
        current_discount_type = current_data.get('discount_type', 'none') or 'none'
        current_discount_value = current_data.get('discount_value', 0) or 0
        current_study_type = current_data.get('study_type', 'حضوري')
        current_institute_waiver = current_data.get('institute_waiver', 0) or 0
        
        # حساب الرصيد الحالي
        balance = finance_service.calculate_student_teacher_balance(student_id, tid)
        
        # ===== فحص اكتمال الأقساط: لا يسمح بتعديل الخصم بعد اكتمال الأقساط =====
        if balance['remaining_balance'] <= 0 and balance['paid_total'] > 0:
            # الحفاظ على الخصم الحالي - لا تحديث للخصم
            new_discount_type = current_discount_type
            new_discount_value = current_discount_value
            new_institute_waiver = current_institute_waiver
        
        # ===== فحص: لا يمكن تطبيق خصم يجعل المدفوع يتجاوز القسط الجديد =====
        if balance['paid_total'] > 0 and (new_discount_type != current_discount_type or new_discount_value != current_discount_value or new_institute_waiver != current_institute_waiver):
            # تم تغيير الخصم - نحتاج فحص إضافي
            original_fee = balance.get('original_fee', balance['total_fee'])
            
            # حساب القسط الجديد بعد الخصم المطلوب
            if new_discount_type == 'free':
                new_fee = 0
            elif new_discount_type in ('percentage', 'custom'):
                new_fee = original_fee - round(original_fee * new_discount_value / 100)
            elif new_discount_type == 'fixed':
                new_fee = original_fee - new_discount_value
            else:
                new_fee = original_fee
            
            if balance['paid_total'] > new_fee:
                # الخصم الجديد يجعل المدفوع يتجاوز القسط - نحافظ على الخصم الحالي
                new_discount_type = current_discount_type
                new_discount_value = current_discount_value
                new_institute_waiver = current_institute_waiver
        
        # ===== فحص: لا يمكن تغيير نوع الدراسة إذا وُجدت أقساط مدفوعة =====
        payment_check = db.execute_query(
            "SELECT COUNT(*) as cnt FROM installments WHERE student_id = %s AND teacher_id = %s",
            (student_id, tid)
        )
        has_payments = payment_check and payment_check[0]['cnt'] > 0
        if has_payments:
            # الحفاظ على نوع الدراسة الحالي
            new_study_type = current_study_type
        
        try:
            db.execute_query(
                "UPDATE student_teacher SET study_type=%s, status=%s, discount_type=%s, discount_value=%s, institute_waiver=%s, discount_notes=%s WHERE student_id=%s AND teacher_id=%s",
                (new_study_type, status, new_discount_type, new_discount_value, new_institute_waiver, new_discount_notes, student_id, tid)
            )
        except:
            pass

    # إضافة روابط جديدة فقط
    # ===== فحص تكرار المادة: لا يسمح بربط الطالب بأكثر من مدرس لنفس المادة =====
    # (إلا إذا كانت حالة الطالب مع المدرس الأول "منسحب")
    added_teacher_ids = new_teacher_ids - old_teacher_ids
    if added_teacher_ids:
        for tid in added_teacher_ids:
            teacher_info = db.execute_query("SELECT id, name, subject FROM teachers WHERE id = %s", (tid,))
            if not teacher_info:
                continue
            teacher_subject = teacher_info[0]['subject']
            # فحص هل الطالب مربوط بمدرس آخر لنفس المادة وحالته ليست "منسحب"
            same_subject_links = db.execute_query('''
                SELECT st.teacher_id, t.name as teacher_name, st.status
                FROM student_teacher st
                JOIN teachers t ON st.teacher_id = t.id
                WHERE st.student_id = %s AND t.subject = %s
            ''', (student_id, teacher_subject))
            if same_subject_links:
                for link_row in same_subject_links:
                    if link_row['teacher_id'] != tid:
                        link_status = link_row.get('status', 'مستمر')
                        if link_status != 'منسحب':
                            return RedirectResponse(
                                url=f"/students/{student_id}/edit?error=duplicate_subject&detail={teacher_subject} ({link_row['teacher_name']})",
                                status_code=303
                            )
            study_type = form_data.get(f"study_type_{tid}", "حضوري")
            status = form_data.get(f"status_{tid}", "مستمر")
            discount_type = form_data.get(f"discount_type_{tid}", "none")
            discount_value = int(form_data.get(f"discount_value_{tid}", 0) or 0)
            institute_waiver = int(form_data.get(f"institute_waiver_{tid}", 0) or 0)
            discount_notes = form_data.get(f"discount_notes_{tid}", "")
            try:
                db.execute_query(
                    "INSERT INTO student_teacher (student_id, teacher_id, study_type, status, discount_type, discount_value, institute_waiver, discount_notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (student_id, tid, study_type, status, discount_type, discount_value, institute_waiver, discount_notes)
                )
            except:
                pass

    # تغيير حالة الروابط التي أزيلت - فقط إذا لم توجد أقساط بين الطالب والمدرس
    for tid in old_teacher_ids - new_teacher_ids:
        # فحص وجود أقساط - لا يمكن إلغاء الربط إذا وُجدت أقساط
        installment_check = db.execute_query(
            "SELECT COUNT(*) as cnt FROM installments WHERE student_id = %s AND teacher_id = %s",
            (student_id, tid)
        )
        has_installments = installment_check and installment_check[0]['cnt'] > 0
        if has_installments:
            # لا يمكن إلغاء الربط - الحفاظ على الربط النشط
            # إعادة إضافة المدرس للقائمة الجديدة لمنع إزالته
            continue
        # لا توجد أقساط - حذف الربط نهائياً
        db.execute_query("DELETE FROM student_teacher WHERE student_id = %s AND teacher_id = %s", (student_id, tid))

    sync_student_status(student_id)

    return RedirectResponse(url="/students?msg=updated", status_code=303)


@router.get("/students/{student_id}", response_class=HTMLResponse)
async def student_profile(request: Request, student_id: int):
    """بروفايل الطالب"""
    check_permission(request, 'preview_students')
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
    """حذف طالب - يمكن حذف أي طالب غير مرتبط بمدرسين (لا يوجد روابط نشطة)"""
    check_permission(request, 'delete_students')
    db = Database()
    
    # فحص إذا كان الطالب مرتبط بمدرسين بحالة مستمر
    active_links = db.execute_query(
        "SELECT COUNT(*) as cnt FROM student_teacher WHERE student_id = %s AND status = 'مستمر'", 
        (student_id,)
    )
    if active_links and active_links[0]['cnt'] > 0:
        cnt = active_links[0]['cnt']
        student = db.execute_query("SELECT name FROM students WHERE id = %s", (student_id,))
        student_name = student[0]['name'] if student else ''
        return RedirectResponse(
            url=f"/students?error=has_teachers&count={cnt}&name={student_name}", 
            status_code=303
        )
    
    # لا توجد روابط نشطة - يمكن الحذف
    # حذف الأقساط المرتبطة بالروابط المنسحبة أولاً
    db.execute_query("DELETE FROM installments WHERE student_id = %s", (student_id,))
    # حذف جميع الروابط (منسحبة وغيرها)
    db.execute_query("DELETE FROM student_teacher WHERE student_id = %s", (student_id,))
    # حذف الطالب
    db.execute_query("DELETE FROM students WHERE id = %s", (student_id,))

    log_action(request, action="delete", entity="student", entity_id=student_id, description="حذف طالب")
    
    cache_service.invalidate_pattern('dashboard_')
    return RedirectResponse(url="/students?msg=deleted", status_code=303)


# ===== المدرسين =====

def _build_institute_rate_display(teacher: dict) -> str:
    """عرض نسبة/مبلغ خصم المعهد - يدعم العرض حسب أنواع التدريس المختلفة بما فيها الأنواع المخصصة"""
    # محاولة عرض معلومات الخصم حسب نوع التدريس
    teaching_types = (teacher.get('teaching_types') or 'حضوري').split(',')
    teaching_types = [t.strip() for t in teaching_types if t.strip()]
    
    type_map = {
        'حضوري': ('institute_pct_in_person', 'inst_ded_type_in_person', 'inst_ded_manual_in_person'),
        'الكتروني': ('institute_pct_electronic', 'inst_ded_type_electronic', 'inst_ded_manual_electronic'),
        'مدمج': ('institute_pct_blended', 'inst_ded_type_blended', 'inst_ded_manual_blended'),
    }
    
    # تحليل الأنواع المخصصة
    custom_settings = parse_custom_type_settings(teacher.get('custom_type_settings'))
    
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
        elif tt in custom_settings:
            # نوع مخصص
            type_data = custom_settings[tt]
            ded_type = type_data.get('deduction_type', 'percentage')
            if ded_type == 'manual':
                manual_val = type_data.get('deduction_manual', 0) or 0
                if manual_val > 0:
                    displays.append(f"{tt}: {format_currency(manual_val)}")
            else:
                pct_val = type_data.get('deduction_pct', 0) or 0
                if pct_val > 0:
                    displays.append(f"{tt}: {pct_val}%")
    
    # إضافة أي أنواع مخصصة ليست في teaching_types
    for ct in custom_settings:
        if ct not in teaching_types:
            type_data = custom_settings[ct]
            ded_type = type_data.get('deduction_type', 'percentage')
            if ded_type == 'manual':
                manual_val = type_data.get('deduction_manual', 0) or 0
                if manual_val > 0:
                    displays.append(f"{ct}: {format_currency(manual_val)}")
            else:
                pct_val = type_data.get('deduction_pct', 0) or 0
                if pct_val > 0:
                    displays.append(f"{ct}: {pct_val}%")
    
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


def _build_teacher_fee_display(teacher: dict) -> str:
    """عرض قسط الأستاذ حسب أنواع التدريس - يدعم الأنواع الأساسية والمخصصة"""
    teaching_types = (teacher.get('teaching_types') or 'حضوري').split(',')
    teaching_types = [t.strip() for t in teaching_types if t.strip()]
    
    type_fee_map = {
        'حضوري': 'fee_in_person',
        'الكتروني': 'fee_electronic',
        'مدمج': 'fee_blended',
    }
    
    # تحليل الأنواع المخصصة
    custom_settings = parse_custom_type_settings(teacher.get('custom_type_settings'))
    
    displays = []
    for tt in teaching_types:
        if tt in type_fee_map:
            fee_val = teacher.get(type_fee_map[tt], 0) or 0
            if fee_val > 0:
                displays.append(f"{tt}: {format_currency(fee_val)}")
        elif tt in custom_settings:
            # نوع مخصص
            fee_val = custom_settings[tt].get('fee', 0) or 0
            if fee_val > 0:
                displays.append(f"{tt}: {format_currency(fee_val)}")
    
    # إضافة أي أنواع مخصصة ليست في teaching_types
    for ct in custom_settings:
        if ct not in teaching_types:
            fee_val = custom_settings[ct].get('fee', 0) or 0
            if fee_val > 0:
                displays.append(f"{ct}: {format_currency(fee_val)}")
    
    if len(displays) > 1:
        return ' | '.join(displays)
    elif len(displays) == 1:
        return displays[0]
    
    # fallback
    fallback_fee = teacher.get('total_fee', 0) or 0
    if fallback_fee > 0:
        return format_currency(fallback_fee)
    return '-'


@router.get("/teachers", response_class=HTMLResponse)
async def teachers_list(request: Request, subject: str = "", search: str = ""):
    """صفحة قائمة المدرسين - محسّنة باستعلامات مجمعة"""
    check_permission(request, 'view_teachers_list')
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

        if not teachers:
            teachers = []
        else:
            # ===== تحسين الأداء: استعلامات مجمعة بدلاً من N+1 =====
            teacher_ids = [t['id'] for t in teachers]
            
            # عدد الطلاب لكل مدرس - استعلام واحد
            try:
                students_count_map = {}
                if teacher_ids:
                    placeholders = ','.join(['%s'] * len(teacher_ids))
                    cnt_results = db.execute_query(
                        f"SELECT teacher_id, COUNT(*) as cnt FROM student_teacher WHERE teacher_id IN ({placeholders}) GROUP BY teacher_id",
                        tuple(teacher_ids)
                    )
                    if cnt_results:
                        students_count_map = {r['teacher_id']: r['cnt'] for r in cnt_results}
                for t in teachers:
                    t['students_count'] = students_count_map.get(t['id'], 0)
            except Exception as e:
                logging.error(f"خطأ في حساب عدد الطلاب: {e}")
                for t in teachers:
                    t['students_count'] = 0

            # البيانات المالية - استعلامات مجمعة
            try:
                # إجمالي المدفوعات لكل مدرس
                received_map = {}
                if teacher_ids:
                    placeholders = ','.join(['%s'] * len(teacher_ids))
                    recv_results = db.execute_query(
                        f"SELECT teacher_id, COALESCE(SUM(amount), 0) as total FROM installments WHERE teacher_id IN ({placeholders}) GROUP BY teacher_id",
                        tuple(teacher_ids)
                    )
                    if recv_results:
                        received_map = {r['teacher_id']: r['total'] for r in recv_results}

                # إجمالي السحوبات لكل مدرس
                withdrawn_map = {}
                if teacher_ids:
                    placeholders = ','.join(['%s'] * len(teacher_ids))
                    with_results = db.execute_query(
                        f"SELECT teacher_id, COALESCE(SUM(amount), 0) as total FROM teacher_withdrawals WHERE teacher_id IN ({placeholders}) GROUP BY teacher_id",
                        tuple(teacher_ids)
                    )
                    if with_results:
                        withdrawn_map = {r['teacher_id']: r['total'] for r in with_results}

                # عدد الطلاب الدافعين لكل مدرس
                paying_map = {}
                if teacher_ids:
                    placeholders = ','.join(['%s'] * len(teacher_ids))
                    paying_results = db.execute_query(
                        f"SELECT teacher_id, COUNT(DISTINCT student_id) as cnt FROM installments WHERE teacher_id IN ({placeholders}) AND amount > 0 GROUP BY teacher_id",
                        tuple(teacher_ids)
                    )
                    if paying_results:
                        paying_map = {r['teacher_id']: r['cnt'] for r in paying_results}

                # حساب خصم المعهد لكل المدرسين دفعة واحدة
                deduction_map = finance_service.calculate_institute_deduction_batch(teacher_ids)
                
                # حساب المطلوب الكلي لكل المدرسين دفعة واحدة
                total_fees_map = finance_service.get_teachers_total_fees_batch(teacher_ids)
                
                # حساب مستحق المدرس المتوقع دفعة واحدة
                # المعادلة: (عدد الحضوريين × قسط الحضوري) + (عدد الالكترونيين × قسط الالكتروني) + (عدد المدمجين × قسط المدمج) - خصم المعهد
                expected_due_map = finance_service.calculate_expected_teacher_due_batch(teacher_ids)
                
                for t in teachers:
                    total_received = received_map.get(t['id'], 0)
                    withdrawn_total = withdrawn_map.get(t['id'], 0)
                    institute_deduction = deduction_map.get(t['id'], 0)
                    
                    # مستحق المدرس = إجمالي الأقساط المتوقعة - خصم المعهد المتوقع
                    expected_info = expected_due_map.get(t['id'], {})
                    teacher_due = expected_info.get('teacher_due', 0)
                    expected_deduction = expected_info.get('expected_deduction', 0)
                    total_fees = expected_info.get('total_fees', 0)
                    
                    remaining_balance = max(0, teacher_due - withdrawn_total)
                    
                    t['total_received'] = total_received
                    t['institute_deduction'] = institute_deduction
                    t['expected_deduction'] = expected_deduction
                    t['teacher_due'] = teacher_due
                    t['withdrawn_total'] = withdrawn_total
                    t['remaining_balance'] = remaining_balance
                    t['total_remaining'] = remaining_balance
                    t['total_fees'] = total_fees
                    t['in_person_count'] = expected_info.get('in_person_count', 0)
                    t['electronic_count'] = expected_info.get('electronic_count', 0)
                    t['blended_count'] = expected_info.get('blended_count', 0)
                    
                    # حساب عرض نسبة المعهد
                    t['institute_rate_display'] = _build_institute_rate_display(t)
                    # حساب عرض قسط الأستاذ
                    t['fee_display'] = _build_teacher_fee_display(t)
            except Exception as e:
                import traceback
                logging.error(f"❌ خطأ في حساب البيانات المالية للمدرسين: {e}")
                logging.error(traceback.format_exc())
                # محاولة حساب فردي لكل مدرس باستخدام المعادلة المتوقعة بدلاً من تعيين 0
                for t in teachers:
                    try:
                        tid = t['id']
                        # استخدام الحساب المتوقع (المعادلة: عدد الطلاب × الأقساط - خصم المعهد)
                        expected_info = finance_service._calculate_expected_teacher_due_single(tid)
                        
                        # إجمالي المدفوعات والسحوبات
                        recv_result = db.execute_query(
                            "SELECT COALESCE(SUM(amount), 0) as total FROM installments WHERE teacher_id = %s",
                            (tid,)
                        )
                        total_received = recv_result[0]['total'] if recv_result else 0
                        
                        with_result = db.execute_query(
                            "SELECT COALESCE(SUM(amount), 0) as total FROM teacher_withdrawals WHERE teacher_id = %s",
                            (tid,)
                        )
                        withdrawn_total = with_result[0]['total'] if with_result else 0
                        
                        ded_result = db.execute_query(
                            "SELECT COALESCE(SUM(amount), 0) as total FROM installments i "
                            "LEFT JOIN student_teacher st ON st.student_id = i.student_id AND st.teacher_id = i.teacher_id "
                            "WHERE i.teacher_id = %s",
                            (tid,)
                        )
                        
                        t['total_received'] = total_received or 0
                        t['teacher_due'] = expected_info.get('teacher_due', 0)
                        t['total_fees'] = expected_info.get('total_fees', 0)
                        t['expected_deduction'] = expected_info.get('expected_deduction', 0)
                        t['institute_deduction'] = expected_info.get('expected_deduction', 0)
                        t['withdrawn_total'] = withdrawn_total or 0
                        t['remaining_balance'] = max(0, expected_info.get('teacher_due', 0) - (withdrawn_total or 0))
                        t['total_remaining'] = t['remaining_balance']
                        t['in_person_count'] = expected_info.get('in_person_count', 0)
                        t['electronic_count'] = expected_info.get('electronic_count', 0)
                        t['blended_count'] = expected_info.get('blended_count', 0)
                        t['institute_rate_display'] = _build_institute_rate_display(t)
                        t['fee_display'] = _build_teacher_fee_display(t)
                    except Exception as inner_e:
                        logging.error(f"❌ خطأ في حساب المدرس {t.get('id')}: {inner_e}")
                        t['total_received'] = 0
                        t['total_remaining'] = 0
                        t['institute_deduction'] = 0
                        t['expected_deduction'] = 0
                        t['teacher_due'] = 0
                        t['withdrawn_total'] = 0
                        t['remaining_balance'] = 0
                        t['total_fees'] = 0
                        t['in_person_count'] = 0
                        t['electronic_count'] = 0
                        t['blended_count'] = 0
                        t['institute_rate_display'] = ''
                        t['fee_display'] = ''
    except Exception as e:
        logging.error(f"خطأ في جلب قائمة المدرسين: {e}")
        teachers = []

    # الحصول على المواد - استعلام واحد
    try:
        subjects_from_table = db.execute_query("SELECT name FROM subjects ORDER BY name")
        subjects_from_teachers = db.execute_query("SELECT DISTINCT subject as name FROM teachers ORDER BY subject")

        all_subjects = set()
        if subjects_from_table:
            all_subjects.update(s['name'] for s in subjects_from_table)
        if subjects_from_teachers:
            all_subjects.update(s['name'] for s in subjects_from_teachers)

        subjects_list = sorted(all_subjects)
    except:
        subjects_list = []

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
    check_permission(request, 'add_teachers')
    db = Database()
    subjects = db.execute_query("SELECT name FROM subjects ORDER BY name")
    return templates.TemplateResponse("teachers/form.html", {
        "request": request,
        "teacher": None,
        "mode": "add",
        "subjects": subjects,
        "error": error,
        "has_payments": False,
        "has_linked_students": False,
        "teacher_custom_type_settings": {}
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
    check_permission(request, 'add_teachers')
    
    # التحقق من أن النسب المئوية بين 1 و 99
    for pct_val, pct_label in [
        (institute_pct_in_person, 'حضوري'),
        (institute_pct_electronic, 'الكتروني'),
        (institute_pct_blended, 'مدمج')
    ]:
        if pct_val != 0 and (pct_val < 1 or pct_val > 99):
            return RedirectResponse(url=f"/teachers/add?error=invalid_pct&label={pct_label}&val={pct_val}", status_code=303)

    # التحقق من أن المبلغ اليدوي للخصم لا يتجاوز القسط الكلي
    for manual_val, fee_val, ded_type, type_label in [
        (inst_ded_manual_in_person, fee_in_person, inst_ded_type_in_person, 'حضوري'),
        (inst_ded_manual_electronic, fee_electronic, inst_ded_type_electronic, 'الكتروني'),
        (inst_ded_manual_blended, fee_blended, inst_ded_type_blended, 'مدمج')
    ]:
        if ded_type == 'manual' and manual_val > 0 and fee_val > 0 and manual_val > fee_val:
            return RedirectResponse(url=f"/teachers/add?error=invalid_manual_ded&label={type_label}&val={manual_val}&fee={fee_val}", status_code=303)

    if not teaching_types or teaching_types.strip() == '':
        return RedirectResponse(url="/teachers/add?error=no_teaching_type", status_code=303)

    db = Database()

    # معالجة الأنواع التدريسية المخصصة
    form_data = await request.form()
    custom_settings, custom_errors = build_custom_type_settings_from_form(form_data)
    
    if custom_errors:
        import urllib.parse
        error_msg = urllib.parse.quote(' | '.join(custom_errors))
        return RedirectResponse(url=f"/teachers/add?error=custom_type&detail={error_msg}", status_code=303)
    
    # التحقق من نسب الخصم للأنواع المخصصة (1-99)
    for ct_name, ct_data in custom_settings.items():
        ded_type = ct_data.get('deduction_type', 'percentage')
        if ded_type == 'percentage':
            pct_val = ct_data.get('deduction_pct', 0)
            if pct_val != 0 and (pct_val < 1 or pct_val > 99):
                return RedirectResponse(url=f"/teachers/add?error=invalid_pct&label={ct_name}&val={pct_val}", status_code=303)
        elif ded_type == 'manual':
            manual_val = ct_data.get('deduction_manual', 0)
            fee_val = ct_data.get('fee', 0)
            if manual_val > 0 and fee_val > 0 and manual_val > fee_val:
                return RedirectResponse(url=f"/teachers/add?error=invalid_manual_ded&label={ct_name}&val={manual_val}&fee={fee_val}", status_code=303)
    
    # إضافة أسماء الأنواع المخصصة إلى teaching_types
    if custom_settings:
        base_types = [t.strip() for t in teaching_types.split(',') if t.strip()]
        custom_type_names = list(custom_settings.keys())
        merged_types = base_types + [ct for ct in custom_type_names if ct not in base_types]
        teaching_types = ','.join(merged_types)
    
    custom_type_json = dump_custom_type_settings(custom_settings)

    try:
        existing_subject = db.execute_query("SELECT id FROM subjects WHERE name = %s", (subject,))
        if not existing_subject:
            try:
                db.execute_query("INSERT INTO subjects (name, created_at) VALUES (%s, %s)", (subject, get_current_date()))
            except Exception as sub_e:
                print(f"تحذير: فشل إضافة المادة: {sub_e}")

        insert_query = '''
            INSERT INTO teachers (name, subject, total_fee, institute_deduction_type, institute_deduction_value, notes, created_at,
                teaching_types, fee_in_person, fee_electronic, fee_blended,
                institute_pct_in_person, institute_pct_electronic, institute_pct_blended,
                inst_ded_type_in_person, inst_ded_type_electronic, inst_ded_type_blended,
                inst_ded_manual_in_person, inst_ded_manual_electronic, inst_ded_manual_blended,
                custom_type_settings)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''

        db.execute_query(insert_query, (name, subject, total_fee, institute_deduction_type, institute_deduction_value, notes, get_current_date(),
            teaching_types, fee_in_person, fee_electronic, fee_blended,
            institute_pct_in_person, institute_pct_electronic, institute_pct_blended,
            inst_ded_type_in_person, inst_ded_type_electronic, inst_ded_type_blended,
            inst_ded_manual_in_person, inst_ded_manual_electronic, inst_ded_manual_blended,
            custom_type_json))

        print(f"تم إضافة المدرس بنجاح: {name} - {subject}")
    except Exception as e:
        print(f"خطأ في إضافة المدرس: {e}")
        import urllib.parse
        error_msg = urllib.parse.quote(str(e))
        return RedirectResponse(url=f"/teachers/add?error=db_error&detail={error_msg}", status_code=303)

    return RedirectResponse(url="/teachers?msg=added", status_code=303)


@router.get("/teachers/{teacher_id}/edit", response_class=HTMLResponse)
async def teacher_edit_form(request: Request, teacher_id: int, error: str = ""):
    """نموذج تعديل مدرس"""
    check_permission(request, 'edit_teachers')
    db = Database()

    query = "SELECT * FROM teachers WHERE id = %s"
    result = db.execute_query(query, (teacher_id,))

    if not result:
        return RedirectResponse(url="/teachers?error=not_found", status_code=303)

    subjects = db.execute_query("SELECT name FROM subjects ORDER BY name")

    # فحص وجود طلاب مرتبطين - يُمنع تغيير أي شيء بعد ارتباط أي طالب
    students_check = db.execute_query(
        "SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s",
        (teacher_id,)
    )
    has_linked_students = students_check and students_check[0]['cnt'] > 0

    # فحص وجود مدفوعات (للعرض فقط)
    payments_check = db.execute_query(
        "SELECT COUNT(*) as cnt FROM installments WHERE teacher_id = %s",
        (teacher_id,)
    )
    has_payments = payments_check and payments_check[0]['cnt'] > 0

    # تحليل الأنواع المخصصة
    teacher_dict = dict(result[0])
    teacher_custom_type_settings = parse_custom_type_settings(teacher_dict.get('custom_type_settings'))

    return templates.TemplateResponse("teachers/form.html", {
        "request": request,
        "teacher": teacher_dict,
        "mode": "edit",
        "subjects": subjects,
        "error": error,
        "has_payments": has_payments,
        "has_linked_students": has_linked_students,
        "teacher_custom_type_settings": teacher_custom_type_settings
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
    """تحديث بيانات مدرس - مع منع تغيير أي شيء بعد ارتباط الطالب به (فقط إضافة نوع تدريسي جديد)"""
    check_permission(request, 'edit_teachers')
    
    # التحقق من أن النسب المئوية بين 1 و 99
    for pct_val, pct_label in [
        (institute_pct_in_person, 'حضوري'),
        (institute_pct_electronic, 'الكتروني'),
        (institute_pct_blended, 'مدمج')
    ]:
        if pct_val != 0 and (pct_val < 1 or pct_val > 99):
            return RedirectResponse(url=f"/teachers/{teacher_id}/edit?error=invalid_pct&label={pct_label}&val={pct_val}", status_code=303)

    # التحقق من أن المبلغ اليدوي للخصم لا يتجاوز القسط الكلي
    for manual_val, fee_val, ded_type, type_label in [
        (inst_ded_manual_in_person, fee_in_person, inst_ded_type_in_person, 'حضوري'),
        (inst_ded_manual_electronic, fee_electronic, inst_ded_type_electronic, 'الكتروني'),
        (inst_ded_manual_blended, fee_blended, inst_ded_type_blended, 'مدمج')
    ]:
        if ded_type == 'manual' and manual_val > 0 and fee_val > 0 and manual_val > fee_val:
            return RedirectResponse(url=f"/teachers/{teacher_id}/edit?error=invalid_manual_ded&label={type_label}&val={manual_val}&fee={fee_val}", status_code=303)
    
    if not teaching_types or teaching_types.strip() == '':
        return RedirectResponse(url=f"/teachers/{teacher_id}/edit?error=no_teaching_type", status_code=303)

    db = Database()

    # معالجة الأنواع التدريسية المخصصة
    form_data = await request.form()
    custom_settings, custom_errors = build_custom_type_settings_from_form(form_data)
    
    if custom_errors:
        import urllib.parse
        error_msg = urllib.parse.quote(' | '.join(custom_errors))
        return RedirectResponse(url=f"/teachers/{teacher_id}/edit?error=custom_type&detail={error_msg}", status_code=303)
    
    # التحقق من نسب الخصم للأنواع المخصصة (1-99)
    for ct_name, ct_data in custom_settings.items():
        ded_type = ct_data.get('deduction_type', 'percentage')
        if ded_type == 'percentage':
            pct_val = ct_data.get('deduction_pct', 0)
            if pct_val != 0 and (pct_val < 1 or pct_val > 99):
                return RedirectResponse(url=f"/teachers/{teacher_id}/edit?error=invalid_pct&label={ct_name}&val={pct_val}", status_code=303)
        elif ded_type == 'manual':
            manual_val = ct_data.get('deduction_manual', 0)
            fee_val = ct_data.get('fee', 0)
            if manual_val > 0 and fee_val > 0 and manual_val > fee_val:
                return RedirectResponse(url=f"/teachers/{teacher_id}/edit?error=invalid_manual_ded&label={ct_name}&val={manual_val}&fee={fee_val}", status_code=303)

    existing_subject = db.execute_query("SELECT id FROM subjects WHERE name = %s", (subject,))
    if not existing_subject:
        try:
            db.execute_query("INSERT INTO subjects (name, created_at) VALUES (%s, %s)", (subject, get_current_date()))
        except:
            pass

    # فحص وجود طلاب مرتبطين - يُمنع تغيير أي شيء بعد ارتباط أي طالب
    students_check = db.execute_query(
        "SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s",
        (teacher_id,)
    )
    has_linked_students = students_check and students_check[0]['cnt'] > 0

    if has_linked_students:
        # جلب البيانات الحالية
        current = db.execute_query("SELECT * FROM teachers WHERE id = %s", (teacher_id,))
        if not current:
            return RedirectResponse(url="/teachers?error=not_found", status_code=303)
        c = current[0]
        current_teaching_types = [t.strip() for t in (c['teaching_types'] or 'حضوري').split(',') if t.strip()]
        new_teaching_types = [t.strip() for t in teaching_types.split(',') if t.strip()]

        # تحديد الأنواع الجديدة المضافة فقط
        added_types = [t for t in new_teaching_types if t not in current_teaching_types]
        removed_types = [t for t in current_teaching_types if t not in new_teaching_types]

        # لا يمكن حذف نوع تدريس مرتبط بطلاب
        if removed_types:
            return RedirectResponse(url=f"/teachers/{teacher_id}/edit?error=cannot_remove_type", status_code=303)

        # الحفاظ على جميع البيانات القديمة - باستثناء الملاحظات (يمكن تعديلها دائماً)
        name = c['name']
        subject = c['subject']
        total_fee = c['total_fee']
        institute_deduction_type = c['institute_deduction_type']
        institute_deduction_value = c['institute_deduction_value']
        # notes: السماح بتعديل الملاحظات حتى مع وجود طلاب مرتبطين
        # لأن الملاحظات لا تؤثر على الحسابات المالية
        fee_in_person = c['fee_in_person']
        fee_electronic = c['fee_electronic']
        fee_blended = c['fee_blended']
        institute_pct_in_person = c['institute_pct_in_person']
        institute_pct_electronic = c['institute_pct_electronic']
        institute_pct_blended = c['institute_pct_blended']
        inst_ded_type_in_person = c['inst_ded_type_in_person']
        inst_ded_type_electronic = c['inst_ded_type_electronic']
        inst_ded_type_blended = c['inst_ded_type_blended']
        inst_ded_manual_in_person = c['inst_ded_manual_in_person']
        inst_ded_manual_electronic = c['inst_ded_manual_electronic']
        inst_ded_manual_blended = c['inst_ded_manual_blended']

        # معالجة الأنواع المخصصة مع وجود طلاب مرتبطين
        # الحفاظ على الأنواع المخصصة الحالية، والسماح بإضافة أنواع جديدة فقط
        current_custom_settings = parse_custom_type_settings(c.get('custom_type_settings'))
        merged_custom_settings = dict(current_custom_settings)  # نسخة من الحالي
        
        # إضافة الأنواع المخصصة الجديدة فقط
        for ct_name, ct_data in custom_settings.items():
            if ct_name not in current_custom_settings:
                merged_custom_settings[ct_name] = ct_data
        
        custom_type_json = dump_custom_type_settings(merged_custom_settings)

        # السماح بإضافة أنواع تدريس جديدة فقط مع أقساطها ونسبها
        if added_types:
            # دمج الأنواع القديمة مع الجديدة
            merged_types = current_teaching_types + added_types
            teaching_types = ','.join(merged_types)

            # إضافة أقساط ونسب الأنواع الجديدة من النموذج
            if 'الكتروني' in added_types:
                fee_electronic = int(form_data.get('fee_electronic', 0) or 0)
                institute_pct_electronic = int(form_data.get('institute_pct_electronic', 0) or 0)
                inst_ded_type_electronic = form_data.get('inst_ded_type_electronic', 'percentage')
                inst_ded_manual_electronic = int(form_data.get('inst_ded_manual_electronic', 0) or 0)
            if 'مدمج' in added_types:
                fee_blended = int(form_data.get('fee_blended', 0) or 0)
                institute_pct_blended = int(form_data.get('institute_pct_blended', 0) or 0)
                inst_ded_type_blended = form_data.get('inst_ded_type_blended', 'percentage')
                inst_ded_manual_blended = int(form_data.get('inst_ded_manual_blended', 0) or 0)
            if 'حضوري' in added_types:
                fee_in_person = int(form_data.get('fee_in_person', 0) or 0)
                institute_pct_in_person = int(form_data.get('institute_pct_in_person', 0) or 0)
                inst_ded_type_in_person = form_data.get('inst_ded_type_in_person', 'percentage')
                inst_ded_manual_in_person = int(form_data.get('inst_ded_manual_in_person', 0) or 0)
        else:
            teaching_types = c['teaching_types']
        
        # إضافة أسماء الأنواع المخصصة الجديدة إلى teaching_types
        if custom_settings:
            base_types = [t.strip() for t in teaching_types.split(',') if t.strip()]
            custom_type_names = list(merged_custom_settings.keys())
            merged_types = base_types + [ct for ct in custom_type_names if ct not in base_types]
            teaching_types = ','.join(merged_types)

        update_query = '''
            UPDATE teachers
            SET notes=%s, teaching_types=%s, fee_in_person=%s, fee_electronic=%s, fee_blended=%s,
                institute_pct_in_person=%s, institute_pct_electronic=%s, institute_pct_blended=%s,
                inst_ded_type_in_person=%s, inst_ded_type_electronic=%s, inst_ded_type_blended=%s,
                inst_ded_manual_in_person=%s, inst_ded_manual_electronic=%s, inst_ded_manual_blended=%s,
                custom_type_settings=%s
            WHERE id = %s
        '''
        db.execute_query(update_query, (
            notes, teaching_types, fee_in_person, fee_electronic, fee_blended,
            institute_pct_in_person, institute_pct_electronic, institute_pct_blended,
            inst_ded_type_in_person, inst_ded_type_electronic, inst_ded_type_blended,
            inst_ded_manual_in_person, inst_ded_manual_electronic, inst_ded_manual_blended,
            custom_type_json, teacher_id))

        if added_types or custom_settings:
            return RedirectResponse(url="/teachers?msg=updated_new_type_added", status_code=303)
        return RedirectResponse(url="/teachers?msg=updated_no_change", status_code=303)

    # لا يوجد طلاب مرتبطين - يمكن التعديل بحرية
    # إضافة أسماء الأنواع المخصصة إلى teaching_types
    if custom_settings:
        base_types = [t.strip() for t in teaching_types.split(',') if t.strip()]
        custom_type_names = list(custom_settings.keys())
        merged_types = base_types + [ct for ct in custom_type_names if ct not in base_types]
        teaching_types = ','.join(merged_types)
    
    custom_type_json = dump_custom_type_settings(custom_settings)

    update_query = '''
        UPDATE teachers
        SET name=%s, subject=%s, total_fee=%s, institute_deduction_type=%s, institute_deduction_value=%s, notes=%s,
            teaching_types=%s, fee_in_person=%s, fee_electronic=%s, fee_blended=%s,
            institute_pct_in_person=%s, institute_pct_electronic=%s, institute_pct_blended=%s,
            inst_ded_type_in_person=%s, inst_ded_type_electronic=%s, inst_ded_type_blended=%s,
            inst_ded_manual_in_person=%s, inst_ded_manual_electronic=%s, inst_ded_manual_blended=%s,
            custom_type_settings=%s
        WHERE id = %s
    '''

    db.execute_query(update_query, (name, subject, total_fee, institute_deduction_type, institute_deduction_value, notes,
        teaching_types, fee_in_person, fee_electronic, fee_blended,
        institute_pct_in_person, institute_pct_electronic, institute_pct_blended,
        inst_ded_type_in_person, inst_ded_type_electronic, inst_ded_type_blended,
        inst_ded_manual_in_person, inst_ded_manual_electronic, inst_ded_manual_blended,
        custom_type_json, teacher_id))

    return RedirectResponse(url="/teachers?msg=updated", status_code=303)


@router.get("/teachers/{teacher_id}", response_class=HTMLResponse)
async def teacher_detail(request: Request, teacher_id: int):
    """تفاصيل المدرس"""
    check_permission(request, 'preview_teachers')
    db = Database()

    teacher_query = "SELECT * FROM teachers WHERE id = %s"
    teacher_result = db.execute_query(teacher_query, (teacher_id,))

    if not teacher_result:
        return RedirectResponse(url="/teachers?error=not_found", status_code=303)

    teacher = dict(teacher_result[0])
    students_list = finance_service.get_teacher_students_list(teacher_id)
    financial_info = finance_service.calculate_teacher_balance(teacher_id)

    # تحليل الأنواع المخصصة
    teacher_custom_type_settings = parse_custom_type_settings(teacher.get('custom_type_settings'))

    counts_query = '''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN study_type = 'حضوري' THEN 1 ELSE 0 END) as in_person,
            SUM(CASE WHEN study_type = 'الكتروني' THEN 1 ELSE 0 END) as electronic,
            SUM(CASE WHEN study_type = 'مدمج' THEN 1 ELSE 0 END) as blended
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
        "format_currency": format_currency,
        "teacher_custom_type_settings": teacher_custom_type_settings
    })


@router.post("/teachers/{teacher_id}/delete")
async def teacher_delete(request: Request, teacher_id: int):
    """حذف مدرس - مع حماية إذا كان مرتبط بطلاب أو لديه سجلات مالية"""
    check_permission(request, 'delete_teachers')
    db = Database()
    
    # فحص إذا كان المدرس مرتبط بطلاب (حالة مستمر)
    active_students = db.execute_query(
        "SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s AND status = 'مستمر'", 
        (teacher_id,)
    )
    if active_students and active_students[0]['cnt'] > 0:
        cnt = active_students[0]['cnt']
        teacher = db.execute_query("SELECT name FROM teachers WHERE id = %s", (teacher_id,))
        teacher_name = teacher[0]['name'] if teacher else ''
        return RedirectResponse(url=f"/teachers?error=has_students&count={cnt}&name={teacher_name}", status_code=303)
    
    # فحص إذا كان المدرس لديه أقساط مسجلة (سجلات مالية)
    installments_count = db.execute_query(
        "SELECT COUNT(*) as cnt FROM installments WHERE teacher_id = %s", 
        (teacher_id,)
    )
    if installments_count and installments_count[0]['cnt'] > 0:
        cnt = installments_count[0]['cnt']
        teacher = db.execute_query("SELECT name FROM teachers WHERE id = %s", (teacher_id,))
        teacher_name = teacher[0]['name'] if teacher else ''
        return RedirectResponse(
            url=f"/teachers?error=has_financial_records&count={cnt}&name={teacher_name}", 
            status_code=303
        )
    
    # لا توجد سجلات مالية - يمكن الحذف بأمان
    db.execute_query("DELETE FROM teacher_withdrawals WHERE teacher_id = %s", (teacher_id,))
    db.execute_query("DELETE FROM student_teacher WHERE teacher_id = %s", (teacher_id,))
    db.execute_query("DELETE FROM teachers WHERE id = %s", (teacher_id,))
    return RedirectResponse(url="/teachers?msg=deleted", status_code=303)


# ===== المحاسبة =====

@router.get("/accounting", response_class=HTMLResponse)
async def accounting_page(request: Request, search: str = "", date_from: str = "", date_to: str = ""):
    """صفحة محاسبة المدرسين"""
    check_permission(request, 'view_accounting')
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
    check_permission(request, 'view_withdrawals_list')
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

@router.get("/payments/add", response_class=HTMLResponse)
async def payment_form(request: Request, student_id: int = None, teacher_id: int = None):
    """صفحة تسجيل قسط جديد"""
    check_permission(request, 'view_payments_list')
    db = Database()
    
    try:
        students = db.execute_query("SELECT id, name FROM students ORDER BY name")
    except:
        students = []
    
    return templates.TemplateResponse("payments/form.html", {
        "request": request,
        "students": students,
        "preselected_student_id": student_id or 0,
        "preselected_teacher_id": teacher_id or 0,
        "format_currency": format_currency
    })


@router.get("/payments", response_class=HTMLResponse)
async def payments_page(request: Request, search: str = "", date_from: str = "", date_to: str = ""):
    """صفحة إدارة الأقساط والمدفوعات"""
    check_permission(request, 'view_payments_list')
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
    check_permission(request, 'view_stats')
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


# ===== الجدول الأسبوعي =====

@router.get("/weekly-schedule", response_class=HTMLResponse)
async def weekly_schedule_page(request: Request):
    """صفحة الجدول الأسبوعي"""
    check_permission(request, 'view_subjects')
    db = Database()
    
    try:
        rooms = db.execute_query("SELECT * FROM rooms ORDER BY name")
        teachers = db.execute_query("SELECT id, name, subject FROM teachers ORDER BY name")
        schedule = db.execute_query('''
            SELECT ws.*, r.name as room_name, t.name as teacher_name, t.subject as teacher_subject
            FROM weekly_schedule ws
            JOIN rooms r ON ws.room_id = r.id
            JOIN teachers t ON ws.teacher_id = t.id
            ORDER BY r.name, ws.day_of_week, ws.start_time
        ''')
    except Exception as e:
        print(f"Error loading weekly schedule: {e}")
        rooms = []
        teachers = []
        schedule = []
    
    return templates.TemplateResponse("weekly_schedule/index.html", {
        "request": request,
        "rooms": [dict(r) for r in rooms] if rooms else [],
        "teachers": [dict(t) for t in teachers] if teachers else [],
        "schedule": [dict(s) for s in schedule] if schedule else []
    })


@router.get("/logs", response_class=HTMLResponse)
async def operation_logs_page(request: Request):
    """صفحة سجل العمليات"""
    check_permission(request, 'view_logs')
    db = Database()

    logs = db.execute_query("""
        SELECT *
        FROM operation_logs
        ORDER BY id DESC
        LIMIT 300
    """)

    return templates.TemplateResponse("logs/index.html", {
        "request": request,
        "logs": logs or []
    })
