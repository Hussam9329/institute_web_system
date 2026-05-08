# ============================================
# database.py - إدارة قاعدة البيانات PostgreSQL (Neon)
# محسّن لبيئة Vercel Serverless مع Connection Pooling
# ============================================

import psycopg2
import psycopg2.extras
import psycopg2.pool
import os
import threading
from config import DATABASE_URL, IS_VERCEL

# ===== علامة تهيئة قاعدة البيانات =====
_db_initialized = False

# ===== Connection Pool =====
_connection_pool = None
_pool_lock = threading.Lock()

def _get_pool():
    """الحصول على أو إنشاء Connection Pool"""
    global _connection_pool
    if _connection_pool is not None:
        return _connection_pool
    
    with _pool_lock:
        if _connection_pool is not None:
            return _connection_pool
        
        if not DATABASE_URL:
            raise ConnectionError(
                "رابط قاعدة البيانات (DATABASE_URL) غير معين! "
                "يرجى تعيينه كمتغير بيئة."
            )
        try:
            _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=5,
                dsn=DATABASE_URL,
                connect_timeout=8,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
            return _connection_pool
        except Exception as e:
            # إذا فشل Pool، نعيد تعيينه للمحاولة لاحقاً
            _connection_pool = None
            raise ConnectionError(f"فشل إنشاء Connection Pool: {e}")

class Database:
    """إدارة اتصال وقاعدة البيانات PostgreSQL - محسّن مع Connection Pooling"""
    
    def get_connection(self):
        """الحصول على اتصال من Connection Pool"""
        if not DATABASE_URL:
            raise ConnectionError(
                "رابط قاعدة البيانات (DATABASE_URL) غير معين! "
                "يرجى تعيينه كمتغير بيئة."
            )
        try:
            pool = _get_pool()
            conn = pool.getconn()
            conn.autocommit = False
            return conn
        except Exception as e:
            # إذا فشل Pool، نحاول اتصال مباشر
            try:
                connection = psycopg2.connect(
                    DATABASE_URL,
                    connect_timeout=8,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=5
                )
                connection.autocommit = False
                return connection
            except psycopg2.OperationalError as oe:
                raise ConnectionError(f"فشل الاتصال بقاعدة البيانات: {oe}")
    
    def return_connection(self, conn):
        """إرجاع الاتصال إلى Pool"""
        global _connection_pool
        if _connection_pool is not None:
            try:
                _connection_pool.putconn(conn)
                return
            except Exception:
                pass
        # Fallback: إغلاق الاتصال مباشر
        try:
            conn.close()
        except Exception:
            pass
    
    def execute_query(self, query: str, params: tuple = ()) -> list:
        """تنفيذ استعلام وإرجاع النتائج"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            cursor.execute(query, params)
            
            query_upper = query.strip().upper()
            if query_upper.startswith('SELECT'):
                results = cursor.fetchall()
                return results
            elif 'RETURNING' in query_upper:
                results = cursor.fetchall()
                conn.commit()
                return results
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
            self.return_connection(conn)


def init_db():
    """تهيئة قاعدة البيانات - إنشاء الجداول إذا لم تكن موجودة"""
    global _db_initialized
    
    if not DATABASE_URL:
        print("تحذير: DATABASE_URL غير معين - لم يتم تهيئة قاعدة البيانات")
        return
    
    # تخطي إذا تم التهيئة مسبقاً في نفس العملية
    if _db_initialized:
        return
    
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
                created_at TEXT NOT NULL,
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
                description TEXT DEFAULT '',
                level VARCHAR(20) DEFAULT 'view'
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
        
        # جداول الجدول الأسبوعي
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                capacity INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weekly_schedule (
                id SERIAL PRIMARY KEY,
                room_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                subject VARCHAR(100) NOT NULL DEFAULT '',
                day_of_week VARCHAR(20) NOT NULL,
                start_time VARCHAR(5) NOT NULL,
                end_time VARCHAR(5) NOT NULL,
                event_type VARCHAR(20) NOT NULL DEFAULT 'محاضرة',
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
                CREATE UNIQUE INDEX IF NOT EXISTS idx_installment_unique_type
                ON installments (student_id, teacher_id, installment_type)
                WHERE installment_type != 'دفعات'
            ''')
            conn.commit()
        except Exception:
            conn.rollback()
        
        # ===== إدراج البيانات الافتراضية (فقط إذا لم تكن موجودة) =====
        # فحص هل توجد صلاحيات مسبقاً
        existing_perms = cursor.execute("SELECT COUNT(*) as cnt FROM permissions")
        perm_count = cursor.fetchone()
        
        if perm_count and perm_count[0] == 0:
            # إدراج الصلاحيات الافتراضية دفعة واحدة
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
                        'INSERT INTO permissions (code, name, category, description, level) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (code) DO NOTHING',
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
                        'INSERT INTO roles (name, description, is_default, created_at) VALUES (%s, %s, %s, %s) ON CONFLICT (name) DO NOTHING',
                        (role_name, role_desc, is_default, now)
                    )
                except Exception:
                    pass
            
            conn.commit()
            
            # إعطاء جميع الصلاحيات للمدير العام
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
            
            # إنشاء مستخدم مدير افتراضي
            try:
                import bcrypt
                admin_pass_hash = bcrypt.hashpw('1111'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            except ImportError:
                import hashlib
                admin_pass_hash = hashlib.sha256('1111'.encode()).hexdigest()

            try:
                cursor.execute('''
                    INSERT INTO users (username, full_name, password_hash, role_id, is_active, created_at)
                    SELECT 'admin', 'المدير العام', %s, r.id, 1, %s
                    FROM roles r WHERE r.name = 'مدير عام'
                    ON CONFLICT (username) DO NOTHING
                ''', (admin_pass_hash, now))
                conn.commit()
            except Exception:
                conn.rollback()
        
        # ===== ALTER TABLE - إضافة أعمدة جديدة =====
        alter_statements = [
            "ALTER TABLE permissions ADD COLUMN IF NOT EXISTS level VARCHAR(20) DEFAULT 'view'",
            "ALTER TABLE students DROP CONSTRAINT IF EXISTS students_study_type_check",
            "ALTER TABLE students ADD CONSTRAINT students_study_type_check CHECK(study_type IN ('حضوري', 'الكتروني', 'مدمج'))",
            "ALTER TABLE students DROP CONSTRAINT IF EXISTS students_status_check",
            "ALTER TABLE students ADD CONSTRAINT students_status_check CHECK(status IN ('مستمر', 'منسحب', 'غير مربوط'))",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_deduction_type VARCHAR(20) DEFAULT 'percentage'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_deduction_value INTEGER DEFAULT 0",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'مستمر'",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT ''",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS study_type VARCHAR(20) DEFAULT 'حضوري'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS teaching_types TEXT DEFAULT 'حضوري'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS fee_in_person INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS fee_electronic INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS fee_blended INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_pct_in_person INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_pct_electronic INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS institute_pct_blended INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_type_in_person VARCHAR(10) DEFAULT 'percentage'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_type_electronic VARCHAR(10) DEFAULT 'percentage'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_type_blended VARCHAR(10) DEFAULT 'percentage'",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_manual_in_person INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_manual_electronic INTEGER DEFAULT 0",
            "ALTER TABLE teachers ADD COLUMN IF NOT EXISTS inst_ded_manual_blended INTEGER DEFAULT 0",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS discount_type VARCHAR(20) DEFAULT 'none'",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS discount_value INTEGER DEFAULT 0",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS institute_waiver INTEGER DEFAULT 0",
            "ALTER TABLE weekly_schedule ADD COLUMN IF NOT EXISTS event_type VARCHAR(20) DEFAULT 'محاضرة'",
            "ALTER TABLE installments ADD COLUMN IF NOT EXISTS created_at TEXT DEFAULT ''",
            "ALTER TABLE installments DROP CONSTRAINT IF EXISTS installments_installment_type_check",
            "ALTER TABLE installments ADD CONSTRAINT installments_installment_type_check CHECK(installment_type IN ('القسط الأول', 'القسط الثاني', 'دفع كامل', 'دفعات'))",
            "ALTER TABLE installments ADD COLUMN IF NOT EXISTS for_installment VARCHAR(30) DEFAULT ''",
            "ALTER TABLE student_teacher DROP CONSTRAINT IF EXISTS student_teacher_institute_waiver_check",
            "ALTER TABLE student_teacher ADD CONSTRAINT student_teacher_institute_waiver_check CHECK(institute_waiver IN (0, 1))",
        ]
        
        for stmt in alter_statements:
            try:
                cursor.execute(stmt)
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except:
                    pass
        
        _db_initialized = True
        
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        # لا نرفع الخطأ - نسمح للتطبيق بالعمل حتى لو فشلت التهيئة
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
