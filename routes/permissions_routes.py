# ============================================
# permissions_routes.py - مسارات نظام الصلاحيات
# ============================================

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from database import Database
from models import RoleCreate, RoleUpdate, UserCreate, UserUpdate, RolePermissionsUpdate
from config import BASE_DIR, format_date, get_client_timestamp, get_current_datetime
from auth import hash_password, check_permission
from services.audit_service import log_action
from datetime import datetime as dt
from pydantic import BaseModel, Field
import os

router = APIRouter(prefix="/permissions")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# ===== صفحة الصلاحيات الرئيسية =====

@router.get("/", response_class=HTMLResponse)
async def permissions_page(request: Request):
    """صفحة إدارة الصلاحيات"""
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
            return {"success": True, "data": dict(result[0]), "message": "تم إنشاء الدور بنجاح"}
        return {"success": False, "message": "فشل إنشاء الدور"}
    except Exception as e:
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            return {"success": False, "message": "اسم الدور موجود مسبقاً"}
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.put("/api/roles/{role_id}")
async def update_role(request: Request, role_id: int, role: RoleUpdate):
    """تحديث بيانات دور"""
    check_permission(request, 'manage_roles')
    db = Database()
    try:
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
        
        return {"success": True, "message": "تم تحديث الدور بنجاح"}
    except Exception as e:
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            return {"success": False, "message": "اسم الدور موجود مسبقاً"}
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.delete("/api/roles/{role_id}")
async def delete_role(request: Request, role_id: int):
    """حذف دور"""
    check_permission(request, 'manage_roles')
    db = Database()
    try:
        # التحقق من عدم وجود مستخدمين مرتبطين
        users = db.execute_query('SELECT id FROM users WHERE role_id = %s', (role_id,))
        if users:
            return {"success": False, "message": "لا يمكن حذف الدور - يوجد مستخدمون مرتبطون به"}
        
        # التحقق من عدم كونه دوراً افتراضياً
        role = db.execute_query('SELECT is_default, name FROM roles WHERE id = %s', (role_id,))
        if role and role[0]['is_default'] == 1:
            return {"success": False, "message": "لا يمكن حذف الأدوار الافتراضية"}
        
        db.execute_query('DELETE FROM roles WHERE id = %s', (role_id,))
        return {"success": True, "message": "تم حذف الدور بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.put("/api/roles/{role_id}/permissions")
async def update_role_permissions(request: Request, role_id: int, data: RolePermissionsUpdate):
    """تحديث صلاحيات دور"""
    check_permission(request, 'manage_roles')
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()

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

        cursor.execute(
            'DELETE FROM role_permissions WHERE role_id = %s',
            (role_id,)
        )

        for permission_id in data.permission_ids:
            cursor.execute(
                'INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
                (role_id, permission_id)
            )

        conn.commit()

        return {
            "success": True,
            "message": "تم تحديث صلاحيات الدور بنجاح. تم تطبيق التغييرات على المستخدمين المرتبطين بهذا الدور."
        }

    except Exception as e:
        conn.rollback()
        return {
            "success": False,
            "message": f"تعذر تحديث الصلاحيات: {str(e)}"
        }

    finally:
        try:
            cursor.close()
        except Exception:
            pass
        if conn:
            db.return_connection(conn)


# ===== API المستخدمين =====

@router.post("/api/users")
async def create_user(request: Request, user: UserCreate):
    """إنشاء مستخدم جديد"""
    check_permission(request, 'manage_users')
    db = Database()
    now = get_current_datetime(get_client_timestamp(request))[:16]  # YYYY-MM-DD HH:MM
    try:
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
            return {"success": True, "data": dict(result[0]), "message": "تم إنشاء المستخدم بنجاح"}
        return {"success": False, "message": "فشل إنشاء المستخدم"}
    except Exception as e:
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            return {"success": False, "message": "اسم المستخدم موجود مسبقاً"}
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.put("/api/users/{user_id}")
async def update_user(request: Request, user_id: int, user: UserUpdate):
    """تحديث بيانات مستخدم"""
    check_permission(request, 'manage_users')
    db = Database()
    try:
        current_user = db.execute_query('SELECT username, full_name FROM users WHERE id = %s', (user_id,))
        if not current_user:
            return {"success": False, "message": "المستخدم غير موجود"}

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
        
        return {"success": True, "message": "تم تحديث المستخدم بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.delete("/api/users/{user_id}")
async def delete_user(request: Request, user_id: int):
    """حذف مستخدم"""
    check_permission(request, 'manage_users')
    db = Database()
    try:
        # لا يمكن حذف المستخدم الافتراضي (admin)
        user = db.execute_query('''
            SELECT u.username, (ta.username IS NOT NULL) AS is_trial
            FROM users u
            LEFT JOIN trial_accounts ta ON ta.username = u.username
            WHERE u.id = %s
        ''', (user_id,))
        if user and user[0]['username'] == 'admin':
            return {"success": False, "message": "لا يمكن حذف المستخدم الافتراضي (admin)"}

        if user and user[0].get('is_trial'):
            from trial_mode import delete_trial_account
            return delete_trial_account(user[0]['username'])
        
        db.execute_query('DELETE FROM users WHERE id = %s', (user_id,))
        return {"success": True, "message": "تم حذف المستخدم بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}


@router.post("/api/users/{user_id}/toggle-active")
async def toggle_user_active(request: Request, user_id: int):
    """تبديل حالة تفعيل المستخدم"""
    check_permission(request, 'manage_users')
    db = Database()
    try:
        user = db.execute_query('SELECT username, is_active FROM users WHERE id = %s', (user_id,))
        if not user:
            return {"success": False, "message": "المستخدم غير موجود"}
        if user[0]['username'] == 'admin':
            return {"success": False, "message": "لا يمكن تعطيل المستخدم الافتراضي"}
        
        new_status = 0 if user[0]['is_active'] == 1 else 1
        db.execute_query('UPDATE users SET is_active = %s WHERE id = %s', (new_status, user_id))
        status_text = "تفعيل" if new_status == 1 else "تعطيل"
        return {"success": True, "message": f"تم {status_text} المستخدم بنجاح", "data": {"is_active": new_status}}
    except Exception as e:
        return {"success": False, "message": f"خطأ: {str(e)}"}

# ===== API إدارة الحسابات التجريبية من صفحة الصلاحيات =====

class TrialAccountCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=4, max_length=100)
    days: int = Field(default=5, ge=1, le=30)


@router.get("/api/trial-accounts")
async def list_trial_accounts(request: Request):
    """عرض الحسابات التجريبية من داخل صفحة الصلاحيات."""
    check_permission(request, 'manage_users')
    from trial_mode import get_all_trial_accounts
    return {"success": True, "data": get_all_trial_accounts()}


@router.post("/api/trial-accounts")
async def create_trial_account(request: Request, data: TrialAccountCreate):
    """إنشاء حساب تجريبي معزول من داخل صفحة الصلاحيات."""
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
        return {"success": True, "message": f"تم إنشاء الحساب التجريبي المعزول لمدة {data.days} يوم/أيام"}
    except Exception as e:
        if conn:
            conn.rollback()
        return {"success": False, "message": f"تعذر إنشاء الحساب التجريبي: {str(e)}"}
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
    check_permission(request, 'manage_users')
    from trial_mode import delete_trial_account
    return delete_trial_account(username)

