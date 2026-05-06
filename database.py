# ============================================
# database.py - إدارة قاعدة البيانات PostgreSQL (Neon)
# ============================================

import psycopg2
import psycopg2.extras
import os
from config import DATABASE_URL, DB_AVAILABLE

class Database:
    """إدارة اتصال وقاعدة البيانات PostgreSQL"""
    
    # لا نستخدم Singleton لأن serverless يحتاج اتصالات جديدة
    # كل طلب يحصل على كائن Database خاص به
    
    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات PostgreSQL"""
        if not DATABASE_URL:
            raise ConnectionError(
                "رابط قاعدة البيانات (DATABASE_URL) غير معين! "
                "يرجى تعيينه كمتغير بيئة. "
                "مثال: export DATABASE_URL=\"postgresql://user:pass@host/db\""
            )
        try:
            connection = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            connection.autocommit = False
            return connection
        except psycopg2.OperationalError as e:
            raise ConnectionError(f"فشل الاتصال بقاعدة البيانات: {e}")
    
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
    if not DATABASE_URL:
        print("تحذير: DATABASE_URL غير معين - لم يتم تهيئة قاعدة البيانات")
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
        
        conn.commit()
        
        # ===== إدراج الصلاحيات الافتراضية =====
        # المستوى: view=عرض فقط, preview=معاينة, edit=تعديل, admin=إدارة كاملة
        default_permissions = [
            # ===== لوحة التحكم (الرئيسية) =====
            ('view_dashboard', 'عرض لوحة التحكم', 'لوحة التحكم', 'عرض الصفحة الرئيسية والإحصائيات العامة', 'view'),
            ('view_quick_stats', 'عرض الإحصائيات السريعة', 'لوحة التحكم', 'عرض الأرقام والإحصائيات المختصرة على الرئيسية', 'preview'),
            ('export_backup', 'إنشاء نسخة احتياطية', 'لوحة التحكم', 'تصدير نسخة احتياطية كاملة من قاعدة البيانات', 'admin'),

            # ===== الطلاب =====
            ('view_students_list', 'عرض قائمة الطلاب', 'الطلاب', 'عرض أسماء الطلاب في القائمة فقط بدون تفاصيل', 'view'),
            ('preview_students', 'معاينة بيانات الطالب', 'الطلاب', 'عرض ملف الطالب الكامل والتفاصيل والأرصدة', 'preview'),
            ('add_students', 'إضافة طالب جديد', 'الطلاب', 'إنشاء سجل طالب جديد في النظام', 'edit'),
            ('edit_students', 'تعديل بيانات الطالب', 'الطلاب', 'تعديل الاسم ونوع الدراسة والملاحظات', 'edit'),
            ('delete_students', 'حذف طالب', 'الطلاب', 'حذف طالب نهائياً من النظام (لا يمكن حذف طالب مرتبط بمدرسين)', 'admin'),
            ('link_students', 'ربط الطلاب بالمدرسين', 'الطلاب', 'ربط أو إلغاء ربط طالب بمدرس', 'edit'),
            ('edit_student_status', 'تغيير حالة الطالب', 'الطلاب', 'تغيير حالة الطالب (مستمر/منسحب/غير مربوط)', 'edit'),

            # ===== المدرسين =====
            ('view_teachers_list', 'عرض قائمة المدرسين', 'المدرسين', 'عرض أسماء المدرسين في القائمة فقط', 'view'),
            ('preview_teachers', 'معاينة بيانات المدرس', 'المدرسين', 'عرض ملف المدرس الكامل والتفاصيل المالية والطلاب', 'preview'),
            ('add_teachers', 'إضافة مدرس جديد', 'المدرسين', 'إنشاء سجل مدرس جديد مع تحديد الأجور والنسب', 'edit'),
            ('edit_teachers', 'تعديل بيانات المدرس', 'المدرسين', 'تعديل البيانات الشخصية والأجور ونسب المعهد', 'edit'),
            ('delete_teachers', 'حذف مدرس', 'المدرسين', 'حذف مدرس نهائياً من النظام (لا يمكن حذف مدرس لديه طلاب)', 'admin'),
            ('view_teacher_balance', 'عرض رصيد المدرس', 'المدرسين', 'عرض الرصيد المتاح والتفاصيل المالية للمدرس', 'preview'),

            # ===== المواد الدراسية =====
            ('view_subjects', 'عرض المواد', 'المواد', 'عرض قائمة المواد الدراسية', 'view'),
            ('add_subjects', 'إضافة مادة', 'المواد', 'إضافة مادة دراسية جديدة', 'edit'),
            ('edit_subjects', 'تعديل المادة', 'المواد', 'تعديل اسم المادة الدراسية', 'edit'),
            ('delete_subjects', 'حذف مادة', 'المواد', 'حذف مادة دراسية من النظام', 'admin'),

            # ===== الأقساط والمدفوعات =====
            ('view_payments_list', 'عرض سجل الأقساط', 'الأقساط', 'عرض قائمة الأقساط المسجلة في النظام', 'view'),
            ('add_payments', 'تسجيل قسط جديد', 'الأقساط', 'تسجيل دفعة أو قسط لطالب عند مدرس', 'edit'),
            ('delete_payments', 'حذف قسط', 'الأقساط', 'حذف قسط من السجل نهائياً', 'admin'),
            ('pay_installment', 'دفع قسط من ملف الطالب', 'الأقساط', 'زر دفع القسط من داخل ملف الطالب', 'edit'),
            ('print_receipt', 'طباعة سند قبض', 'الأقساط', 'طباعة أو معاينة سند القبض بعد الدفع', 'preview'),

            # ===== المحاسبة =====
            ('view_accounting', 'عرض صفحة المحاسبة', 'المحاسبة', 'عرض لوحة المحاسبة وملخص الأرصدة', 'view'),
            ('preview_accounting_details', 'معاينة تفاصيل المحاسبة', 'المحاسبة', 'عرض التفاصيل المالية الكاملة لكل مدرس', 'preview'),
            ('manage_commission', 'إدارة نسبة المعهد', 'المحاسبة', 'تعديل نسبة أو مبلغ خصم المعهد من المدرسين', 'admin'),

            # ===== السحوبات =====
            ('view_withdrawals_list', 'عرض سجل السحوبات', 'السحوبات', 'عرض قائمة السحوبات المسجلة', 'view'),
            ('add_withdrawals', 'تسجيل سحب جديد', 'السحوبات', 'تسجيل سحب مبلغ من رصيد المدرس', 'edit'),
            ('delete_withdrawals', 'حذف سحب', 'السحوبات', 'حذف سجل سحب من النظام', 'admin'),

            # ===== التقارير =====
            ('view_reports', 'عرض التقارير', 'التقارير', 'عرض ومعاينة التقارير المختلفة', 'preview'),
            ('print_reports', 'طباعة التقارير', 'التقارير', 'طباعة أو تصدير التقارير', 'edit'),
            ('view_student_reports', 'تقارير الطلاب', 'التقارير', 'تقارير خاصة بالطلاب ومبالغهم المدفوعة والمتبقية', 'preview'),
            ('view_teacher_reports', 'تقارير المدرسين', 'التقارير', 'تقارير خاصة بالمدرسين وأرصدتهم وسحوباتهم', 'preview'),

            # ===== الإحصائيات =====
            ('view_stats', 'عرض الإحصائيات', 'الإحصائيات', 'عرض لوحة الإحصائيات والرسوم البيانية', 'view'),

            # ===== الصلاحيات وإدارة النظام =====
            ('view_permissions', 'عرض الصلاحيات', 'الصلاحيات', 'عرض صفحة الصلاحيات والمستخدمين والأدوار', 'preview'),
            ('manage_users', 'إدارة المستخدمين', 'الصلاحيات', 'إضافة وتعديل وحذف وتفعيل المستخدمين', 'admin'),
            ('manage_roles', 'إدارة الأدوار', 'الصلاحيات', 'إنشاء أدوار جديدة وتعديل صلاحياتها', 'admin'),
            ('system_settings', 'إعدادات النظام', 'الصلاحيات', 'تغيير إعدادات النظام وكلمة المرور العامة', 'admin'),
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
        
        # ===== إدراج الأدوار الافتراضية =====
        from datetime import datetime as dt
        now = dt.now().strftime('%Y-%m-%d %H:%M')
        
        default_roles = [
            ('مدير عام', 'التحكم الكامل بجميع أقسام النظام - جميع الصلاحيات', 1),
            ('محاسب', 'إدارة العمليات المالية - أقساط، سحوبات، محاسبة، تقارير', 0),
            ('مدخل بيانات', 'إضافة وتعديل البيانات الأساسية - طلاب ومدرسين', 0),
            ('مشاهد', 'عرض البيانات فقط - بدون إضافة أو تعديل أو حذف', 0),
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
            'view_dashboard', 'view_quick_stats',
            'view_students_list', 'preview_students', 'add_students', 'edit_students', 'link_students', 'edit_student_status',
            'view_teachers_list', 'preview_teachers', 'view_teacher_balance',
            'view_subjects',
            'view_payments_list', 'add_payments', 'pay_installment', 'print_receipt',
            'view_accounting', 'preview_accounting_details',
            'view_withdrawals_list', 'add_withdrawals',
            'view_reports', 'print_reports', 'view_student_reports', 'view_teacher_reports',
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
        
        # ===== إعطاء صلاحيات مدخل البيانات =====
        data_entry_perms = [
            'view_dashboard', 'view_quick_stats',
            'view_students_list', 'preview_students', 'add_students', 'edit_students', 'link_students', 'edit_student_status',
            'view_teachers_list', 'preview_teachers', 'add_teachers', 'edit_teachers',
            'view_subjects', 'add_subjects',
            'view_payments_list', 'add_payments', 'pay_installment',
            'view_reports',
        ]
        try:
            for perm_code in data_entry_perms:
                cursor.execute('''
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT r.id, p.id FROM roles r, permissions p
                    WHERE r.name = 'مدخل بيانات' AND p.code = %s
                    ON CONFLICT (role_id, permission_id) DO NOTHING
                ''', (perm_code,))
            conn.commit()
        except Exception:
            conn.rollback()
        
        # ===== إعطاء صلاحيات المشاهد =====
        viewer_perms = [
            'view_dashboard', 'view_quick_stats',
            'view_students_list', 'preview_students',
            'view_teachers_list', 'preview_teachers', 'view_teacher_balance',
            'view_subjects',
            'view_payments_list',
            'view_accounting',
            'view_withdrawals_list',
            'view_reports', 'view_student_reports', 'view_teacher_reports',
            'view_stats',
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
        # استخدام bcrypt لتشفير كلمة المرور
        try:
            import bcrypt
            admin_pass_hash = bcrypt.hashpw('1111'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        except ImportError:
            # إذا لم تكن bcrypt متوفرة، نستخدم SHA-256 كاحتياط
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
        
        # ===== ALTER TABLE - إضافة أعمدة جديدة للجداول الموجودة =====
        alter_statements = [
            # إضافة عمود level لجدول الصلاحيات
            "ALTER TABLE permissions ADD COLUMN IF NOT EXISTS level VARCHAR(20) DEFAULT 'view'",
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
            # أعمدة الخصم لجدول student_teacher
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS discount_type VARCHAR(20) DEFAULT 'none'",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS discount_value INTEGER DEFAULT 0",
            "ALTER TABLE student_teacher ADD COLUMN IF NOT EXISTS institute_waiver INTEGER DEFAULT 0",
            # عمود نوع الحدث للجدول الأسبوعي (محاضرة / امتحان)
            "ALTER TABLE weekly_schedule ADD COLUMN IF NOT EXISTS event_type VARCHAR(20) DEFAULT 'محاضرة'",
        ]
        
        # ===== جداول الجدول الأسبوعي =====
        # جدول القاعات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                capacity INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        
        # جدول الجدول الأسبوعي
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
        
        # فهرس فريد لمنع تعارض المحاضرات في نفس القاعة والوقت
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_weekly_schedule_no_conflict
            ON weekly_schedule (room_id, day_of_week, start_time, end_time)
        ''')
        conn.commit()
        
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
