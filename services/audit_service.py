# ============================================
# audit_service.py - خدمة تسجيل العمليات
# ============================================

from database import Database
from config import get_current_datetime


def log_action(request, action: str, entity: str, entity_id: str = "", description: str = ""):
    """تسجيل عملية في سجل العمليات"""
    try:
        db = Database()

        user = getattr(request.state, "user", None) or {}
        user_id = user.get("id")
        username = user.get("username", "")

        ip_address = ""
        try:
            ip_address = request.client.host if request.client else ""
        except Exception:
            pass

        user_agent = request.headers.get("user-agent", "")[:500] if hasattr(request, 'headers') else ""

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
            get_current_datetime()
        ))
    except Exception:
        pass
