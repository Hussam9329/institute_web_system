# ============================================
# auth.py - نظام المصادقة والتفويض
# ============================================

import hmac
import hashlib
import json
import base64
import time
import logging
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from database import Database
from config import SECRET_KEY

logger = logging.getLogger(__name__)

SESSION_COOKIE = "institute_session"
SESSION_EXPIRY = 86400 * 7  # 7 أيام


# ===== تشفير كلمات المرور بـ bcrypt =====

def hash_password(password: str) -> str:
    """تشفير كلمة المرور باستخدام bcrypt"""
    import bcrypt
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    التحقق من كلمة المرور
    يدعم bcrypt (الجديد) و SHA-256 (القديم - للترحيل)
    """
    # إذا كان الهاش يبدأ بـ $2b$ أو $2a$ فهو bcrypt
    if password_hash.startswith('$2b$') or password_hash.startswith('$2a$'):
        import bcrypt
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception:
            return False
    # ترحيل من SHA-256 القديم
    return hashlib.sha256(password.encode('utf-8')).hexdigest() == password_hash


def needs_bcrypt_migration(password_hash: str) -> bool:
    """فحص هل يحتاج الهاش للترحيل من SHA-256 إلى bcrypt"""
    return not (password_hash.startswith('$2b$') or password_hash.startswith('$2a$'))


# ===== إدارة الجلسات =====

def _sign_token(data: str) -> str:
    """توقيع البيانات باستخدام HMAC"""
    sig = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{sig}"


def _verify_token(token: str) -> str | None:
    """التحقق من التوقيع وإرجاع البيانات"""
    if '.' not in token:
        return None
    data, sig = token.rsplit('.', 1)
    expected_sig = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected_sig):
        return data
    return None


def create_session_token(user_id: int, remember: bool = False) -> str:
    """إنشاء رمز جلسة موقع"""
    expiry_seconds = 86400 * 30 if remember else SESSION_EXPIRY
    payload = json.dumps({"uid": user_id, "exp": int(time.time()) + expiry_seconds, "remember": remember})
    encoded = base64.urlsafe_b64encode(payload.encode()).decode()
    return _sign_token(encoded)


def get_session_user_id(token: str) -> int | None:
    """استخراج معرف المستخدم من رمز الجلسة"""
    data = _verify_token(token)
    if not data:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(data.encode()).decode())
        if payload.get('exp', 0) < time.time():
            return None
        return payload.get('uid')
    except Exception:
        return None


# ===== الحصول على المستخدم الحالي =====

def get_current_user(request: Request) -> dict | None:
    """الحصول على بيانات المستخدم الحالي من الطلب"""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    user_id = get_session_user_id(token)
    if not user_id:
        return None
    try:
        db = Database()
        user = db.execute_query('''
            SELECT u.id, u.username, u.full_name, u.role_id, u.is_active, u.password_hash,
                   r.name as role_name
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.id = %s
        ''', (user_id,))
        if not user or user[0]['is_active'] != 1:
            return None
        return dict(user[0])
    except Exception:
        return None


def get_user_permissions(user_id: int) -> list[str]:
    """الحصول على قائمة صلاحيات المستخدم"""
    try:
        db = Database()
        result = db.execute_query('''
            SELECT p.code
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.id
            JOIN users u ON u.role_id = rp.role_id
            WHERE u.id = %s
        ''', (user_id,))
        return [r['code'] for r in result] if result else []
    except Exception:
        return []


def user_has_permission(user: dict, permission_code: str) -> bool:
    """فحص هل المستخدم يملك صلاحية معينة"""
    if not user:
        return False
    try:
        db = Database()
        result = db.execute_query('''
            SELECT 1 FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.id
            WHERE rp.role_id = %s AND p.code = %s
        ''', (user['role_id'], permission_code))
        return bool(result)
    except Exception:
        return False


# ===== فحص الصلاحيات =====

def check_permission(request: Request, permission_code: str):
    """
    فحص صلاحية المستخدم
    يتحقق من أن المستخدم الحالي يملك الصلاحية المطلوبة
    """
    user = getattr(request.state, 'user', None)
    if not user:
        raise HTTPException(status_code=401, detail="يجب تسجيل الدخول")

    # مدير العام يملك كل الصلاحيات
    if user.get('role_name') == 'مدير عام':
        return

    permissions = getattr(request.state, 'user_permissions', [])
    if 'all' in permissions or permission_code in permissions:
        return

    raise HTTPException(status_code=403, detail="ليس لديك صلاحية")


# ===== وسيط المصادقة (Middleware) =====

PUBLIC_PATHS = [
    "/login",
    "/api/login",
    "/static",
    "/health"
]

async def auth_middleware(request: Request, call_next):
    """وسيط المصادقة - التحقق من تسجيل الدخول"""
    path = request.url.path

    # السماح بالمسارات العامة
    if any(path == p or path.startswith(p + "/") for p in PUBLIC_PATHS):
        return await call_next(request)

    user = get_current_user(request)

    if not user:
        if path.startswith("/api/"):
            return JSONResponse(
                {"success": False, "message": "يجب تسجيل الدخول"},
                status_code=401
            )
        return RedirectResponse(url="/login", status_code=303)

    request.state.user = user
    request.state.user_permissions = get_user_permissions(user["id"])

    # مدير العام يملك كل الصلاحيات
    if user.get('role_name') == 'مدير عام':
        request.state.user_permissions = ['all']

    # ===== استخراج توقيت العميل من HTTP Header =====
    # يُستخدم في سجل العمليات (logs) بدلاً من توقيت السيرفر
    try:
        header_ts = request.headers.get('x-client-timestamp', '')
        if header_ts:
            request.state.client_timestamp = header_ts
        else:
            request.state.client_timestamp = None
    except Exception:
        request.state.client_timestamp = None

    response = await call_next(request)
    return response


# ===== تسجيل الدخول =====

def login_user(username: str, password: str) -> dict | None:
    """
    تسجيل دخول المستخدم
    يرجع بيانات المستخدم إذا نجح، أو None إذا فشل
    يقوم بترحيل كلمات المرور من SHA-256 إلى bcrypt تلقائياً
    """
    try:
        db = Database()
        user = db.execute_query('''
            SELECT u.id, u.username, u.full_name, u.role_id, u.is_active, u.password_hash,
                   r.name as role_name
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.username = %s
        ''', (username,))

        if not user:
            logger.warning(f"محاولة تسجيل دخول فاشلة - المستخدم غير موجود: {username}")
            return None

        if user[0]['is_active'] != 1:
            logger.warning(f"محاولة تسجيل دخول فاشلة - الحساب معطل: {username}")
            return None

        user_data = dict(user[0])

        if not verify_password(password, user_data['password_hash']):
            logger.warning(f"محاولة تسجيل دخول فاشلة - كلمة مرور خاطئة: {username}")
            return None

        # ترحيل كلمة المرور من SHA-256 إلى bcrypt
        if needs_bcrypt_migration(user_data['password_hash']):
            try:
                new_hash = hash_password(password)
                db.execute_query(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (new_hash, user_data['id'])
                )
                logger.info(f"تم ترحيل كلمة مرور المستخدم {username} من SHA-256 إلى bcrypt")
            except Exception as e:
                logger.warning(f"فشل ترحيل كلمة المرور للمستخدم {username}: {e}")

        logger.info(f"تسجيل دخول ناجح: {username}")
        return user_data

    except Exception as e:
        logger.error(f"خطأ في تسجيل الدخول: {e}")
        return None
