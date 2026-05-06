# ============================================
# auth.py - نظام المصادقة والتفويض
# ============================================

import hmac
import hashlib
import json
import base64
import time
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from database import Database
from config import SECRET_KEY

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


def is_bcrypt_hash(password_hash: str) -> bool:
    """فحص هل الهاش من نوع bcrypt"""
    return password_hash.startswith('$2b$') or password_hash.startswith('$2a$')


def needs_bcrypt_migration(password_hash: str) -> bool:
    """فحص هل يحتاج الهاش للترحيل من SHA-256 إلى bcrypt"""
    return not is_bcrypt_hash(password_hash)


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


def create_session_token(user_id: int) -> str:
    """إنشاء رمز جلسة موقع"""
    payload = json.dumps({"uid": user_id, "exp": int(time.time()) + SESSION_EXPIRY})
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


# ===== فحص الصلاحيات (يُستخدم في المسارات) =====

def check_permission(request: Request, permission_code: str):
    """
    فحص صلاحية المستخدم - يُستخدم في بداية كل مسار
    يرفع HTTPException إذا لم يكن المستخدم يملك الصلاحية
    """
    user = getattr(request.state, 'user', None)
    if not user:
        raise HTTPException(status_code=401, detail="يجب تسجيل الدخول")
    if not user_has_permission(user, permission_code):
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية لهذا الإجراء")


def check_permission_or_redirect(request: Request, permission_code: str):
    """
    فحص صلاحية المستخدم - يُعيد توجيه إذا لم يملك الصلاحية
    يُستخدم في مسارات HTML
    """
    user = getattr(request.state, 'user', None)
    if not user:
        return RedirectResponse(url='/login', status_code=303)
    if not user_has_permission(user, permission_code):
        return RedirectResponse(url='/?error=no_permission', status_code=303)
    return None


# ===== وسيط المصادقة (Middleware) =====

async def auth_middleware(request: Request, call_next):
    """
    وسيط المصادقة - يتحقق من تسجيل الدخول قبل كل طلب
    """
    path = request.url.path

    # صفحات لا تحتاج مصادقة
    public_paths = ['/login', '/api/login', '/api/logout', '/health']
    if path in public_paths or path.startswith('/static'):
        return await call_next(request)

    # التحقق من الجلسة
    user = get_current_user(request)
    request.state.user = user

    if user:
        # ترحيل كلمة المرور من SHA-256 إلى bcrypt عند تسجيل الدخول
        try:
            if needs_bcrypt_migration(user.get('password_hash', '')):
                db = Database()
                new_hash = hash_password('1111')  # سيتم تحديثها عند تسجيل الدخول الفعلي
                # لا نحدّث هنا لأننا لا نعرف كلمة المرور الأصلية
                # الترحيل يتم عند تسجيل الدخول بنجاح
        except Exception:
            pass

        # تحميل صلاحيات المستخدم
        request.state.user_permissions = get_user_permissions(user['id'])
    else:
        request.state.user = None
        request.state.user_permissions = []

        # إعادة توجيه إلى صفحة تسجيل الدخول
        if path.startswith('/api/'):
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "يجب تسجيل الدخول"}
            )
        return RedirectResponse(url='/login', status_code=303)

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

        if not user or user[0]['is_active'] != 1:
            return None

        user_data = dict(user[0])

        if not verify_password(password, user_data['password_hash']):
            return None

        # ترحيل كلمة المرور من SHA-256 إلى bcrypt
        if needs_bcrypt_migration(user_data['password_hash']):
            try:
                new_hash = hash_password(password)
                db.execute_query(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (new_hash, user_data['id'])
                )
            except Exception:
                pass  # فشل الترحيل لا يمنع تسجيل الدخول

        return user_data

    except Exception:
        return None
