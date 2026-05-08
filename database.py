# ============================================
# database.py - إدارة قاعدة البيانات SQLite (محلية)
# قاعدة بيانات محلية مضمنة داخل ملفات النظام
# ============================================

import sqlite3
import os
import re
import threading
from config import BASE_DIR, IS_VERCEL

# ===== مسار قاعدة البيانات =====
if IS_VERCEL:
    DB_DIR = "/tmp"
else:
    DB_DIR = BASE_DIR

DB_PATH = os.path.join(DB_DIR, "institute.db")

# ===== علامة تهيئة قاعدة البيانات =====
_db_initialized = False
_db_lock = threading.Lock()


def _ensure_db_dir():
    """التأكد من وجود مجلد قاعدة البيانات"""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
        except OSError:
            pass


class Database:
    """إدارة اتصال قاعدة البيانات SQLite - محلية"""
    
    def _get_connection(self):
        """الحصول على اتصال SQLite"""
        _ensure_db_dir()
        conn = sqlite3.connect(DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn
    
    def _convert_query(self, query: str, params) -> tuple:
        """تحويل استعلام PostgreSQL إلى SQLite"""
        # تحويل %s إلى ?
        sqlite_query = query.replace('%s', '?')
        return sqlite_query, params
    
    def execute_query(self, query: str, params=None) -> list:
        """تنفيذ استعلام وإرجاع النتائج"""
        if params is None:
            params = ()
        
        # تحويل الاستعلام
        sqlite_query, sqlite_params = self._convert_query(query, params)
        
        # معالجة RETURNING
        has_returning = bool(re.search(r'\bRETURNING\b', sqlite_query, re.IGNORECASE))
        
        if has_returning:
            # إزالة RETURNING clause
            sqlite_query = re.sub(r'\s+RETURNING\s+\w+', '', sqlite_query, flags=re.IGNORECASE)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(sqlite_query, sqlite_params)
            
            query_upper = sqlite_query.strip().upper()
            if query_upper.startswith('SELECT'):
                results = [dict(row) for row in cursor.fetchall()]
                return results
            elif has_returning:
                conn.commit()
                return [{'id': cursor.lastrowid}]
            else:
                conn.commit()
                return []
                
        except Exception as e:
            try:
                conn.rollback()
            except:
                pass
            raise e
        finally:
            try:
                cursor.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass
    
    def get_connection(self):
        """الحصول على اتصال مباشر - للاستخدام المتقدم"""
        return self._get_connection()
    
    def return_connection(self, conn):
        """إغلاق الاتصال"""
        try:
            conn.close()
        except:
            pass


def init_db():
    """تهيئة قاعدة البيانات - إنشاء الجداول إذا لم تكن موجودة"""
    global _db_initialized
    
    if _db_initialized:
        return
    
    with _db_lock:
        if _db_initialized:
            return
        
        db = Database()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        try:
            # جدول المواد الدراسية
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subjects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    study_type TEXT NOT NULL DEFAULT 'حضوري',
                    has_badge INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'مستمر',
                    barcode TEXT UNIQUE NOT NULL,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teachers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    total_fee INTEGER NOT NULL DEFAULT 0,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    institute_deduction_type TEXT DEFAULT 'percentage',
                    institute_deduction_value INTEGER DEFAULT 0,
                    teaching_types TEXT DEFAULT 'حضوري',
                    fee_in_person INTEGER DEFAULT 0,
                    fee_electronic INTEGER DEFAULT 0,
                    fee_blended INTEGER DEFAULT 0,
                    institute_pct_in_person INTEGER DEFAULT 0,
                    institute_pct_electronic INTEGER DEFAULT 0,
                    institute_pct_blended INTEGER DEFAULT 0,
                    inst_ded_type_in_person TEXT DEFAULT 'percentage',
                    inst_ded_type_electronic TEXT DEFAULT 'percentage',
                    inst_ded_type_blended TEXT DEFAULT 'percentage',
                    inst_ded_manual_in_person INTEGER DEFAULT 0,
                    inst_ded_manual_electronic INTEGER DEFAULT 0,
                    inst_ded_manual_blended INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS student_teacher (
                    student_id INTEGER NOT NULL,
                    teacher_id INTEGER NOT NULL,
                    study_type TEXT DEFAULT 'حضوري',
                    status TEXT DEFAULT 'مستمر',
                    notes TEXT DEFAULT '',
                    discount_type TEXT DEFAULT 'none',
                    discount_value INTEGER DEFAULT 0,
                    institute_waiver INTEGER DEFAULT 0,
                    PRIMARY KEY (student_id, teacher_id),
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS installments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    teacher_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    payment_date TEXT NOT NULL,
                    installment_type TEXT NOT NULL DEFAULT 'القسط الأول',
                    notes TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    for_installment TEXT DEFAULT '',
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teacher_withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    is_default INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    level TEXT DEFAULT 'view'
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role_id INTEGER NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
                )
            ''')
            
            # جداول الجدول الأسبوعي
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    capacity INTEGER DEFAULT 0,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS weekly_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    teacher_id INTEGER NOT NULL,
                    subject TEXT NOT NULL DEFAULT '',
                    day_of_week TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    event_type TEXT NOT NULL DEFAULT 'محاضرة',
                    notes TEXT DEFAULT '',
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()
            
            # ===== الفهارس =====
            try:
                cursor.execute('''
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_weekly_schedule_no_conflict
                    ON weekly_schedule (room_id, day_of_week, start_time, end_time)
                ''')
                conn.commit()
            except Exception:
                conn.rollback()
            
            try:
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_installment_student_teacher
                    ON installments (student_id, teacher_id)
                ''')
                conn.commit()
            except Exception:
                conn.rollback()
            
            # ===== إدراج البيانات الافتراضية =====
            existing_perms = cursor.execute("SELECT COUNT(*) as cnt FROM permissions")
            perm_count = existing_perms.fetchone()
            
            if perm_count and perm_count[0] == 0:
                # إدراج الصلاحيات الافتراضية
                default_permissions = [
                    ('view_dashboard', 'عرض لوحة التحكم', 'لوحة التحكم', 'عرض الصفحة الرئيسية والإحصائيات العامة', 'view'),
                    ('view_quick_stats', 'عرض الإحصائيات السريعة', 'لوحة التحكم', 'عرض الأرقام والإحصائيات المختصرة على الرئيسية', 'preview'),
                    ('export_backup', 'إنشاء نسخة احتياطية', 'لوحة التحكم', 'تصدير نسخة احتياطية كاملة من قاعدة البيانات', 'admin'),
                    ('view_students_list', 'عرض قائمة الطلاب', 'الطلاب', 'عرض أسماء الطلاب في القائمة فقط بدون تفاصيل', 'view'),
                    ('preview_students', 'معاينة بيانات الطالب', 'الطلاب', 'عرض ملف الطالب الكامل والتفاصيل والأرصدة', 'preview'),
                    ('add_students', 'إضافة طالب جديد', 'الطلاب', 'إنشاء سجل طالب جديد في النظام', 'edit'),
                    ('edit_students', 'تعديل بيانات الطالب', 'الطلاب', 'تعديل الاسم ونوع الدراسة والملاحظات', 'edit'),
                    ('delete_students', 'حذف طالب', 'الطلاب', 'حذف طالب نهائياً من النظام', 'admin'),
                    ('link_students', 'ربط الطلاب بالمدرسين', 'الطلاب', 'ربط أو إلغاء ربط طالب بمدرس', 'edit'),
                    ('edit_student_status', 'تغيير حالة الطالب', 'الطلاب', 'تغيير حالة الطالب', 'edit'),
                    ('view_teachers_list', 'عرض قائمة المدرسين', 'المدرسين', 'عرض أسماء المدرسين', 'view'),
                    ('preview_teachers', 'معاينة بيانات المدرس', 'المدرسين', 'عرض ملف المدرس الكامل', 'preview'),
                    ('add_teachers', 'إضافة مدرس جديد', 'المدرسين', 'إنشاء سجل مدرس جديد', 'edit'),
                    ('edit_teachers', 'تعديل بيانات المدرس', 'المدرسين', 'تعديل البيانات', 'edit'),
                    ('delete_teachers', 'حذف مدرس', 'المدرسين', 'حذف مدرس نهائياً', 'admin'),
                    ('view_teacher_balance', 'عرض رصيد المدرس', 'المدرسين', 'عرض الرصيد المتاح', 'preview'),
                    ('view_subjects', 'عرض المواد', 'المواد', 'عرض قائمة المواد', 'view'),
                    ('add_subjects', 'إضافة مادة', 'المواد', 'إضافة مادة دراسية جديدة', 'edit'),
                    ('edit_subjects', 'تعديل المادة', 'المواد', 'تعديل اسم المادة', 'edit'),
                    ('delete_subjects', 'حذف مادة', 'المواد', 'حذف مادة دراسية', 'admin'),
                    ('view_payments_list', 'عرض سجل الأقساط', 'الأقساط', 'عرض قائمة الأقساط', 'view'),
                    ('add_payments', 'تسجيل قسط جديد', 'الأقساط', 'تسجيل دفعة أو قسط', 'edit'),
                    ('delete_payments', 'حذف قسط', 'الأقساط', 'حذف قسط من السجل', 'admin'),
                    ('pay_installment', 'دفع قسط', 'الأقساط', 'دفع قسط من ملف الطالب', 'edit'),
                    ('print_receipt', 'طباعة سند قبض', 'الأقساط', 'طباعة سند القبض', 'preview'),
                    ('view_accounting', 'عرض صفحة المحاسبة', 'المحاسبة', 'عرض لوحة المحاسبة', 'view'),
                    ('preview_accounting_details', 'معاينة تفاصيل المحاسبة', 'المحاسبة', 'عرض التفاصيل المالية', 'preview'),
                    ('manage_commission', 'إدارة نسبة المعهد', 'المحاسبة', 'تعديل نسبة خصم المعهد', 'admin'),
                    ('view_withdrawals_list', 'عرض سجل السحوبات', 'السحوبات', 'عرض قائمة السحوبات', 'view'),
                    ('add_withdrawals', 'تسجيل سحب جديد', 'السحوبات', 'تسجيل سحب مبلغ', 'edit'),
                    ('delete_withdrawals', 'حذف سحب', 'السحوبات', 'حذف سجل سحب', 'admin'),
                    ('view_reports', 'عرض التقارير', 'التقارير', 'عرض التقارير', 'preview'),
                    ('print_reports', 'طباعة التقارير', 'التقارير', 'طباعة التقارير', 'edit'),
                    ('view_student_reports', 'تقارير الطلاب', 'التقارير', 'تقارير الطلاب', 'preview'),
                    ('view_teacher_reports', 'تقارير المدرسين', 'التقارير', 'تقارير المدرسين', 'preview'),
                    ('view_stats', 'عرض الإحصائيات', 'الإحصائيات', 'عرض لوحة الإحصائيات', 'view'),
                    ('view_permissions', 'عرض الصلاحيات', 'الصلاحيات', 'عرض صفحة الصلاحيات', 'preview'),
                    ('manage_users', 'إدارة المستخدمين', 'الصلاحيات', 'إضافة وتعديل وحذف المستخدمين', 'admin'),
                    ('manage_roles', 'إدارة الأدوار', 'الصلاحيات', 'إنشاء أدوار جديدة', 'admin'),
                    ('system_settings', 'إعدادات النظام', 'الصلاحيات', 'تغيير إعدادات النظام', 'admin'),
                ]
                
                for perm in default_permissions:
                    try:
                        cursor.execute(
                            'INSERT OR IGNORE INTO permissions (code, name, category, description, level) VALUES (?, ?, ?, ?, ?)',
                            perm
                        )
                    except Exception:
                        pass
                
                conn.commit()
                
                # إدراج الأدوار
                from datetime import datetime as dt
                now = dt.now().strftime('%Y-%m-%d %H:%M')
                
                default_roles = [
                    ('مدير عام', 'التحكم الكامل بجميع أقسام النظام', 1),
                    ('محاسب', 'إدارة العمليات المالية', 0),
                    ('مدخل بيانات', 'إضافة وتعديل البيانات', 0),
                    ('مشاهد', 'عرض البيانات فقط', 0),
                ]
                
                for role_name, role_desc, is_default in default_roles:
                    try:
                        cursor.execute(
                            'INSERT OR IGNORE INTO roles (name, description, is_default, created_at) VALUES (?, ?, ?, ?)',
                            (role_name, role_desc, is_default, now)
                        )
                    except Exception:
                        pass
                
                conn.commit()
                
                # إعطاء جميع الصلاحيات للمدير العام
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                        SELECT r.id, p.id FROM roles r, permissions p
                        WHERE r.name = 'مدير عام'
                    ''')
                    conn.commit()
                except Exception:
                    conn.rollback()
                
                # إنشاء مستخدم مدير افتراضي
                try:
                    import bcrypt
                    admin_pass_hash = bcrypt.hashpw('1111'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                except ImportError:
                    import hashlib
                    admin_pass_hash = hashlib.sha256('1111'.encode()).hexdigest()

                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO users (username, full_name, password_hash, role_id, is_active, created_at)
                        SELECT 'admin', 'المدير العام', ?, r.id, 1, ?
                        FROM roles r WHERE r.name = 'مدير عام'
                    ''', (admin_pass_hash, now))
                    conn.commit()
                except Exception:
                    conn.rollback()
            
            _db_initialized = True
            
        except Exception as e:
            try:
                conn.rollback()
            except:
                pass
            print(f"تحذير في تهيئة قاعدة البيانات: {e}")
        finally:
            try:
                cursor.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass
