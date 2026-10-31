# ============================================
# audit_service.py - خدمة تسجيل العمليات
# ============================================

from database import Database, in_transaction
from config import now_baghdad


def log_action(request, action: str, entity: str, entity_id: str = "", description: str = ""):
    """
    تسجيل عملية في سجل العمليات بتوقيت الخادم (بغداد).
    لا يُعتمد توقيت المتصفح لأنه قابل للتلاعب ويخلط بين منطقتين زمنيتين.
    فشل التسجيل لا يُفشل العملية الأصلية.
    """
    db = Database()
    savepoint = in_transaction()
    try:
        user = getattr(request.state, "user", None) or {}
        user_id = user.get("id")
        username = user.get("username", "")

        ip_address = ""
        try:
            ip_address = request.client.host if request.client else ""
        except Exception:
            pass

        user_agent = request.headers.get("user-agent", "")[:500] if hasattr(request, 'headers') else ""

        # داخل معاملة مفتوحة: نقطة حفظ حتى لا يُلغي فشل التسجيل المعاملة كلها
        if savepoint:
            db.execute_query("SAVEPOINT audit_log")

        db.execute_query("""
            INSERT INTO operation_logs
            (user_id, username, action, entity, entity_id, description, ip_address, user_agent, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            username,
            action,
            entity,
            str(entity_id or ""),
            description,
            ip_address,
            user_agent,
            now_baghdad().strftime("%Y-%m-%d %H:%M:%S")
        ))

        if savepoint:
            db.execute_query("RELEASE SAVEPOINT audit_log")
    except Exception:
        if savepoint:
            try:
                db.execute_query("ROLLBACK TO SAVEPOINT audit_log")
            except Exception:
                pass
