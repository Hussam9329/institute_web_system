# ============================================
# routes/report_routes.py
# مسارات التقارير HTML مع زر الطباعة
# ============================================

from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from datetime import datetime
import os

from config import APP_TITLE, BASE_DIR, format_currency, format_date, format_report_datetime, format_report_date, format_report_time
from services.finance_service import finance_service
from database import Database
from auth import check_permission

router = APIRouter(prefix="/reports")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# إضافة دالة format_date للقوالب
templates.env.globals['format_currency'] = format_currency
templates.env.globals['format_date'] = format_date
templates.env.globals['app_title'] = APP_TITLE


@router.get("/student/{student_id}")
async def student_report(request: Request, student_id: int):
    """تقرير الطالب المالي الشامل - HTML مع زر طباعة"""
    check_permission(request, 'view_student_reports')
    db = Database()

    student_result = db.execute_query("SELECT * FROM students WHERE id = %s", (student_id,))
    if not student_result:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    student = dict(student_result[0])

    teachers_summary = finance_service.get_student_all_teachers_summary(student_id)

    total_original_fee_all = sum(ts['original_fee'] for ts in teachers_summary) if teachers_summary else 0
    total_fee_all = sum(ts['total_fee'] for ts in teachers_summary) if teachers_summary else 0
    total_paid_all = sum(ts['paid_total'] for ts in teachers_summary) if teachers_summary else 0
    remaining_all = sum(ts['remaining_balance'] for ts in teachers_summary) if teachers_summary else 0
    payment_pct = round((total_paid_all / total_fee_all) * 100) if total_fee_all > 0 else 0

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

    # بيانات إضافية للكارتات والتصدير
    num_installments = len(installments) if installments else 0
    last_payment_date = ""
    last_payment_amount = 0
    if installments and len(installments) > 0:
        try:
            last_payment_date = format_date(installments[0].get('payment_date', ''))
            last_payment_amount = int(installments[0].get('amount', 0) or 0)
        except (TypeError, ValueError):
            last_payment_date = ""
            last_payment_amount = 0

    # حساب المدفوع الزائد (إذا تجاوز المدفوع القسط)
    overpayment = max(0, total_paid_all - total_fee_all) if total_fee_all > 0 else 0

    # قائمة المدرسين والمواد للفلترة
    teacher_names = list(dict.fromkeys(ts['teacher_name'] for ts in teachers_summary if ts.get('teacher_name'))) if teachers_summary else []
    subjects = list(dict.fromkeys(ts.get('subject', '') for ts in teachers_summary if ts.get('subject'))) if teachers_summary else []
    installment_types = list(dict.fromkeys(inst.get('installment_type', '') for inst in installments if inst.get('installment_type'))) if installments else []

    return templates.TemplateResponse("reports/student_report.html", {
        "request": request,
        "student": student,
        "teachers_summary": teachers_summary,
        "num_teachers": len(teachers_summary),
        "total_original_fee": format_currency(total_original_fee_all),
        "total_original_fee_raw": total_original_fee_all,
        "total_fee": format_currency(total_fee_all),
        "total_paid": format_currency(total_paid_all),
        "remaining": format_currency(remaining_all),
        "total_discount": format_currency(total_original_fee_all - total_fee_all),
        "total_discount_raw": total_original_fee_all - total_fee_all,
        "total_fee_raw": total_fee_all,
        "total_paid_raw": total_paid_all,
        "remaining_raw": remaining_all,
        "payment_pct": payment_pct,
        "overpayment_raw": overpayment,
        "overpayment": format_currency(overpayment),
        "num_installments": num_installments,
        "last_payment_date": last_payment_date,
        "last_payment_amount_raw": last_payment_amount,
        "last_payment_amount": format_currency(last_payment_amount),
        "teacher_names": teacher_names,
        "subjects": subjects,
        "installment_types": installment_types,
        "installments": installments,
        "report_date": format_report_datetime(),
        "student_id": student_id,
    })


@router.get("/teacher/{teacher_id}")
async def teacher_report(request: Request, teacher_id: int):
    """تقرير المدرس المالي الشامل - HTML مع زر طباعة"""
    check_permission(request, 'view_teacher_reports')
    db = Database()

    teacher_result = db.execute_query("SELECT * FROM teachers WHERE id = %s", (teacher_id,))
    if not teacher_result:
        raise HTTPException(status_code=404, detail="المدرس غير موجود")
    teacher = dict(teacher_result[0])

    balance_info = finance_service.calculate_teacher_balance(teacher_id)
    students_list = finance_service.get_teacher_students_list(teacher_id)
    recent_withdrawals = finance_service.get_teacher_recent_withdrawals(teacher_id, limit=20)

    expected_total = sum(int(s.get("total_fee") or 0) for s in students_list)
    paid_total = sum(int(s.get("paid_total") or 0) for s in students_list)
    remaining_total = sum(int(s.get("remaining_balance") or 0) for s in students_list)

    return templates.TemplateResponse("reports/teacher_report.html", {
        "request": request,
        "teacher": teacher,
        "balance_info": balance_info,
        "students_list": students_list,
        "recent_withdrawals": recent_withdrawals,
        "expected_total": expected_total,
        "paid_total": paid_total,
        "remaining_total": remaining_total,
        "report_date": format_report_datetime(),
    })


@router.get("/receipt/{installment_id}")
async def receipt_report(request: Request, installment_id: int):
    """وصل دفع - HTML مع زر طباعة"""
    check_permission(request, 'print_receipt')
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

    # استخدام finance_service لحساب القسط مع تطبيق الخصم
    balance = finance_service.calculate_student_teacher_balance(
        installment['student_id'], installment['teacher_id']
    )
    total_fee = balance['total_fee']           # القسط بعد الخصم
    original_fee = balance.get('original_fee', total_fee)  # القسط الأصلي قبل الخصم
    total_paid = balance['paid_total']
    remaining_balance = balance['remaining_balance']
    discount_info = balance.get('discount_info', {'discount_type': 'none', 'discount_value': 0, 'institute_waiver': 0})

    # حساب مبلغ الخصم
    discount_amount = original_fee - total_fee if original_fee > total_fee else 0
    discount_type = discount_info.get('discount_type', 'none')
    discount_value = discount_info.get('discount_value', 0)

    return templates.TemplateResponse("reports/receipt.html", {
        "request": request,
        "installment": installment,
        "total_fee": total_fee,
        "original_fee": original_fee,
        "total_paid": total_paid,
        "remaining_balance": remaining_balance,
        "discount_type": discount_type,
        "discount_value": discount_value,
        "discount_amount": discount_amount,
        "discount_info": discount_info,
        "report_date": format_report_datetime(),
        "report_date_only": format_report_date(),
        "report_time": format_report_time(),
    })


@router.get("/withdrawal/{withdrawal_id}")
async def withdrawal_report(request: Request, withdrawal_id: int):
    """تقرير سحب فردي - HTML مع زر طباعة وتوقيعات"""
    check_permission(request, 'view_withdrawals_list')
    db = Database()

    withdrawal_query = '''
        SELECT w.*, t.name as teacher_name, t.subject, t.total_fee as teacher_fee
        FROM teacher_withdrawals w
        JOIN teachers t ON w.teacher_id = t.id
        WHERE w.id = %s
    '''
    withdrawal_result = db.execute_query(withdrawal_query, (withdrawal_id,))
    if not withdrawal_result:
        raise HTTPException(status_code=404, detail="السحب غير موجود")
    withdrawal = dict(withdrawal_result[0])

    # حساب رصيد المدرس الكامل
    balance_info = finance_service.calculate_teacher_balance(withdrawal['teacher_id'])

    # إجمالي المسحوبات قبل هذا السحب (لعرض الرصيد وقت السحب)
    total_withdrawn_before = finance_service.get_teacher_withdrawn_total_until(
        withdrawal['teacher_id'],
        withdrawal['withdrawal_date'],
        exclude_id=withdrawal_id
    )

    # عدد سحوبات المدرس
    all_teacher_withdrawals = finance_service.get_teacher_recent_withdrawals(withdrawal['teacher_id'], limit=100)

    return templates.TemplateResponse("reports/withdrawal_report.html", {
        "request": request,
        "withdrawal": withdrawal,
        "balance_info": balance_info,
        "total_withdrawn_before": total_withdrawn_before,
        "num_withdrawals": len(all_teacher_withdrawals) if all_teacher_withdrawals else 0,
        "report_date": format_report_datetime(),
        "report_date_only": format_report_date(),
        "report_time": format_report_time(),
    })


@router.get("/subject/{subject_name}")
async def subject_report(request: Request, subject_name: str):
    """تقرير مادة - HTML مع زر طباعة"""
    check_permission(request, 'view_reports')
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
        "report_date": format_report_datetime(),
    })


@router.get("/subjects/all")
async def all_subjects_report(request: Request):
    """تقرير شامل لجميع المواد - HTML مع زر طباعة"""
    check_permission(request, 'view_reports')
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
        "report_date": format_report_datetime(),
    })
