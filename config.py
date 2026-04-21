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
DATABASE_URL = "sqlite:///./institute.db"
DATABASE_NAME = "institute.db"

# ===== الثوابت المالية (مهم: لا تغيّرها) =====
# الوحدة: دينار عراقي (Integer)
INSTITUTE_DEDUCTION_PER_STUDENT = 50000  # 50,000 دينار لكل طالب دافع

# ===== مسارات الملفات =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
STUDENT_PDFS_DIR = os.path.join(REPORTS_DIR, "student_pdfs")
TEACHER_PDFS_DIR = os.path.join(REPORTS_DIR, "teacher_pdfs")
RECEIPTS_DIR = os.path.join(REPORTS_DIR, "receipts")

# ===== أنواع الدراسة =====
STUDY_TYPES = ["حضوري", "الكتروني"]

# ===== حالات الطالب =====
STUDENT_STATUSES = ["مستمر", "منسحب", "مكتمل"]

# ===== أنواع الأقساط =====
INSTALLMENT_TYPES = [
    "القسط الأول",
    "القسط الثاني",
    "القسط الثالث",
    "دفع كامل",
    "دفعة جزئية"
]

# ===== إعدادات PDF =====
PDF_FONT_PATH = os.path.join(BASE_DIR, "static", "fonts", "arial.ttf")
PDF_PAGE_SIZE = "A4"

# ===== إنشاء المجلدات المطلوبة =====
def ensure_directories_exist():
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
            os.makedirs(directory)
            print(f"✅ تم إنشاء المجلد: {directory}")

# ===== تنسيق العملة =====
def format_currency(amount: int) -> str:
    """
    تنسيق المبلغ بالدينار العراقي مع فاصلة الآلاف
    Input: 150000 (integer)
    Output: "150,000 د.ع"
    """
    if amount is None:
        return "0 د.ع"
    
    # تحويل لـ string وإضافة فاصلة الآلاف
    formatted = f"{amount:,}"
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