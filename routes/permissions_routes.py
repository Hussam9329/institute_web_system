# ============================================
# permissions_routes.py - مسارات نظام الصلاحيات
# ============================================

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from database import Database, transaction
from models import RoleCreate, RoleUpdate, UserCreate, UserUpdate, RolePermissionsUpdate
from config import BASE_DIR, format_date, get_client_timestamp, get_current_datetime
from auth import hash_password, check_permission, is_superuser, SUPERUSER_ROLE_NAME
from services.audit_service import log_action
from datetime import datetime as dt
from pydantic import BaseModel, Field
import logging
import os

router = APIRouter(prefix="/permissions")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
logger = logging.getLogger(__name__)

GENERIC_ERROR_MESSAGE = "تعذر تنفيذ العملية - حاول مرة أخرى"


def _actor(request: Request) -> dict:
    return getattr(request.state, 'user', None) or {}


def _role_name(db: Database, role_id) -> str | None:
    if role_id is None:
        return None
    row = db.execute_query('SELECT name FROM roles WHERE id = %s', (role_id,))
    return row[0]['name'] if row else None


def _user_management_denial(request: Request, db: Database, target: dict | None, new_role_id=None,
                            changes_active: bool = False) -> str | None:
    """
    قواعد حماية إدارة المستخدمين. ترجع رسالة الرفض أو None إذا كان التعديل مسموحاً.
    target: صف المستخدم المستهدف (username, role_name) أو None عند الإنشاء.
    """
    actor = _actor(request)
    actor_is_super = is_superuser(actor)
    new_role_name = _role_name(db, new_role_id)

    if new_role_id is not None and new_role_name is None:
        return "الدور المحدد غير موجود"

    if new_role_name == SUPERUSER_ROLE_NAME and not actor_is_super:
        return "منح دور المدير العام مسموح للمدير العام فقط"

    if target:
        if target.get('role_name') == SUPERUSER_ROLE_NAME and not actor_is_super:
            return "تعديل حساب مدير عام مسموح للمدير العام فقط"
        if target.get('username') == 'admin':
            if new_role_id is not None and new_role_name != SUPERUSER_ROLE_NAME:
                return "لا يمكن تغيير دور المستخدم الافتراضي (admin)"
            if changes_active:
                return "لا يمكن تعطيل المستخدم الافتراضي (admin)"
        if target.get('id') == actor.get('id'):
            if new_role_id is not None and new_role_name != target.get('role_name'):
                return "لا يمكنك تغيير دورك بنفسك"
            if changes_active:
                return "لا يمكنك تعطيل حسابك بنفسك"
    return None


def _role_management_denial(request: Request, role_row: dict | None, renaming: bool = False) -> str | None:
    """دور المدير العام هو أساس الصلاحيات الكاملة: لا يُعاد تسميته، ولا يعدّله إلا المدير العام."""
    if not role_row:
        return None
    if role_row.get('name') == SUPERUSER_ROLE_NAME:
        if renaming:
            return "لا يمكن إعادة تسمية دور المدير العام"
        if not is_superuser(_actor(request)):
            return "تعديل دور المدير العام مسموح للمدير العام فقط"
    return None


TRIAL_PERMISSIONS_PREVIEW_ITEMS = [
    "إنشاء مستخدمين جدد للنظام وتحديد أدوارهم.",
    "تعديل بيانات المستخدمين أو تغيير كلمة المرور أو تعطيل وتفعيل الحسابات.",
    "حذف المستخدمين غير الأساسيين عند الحاجة.",
    "إنشاء أدوار مخصصة مثل محاسب، مدخل بيانات، مشاهد، أو أي دور آخر.",
    "ربط كل دور بالصلاحيات المناسبة له حسب طبيعة عمل الموظف.",
    "مراجعة مصفوفة الصلاحيات لمعرفة ما المسموح لكل دور.",
    "إنشاء وإدارة الحسابات التجريبية المعزولة للعملاء أو الموظفين."
]

TRIAL_PERMISSIONS_BLOCKED_ITEMS = [
    "لا يتم عرض أسماء المستخدمين الحقيقيين أو أدوارهم داخل الحساب التجريبي.",
    "لا يمكن إنشاء أو تعديل أو حذف مستخدمين من الحساب التجريبي.",
    "لا يمكن إنشاء أو تعديل أو حذف أدوار من الحساب التجريبي.",
    "لا يمكن تغيير صلاحيات أي دور أو الوصول إلى مصفوفة الصلاحيات الفعلية.",
    "لا يمكن إنشاء أو حذف حسابات تجريبية من داخل حساب تجريبي آخر."
]


def _is_trial_permissions_user(request: Request) -> bool:
    """يرجع True إذا كان المستخدم الحالي حساباً تجريبياً."""
    user = getattr(request.state, 'user', None) or {}
    return bool(user.get('is_trial') or getattr(request.state, 'trial_account', None))


def _trial_permissions_api_denied() -> dict:
    """رسالة موحدة عند محاولة الحساب التجريبي تنفيذ إدارة فعلية للصلاحيات."""
    return {
        "success": False,
        "message": "الحساب التجريبي يعرض شرح تبويبة الصلاحيات فقط، ولا يسمح له بتنفيذ إدارة فعلية للمستخدمين أو الأدوار أو الصلاحيات."
    }


# ===== صفحة الصلاحيات الرئيسية =====

@router.get("/", response_class=HTMLResponse)
async def permissions_page(request: Request):
    """صفحة إدارة الصلاحيات"""
    if _is_trial_permissions_user(request):
        return templates.TemplateResponse("permissions/trial_readonly.html", {
            "request": request,
            "preview_items": TRIAL_PERMISSIONS_PREVIEW_ITEMS,
            "blocked_items": TRIAL_PERMISSIONS_BLOCKED_ITEMS,
        })

    check_permission(request, 'view_permissions')
    db = Database()
    
    # جلب المستخدمين مع أسماء الأدوار ومعلومات النسخة التجريبية إن وجدت
    users = db.execute_query('''
        SELECT u.*, r.name as role_name,
               (ta.username IS NOT NULL) AS is_trial,
               ta.started_at AS trial_started_at,
               ta.expires_at AS trial_expires_at,
               ta.expired_at AS trial_expired_at,
               ta.is_expired AS trial_is_expired,
               GREATEST(0, EXTRACT(EPOCH FROM (ta.expires_at - NOW())))::INTEGER AS trial_seconds_remaining,
               (ta.expires_at <= NOW() OR ta.is_expired = 1) AS trial_expired
        FROM users u
        JOIN roles r ON u.role_id = r.id
        LEFT JOIN trial_accounts ta ON ta.username = u.username
        ORDER BY u.id
    ''')
    
    # جلب الأدوار مع عدد المستخدمين وعدد الصلاحيات
    roles = db.execute_query('''
        SELECT r.*,
            COUNT(DISTINCT u.id) as users_count,
            COUNT(DISTINCT rp.permission_id) as permissions_count
        FROM roles r
        LEFT JOIN users u ON u.role_id = r.id
        LEFT JOIN role_permissions rp ON rp.role_id = r.id
        GROUP BY r.id
        ORDER BY r.is_default DESC, r.id
    ''')
    
    # جلب جميع الصلاحيات مصنفة حسب الفئة
    permissions = db.execute_query('''
        SELECT * FROM permissions ORDER BY category, id
    ''')
    
    # تجميع الصلاحيات حسب الفئة
    permissions_by_category = {}
    for p in permissions:
        cat = p['category']
        if cat not in permissions_by_category:
            permissions_by_category[cat] = []
        permissions_by_category[cat].append(dict(p))
    
    # جلب صلاحيات كل دور
    role_permissions_map = {}
    for role in roles:
        rp = db.execute_query('''
            SELECT permission_id FROM role_permissions WHERE role_id = %s
        ''', (role['id'],))
        role_permissions_map[role['id']] = [str(p['permission_id']) for p in rp]

    try:
        from trial_mode import get_all_trial_accounts
        trial_accounts = get_all_trial_accounts()
    except Exception:
        trial_accounts = []
    
    return templates.TemplateResponse("permissions/index.html", {
        "request": request,
        "users": users,
        "roles": roles,
        "permissions_by_category": permissions_by_category,
        "role_permissions_map": role_permissions_map,
        "trial_accounts": trial_accounts,
    })


# ===== API الأدوار =====

@router.post("/api/roles")
async def create_role(request: Request, role: RoleCreate):
    """إنشاء دور جديد"""
    if _is_trial_permissions_user(request):
        return _trial_permissions_api_denied()
    check_permission(request, 'manage_roles')
    db = Database()
    now = get_current_datetime(get_client_timestamp(request))[:16]  # YYYY-MM-DD HH:MM
    try:
        result = db.execute_query('''
            INSERT INTO roles (name, description, is_default, created_at)
            VALUES (%s, %s, 0, %s)
            RETURNING id, name, description
        ''', (role.name, role.description or '', now))
        if result:
            log_action(request, "create", "role", result[0]['id'], f"إنشاء دور: {role.name}")
            return {"success": True, "data": dict(result[0]), "message": "تم إنشاء الدور بنجاح"}
        return {"success": False, "message": "فشل إنشاء الدور"}
    except Exception as e:
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            return {"success": False, "message": "اسم الدور موجود مسبقاً"}
        logger.exception("فشل إنشاء دور")
        return {"success": False, "message": GENERIC_ERROR_MESSAGE}


@router.put("/api/roles/{role_id}")
async def update_role(request: Request, role_id: int, role: RoleUpdate):
    """تحديث بيانات دور"""
    if _is_trial_permissions_user(request):
        return _trial_permissions_api_denied()
    check_permission(request, 'manage_roles')
    db = Database()
    try:
        existing = db.execute_query('SELECT id, name FROM roles WHERE id = %s', (role_id,))
        if not existing:
            return {"success": False, "message": "الدور غير موجود"}
        denial = _role_management_denial(
            request, existing[0], renaming=role.name is not None and role.name != existing[0]['name'])
        if denial:
            return {"success": False, "message": denial}

        updates = []
        params = []
        if role.name is not None:
            updates.append("name = %s")
            params.append(role.name)
        if role.description is not None:
            updates.append("description = %s")
            params.append(role.description)
        
        if not updates:
            return {"success": False, "message": "لا توجد بيانات للتحديث"}
        
        params.append(role_id)
        db.execute_query(f'''
            UPDATE roles SET {', '.join(updates)} WHERE id = %s
        ''', tuple(params))
        log_action(request, "update", "role", role_id, f"تعديل الدور: {existing[0]['name']}")

        return {"success": True, "message": "تم تحديث الدور بنجاح"}
    except Exception as e:
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            return {"success": False, "message": "اسم الدور موجود مسبقاً"}
        logger.exception("فشل تحديث دور")
        return {"success": False, "message": GENERIC_ERROR_MESSAGE}


@router.delete("/api/roles/{role_id}")
async def delete_role(request: Request, role_id: int):
    """حذف دور"""
    if _is_trial_permissions_user(request):
        return _trial_permissions_api_denied()
    check_permission(request, 'manage_roles')
    db = Database()
    try:
        # التحقق من عدم وجود مستخدمين مرتبطين
        users = db.execute_query('SELECT id FROM users WHERE role_id = %s', (role_id,))
        if users:
            return {"success": False, "message": "لا يمكن حذف الدور - يوجد مستخدمون مرتبطون به"}
        
        # التحقق من عدم كونه دوراً افتراضياً
        role = db.execute_query('SELECT is_default, name FROM roles WHERE id = %s', (role_id,))
        if not role:
            return {"success": False, "message": "الدور غير موجود"}
        if role[0]['is_default'] == 1 or role[0]['name'] == SUPERUSER_ROLE_NAME:
            return {"success": False, "message": "لا يمكن حذف الأدوار الافتراضية"}

        db.execute_query('DELETE FROM roles WHERE id = %s', (role_id,))
        log_action(request, "delete", "role", role_id, f"حذف الدور: {role[0]['name']}")
        return {"success": True, "message": "تم حذف الدور بنجاح"}
    except Exception:
        logger.exception("فشل حذف دور")
        return {"success": False, "message": GENERIC_ERROR_MESSAGE}


@router.put("/api/roles/{role_id}/permissions")
async def update_role_permissions(request: Request, role_id: int, data: RolePermissionsUpdate):
    """تحديث صلاحيات دور"""
    if _is_trial_permissions_user(request):
        return _trial_permissions_api_denied()
    check_permission(request, 'manage_roles')
    db = Database()

    try:
        role = db.execute_query(
            'SELECT id, name, is_default FROM roles WHERE id = %s',
            (role_id,)
        )

        if not role:
            return {
                "success": False,
                "message": "الدور غير موجود"
            }

        denial = _role_management_denial(request, role[0])
        if denial:
            return {"success": False, "message": denial}

        if role[0]["is_default"] == 1 and len(data.permission_ids) == 0:
            return {
                "success": False,
                "message": "لا يمكن إزالة جميع الصلاحيات من دور أساسي في النظام."
            }

        valid_permissions = db.execute_query(
            'SELECT id FROM permissions WHERE id = ANY(%s)',
            (data.permission_ids,)
        ) if data.permission_ids else []

        valid_permission_ids = {p["id"] for p in valid_permissions}

        invalid_ids = [
            permission_id for permission_id in data.permission_ids
            if permission_id not in valid_permission_ids
        ]

        if invalid_ids:
            return {
                "success": False,
                "message": "توجد صلاحيات غير صحيحة. يرجى تحديث الصفحة والمحاولة مرة أخرى."
            }

        # غير المدير العام لا يمنح صلاحية لا يملكها (يمنع رفع الصلاحيات الذاتي)
        if not is_superuser(_actor(request)):
            actor_codes = set(getattr(request.state, 'user_permissions', []) or [])
            current_ids = {r['permission_id'] for r in db.execute_query(
                'SELECT permission_id FROM role_permissions WHERE role_id = %s', (role_id,))}
            added_ids = set(data.permission_ids) - current_ids
            if added_ids:
                added = db.execute_query('SELECT code FROM permissions WHERE id = ANY(%s)', (list(added_ids),))
                if any(p['code'] not in actor_codes for p in added):
                    return {"success": False, "message": "لا يمكنك منح صلاحيات لا تملكها أنت"}

        with transaction():
            db.execute_query('DELETE FROM role_permissions WHERE role_id = %s', (role_id,))
            for permission_id in data.permission_ids:
                db.execute_query(
                    'INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
                    (role_id, permission_id)
                )
            log_action(request, "update", "role_permissions", role_id,
                       f"تعديل صلاحيات الدور: {role[0]['name']} ({len(data.permission_ids)} صلاحية)")

        return {
            "success": True,
            "message": "تم تحديث صلاحيات الدور بنجاح. تم تطبيق التغييرات على المستخدمين المرتبطين بهذا الدور."
        }

    except Exception:
        logger.exception("فشل تحديث صلاحيات الدور")
        return {"success": False, "message": GENERIC_ERROR_MESSAGE}


# ===== API المستخدمين =====

@router.post("/api/users")
async def create_user(request: Request, user: UserCreate):
    """إنشاء مستخدم جديد"""
    if _is_trial_permissions_user(request):
        return _trial_permissions_api_denied()
    check_permission(request, 'manage_users')
    db = Database()
    now = get_current_datetime(get_client_timestamp(request))[:16]  # YYYY-MM-DD HH:MM
    try:
        denial = _user_management_denial(request, db, None, new_role_id=user.role_id)
        if denial:
            return {"success": False, "message": denial}

        # إذا اختار المدير دور "نسخة تجريبية" فلا يكفي إنشاء مستخدم عادي؛
        # يجب تسجيله داخل trial_accounts وإنشاء جداوله المعزولة.
        from trial_mode import TRIAL_ROLE_NAME, ensure_trial_environment
        role = db.execute_query('SELECT name FROM roles WHERE id = %s', (user.role_id,))
        if role and role[0]['name'] == TRIAL_ROLE_NAME:
            existing = db.execute_query('SELECT id FROM users WHERE username = %s', (user.username,))
            if existing:
                return {"success": False, "message": "اسم المستخدم موجود مسبقاً"}

            conn = None
            cursor = None
            try:
                conn = db.get_connection()
                cursor = conn.cursor()
                result = ensure_trial_environment(
                    cursor,
                    username=user.username,
                    password=user.password,
                    full_name=user.full_name,
                    days=5,
                )
                conn.commit()
                if isinstance(result, dict) and not result.get('success', True):
                    return result
                created = db.execute_query('''
                    SELECT id, username, full_name, role_id, is_active, created_at
                    FROM users WHERE username = %s
                ''', (user.username,))
                return {
                    "success": True,
                    "data": dict(created[0]) if created else None,
                    "message": "تم إنشاء المستخدم التجريبي بنجاح وببيانات معزولة لمدة 5 أيام"
                }
            except Exception:
                if conn:
                    conn.rollback()
                raise
            finally:
                try:
                    if cursor:
                        cursor.close()
                except Exception:
                    pass
                if conn:
                    db.return_connection(conn)

        password_hash = hash_password(user.password)
        result = db.execute_query('''
            INSERT INTO users (username, full_name, password_hash, role_id, is_active, created_at)
            VALUES (%s, %s, %s, %s, 1, %s)
            RETURNING id, username, full_name, role_id, is_active, created_at
        ''', (user.username, user.full_name, password_hash, user.role_id, now))
        if result:
            log_action(request, "create", "user", result[0]['id'], f"إنشاء مستخدم: {user.username}")
            return {"success": True, "data": dict(result[0]), "message": "تم إنشاء المستخدم بنجاح"}
        return {"success": False, "message": "فشل إنشاء المستخدم"}
    except Exception as e:
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            return {"success": False, "message": "اسم المستخدم موجود مسبقاً"}
        logger.exception("فشل إنشاء مستخدم")
        return {"success": False, "message": GENERIC_ERROR_MESSAGE}


@router.put("/api/users/{user_id}")
async def update_user(request: Request, user_id: int, user: UserUpdate):
    """تحديث بيانات مستخدم"""
    if _is_trial_permissions_user(request):
        return _trial_permissions_api_denied()
    check_permission(request, 'manage_users')
    db = Database()
    try:
        current_user = db.execute_query('''
            SELECT u.id, u.username, u.full_name, u.is_active, r.name AS role_name
            FROM users u LEFT JOIN roles r ON r.id = u.role_id
            WHERE u.id = %s
        ''', (user_id,))
        if not current_user:
            return {"success": False, "message": "المستخدم غير موجود"}

        denial = _user_management_denial(
            request, db, current_user[0], new_role_id=user.role_id,
            changes_active=user.is_active is not None and user.is_active != current_user[0]['is_active'])
        if denial:
            return {"success": False, "message": denial}

        updates = []
        params = []
        if user.full_name is not None:
            updates.append("full_name = %s")
            params.append(user.full_name)
        if user.password is not None:
            password_hash = hash_password(user.password)
            updates.append("password_hash = %s")
            params.append(password_hash)
        if user.role_id is not None:
            updates.append("role_id = %s")
            params.append(user.role_id)
        if user.is_active is not None:
            updates.append("is_active = %s")
            params.append(user.is_active)
        
        if not updates:
            return {"success": False, "message": "لا توجد بيانات للتحديث"}
        
        params.append(user_id)
        db.execute_query(f'''
            UPDATE users SET {', '.join(updates)} WHERE id = %s
        ''', tuple(params))

        # إذا تم تحويل المستخدم إلى دور نسخة تجريبية، جهّز له بيئة معزولة فوراً.
        if user.role_id is not None:
            from trial_mode import TRIAL_ROLE_NAME, ensure_trial_environment
            role = db.execute_query('SELECT name FROM roles WHERE id = %s', (user.role_id,))
            if role and role[0]['name'] == TRIAL_ROLE_NAME:
                conn = None
                cursor = None
                try:
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    result = ensure_trial_environment(
                        cursor,
                        username=current_user[0]['username'],
                        password=user.password,
                        full_name=user.full_name or current_user[0]['full_name'],
                        days=5,
                    )
                    conn.commit()
                    if isinstance(result, dict) and not result.get('success', True):
                        return result
                except Exception:
                    if conn:
                        conn.rollback()
                    raise
                finally:
                    try:
                        if cursor:
                            cursor.close()
                    except Exception:
                        pass
                    if conn:
                        db.return_connection(conn)

        changed = [label for label, value in (("الاسم", user.full_name), ("كلمة المرور", user.password),
                                              ("الدور", user.role_id), ("الحالة", user.is_active)) if value is not None]
        log_action(request, "update", "user", user_id,
                   f"تعديل المستخدم {current_user[0]['username']}: {'، '.join(changed)}")
        return {"success": True, "message": "تم تحديث المستخدم بنجاح"}
    except Exception:
        logger.exception("فشل تحديث مستخدم")
        return {"success": False, "message": GENERIC_ERROR_MESSAGE}


@router.delete("/api/users/{user_id}")
async def delete_user(request: Request, user_id: int):
    """حذف مستخدم"""
    if _is_trial_permissions_user(request):
        return _trial_permissions_api_denied()
    check_permission(request, 'manage_users')
    db = Database()
    try:
        # لا يمكن حذف المستخدم الافتراضي (admin)
        user = db.execute_query('''
            SELECT u.id, u.username, r.name AS role_name, (ta.username IS NOT NULL) AS is_trial
            FROM users u
            LEFT JOIN roles r ON r.id = u.role_id
            LEFT JOIN trial_accounts ta ON ta.username = u.username
            WHERE u.id = %s
        ''', (user_id,))
        if not user:
            return {"success": False, "message": "المستخدم غير موجود"}
        if user[0]['username'] == 'admin':
            return {"success": False, "message": "لا يمكن حذف المستخدم الافتراضي (admin)"}
        if user[0]['id'] == _actor(request).get('id'):
            return {"success": False, "message": "لا يمكنك حذف حسابك بنفسك"}
        denial = _user_management_denial(request, db, user[0])
        if denial:
            return {"success": False, "message": denial}

        if user[0].get('is_trial'):
            from trial_mode import delete_trial_account
            result = delete_trial_account(user[0]['username'])
            if result.get('success'):
                log_action(request, "delete", "user", user_id, f"حذف الحساب التجريبي: {user[0]['username']}")
            return result

        db.execute_query('DELETE FROM users WHERE id = %s', (user_id,))
        log_action(request, "delete", "user", user_id, f"حذف المستخدم: {user[0]['username']}")
        return {"success": True, "message": "تم حذف المستخدم بنجاح"}
    except Exception:
        logger.exception("فشل حذف مستخدم")
        return {"success": False, "message": GENERIC_ERROR_MESSAGE}


@router.post("/api/users/{user_id}/toggle-active")
async def toggle_user_active(request: Request, user_id: int):
    """تبديل حالة تفعيل المستخدم"""
    if _is_trial_permissions_user(request):
        return _trial_permissions_api_denied()
    check_permission(request, 'manage_users')
    db = Database()
    try:
        user = db.execute_query('''
            SELECT u.id, u.username, u.is_active, r.name AS role_name
            FROM users u LEFT JOIN roles r ON r.id = u.role_id
            WHERE u.id = %s
        ''', (user_id,))
        if not user:
            return {"success": False, "message": "المستخدم غير موجود"}
        denial = _user_management_denial(request, db, user[0], changes_active=True)
        if denial:
            return {"success": False, "message": denial}

        new_status = 0 if user[0]['is_active'] == 1 else 1
        db.execute_query('UPDATE users SET is_active = %s WHERE id = %s', (new_status, user_id))
        status_text = "تفعيل" if new_status == 1 else "تعطيل"
        log_action(request, "update", "user", user_id, f"{status_text} المستخدم: {user[0]['username']}")
        return {"success": True, "message": f"تم {status_text} المستخدم بنجاح", "data": {"is_active": new_status}}
    except Exception:
        logger.exception("فشل تغيير حالة مستخدم")
        return {"success": False, "message": GENERIC_ERROR_MESSAGE}

# ===== API إدارة الحسابات التجريبية من صفحة الصلاحيات =====

class TrialAccountCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=4, max_length=100)
    days: int = Field(default=5, ge=1, le=30)


@router.get("/api/trial-accounts")
async def list_trial_accounts(request: Request):
    """عرض الحسابات التجريبية من داخل صفحة الصلاحيات."""
    if _is_trial_permissions_user(request):
        return _trial_permissions_api_denied()
    check_permission(request, 'manage_users')
    from trial_mode import get_all_trial_accounts
    return {"success": True, "data": get_all_trial_accounts()}


@router.post("/api/trial-accounts")
async def create_trial_account(request: Request, data: TrialAccountCreate):
    """إنشاء حساب تجريبي معزول من داخل صفحة الصلاحيات."""
    if _is_trial_permissions_user(request):
        return _trial_permissions_api_denied()
    check_permission(request, 'manage_users')

    import re
    username = data.username.strip()
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return {"success": False, "message": "اسم المستخدم يجب أن يحتوي على أحرف إنجليزية وأرقام وشرطة سفلية فقط"}

    db = Database()
    existing = db.execute_query('SELECT id FROM users WHERE username = %s', (username,))
    if existing:
        return {"success": False, "message": "اسم المستخدم موجود مسبقاً"}

    conn = None
    cursor = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        from trial_mode import ensure_trial_environment
        result = ensure_trial_environment(
            cursor,
            username=username,
            password=data.password,
            full_name=data.full_name.strip(),
            days=data.days,
        )
        conn.commit()
        if isinstance(result, dict) and not result.get('success', True):
            return result
        log_action(request, "create", "user", username, f"إنشاء حساب تجريبي: {username} ({data.days} أيام)")
        return {"success": True, "message": f"تم إنشاء الحساب التجريبي المعزول لمدة {data.days} يوم/أيام"}
    except Exception:
        logger.exception("فشل إنشاء حساب تجريبي")
        if conn:
            conn.rollback()
        return {"success": False, "message": GENERIC_ERROR_MESSAGE}
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        if conn:
            db.return_connection(conn)


@router.delete("/api/trial-accounts/{username}")
async def remove_trial_account(request: Request, username: str):
    """حذف حساب تجريبي مع بياناته المعزولة."""
    if _is_trial_permissions_user(request):
        return _trial_permissions_api_denied()
    check_permission(request, 'manage_users')
    from trial_mode import delete_trial_account
    result = delete_trial_account(username)
    if result.get('success'):
        log_action(request, "delete", "user", username, f"حذف الحساب التجريبي: {username}")
    return result

