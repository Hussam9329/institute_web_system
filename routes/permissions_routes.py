# ============================================
# permissions_routes.py - مسارات نظام الصلاحيات
# ============================================

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from database import Database
from models import RoleCreate, RoleUpdate, UserCreate, UserUpdate, RolePermissionsUpdate
from config import BASE_DIR, format_date
from auth import hash_password, check_permission
from datetime import datetime as dt
import os

router = APIRouter(prefix="/permissions")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# ===== صفحة الصلاحيات الرئيسية =====

@router.get("/", response_class=HTMLResponse)
async def permissions_page(request: Request):
    """صفحة إدارة الصلاحيات"""
    check_permission(request, 'view_permissions')
    db = Database()
    
    # جلب المستخدمين مع أسماء الأدوار
    users = db.execute_query('''
        SELECT u.*, r.name as role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
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
    
    return templates.TemplateResponse("permissions/index.html", {
        "request": request,
        "users": users,
        "roles": roles,
        "permissions_by_category": permissions_by_category,
        "role_permissions_map": role_permissions_map,
    })


# ===== API الأدوار =====

@router.post("/api/roles")
async def create_role(request: Request, role: RoleCreate):
    """إنشاء دور جديد"""
    check_permission(request, 'manage_roles')
    db = Database()
    now = dt.now().strftime('%Y-%m-%d %H:%M')
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
        # حذف الصلاحيات الحالية
        cursor.execute('DELETE FROM role_permissions WHERE role_id = ?', (role_id,))
        
        # إضافة الصلاحيات الجديدة
        for perm_id in data.permission_ids:
            cursor.execute(
                'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                (role_id, perm_id)
            )
        
        conn.commit()
        return {"success": True, "message": "تم تحديث الصلاحيات بنجاح"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"خطأ: {str(e)}"}
    finally:
        cursor.close()
        conn.close()


# ===== API المستخدمين =====

@router.post("/api/users")
async def create_user(request: Request, user: UserCreate):
    """إنشاء مستخدم جديد"""
    check_permission(request, 'manage_users')
    db = Database()
    now = dt.now().strftime('%Y-%m-%d %H:%M')
    try:
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
        user = db.execute_query('SELECT username FROM users WHERE id = %s', (user_id,))
        if user and user[0]['username'] == 'admin':
            return {"success": False, "message": "لا يمكن حذف المستخدم الافتراضي (admin)"}
        
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
