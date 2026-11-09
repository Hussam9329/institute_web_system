# ============================================
# routes/parent_routes.py
# رابط ولي الأمر: صفحة عامة تتحدث تلقائياً من بيانات الطالب الحالية
# ============================================

import os
import re
import secrets

from fastapi import APIRouter, Request, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import APP_TITLE, BASE_DIR, format_currency, format_date, format_report_datetime
from database import Database
from auth import check_permission
from services.audit_service import log_action
from services.finance_service import finance_service

router = APIRouter()

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.globals['format_currency'] = format_currency
templates.env.globals['format_date'] = format_date
templates.env.globals['app_title'] = APP_TITLE

# الرمز من secrets.token_urlsafe(24): 32 حرفاً من [A-Za-z0-9_-]
_TOKEN_PATTERN = re.compile(r'^[A-Za-z0-9_-]{32}$')

# صفحة ولي الأمر لا تُخزَّن ولا تُفهرس ولا تُرسل الرابط لمواقع أخرى
_PRIVATE_HEADERS = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    "Referrer-Policy": "no-referrer",
}


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def _ensure_token(db: Database, student_id: int, regenerate: bool = False) -> str | None:
    """يرجع رمز الطالب، وينشئه إن لم يوجد (أو يستبدله عند regenerate)"""
    if not regenerate:
        row = db.execute_query("SELECT parent_token FROM students WHERE id = %s", (student_id,))
        if not row:
            return None
        if row[0].get('parent_token'):
            return row[0]['parent_token']
    token = _new_token()
    # عند عدم الاستبدال لا نكتب فوق رمز أنشأه طلب متزامن
    condition = "" if regenerate else " AND parent_token IS NULL"
    db.execute_query(f"UPDATE students SET parent_token = %s WHERE id = %s{condition}", (token, student_id))
    row = db.execute_query("SELECT parent_token FROM students WHERE id = %s", (student_id,))
    return row[0]['parent_token'] if row else None


def _whatsapp_number(phone: str) -> str:
    """07XXXXXXXXX → 9647XXXXXXXXX (صيغة wa.me الدولية)"""
    phone = (phone or '').strip()
    return '964' + phone[1:] if re.match(r'^07\d{9}$', phone) else ''


# ===== صفحة ولي الأمر (عامة) =====

@router.get("/parent/{token}", response_class=HTMLResponse)
async def parent_report_page(request: Request, token: str):
    """تقرير الطالب لولي الأمر - يُقرأ من البيانات الحالية في كل فتح"""
    student = None
    if _TOKEN_PATTERN.match(token or ''):
        db = Database()
        rows = db.execute_query(
            "SELECT id, name, status FROM students WHERE parent_token = %s", (token,)
        )
        student = dict(rows[0]) if rows else None

    if not student:
        return templates.TemplateResponse(
            "parent/report.html",
            {"request": request, "student": None},
            status_code=404,
            headers=_PRIVATE_HEADERS,
        )

    db = Database()
    teachers_summary = finance_service.get_student_all_teachers_summary(student['id']) or []
    installments = db.execute_query('''
        SELECT i.amount, i.payment_date, i.installment_type, t.name AS teacher_name, t.subject
        FROM installments i
        JOIN teachers t ON i.teacher_id = t.id
        WHERE i.student_id = %s
        ORDER BY i.payment_date DESC, i.id DESC
    ''', (student['id'],)) or []

    total_fee = sum(ts['total_fee'] for ts in teachers_summary)
    total_paid = sum(ts['paid_total'] for ts in teachers_summary)
    remaining = sum(ts['remaining_balance'] for ts in teachers_summary)

    return templates.TemplateResponse(
        "parent/report.html",
        {
            "request": request,
            "student": student,
            "teachers_summary": teachers_summary,
            "installments": [dict(i) for i in installments],
            "total_fee": total_fee,
            "total_paid": total_paid,
            "remaining": remaining,
            "payment_pct": round(total_paid * 100 / total_fee) if total_fee > 0 else 0,
            "updated_at": format_report_datetime(),
        },
        headers=_PRIVATE_HEADERS,
    )


# ===== صفحة إرسال الروابط للموظفين =====

@router.get("/parent-links", response_class=HTMLResponse)
async def parent_links_page(request: Request):
    """روابط أولياء الأمور مجمّعة حسب رقم ولي الأمر (الإخوة برسالة واحدة)"""
    check_permission(request, 'view_student_reports')
    db = Database()

    # إنشاء الرموز الناقصة مرة واحدة لكل طالب
    missing = db.execute_query(
        "SELECT id FROM students WHERE parent_token IS NULL AND status != 'منسحب'"
    ) or []
    for row in missing:
        _ensure_token(db, row['id'])

    students = db.execute_query('''
        SELECT id, name, parent_phone, parent_token
        FROM students
        WHERE status != 'منسحب'
        ORDER BY name
    ''') or []

    groups = {}
    without_phone = []
    for s in students:
        item = {"id": s['id'], "name": s['name'], "path": f"/parent/{s['parent_token']}"}
        phone = (s.get('parent_phone') or '').strip()
        wa = _whatsapp_number(phone)
        if wa:
            groups.setdefault(phone, {"phone": phone, "wa": wa, "students": []})["students"].append(item)
        else:
            without_phone.append(item)

    return templates.TemplateResponse("students/parent_links.html", {
        "request": request,
        "groups": sorted(groups.values(), key=lambda g: g["students"][0]["name"]),
        "without_phone": without_phone,
        "students_count": len(students),
    })


# ===== رابط طالب واحد (من صفحة الطالب) =====

@router.post("/api/students/{student_id}/parent-link")
async def api_student_parent_link(request: Request, student_id: int, data: dict = Body(default={})):
    """يرجع مسار رابط ولي الأمر، أو يستبدله برابط جديد (يُبطل القديم)"""
    regenerate = bool((data or {}).get('regenerate'))
    check_permission(request, 'edit_students' if regenerate else 'view_student_reports')
    db = Database()

    student = db.execute_query("SELECT name, parent_phone FROM students WHERE id = %s", (student_id,))
    if not student:
        return {"success": False, "message": "الطالب غير موجود"}

    token = _ensure_token(db, student_id, regenerate=regenerate)
    if not token:
        return {"success": False, "message": "تعذر إنشاء الرابط"}

    if regenerate:
        log_action(request, "update", "student_parent_link", str(student_id),
                   f"إنشاء رابط ولي أمر جديد للطالب {student[0]['name']} (الرابط القديم لم يعد يعمل)")

    return {
        "success": True,
        "path": f"/parent/{token}",
        "whatsapp": _whatsapp_number(student[0].get('parent_phone') or ''),
        "message": "تم إنشاء رابط جديد؛ الرابط القديم لم يعد يعمل" if regenerate else "",
    }
