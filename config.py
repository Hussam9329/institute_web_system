# ============================================
# config.py - الإعدادات والثوابت الأساسية
# ============================================

import os

# ===== إعدادات التطبيق =====
APP_TITLE = "نظام إدارة المعهد المتكامل"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "نظام محاسبي وإداري متكامل للمعاهد التعليمية"

# ===== إعدادات السيرفر =====
HOST = "0.0.0.0"
PORT = 8000
DEBUG = True

# ===== إعدادات قاعدة البيانات =====
# يمكن تعيين متغير البيئة DATABASE_URL أو سيتم استخدام القيمة الافتراضية
# مثال: export DATABASE_URL="postgresql://user:pass@host/db"
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# فحص توفر رابط قاعدة البيانات
DB_AVAILABLE = bool(DATABASE_URL)

# ===== مفتاح التشفير للجلسات =====
SECRET_KEY = os.environ.get("SECRET_KEY", "institute-system-change-in-production-2024")

# ===== كلمة مرور النظام =====
SYSTEM_PIN = "1111"

# ===== مسارات الملفات =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# في Vercel، فقط /tmp قابل للكتابة
IS_VERCEL = os.environ.get("VERCEL") == "1"
TMP_DIR = "/tmp" if IS_VERCEL else BASE_DIR

REPORTS_DIR = os.path.join(TMP_DIR, "reports")
STUDENT_PDFS_DIR = os.path.join(REPORTS_DIR, "student_pdfs")
TEACHER_PDFS_DIR = os.path.join(REPORTS_DIR, "teacher_pdfs")
RECEIPTS_DIR = os.path.join(REPORTS_DIR, "receipts")

# ===== أنواع الدراسة =====
STUDY_TYPES = ["حضوري", "الكتروني", "مدمج"]

# ===== حالات الطالب =====
STUDENT_STATUSES = ["مستمر", "منسحب", "غير مربوط"]

# ===== أنواع الأقساط =====
INSTALLMENT_TYPES = [
    "القسط الأول",
    "القسط الثاني",
    "دفع كامل"
]

# ===== إعدادات PDF =====
PDF_FONT_PATH = os.path.join(BASE_DIR, "static", "fonts", "arial.ttf")
PDF_PAGE_SIZE = "A4"

# ===== إنشاء المجلدات المطلوبة =====
def ensure_directories_exists():
    """إنشاء المجلدات إذا لم تكن موجودة"""
    directories = [
        REPORTS_DIR,
        STUDENT_PDFS_DIR,
        TEACHER_PDFS_DIR,
        RECEIPTS_DIR,
        os.path.join(BASE_DIR, "static", "fonts")
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError:
                pass  # تجاهل الأخطاء على Vercel (مجلدات readonly)

# ===== تنسيق العملة =====
def format_currency(amount: int) -> str:
    """
    تنسيق المبلغ بالدينار العراقي مع فاصلة الآلاف
    Input: 150000 (integer)
    Output: "150.000 د.ع"
    يدعم القيم السالبة: -5000 → "-5.000 د.ع"
    """
    if amount is None:
        return "0 د.ع"
    
    # التعامل مع القيم السالبة
    is_negative = amount < 0
    abs_amount = abs(amount)
    
    # تحويل لـ string واستبدال الفاصلة بنقطة
    formatted = f"{abs_amount:,}".replace(",", ".")
    
    if is_negative:
        return f"-{formatted} د.ع"
    return f"{formatted} د.ع"

# ===== تنسيق التاريخ =====
def format_date(date_string: str) -> str:
    """
    تنسيق التاريخ للعرض
    Input: "2024-01-15"
    Output: "15/01/2024"
    """
    if not date_string:
        return ""
    
    try:
        from datetime import datetime
        date_obj = datetime.strptime(date_string, "%Y-%m-%d")
        return date_obj.strftime("%d/%m/%Y")
    except:
        return date_string

# ===== تنسيق تاريخ ووقت التقارير =====
def format_report_datetime() -> str:
    """
    تنسيق التاريخ والوقت الحالي للتقارير بشكل عربي
    Output: "15/01/2025 - 03:30 م"
    """
    from datetime import datetime
    now = datetime.now()
    ampm = "ص" if now.hour < 12 else "م"
    hours = now.hour % 12
    hours = hours if hours else 12
    return now.strftime(f"%d/%m/%Y - {hours}:%M {ampm}")

def format_report_date() -> str:
    """تنسيق التاريخ فقط للتقارير: DD/MM/YYYY"""
    from datetime import datetime
    return datetime.now().strftime("%d/%m/%Y")

def format_report_time() -> str:
    """تنسيق الوقت فقط للتقارير: 12 ساعة مع ص/م"""
    from datetime import datetime
    now = datetime.now()
    ampm = "ص" if now.hour < 12 else "م"
    hours = now.hour % 12
    hours = hours if hours else 12
    return f"{hours}:{now.strftime('%M')} {ampm}"

# ===== الحصول على التاريخ الحالي =====
def get_current_date() -> str:
    """إرجاع التاريخ الحالي بصيغة YYYY-MM-DD"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")

# ===== الحصول على الوقت الحالي =====
def get_current_datetime() -> str:
    """إرجاع التاريخ والوقت الحالي"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ===== توليد باركود فريد =====
def generate_barcode(student_id: int) -> str:
    """توليد رمز باركود فريد للطالب"""
    from datetime import datetime
    year = datetime.now().year
    return f"STU-{year}-{str(student_id).zfill(6)}"
