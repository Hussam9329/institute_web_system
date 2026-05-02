# ============================================
# database.py - إدارة قاعدة البيانات PostgreSQL (Neon)
# ============================================

import psycopg2
import psycopg2.extras
import os
from config import DATABASE_URL

class Database:
    """إدارة اتصال وقاعدة البيانات PostgreSQL"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات PostgreSQL"""
        connection = psycopg2.connect(DATABASE_URL)
        connection.autocommit = False
        return connection
    
    def execute_query(self, query: str, params: tuple = ()) -> list:
        """تنفيذ استعلام وإرجاع النتائج"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            cursor.execute(query, params)
            
            # إذا كان الاستعلام SELECT، أرجع النتائج
            query_upper = query.strip().upper()
            if query_upper.startswith('SELECT'):
                results = cursor.fetchall()
                return results
            # إذا كان الاستعلام يحتوي على RETURNING (INSERT/UPDATE/DELETE)
            elif 'RETURNING' in query_upper:
                results = cursor.fetchall()
                conn.commit()
                return results
            else:
                conn.commit()
                return []
                
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()


def init_db():
    """تهيئة قاعدة البيانات - إنشاء الجداول إذا لم تكن موجودة"""
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    try:
        # جدول المواد الدراسية
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                study_type VARCHAR(20) CHECK(study_type IN ('حضوري', 'الكتروني', 'مدمج')) DEFAULT 'حضوري',
                has_badge INTEGER NOT NULL DEFAULT 0,
                status VARCHAR(20) NOT NULL DEFAULT 'مستمر',
                barcode VARCHAR(50) UNIQUE NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teachers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                subject VARCHAR(50) NOT NULL,
                total_fee INTEGER NOT NULL DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_teacher (
                student_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                study_type VARCHAR(20) DEFAULT 'حضوري',
                status VARCHAR(20) DEFAULT 'مستمر',
                notes TEXT DEFAULT '',
                PRIMARY KEY (student_id, teacher_id),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS installments (
                id SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                payment_date TEXT NOT NULL,
                installment_type VARCHAR(30) NOT NULL DEFAULT 'القسط الأول',
                notes TEXT DEFAULT '',
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teacher_withdrawals (
                id SERIAL PRIMARY KEY,
                teacher_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                withdrawal_date TEXT NOT NULL,
                notes TEXT DEFAULT '',
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            )
        ''')
        
        # ===== جداول نظام الصلاحيات =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS permissions (
                id SERIAL PRIMARY KEY,
                code VARCHAR(80) NOT NULL UNIQUE,
                name VARCHAR(100) NOT NULL,
                category VARCHAR(50) NOT NULL,
                description TEXT DEFAULT ''
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                PRIMARY KEY (role_id, permission_id),
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
                FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                full_name VARCHAR(100) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role_id INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
            )
        ''')
        
        conn.commit()
        
        # ===== إدراج الصلاحيات الافتراضية =====
        default_permissions = [
            # الطلاب
            ('view_students', 'عرض الطلاب', 'الطلاب', 'عرض قائمة الطلاب وبياناتهم'),
            ('add_students', 'إضافة طلاب', 'الطلاب', 'إضافة طالب جديد'),
            ('edit_students', 'تعديل الطلاب', 'الطلاب', 'تعديل بيانات الطالب'),
            ('delete_students', 'حذف الطلاب', 'الطلاب', 'حذف طالب من النظام'),
            # المدرسين
            ('view_teachers', 'عرض المدرسين', 'المدرسين', 'عرض قائمة المدرسين وبياناتهم'),
            ('add_teachers', 'إضافة مدرسين', 'المدرسين', 'إضافة مدرس جديد'),
            ('edit_teachers', 'تعديل المدرسين', 'المدرسين', 'تعديل بيانات المدرس'),
            ('delete_teachers', 'حذف المدرسين', 'المدرسين', 'حذف مدرس من النظام'),
            # المواد
            ('view_subjects', 'عرض المواد', 'المواد', 'عرض قائمة المواد'),
            ('add_subjects', 'إضافة مواد', 'المواد', 'إضافة مادة جديدة'),
            ('edit_subjects', 'تعديل المواد', 'المواد', 'تعديل اسم المادة'),
            ('delete_subjects', 'حذف المواد', 'المواد', 'حذف مادة من النظام'),
            # الأقساط
            ('view_payments', 'عرض الأقساط', 'الأقساط', 'عرض سجل الأقساط والمدفوعات'),
            ('add_payments', 'إضافة أقساط', 'الأقساط', 'تسجيل قسط جديد'),
            ('delete_payments', 'حذف الأقساط', 'الأقساط', 'حذف قسط من السجل'),
            # المحاسبة
            ('view_accounting', 'عرض المحاسبة', 'المحاسبة', 'عرض صفحة المحاسبة والأرصدة'),
            # السحوبات
            ('view_withdrawals', 'عرض السحوبات', 'السحوبات', 'عرض سجل السحوبات'),
            ('add_withdrawals', 'إضافة سحوبات', 'السحوبات', 'تسجيل سحب جديد'),
            # الإحصائيات
            ('view_stats', 'عرض الإحصائيات', 'الإحصائيات', 'عرض لوحة الإحصائيات'),
            # الصلاحيات
            ('manage_permissions', 'إدارة الصلاحيات', 'الصلاحيات', 'إدارة المستخدمين والأدوار والصلاحيات'),
            # التصدير
            ('export_data', 'تصدير البيانات', 'التصدير', 'تصدير نسخة احتياطية من البيانات'),
        ]
        
        for perm in default_permissions:
            try:
                cursor.execute(
                    'INSERT INTO permissions (code, name, category, description) VALUES (%s, %s, %s, %s) ON CONFLICT (code) DO NOTHING',
                    perm
                )
            except Exception:
                pass
        
        conn.commit()
        
        # ===== إدراج الأدوار الافتراضية =====
        from datetime import datetime as dt
        now = dt.now().strftime('%Y-%m-%d %H:%M')
        
        default_roles = [
            ('مدير عام', 'التحكم الكامل بجميع أقسام النظام', 1),
            ('محاسب', 'إدارة العمليات المالية والأقساط والسحوبات', 0),
            ('مشاهد', 'عرض البيانات فقط بدون إضافة أو تعديل أو حذف', 0),
        ]
        
        for role_name, role_desc, is_default in default_roles:
            try:
                cursor.execute(
                    'INSERT INTO roles (name, description, is_default, created_at) VALUES (%s, %s, %s, %s) ON CONFLICT (name) DO NOTHING',
                    (role_name, role_desc, is_default, now)
                )
            except Exception:
                pass
        
        conn.commit()
        
        # ===== إعطاء جميع الصلاحيات لدور المدير العام =====
        try:
            cursor.execute('''
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id FROM roles r, permissions p
                WHERE r.name = 'مدير عام'
                ON CONFLICT (role_id, permission_id) DO NOTHING
            ''')
            conn.commit()
        except Exception:
            conn.rollback()
        
        # ===== إعطاء صلاحيات المحاسب =====
        accountant_perms = [
            'view_students', 'add_students', 'edit_students',
            'view_teachers',
            'view_subjects',
            'view_payments', 'add_payments',
            'view_accounting',
            'view_withdrawals', 'add_withdrawals',
            'view_stats',
        ]
        try:
            for perm_code in accountant_perms:
                cursor.execute('''
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT r.id, p.id FROM roles r, permissions p
                    WHERE r.name = 'محاسب' AND p.code = %s
                    ON CONFLICT (role_id, permission_id) DO NOTHING
                ''', (perm_code,))
            conn.commit()
        except Exception:
            conn.rollback()
        
        # ===== إعطاء صلاحيات المشاهد =====
        viewer_perms = [
            'view_students', 'view_teachers', 'view_subjects',
            'view_payments', 'view_accounting', 'view_withdrawals', 'view_stats',
        ]
        try:
            for perm_code in viewer_perms:
                cursor.execute('''
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT r.id, p.id FROM roles r, permissions p
                    WHERE r.name = 'مشاهد' AND p.code = %s
                    ON CONFLICT (role_id, permission_id) DO NOTHING
                ''', (perm_code,))
            conn.commit()
        except Exception:
            conn.rollback()
        
        # ===== إنشاء مستخدم مدير افتراضي =====
        import hashlib
        try:
            admin_pass_hash = hashlib.sha256('1111'.encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (username, full_name, password_hash, role_id, is_active, created_at)
                SELECT 'admin', 'المدير العام', %s, r.id, 1, %s
                FROM roles r WHERE r.name = 'مدير عام'
                ON CONFLICT (username) DO NOTHING
            ''', (admin_pass_hash, now))
            conn.commit()
        except Exception:
            conn.rollback()
        
        # ===== ALTER TABLE - إضافة أعمدة جديدة للجداول الموجودة =====
        alter_statements = [
            # إصلاح CHECK constraint لجدول الطلاب - إضافة 'مدمج' و 'غير مربوط'
            "ALTER TABLE students DROP CONSTRAINT IF EXISTS students_study_type_check",
            "ALTER TABLE students ADD CONSTRAINT students_study_type_check CHECK(study_type IN ('حضوري', 'الكتروني', 'مدمج'))",
            "ALTER TABLE students DROP CONSTRAINT IF EXISTS students_status_check",
            "ALTER TABLE students ADD CONSTRAINT students_status_check CHECK(status IN ('مستمر', 'منسحب', 'غير مربوط'))",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_deduction_type VARCHAR(20) DEFAULT 'percentage'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_deduction_value INTEGER DEFAULT 0",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'مستمر'",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT ''",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS study_type VARCHAR(20) DEFAULT 'حضوري'",
            # أعمدة أنواع التدريس المتعددة
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS teaching_types TEXT DEFAULT 'حضوري'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS fee_in_person INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS fee_electronic INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS fee_blended INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_pct_in_person INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_pct_electronic INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_pct_blended INTEGER DEFAULT 0",
            # نوع الخصم لكل نوع تدريس: percentage أو manual
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_type_in_person VARCHAR(10) DEFAULT 'percentage'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_type_electronic VARCHAR(10) DEFAULT 'percentage'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_type_blended VARCHAR(10) DEFAULT 'percentage'",
            # المبلغ اليدوي للخصم لكل نوع تدريس
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_manual_in_person INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_manual_electronic INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_manual_blended INTEGER DEFAULT 0",
        ]
        
        for stmt in alter_statements:
            try:
                cursor.execute(stmt)
                conn.commit()
            except Exception:
                conn.rollback()
                pass  # العمود موجود مسبقاً
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def get_db():
    """Dependency للحصول على اتصال قاعدة البيانات في FastAPI"""
    db = Database()
    try:
        yield db.get_connection()
    finally:
        pass
