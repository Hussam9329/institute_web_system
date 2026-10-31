# ============================================
# trial_mode.py - عزل النسخ التجريبية (متعدد الحسابات)
# ============================================

import contextvars
import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Optional

from psycopg2 import sql as psycopg_sql

logger = logging.getLogger(__name__)


# ===== إعدادات الحسابات التجريبية =====
TRIAL_ACCOUNTS = {
    "raihany": {
        "password": "12345",
        "full_name": "حساب تجريبي - raihany",
        "days": 5,
    },
    "athar": {
        "password": "67890",
        "full_name": "حساب تجريبي - athar",
        "days": 5,
    },
}

# أسماء الحسابات التجريبية التي أُنشئت أثناء التشغيل أو تم اكتشافها من قاعدة البيانات.
# وجود هذه القائمة يمنع حصر العزل بالحسابين الافتراضيين فقط.
_runtime_trial_usernames = set(TRIAL_ACCOUNTS.keys())

TRIAL_ROLE_NAME = "نسخة تجريبية"

# حدود النسخة التجريبية (مشتركة لجميع الحسابات)
TRIAL_LIMITS = {
    "students": (20, "طلاب"),
    "teachers": (7, "مدرسين"),
    "subjects": (4, "مواد دراسية"),
    "installments": (10, "أقساط"),
    "teacher_withdrawals": (8, "سحوبات"),
}

# الجداول الأساسية التي يجب عزلها (الترتيب مهم: الأطول أولاً لتجنب الاستبدال الجزئي)
BASE_TRIAL_TABLES = [
    "teacher_withdrawals",
    "weekly_schedule",
    "student_teacher",
    "installments",
    "subjects",
    "students",
    "teachers",
    "rooms",
]

# ترتيب حذف الجداول (مراعاة المفاتيح الأجنبية)
BASE_DROP_ORDER = [
    "weekly_schedule",
    "rooms",
    "installments",
    "teacher_withdrawals",
    "student_teacher",
    "students",
    "teachers",
    "subjects",
]

# صلاحيات الحساب التجريبي: تشغيل كامل للبيانات المعزولة، بدون صلاحيات الإدارة المشتركة.
TRIAL_PERMISSION_CODES = [
    # لوحة التحكم
    "view_dashboard",
    "view_quick_stats",
    # الطلاب
    "view_students_list",
    "preview_students",
    "add_students",
    "edit_students",
    "delete_students",
    "link_students",
    "edit_student_status",
    # المدرسين
    "view_teachers_list",
    "preview_teachers",
    "add_teachers",
    "edit_teachers",
    "delete_teachers",
    "view_teacher_balance",
    # المواد
    "view_subjects",
    "add_subjects",
    "edit_subjects",
    "delete_subjects",
    # الأقساط
    "view_payments_list",
    "add_payments",
    "delete_payments",
    "pay_installment",
    "print_receipt",
    # المحاسبة
    "view_accounting",
    "preview_accounting_details",
    "manage_commission",
    # السحوبات
    "view_withdrawals_list",
    "add_withdrawals",
    "delete_withdrawals",
    # التقارير
    "view_reports",
    "print_reports",
    "view_student_reports",
    "view_teacher_reports",
    # الإحصائيات
    "view_stats",
    # الصلاحيات: يسمح فقط بفتح صفحة شرح نصية، وليس إدارة فعلية
    "view_permissions",
    # ملاحظة: لا تُمنح صلاحيات الإدارة المشتركة للحساب التجريبي
    # مثل إدارة المستخدمين/الأدوار/سجل العمليات/النسخ الاحتياطي
    # لأنها تعمل على جداول النظام الأصلية وليست جداول التجربة المعزولة.
]

# ===== خريطة جداول raihany القديمة (للتوافق مع البيانات الموجودة) =====
_RAIHANY_LEGACY_TABLE_MAP = {
    "teacher_withdrawals": "trial_teacher_withdrawals",
    "weekly_schedule": "trial_weekly_schedule",
    "student_teacher": "trial_student_teacher",
    "installments": "trial_installments",
    "subjects": "trial_subjects",
    "students": "trial_students",
    "teachers": "trial_teachers",
    "rooms": "trial_rooms",
}

_RAIHANY_LEGACY_DROP_ORDER = [
    "trial_weekly_schedule",
    "trial_rooms",
    "trial_installments",
    "trial_teacher_withdrawals",
    "trial_student_teacher",
    "trial_students",
    "trial_teachers",
    "trial_subjects",
]

_current_user = contextvars.ContextVar("trial_current_user", default=None)


class TrialLimitExceeded(Exception):
    """يُرمى عند تجاوز حدود الحساب التجريبي."""


def set_current_user_context(user: Optional[dict]):
    """تثبيت المستخدم الحالي داخل سياق الطلب."""
    if not user:
        return _current_user.set(None)

    username = user.get("username")
    is_trial = bool(
        user.get("is_trial")
        or username in _runtime_trial_usernames
        or username in TRIAL_ACCOUNTS
    )
    if is_trial and username:
        _runtime_trial_usernames.add(username)

    return _current_user.set({
        "id": user.get("id"),
        "username": username,
        "role_name": user.get("role_name"),
        "is_trial": is_trial,
    })


def reset_current_user_context(token):
    try:
        _current_user.reset(token)
    except Exception:
        pass


def get_current_context_user() -> Optional[dict]:
    return _current_user.get()


def is_trial_request() -> bool:
    """هل الطلب الحالي من حساب تجريبي؟"""
    user = _current_user.get()
    return bool(user and user.get("is_trial") and user.get("username"))


def get_current_trial_username() -> Optional[str]:
    """اسم المستخدم التجريبي الحالي أو None."""
    user = _current_user.get()
    if user and user.get("is_trial") and user.get("username"):
        return user["username"]
    return None


def is_trial_username(username: str) -> bool:
    """هل هذا الاسم مستخدم تجريبي؟"""
    if not username:
        return False
    if username in TRIAL_ACCOUNTS or username in _runtime_trial_usernames:
        return True
    user = _current_user.get()
    if user and user.get("username") == username and user.get("is_trial"):
        _runtime_trial_usernames.add(username)
        return True
    return False


_TRIAL_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{1,50}$")


def _require_safe_trial_username(username: str) -> str:
    """
    اسم المستخدم التجريبي يدخل في أسماء الجداول (trial_<username>_...)،
    لذا يُرفض أي اسم خارج [a-zA-Z0-9_] قبل أن يصل لأي استعلام.
    """
    if not isinstance(username, str) or not _TRIAL_USERNAME_RE.match(username):
        raise ValueError("اسم المستخدم التجريبي غير صالح")
    return username


def get_trial_table_map(username: str) -> dict:
    """ترجع خريطة تحويل الجداول لحساب تجريبي معين."""
    if username == "raihany":
        # توافق مع الجداول الموجودة مسبقاً
        return dict(_RAIHANY_LEGACY_TABLE_MAP)
    _require_safe_trial_username(username)
    # الحسابات الجديدة تستخدم بادئة اسم المستخدم
    return {table: f"trial_{username}_{table}" for table in BASE_TRIAL_TABLES}


def get_trial_tables_drop_order(username: str) -> list:
    """ترجع قائمة الجداول بترتيب الحذف لحساب تجريبي معين."""
    if username == "raihany":
        return list(_RAIHANY_LEGACY_DROP_ORDER)
    _require_safe_trial_username(username)
    return [f"trial_{username}_{table}" for table in BASE_DROP_ORDER]


def _password_hash(password: str) -> str:
    """نفس منطق النظام: bcrypt عند توفره، وإلا SHA-256 كاحتياط."""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    except Exception:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _extract_base_table_name(trial_table: str) -> str:
    """استخراج اسم الجدول الأساسي من اسم الجدول التجريبي.
    يدعم الصيغة القديمة trial_students والصيغة الجديدة trial_{username}_students
    حتى لو كان اسم المستخدم أُنشئ ديناميكياً وليس موجوداً داخل TRIAL_ACCOUNTS.
    """
    name = (trial_table or "").lower()
    if name in BASE_TRIAL_TABLES:
        return name
    for base_table in sorted(BASE_TRIAL_TABLES, key=len, reverse=True):
        if name == f"trial_{base_table}" or name.endswith(f"_{base_table}"):
            return base_table
    if name.startswith("trial_"):
        return name[6:]
    return name


def rewrite_query_for_trial(query: str) -> str:
    """
    يحوّل استعلامات الحسابات التجريبية من الجداول الأصلية إلى الجداول المعزولة.
    المستخدمون والأدوار والصلاحيات وسجل العمليات تبقى على قاعدة النظام الأصلية.
    """
    if not is_trial_request() or not query:
        return query

    username = get_current_trial_username()
    if not username:
        return query

    table_map = get_trial_table_map(username)
    rewritten = query
    # الترتيب: الأطول أولاً لتجنب الاستبدال الجزئي (teacher_withdrawals قبل teachers)
    for base_table, trial_table in sorted(table_map.items(), key=lambda x: -len(x[0])):
        rewritten = re.sub(
            rf"(?<!trial_)\b{re.escape(base_table)}\b",
            trial_table,
            rewritten,
            flags=re.IGNORECASE,
        )
    return rewritten


def _extract_insert_table(query: str) -> Optional[str]:
    match = re.search(r"^\s*INSERT\s+INTO\s+([a-zA-Z_][\w]*)", query, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1).lower()


def _extract_insert_columns(query: str) -> list[str]:
    match = re.search(
        r"^\s*INSERT\s+INTO\s+[a-zA-Z_][\w]*\s*\((.*?)\)\s*VALUES",
        query,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []
    return [c.strip().strip('"').lower() for c in match.group(1).split(",")]


def _param_at(params: Any, index: int):
    if params is None:
        return None
    if isinstance(params, (list, tuple)):
        return params[index] if index < len(params) else None
    return None


def _get_insert_param(query: str, params: Any, column_name: str):
    columns = _extract_insert_columns(query)
    if not columns:
        return None
    try:
        idx = columns.index(column_name.lower())
    except ValueError:
        return None
    return _param_at(params, idx)


def _scalar(cursor, sql: str, params: tuple = ()):  # RealDictCursor friendly
    cursor.execute(sql, params)
    row = cursor.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


def _ensure_limit_not_exceeded(cursor, table_name: str, new_item_label: str | None = None):
    base_table = _extract_base_table_name(table_name)
    limit_info = TRIAL_LIMITS.get(base_table)
    if not limit_info:
        return
    limit, label = limit_info
    current_count = int(_scalar(cursor, f"SELECT COUNT(*) AS cnt FROM {table_name}") or 0)
    if current_count >= limit:
        item_label = new_item_label or label
        raise TrialLimitExceeded(
            f"تجاوزت حد النسخة التجريبية: الحد الأقصى لـ {item_label} هو {limit} فقط."
        )


def enforce_trial_constraints(cursor, query: str, params=None):
    """يفرض حدود النسخة التجريبية قبل تنفيذ INSERT على الجداول التجريبية."""
    if not is_trial_request():
        return

    username = get_current_trial_username()
    if not username:
        return

    table_map = get_trial_table_map(username)
    table_name = _extract_insert_table(query)
    if not table_name:
        return

    # عند إضافة مدرس بمادة جديدة، نضمن أن المادة ضمن جدول المواد التجريبي ولا تتجاوز حد 4 مواد.
    if table_name == table_map["teachers"]:
        subject_value = _get_insert_param(query, params, "subject")
        if subject_value:
            subjects_table = table_map["subjects"]
            exists = _scalar(
                cursor,
                f"SELECT 1 FROM {subjects_table} WHERE name = %s LIMIT 1",
                (str(subject_value),),
            )
            if not exists:
                _ensure_limit_not_exceeded(cursor, subjects_table, "المواد الدراسية")
                cursor.execute(
                    f"INSERT INTO {subjects_table} (name, created_at) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (str(subject_value), datetime.now().strftime("%Y-%m-%d")),
                )

    # إذا كانت المادة موجودة مسبقاً لا نحسبها كإضافة جديدة حتى لو أتى INSERT مع ON CONFLICT.
    if table_name == table_map["subjects"]:
        subject_name = _get_insert_param(query, params, "name")
        if subject_name:
            subjects_table = table_map["subjects"]
            exists = _scalar(
                cursor,
                f"SELECT 1 FROM {subjects_table} WHERE name = %s LIMIT 1",
                (str(subject_name),),
            )
            if exists:
                return

    _ensure_limit_not_exceeded(cursor, table_name)


def create_trial_tables(cursor, username: str):
    """إنشاء الجداول التجريبية لحساب معين داخل نفس قاعدة PostgreSQL."""
    t = get_trial_table_map(username)

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {t["subjects"]} (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            created_by INTEGER,
            updated_by INTEGER
        )
    ''')

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {t["students"]} (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            study_type TEXT NOT NULL DEFAULT 'حضوري',
            has_badge INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'مستمر',
            barcode TEXT UNIQUE NOT NULL,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            phone TEXT DEFAULT '',
            parent_phone TEXT DEFAULT '',
            created_by INTEGER,
            updated_by INTEGER
        )
    ''')
    idx_pfx = f"trial_{username}_" if username != "raihany" else "trial_"
    cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{idx_pfx}students_phone_not_empty ON {t['students']} (phone) WHERE phone IS NOT NULL AND phone != ''")
    cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{idx_pfx}students_parent_phone_not_empty ON {t['students']} (parent_phone) WHERE parent_phone IS NOT NULL AND parent_phone != ''")

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {t["teachers"]} (
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
            inst_ded_manual_blended INTEGER DEFAULT 0,
            custom_type_settings TEXT DEFAULT '{{}}',
            created_by INTEGER,
            updated_by INTEGER
        )
    ''')

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {t["student_teacher"]} (
            student_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            study_type TEXT DEFAULT 'حضوري',
            status TEXT DEFAULT 'مستمر',
            notes TEXT DEFAULT '',
            discount_type TEXT DEFAULT 'none',
            discount_value INTEGER DEFAULT 0,
            institute_waiver INTEGER DEFAULT 0,
            discount_notes TEXT DEFAULT '',
            created_by INTEGER,
            updated_by INTEGER,
            PRIMARY KEY (student_id, teacher_id),
            FOREIGN KEY (student_id) REFERENCES {t["students"]}(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES {t["teachers"]}(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {t["installments"]} (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            payment_date TEXT NOT NULL,
            installment_type TEXT NOT NULL DEFAULT 'القسط الأول',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            for_installment TEXT DEFAULT '',
            created_by INTEGER,
            updated_by INTEGER,
            FOREIGN KEY (student_id) REFERENCES {t["students"]}(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES {t["teachers"]}(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{idx_pfx}installment_student_teacher ON {t['installments']} (student_id, teacher_id)")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{idx_pfx}installments_teacher_date ON {t['installments']} (teacher_id, payment_date)")

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {t["teacher_withdrawals"]} (
            id SERIAL PRIMARY KEY,
            teacher_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            withdrawal_date TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_by INTEGER,
            updated_by INTEGER,
            FOREIGN KEY (teacher_id) REFERENCES {t["teachers"]}(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{idx_pfx}withdrawals_teacher_date ON {t['teacher_withdrawals']} (teacher_id, withdrawal_date)")

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {t["rooms"]} (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            capacity INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    ''')

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {t["weekly_schedule"]} (
            id SERIAL PRIMARY KEY,
            room_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            subject TEXT NOT NULL DEFAULT '',
            day_of_week TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            event_type TEXT NOT NULL DEFAULT 'محاضرة',
            notes TEXT DEFAULT '',
            FOREIGN KEY (room_id) REFERENCES {t["rooms"]}(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES {t["teachers"]}(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute(f'''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_{idx_pfx}weekly_schedule_no_conflict
        ON {t["weekly_schedule"]} (room_id, day_of_week, start_time, end_time)
    ''')


def drop_trial_tables(cursor, username: str):
    """حذف جداول النسخة التجريبية وبياناتها عند انتهاء مدة التجربة."""
    for table_name in get_trial_tables_drop_order(username):
        cursor.execute(
            psycopg_sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(psycopg_sql.Identifier(table_name))
        )


def ensure_trial_environment(cursor, username: str = None, password: str = None, full_name: str = None, days: int = None):
    """
    يضمن وجود حساب تجريبي وجداوله.
    إذا لم يُحدد username، يهيئ الحسابات الافتراضية فقط.
    يدعم أيضاً إنشاء حسابات تجريبية ديناميكية من صفحة الصلاحيات أو API.
    لا يتم تمديد المدة عند إعادة تشغيل التطبيق.
    """
    if username is None:
        for uname, config in TRIAL_ACCOUNTS.items():
            ensure_trial_environment(
                cursor,
                uname,
                password=config.get("password"),
                full_name=config.get("full_name"),
                days=config.get("days", 5),
            )
        return {"success": True, "message": "تم تهيئة الحسابات التجريبية الافتراضية"}

    username = str(username).strip()
    if not username:
        return {"success": False, "message": "اسم المستخدم التجريبي مطلوب"}
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return {"success": False, "message": "اسم المستخدم يجب أن يحتوي على أحرف إنجليزية وأرقام وشرطة سفلية فقط"}

    account_config = TRIAL_ACCOUNTS.get(username, {})
    password = password if password is not None else account_config.get("password")
    full_name = full_name or account_config.get("full_name") or f"حساب تجريبي - {username}"
    days = int(days or account_config.get("days", 5) or 5)

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trial_accounts (
            username TEXT PRIMARY KEY,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            expired_at TIMESTAMPTZ,
            is_expired INTEGER NOT NULL DEFAULT 0
        )
    ''')

    cursor.execute('''
        INSERT INTO roles (name, description, is_default, created_at)
        VALUES (%s, %s, 0, TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI'))
        ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
    ''', (TRIAL_ROLE_NAME, "حساب تجريبي بصلاحيات تشغيل معزولة وشرح نصي للصلاحيات لمدة 5 أيام"))

    if TRIAL_PERMISSION_CODES:
        placeholders = ",".join(["%s"] * len(TRIAL_PERMISSION_CODES))
        cursor.execute(f'''
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r
            JOIN permissions p ON p.code IN ({placeholders})
            WHERE r.name = %s
            ON CONFLICT DO NOTHING
        ''', tuple(TRIAL_PERMISSION_CODES) + (TRIAL_ROLE_NAME,))

    cursor.execute('''
        SELECT username, expires_at, is_expired,
               (expires_at <= NOW() OR is_expired = 1) AS expired
        FROM trial_accounts
        WHERE username = %s
    ''', (username,))
    account = cursor.fetchone()

    cursor.execute('''
        SELECT u.id, u.password_hash, r.name AS role_name
        FROM users u LEFT JOIN roles r ON r.id = u.role_id
        WHERE u.username = %s
    ''', (username,))
    existing_user = cursor.fetchone()

    def _row_get(row, key, idx=None):
        if not row:
            return None
        if isinstance(row, dict):
            return row.get(key)
        return row[idx] if idx is not None else None

    def _upsert_trial_user(active: int = 1):
        existing_hash = _row_get(existing_user, "password_hash", 1)
        if password:
            password_hash = _password_hash(password)
        elif existing_hash:
            password_hash = existing_hash
        else:
            raise ValueError("كلمة المرور مطلوبة عند إنشاء حساب تجريبي جديد")

        cursor.execute('''
            INSERT INTO users (username, full_name, password_hash, role_id, is_active, created_at)
            SELECT %s, %s, %s, r.id, %s, TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI')
            FROM roles r WHERE r.name = %s
            ON CONFLICT (username) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                password_hash = EXCLUDED.password_hash,
                role_id = EXCLUDED.role_id,
                is_active = EXCLUDED.is_active
        ''', (username, full_name, password_hash, active, TRIAL_ROLE_NAME))

    # أول تشغيل/أول إنشاء: إنشاء الحساب وبدء عداد الأيام.
    if not account:
        # لا يُحوَّل مستخدم حقيقي موجود (مثل admin أو موظف) إلى حساب تجريبي أبداً
        if existing_user and _row_get(existing_user, "role_name", 2) != TRIAL_ROLE_NAME:
            return {"success": False, "message": "اسم المستخدم مستخدم لحساب حقيقي في النظام - اختر اسماً آخر"}
        _upsert_trial_user(active=1)
        cursor.execute('''
            INSERT INTO trial_accounts (username, started_at, expires_at, is_expired)
            VALUES (%s, NOW(), NOW() + (%s || ' days')::INTERVAL, 0)
            ON CONFLICT (username) DO NOTHING
        ''', (username, str(days)))
        create_trial_tables(cursor, username)
        _runtime_trial_usernames.add(username)
        return {"success": True, "message": "تم إنشاء الحساب التجريبي المعزول بنجاح"}

    # بعد انتهاء المدة: حذف الجداول التجريبية وتعطيل المستخدم.
    try:
        expired = bool(account.get("expired"))
    except AttributeError:
        expired = bool(account[3])

    if expired:
        drop_trial_tables(cursor, username)
        cursor.execute('''
            UPDATE trial_accounts
            SET is_expired = 1,
                expired_at = COALESCE(expired_at, NOW())
            WHERE username = %s
        ''', (username,))
        cursor.execute("UPDATE users SET is_active = 0 WHERE username = %s", (username,))
        _runtime_trial_usernames.discard(username)
        return {"success": False, "message": "الحساب التجريبي منتهي وتم تعطيله وحذف بياناته"}

    # الحساب ما زال ضمن مدة التجربة: تأكد من وجود المستخدم والجداول، ولا تمدد تاريخ الانتهاء.
    _upsert_trial_user(active=1)
    create_trial_tables(cursor, username)
    _runtime_trial_usernames.add(username)
    return {"success": True, "message": "تم تجهيز الحساب التجريبي المعزول بنجاح"}


def get_all_trial_accounts() -> list[dict]:
    """إرجاع كل الحسابات التجريبية من قاعدة البيانات."""
    from database import Database
    db = Database()
    rows = db.execute_query('''
        SELECT ta.username,
               u.full_name,
               u.is_active,
               ta.started_at,
               ta.expires_at,
               ta.expired_at,
               ta.is_expired,
               GREATEST(0, EXTRACT(EPOCH FROM (ta.expires_at - NOW())))::INTEGER AS seconds_remaining,
               (ta.expires_at <= NOW() OR ta.is_expired = 1) AS expired
        FROM trial_accounts ta
        LEFT JOIN users u ON u.username = ta.username
        ORDER BY ta.started_at DESC
    ''')
    for row in rows:
        if row.get("username"):
            _runtime_trial_usernames.add(row["username"])
    return [dict(row) for row in rows]


def delete_trial_account(username: str) -> dict:
    """حذف حساب تجريبي مع جداوله وملفاته المنطقية من قاعدة البيانات."""
    from database import Database
    username = str(username or "").strip()
    if not username:
        return {"success": False, "message": "اسم المستخدم مطلوب"}
    if username != "raihany" and not _TRIAL_USERNAME_RE.match(username):
        return {"success": False, "message": "اسم المستخدم التجريبي غير صالح"}

    db = Database()
    conn = None
    cursor = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        # الحذف مسموح للحسابات المسجلة كتجريبية فقط، وليس لأي مستخدم حقيقي
        cursor.execute("SELECT 1 FROM trial_accounts WHERE username = %s", (username,))
        if cursor.fetchone() is None:
            conn.rollback()
            return {"success": False, "message": "هذا الحساب ليس حساباً تجريبياً"}
        drop_trial_tables(cursor, username)
        cursor.execute("DELETE FROM trial_accounts WHERE username = %s", (username,))
        cursor.execute("DELETE FROM users WHERE username = %s", (username,))
        conn.commit()
        _runtime_trial_usernames.discard(username)
        return {"success": True, "message": "تم حذف الحساب التجريبي وبياناته المعزولة"}
    except Exception:
        logger.exception("تعذر حذف الحساب التجريبي %s", username)
        if conn:
            conn.rollback()
        return {"success": False, "message": "تعذر حذف الحساب التجريبي - حاول مرة أخرى"}
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        if conn:
            db.return_connection(conn)
