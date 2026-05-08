# ============================================
# database.py - إدارة قاعدة البيانات PostgreSQL (سحابية)
# قاعدة بيانات سحابية سريعة مع تجمع اتصالات
# محسّن: منطق إعادة المحاولة لـ Neon cold starts
# ============================================

import os
import re
import time
import logging
import threading
import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from psycopg2 import InterfaceError, OperationalError, DatabaseError

# ===== إعدادات قاعدة البيانات =====
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ===== إعدادات إعادة المحاولة =====
MAX_RETRIES = 3                    # عدد المحاولات الأقصى
RETRY_DELAYS = [0.5, 1.5, 3.0]    # تأخيرات بالم ثانية بين المحاولات (exponential backoff)
CONNECT_TIMEOUT = 10               # مهلة الاتصال بالثواني
STATEMENT_TIMEOUT = 30000          # مهلة الاستعلام بالملي ثانية (30 ثانية)

# ===== تسجيل الأخطاء =====
logger = logging.getLogger(__name__)

# ===== تجمع الاتصالات =====
_pool = None
_pool_lock = threading.Lock()
_db_initialized = False
_db_init_lock = threading.Lock()


def _is_retryable_error(error) -> bool:
    """تحقق هل الخطأ يستحق إعادة المحاولة (Neon cold starts, connection drops, etc.)"""
    error_str = str(error).lower()
    
    # أخطاء تتعلق بالاتصال - تستحق إعادة المحاولة
    retryable_keywords = [
        'connection',           # مشاكل الاتصال
        'timeout',              # انتهاء المهلة
        'could not connect',    # لم يتمكن من الاتصال
        'connection refused',   # رفض الاتصال
        'connection reset',     # إعادة تعيين الاتصال
        'broken pipe',          # أنبوب مقطوع
        'server closed',        # إغلاق الخادم للاتصال
        'unexpectedly closed',  # إغلاق غير متوقع
        'network',              # مشاكل الشبكة
        'tcp',                  # مشاكل TCP
        'ssl',                  # مشاكل SSL
        'handshake',            # مشاكل المصافحة
        'cold start',           # Neon cold start
        'startup',              # Neon startup
        'idle session',         # جلسة خاملة
        'pool exhausted',       # تجمع الاتصالات منتهي
        'too many connections', # اتصالات كثيرة
        'deadline exceeded',    # تجاوز الموعد النهائي
        'temporarily unavailable',  # غير متاح مؤقتاً
        'retry',                # طلب إعادة المحاولة
    ]
    
    # أنواع الأخطاء القابلة لإعادة المحاولة
    if isinstance(error, (InterfaceError, OperationalError)):
        return True
    
    for keyword in retryable_keywords:
        if keyword in error_str:
            return True
    
    return False


def _reset_pool():
    """إعادة تعيين تجمع الاتصالات عند فشل جميع الاتصالات"""
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.closeall()
            except Exception:
                pass
            _pool = None


def _get_pool():
    """الحصول على تجمع الاتصالات (Singleton) مع إعادة المحاولة"""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                for attempt in range(MAX_RETRIES):
                    try:
                        connect_args = {
                            'dsn': DATABASE_URL,
                            'sslmode': 'require' if 'sslmode' not in DATABASE_URL else None,
                            'connect_timeout': CONNECT_TIMEOUT,
                        }
                        # إزالة القيم None
                        connect_args = {k: v for k, v in connect_args.items() if v is not None}
                        
                        _pool = ThreadedConnectionPool(
                            minconn=1,
                            maxconn=10,
                            **connect_args
                        )
                        logger.info(f"تم إنشاء تجمع الاتصالات بنجاح (المحاولة {attempt + 1})")
                        break
                    except Exception as e:
                        logger.warning(f"فشل إنشاء تجمع الاتصالات (المحاولة {attempt + 1}/{MAX_RETRIES}): {e}")
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                        else:
                            # إذا فشل تجمع الاتصالات، نستخدم اتصال مباشر
                            _pool = None
                            logger.error("فشل إنشاء تجمع الاتصالات - سيتم استخدام اتصال مباشر")
    return _pool


class Database:
    """إدارة اتصال قاعدة البيانات PostgreSQL - سحابية محسّنة مع إعادة المحاولة"""
    
    def _get_connection(self):
        """الحصول على اتصال PostgreSQL من التجمع أو مباشر مع إعادة المحاولة"""
        pool = _get_pool()
        if pool:
            for attempt in range(MAX_RETRIES):
                try:
                    conn = pool.getconn()
                    conn.autocommit = False
                    # فحص صحة الاتصال
                    try:
                        with conn.cursor() as test_cursor:
                            test_cursor.execute("SELECT 1")
                    except Exception:
                        # الاتصال غير صالح - نعيده ونحاول مجدداً
                        try:
                            pool.putconn(conn, close=True)
                        except Exception:
                            pass
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                            continue
                        raise
                    return conn
                except Exception as e:
                    logger.warning(f"فشل الحصول على اتصال من التجمع (المحاولة {attempt + 1}/{MAX_RETRIES}): {e}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                    else:
                        # إعادة تعيين التجمع والمحاولة باتصال مباشر
                        _reset_pool()
        
        # اتصال مباشر مع إعادة المحاولة
        for attempt in range(MAX_RETRIES):
            try:
                conn = psycopg2.connect(
                    DATABASE_URL, 
                    sslmode='require',
                    connect_timeout=CONNECT_TIMEOUT
                )
                conn.autocommit = False
                return conn
            except Exception as e:
                logger.warning(f"فشل الاتصال المباشر (المحاولة {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                else:
                    raise
    
    def _return_connection(self, conn):
        """إرجاع الاتصال إلى التجمع"""
        pool = _get_pool()
        if pool:
            try:
                pool.putconn(conn)
                return
            except Exception:
                pass
        # إغلاق مباشر إذا لم يكن هناك تجمع
        try:
            conn.close()
        except:
            pass
    
    def execute_query(self, query: str, params=None) -> list:
        """تنفيذ استعلام مع إعادة المحاولة التلقائية للأخطاء العابرة"""
        if params is None:
            params = ()
        
        last_error = None
        
        for attempt in range(MAX_RETRIES):
            conn = None
            cursor = None
            try:
                conn = self._get_connection()
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # تعيين مهلة الاستعلام
                cursor.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT}")
                
                cursor.execute(query, params)
                
                query_upper = query.strip().upper()
                if query_upper.startswith('SELECT') or 'RETURNING' in query_upper:
                    results = [dict(row) for row in cursor.fetchall()]
                    if not query_upper.startswith('SELECT') and 'RETURNING' in query_upper:
                        conn.commit()
                    return results
                else:
                    conn.commit()
                    return []
                    
            except Exception as e:
                last_error = e
                # إعادة المحاولة فقط للأخطاء القابلة لذلك
                if _is_retryable_error(e) and attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    logger.warning(f"خطأ قابل لإعادة المحاولة في الاستعلام (المحاولة {attempt + 1}/{MAX_RETRIES}): {e}")
                    time.sleep(delay)
                    # إعادة تعيين الاتصال
                    if conn:
                        try:
                            conn.rollback()
                        except:
                            pass
                        try:
                            self._return_connection(conn)
                        except:
                            pass
                    continue
                else:
                    # خطأ غير قابل لإعادة المحاولة أو تجاوز عدد المحاولات
                    if conn:
                        try:
                            conn.rollback()
                        except:
                            pass
                    raise e
            finally:
                try:
                    if cursor:
                        cursor.close()
                except:
                    pass
                if conn:
                    self._return_connection(conn)
        
        # إذا وصلنا هنا، فقد فشلت جميع المحاولات
        raise last_error
    
    def get_connection(self):
        """الحصول على اتصال مباشر - للاستخدام المتقدم"""
        return self._get_connection()
    
    def return_connection(self, conn):
        """إرجاع الاتصال إلى التجمع"""
        self._return_connection(conn)


def init_db():
    """تهيئة قاعدة البيانات - إنشاء الجداول إذا لم تكن موجودة مع إعادة المحاولة"""
    global _db_initialized
    
    if _db_initialized:
        return
    
    with _db_init_lock:
        if _db_initialized:
            return
        
        for init_attempt in range(MAX_RETRIES):
            db = Database()
            conn = None
            cursor = None
            
            try:
                conn = db.get_connection()
                cursor = conn.cursor()
                
                # جدول المواد الدراسية
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subjects (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS students (
                        id SERIAL PRIMARY KEY,
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
                        id SERIAL PRIMARY KEY,
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
                        id SERIAL PRIMARY KEY,
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
                        name TEXT NOT NULL UNIQUE,
                        description TEXT DEFAULT '',
                        is_default INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS permissions (
                        id SERIAL PRIMARY KEY,
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
                        id SERIAL PRIMARY KEY,
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
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
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
                existing_perms = cursor.execute("SELECT COUNT(*) FROM permissions")
                perm_count = cursor.fetchone()
                
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
                                'INSERT INTO permissions (code, name, category, description, level) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING',
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
                                'INSERT INTO roles (name, description, is_default, created_at) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING',
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
                            ON CONFLICT DO NOTHING
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
                            ON CONFLICT DO NOTHING
                        ''', (admin_pass_hash, now))
                        conn.commit()
                    except Exception:
                        conn.rollback()
                
                _db_initialized = True
                logger.info("تم تهيئة قاعدة البيانات بنجاح")
                break  # نجح التهيئة - نخرج من حلقة المحاولات
                
            except Exception as e:
                try:
                    if conn:
                        conn.rollback()
                except:
                    pass
                logger.warning(f"تحذير في تهيئة قاعدة البيانات (المحاولة {init_attempt + 1}/{MAX_RETRIES}): {e}")
                
                if _is_retryable_error(e) and init_attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[min(init_attempt, len(RETRY_DELAYS) - 1)]
                    logger.info(f"إعادة محاولة تهيئة قاعدة البيانات بعد {delay} ثانية...")
                    time.sleep(delay)
                else:
                    logger.error(f"فشل تهيئة قاعدة البيانات بعد {MAX_RETRIES} محاولات: {e}")
            finally:
                try:
                    if cursor:
                        cursor.close()
                except:
                    pass
                if conn:
                    db.return_connection(conn)
