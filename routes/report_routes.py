# ============================================
# routes/report_routes.py
# مسارات التقارير HTML مع زر الطباعة
# ============================================

from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from datetime import datetime
import os

from config import APP_TITLE, BASE_DIR, format_currency, format_date
from services.finance_service import finance_service
from database import Database

router = APIRouter(prefix="/reports")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# إضافة دالة format_date للقوالب
templates.env.globals['format_currency'] = format_currency
templates.env.globals['format_date'] = format_date
templates.env.globals['app_title'] = APP_TITLE


@router.get("/student/{student_id}")
async def student_report(request: Request, student_id: int):
    """تقرير الطالب المالي الشامل - HTML مع زر طباعة"""
    db = Database()

    student_result = db.execute_query("SELECT * FROM students WHERE id = %s", (student_id,))
    if not student_result:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    student = dict(student_result[0])

    teachers_summary = finance_service.get_student_all_teachers_summary(student_id)

    total_fee_all = sum(ts['total_fee'] for ts in teachers_summary) if teachers_summary else 0
    total_paid_all = sum(ts['paid_total'] for ts in teachers_summary) if teachers_summary else 0
    remaining_all = sum(ts['remaining_balance'] for ts in teachers_summary) if teachers_summary else 0
    payment_pct = int((total_paid_all / total_fee_all) * 100) if total_fee_all > 0 else 0

    # سجل المدفوعات
    try:
        installments = db.execute_query('''
            SELECT i.*, t.name as teacher_name, t.subject
            FROM installments i
            JOIN teachers t ON i.teacher_id = t.id
            WHERE i.student_id = %s
            ORDER BY i.payment_date DESC
        ''', (student_id,))
    except Exception:
        installments = []

    return templates.TemplateResponse("reports/student_report.html", {
        "request": request,
        "student": student,
        "teachers_summary": teachers_summary,
        "num_teachers": len(teachers_summary),
        "total_fee": format_currency(total_fee_all),
        "total_paid": format_currency(total_paid_all),
        "remaining": format_currency(remaining_all),
        "total_fee_raw": total_fee_all,
        "total_paid_raw": total_paid_all,
        "remaining_raw": remaining_all,
        "payment_pct": payment_pct,
        "installments": installments,
        "report_date": datetime.now().strftime("%Y/%m/%d - %H:%M"),
    })


@router.get("/teacher/{teacher_id}")
async def teacher_report(request: Request, teacher_id: int):
    """تقرير المدرس المالي الشامل - HTML مع زر طباعة"""
    db = Database()

    teacher_result = db.execute_query("SELECT * FROM teachers WHERE id = %s", (teacher_id,))
    if not teacher_result:
        raise HTTPException(status_code=404, detail="المدرس غير موجود")
    teacher = dict(teacher_result[0])

    balance_info = finance_service.calculate_teacher_balance(teacher_id)
    students_list = finance_service.get_teacher_students_list(teacher_id)
    recent_withdrawals = finance_service.get_teacher_recent_withdrawals(teacher_id, limit=20)

    return templates.TemplateResponse("reports/teacher_report.html", {
        "request": request,
        "teacher": teacher,
        "balance_info": balance_info,
        "students_list": students_list,
        "recent_withdrawals": recent_withdrawals,
        "report_date": datetime.now().strftime("%Y/%m/%d - %H:%M"),
    })


@router.get("/receipt/{installment_id}")
async def receipt_report(request: Request, installment_id: int):
    """وصل دفع - HTML مع زر طباعة"""
    db = Database()

    installment_query = '''
        SELECT i.*, s.name as student_name, s.barcode, t.name as teacher_name, t.subject
        FROM installments i
        JOIN students s ON i.student_id = s.id
        JOIN teachers t ON i.teacher_id = t.id
        WHERE i.id = %s
    '''
    installment_result = db.execute_query(installment_query, (installment_id,))
    if not installment_result:
        raise HTTPException(status_code=404, detail="القسط غير موجود")
    installment = dict(installment_result[0])

    # حساب القسط الكلي والمدفوع والمتبقي
    teacher_info_query = '''
        SELECT t.total_fee, t.fee_in_person, t.fee_electronic, t.fee_blended, st.study_type
        FROM installments i
        JOIN students s ON i.student_id = s.id
        JOIN teachers t ON i.teacher_id = t.id
        LEFT JOIN student_teacher st ON st.student_id = i.student_id AND st.teacher_id = i.teacher_id
        WHERE i.id = %s
    '''
    teacher_info_result = db.execute_query(teacher_info_query, (installment_id,))
    teacher_info = teacher_info_result[0] if teacher_info_result else {}
    study_type = teacher_info.get('study_type', 'حضوري')

    if study_type == 'الكتروني' and teacher_info.get('fee_electronic', 0) > 0:
        total_fee = teacher_info['fee_electronic']
    elif study_type == 'مدمج' and teacher_info.get('fee_blended', 0) > 0:
        total_fee = teacher_info['fee_blended']
    elif study_type == 'حضوري' and teacher_info.get('fee_in_person', 0) > 0:
        total_fee = teacher_info['fee_in_person']
    else:
        total_fee = teacher_info.get('total_fee', 0)

    paid_result = db.execute_query('''
        SELECT COALESCE(SUM(amount), 0) as total
        FROM installments
        WHERE student_id = %s AND teacher_id = %s
    ''', (installment['student_id'], installment['teacher_id']))
    total_paid = paid_result[0]['total'] if paid_result else 0
    remaining_balance = total_fee - total_paid

    now = datetime.now()

    return templates.TemplateResponse("reports/receipt.html", {
        "request": request,
        "installment": installment,
        "total_fee": total_fee,
        "total_paid": total_paid,
        "remaining_balance": remaining_balance,
        "report_date": now.strftime("%Y/%m/%d - %H:%M"),
        "report_date_only": now.strftime("%Y/%m/%d"),
        "report_time": now.strftime("%H:%M"),
    })


@router.get("/subject/{subject_name}")
async def subject_report(request: Request, subject_name: str):
    """تقرير مادة - HTML مع زر طباعة"""
    db = Database()

    teachers = db.execute_query(
        "SELECT * FROM teachers WHERE subject = %s ORDER BY name", (subject_name,)
    )
    if not teachers:
        raise HTTPException(status_code=404, detail="لا يوجد مدرسين لهذه المادة")

    total_students = 0
    teacher_data = []
    for t in teachers:
        cnt = db.execute_query(
            "SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],)
        )
        sc = cnt[0]['cnt'] if cnt else 0
        total_students += sc
        teacher_data.append({
            "name": t['name'],
            "total_fee": t['total_fee'],
            "student_count": sc,
        })

    total_fees = sum(td['total_fee'] for td in teacher_data)

    return templates.TemplateResponse("reports/subject_report.html", {
        "request": request,
        "subject_name": subject_name,
        "teachers": teachers,
        "teacher_data": teacher_data,
        "total_students": total_students,
        "total_fees": total_fees,
        "report_date": datetime.now().strftime("%Y/%m/%d - %H:%M"),
    })


@router.get("/subjects/all")
async def all_subjects_report(request: Request):
    """تقرير شامل لجميع المواد - HTML مع زر طباعة"""
    db = Database()

    subjects = db.execute_query("SELECT name FROM subjects ORDER BY name")
    if not subjects:
        raise HTTPException(status_code=404, detail="لا توجد مواد")

    total_teachers = 0
    total_students = 0
    total_fees = 0
    subject_details = []

    for subj in subjects:
        teachers = db.execute_query(
            "SELECT id, name, total_fee FROM teachers WHERE subject = %s ORDER BY name",
            (subj['name'],)
        )
        subj_students = 0
        subj_fees = 0
        teacher_list = []

        for t in teachers:
            cnt = db.execute_query(
                "SELECT COUNT(*) as cnt FROM student_teacher WHERE teacher_id = %s", (t['id'],)
            )
            sc = cnt[0]['cnt'] if cnt else 0
            subj_students += sc
            subj_fees += t['total_fee']
            teacher_list.append({
                "name": t['name'],
                "total_fee": t['total_fee'],
                "student_count": sc,
            })

        total_teachers += len(teachers)
        total_students += subj_students
        total_fees += subj_fees

        subject_details.append({
            "name": subj['name'],
            "teachers": teacher_list,
            "student_count": subj_students,
            "fee_total": subj_fees,
        })

    return templates.TemplateResponse("reports/all_subjects_report.html", {
        "request": request,
        "total_subjects": len(subjects),
        "total_teachers": total_teachers,
        "total_students": total_students,
        "total_fees": total_fees,
        "subject_details": subject_details,
        "report_date": datetime.now().strftime("%Y/%m/%d - %H:%M"),
    })
