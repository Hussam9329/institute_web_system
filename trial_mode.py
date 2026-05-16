# ============================================
# trial_mode.py - عزل النسخة التجريبية لحساب raihany
# ============================================

import contextvars
import hashlib
import re
from datetime import datetime
from typing import Any, Optional


# ===== إعدادات الحساب التجريبي المطلوبة =====
TRIAL_USERNAME = "raihany"
TRIAL_PASSWORD = "12345"
TRIAL_FULL_NAME = "حساب تجريبي - raihany"
TRIAL_ROLE_NAME = "نسخة تجريبية"
TRIAL_DAYS = 5

# حدود النسخة التجريبية
TRIAL_LIMITS = {
    "trial_students": (10, "طلاب"),
    "trial_teachers": (7, "مدرسين"),
    "trial_subjects": (4, "مواد دراسية"),
    "trial_installments": (10, "أقساط"),
    "trial_teacher_withdrawals": (8, "سحوبات"),
}

# الجداول التي يجب عزلها للحساب التجريبي داخل نفس قاعدة بيانات البرنامج
# الترتيب مهم حتى لا يستبدل teachers داخل teacher_withdrawals مثلاً.
TRIAL_TABLE_MAP = {
    "teacher_withdrawals": "trial_teacher_withdrawals",
    "weekly_schedule": "trial_weekly_schedule",
    "student_teacher": "trial_student_teacher",
    "installments": "trial_installments",
    "subjects": "trial_subjects",
    "students": "trial_students",
    "teachers": "trial_teachers",
    "rooms": "trial_rooms",
}

TRIAL_TABLES_DROP_ORDER = [
    "trial_weekly_schedule",
    "trial_rooms",
    "trial_installments",
    "trial_teacher_withdrawals",
    "trial_student_teacher",
    "trial_students",
    "trial_teachers",
    "trial_subjects",
]

# صلاحيات الحساب التجريبي: كل ما يحتاجه للتجربة، بدون إدارة مستخدمين/أدوار/إعدادات النظام.
TRIAL_PERMISSION_CODES = [
    "view_dashboard",
    "view_quick_stats",
    "view_students_list",
    "preview_students",
    "add_students",
    "edit_students",
    "delete_students",
    "link_students",
    "edit_student_status",
    "view_teachers_list",
    "preview_teachers",
    "add_teachers",
    "edit_teachers",
    "delete_teachers",
    "view_teacher_balance",
    "view_subjects",
    "add_subjects",
    "edit_subjects",
    "delete_subjects",
    "view_payments_list",
    "add_payments",
    "delete_payments",
    "pay_installment",
    "print_receipt",
    "view_accounting",
    "preview_accounting_details",
    "manage_commission",
    "view_withdrawals_list",
    "add_withdrawals",
    "delete_withdrawals",
    "view_reports",
    "print_reports",
    "view_student_reports",
    "view_teacher_reports",
    "view_stats",
]

_current_user = contextvars.ContextVar("trial_current_user", default=None)


class TrialLimitExceeded(Exception):
    """يُرمى عند تجاوز حدود الحساب التجريبي."""


def set_current_user_context(user: Optional[dict]):
    """تثبيت المستخدم الحالي داخل سياق الطلب حتى تعرف قاعدة البيانات هل تعيد توجيه الجداول أم لا."""
    if not user:
        return _current_user.set(None)
    return _current_user.set({
        "id": user.get("id"),
        "username": user.get("username"),
        "role_name": user.get("role_name"),
    })


def reset_current_user_context(token):
    try:
        _current_user.reset(token)
    except Exception:
        pass


def get_current_context_user() -> Optional[dict]:
    return _current_user.get()


def is_trial_request() -> bool:
    user = _current_user.get()
    return bool(user and user.get("username") == TRIAL_USERNAME)


def _password_hash(password: str) -> str:
    """نفس منطق النظام: bcrypt عند توفره، وإلا SHA-256 كاحتياط."""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    except Exception:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()


def rewrite_query_for_trial(query: str) -> str:
    """
    يحوّل استعلامات حساب raihany فقط من الجداول الأصلية إلى الجداول التجريبية.
    المستخدمون والأدوار والصلاحيات وسجل العمليات تبقى على قاعدة النظام الأصلية.
    """
    if not is_trial_request() or not query:
        return query

    rewritten = query
    for base_table, trial_table in TRIAL_TABLE_MAP.items():
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
    limit_info = TRIAL_LIMITS.get(table_name)
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

    table_name = _extract_insert_table(query)
    if not table_name:
        return

    # عند إضافة مدرس بمادة جديدة، نضمن أن المادة ضمن جدول المواد التجريبي ولا تتجاوز حد 4 مواد.
    if table_name == "trial_teachers":
        subject_value = _get_insert_param(query, params, "subject")
        if subject_value:
            exists = _scalar(
                cursor,
                "SELECT 1 FROM trial_subjects WHERE name = %s LIMIT 1",
                (str(subject_value),),
            )
            if not exists:
                _ensure_limit_not_exceeded(cursor, "trial_subjects", "المواد الدراسية")
                cursor.execute(
                    "INSERT INTO trial_subjects (name, created_at) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (str(subject_value), datetime.now().strftime("%Y-%m-%d")),
                )

    # إذا كانت المادة موجودة مسبقاً لا نحسبها كإضافة جديدة حتى لو أتى INSERT مع ON CONFLICT.
    if table_name == "trial_subjects":
        subject_name = _get_insert_param(query, params, "name")
        if subject_name:
            exists = _scalar(
                cursor,
                "SELECT 1 FROM trial_subjects WHERE name = %s LIMIT 1",
                (str(subject_name),),
            )
            if exists:
                return

    _ensure_limit_not_exceeded(cursor, table_name)


def create_trial_tables(cursor):
    """إنشاء الجداول التجريبية داخل نفس قاعدة PostgreSQL، لكنها منفصلة عن بيانات النظام الأصلية."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trial_subjects (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            created_by INTEGER,
            updated_by INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trial_students (
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
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trial_students_phone_not_empty ON trial_students (phone) WHERE phone IS NOT NULL AND phone != ''")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trial_students_parent_phone_not_empty ON trial_students (parent_phone) WHERE parent_phone IS NOT NULL AND parent_phone != ''")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trial_teachers (
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
            custom_type_settings TEXT DEFAULT '{}',
            created_by INTEGER,
            updated_by INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trial_student_teacher (
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
            FOREIGN KEY (student_id) REFERENCES trial_students(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES trial_teachers(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trial_installments (
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
            FOREIGN KEY (student_id) REFERENCES trial_students(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES trial_teachers(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trial_installment_student_teacher ON trial_installments (student_id, teacher_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trial_installments_teacher_date ON trial_installments (teacher_id, payment_date)")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trial_teacher_withdrawals (
            id SERIAL PRIMARY KEY,
            teacher_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            withdrawal_date TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_by INTEGER,
            updated_by INTEGER,
            FOREIGN KEY (teacher_id) REFERENCES trial_teachers(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trial_withdrawals_teacher_date ON trial_teacher_withdrawals (teacher_id, withdrawal_date)")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trial_rooms (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            capacity INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trial_weekly_schedule (
            id SERIAL PRIMARY KEY,
            room_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            subject TEXT NOT NULL DEFAULT '',
            day_of_week TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            event_type TEXT NOT NULL DEFAULT 'محاضرة',
            notes TEXT DEFAULT '',
            FOREIGN KEY (room_id) REFERENCES trial_rooms(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES trial_teachers(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trial_weekly_schedule_no_conflict
        ON trial_weekly_schedule (room_id, day_of_week, start_time, end_time)
    ''')


def drop_trial_tables(cursor):
    """حذف قاعدة/جداول النسخة التجريبية وبياناتها عند انتهاء مدة 5 أيام."""
    for table_name in TRIAL_TABLES_DROP_ORDER:
        cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")


def ensure_trial_environment(cursor):
    """
    يضمن وجود حساب raihany التجريبي مرة واحدة فقط.
    لا يتم تمديد مدة الـ 5 أيام عند إعادة تشغيل التطبيق.
    """
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
    ''', (TRIAL_ROLE_NAME, "حساب تجريبي محدود ومعزول لمدة 5 أيام"))

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
    ''', (TRIAL_USERNAME,))
    account = cursor.fetchone()

    # أول تشغيل للكود بعد نشره: إنشاء الحساب وبدء عداد 5 أيام.
    if not account:
        password_hash = _password_hash(TRIAL_PASSWORD)
        cursor.execute('''
            INSERT INTO users (username, full_name, password_hash, role_id, is_active, created_at)
            SELECT %s, %s, %s, r.id, 1, TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI')
            FROM roles r WHERE r.name = %s
            ON CONFLICT (username) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                password_hash = EXCLUDED.password_hash,
                role_id = EXCLUDED.role_id,
                is_active = 1
        ''', (TRIAL_USERNAME, TRIAL_FULL_NAME, password_hash, TRIAL_ROLE_NAME))
        cursor.execute('''
            INSERT INTO trial_accounts (username, started_at, expires_at, is_expired)
            VALUES (%s, NOW(), NOW() + (%s || ' days')::INTERVAL, 0)
            ON CONFLICT (username) DO NOTHING
        ''', (TRIAL_USERNAME, str(TRIAL_DAYS)))
        create_trial_tables(cursor)
        return

    # بعد انتهاء المدة: حذف الجداول التجريبية وتعطيل المستخدم، بدون إعادة إنشائه تلقائياً.
    try:
        expired = bool(account.get("expired"))
    except AttributeError:
        expired = bool(account[3])

    if expired:
        drop_trial_tables(cursor)
        cursor.execute('''
            UPDATE trial_accounts
            SET is_expired = 1,
                expired_at = COALESCE(expired_at, NOW())
            WHERE username = %s
        ''', (TRIAL_USERNAME,))
        cursor.execute("UPDATE users SET is_active = 0 WHERE username = %s", (TRIAL_USERNAME,))
        return

    # الحساب ما زال ضمن مدة التجربة: تأكد من وجود المستخدم والجداول، ولا تمدد تاريخ الانتهاء.
    password_hash = _password_hash(TRIAL_PASSWORD)
    cursor.execute('''
        INSERT INTO users (username, full_name, password_hash, role_id, is_active, created_at)
        SELECT %s, %s, %s, r.id, 1, TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI')
        FROM roles r WHERE r.name = %s
        ON CONFLICT (username) DO UPDATE SET
            full_name = EXCLUDED.full_name,
            password_hash = EXCLUDED.password_hash,
            role_id = EXCLUDED.role_id,
            is_active = 1
    ''', (TRIAL_USERNAME, TRIAL_FULL_NAME, password_hash, TRIAL_ROLE_NAME))
    create_trial_tables(cursor)
