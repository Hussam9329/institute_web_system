# ============================================
# app.py - نقطة الدخول الرئيسية للتطبيق
# ============================================

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import (
    APP_TITLE,
    APP_VERSION,
    APP_DESCRIPTION,
    ensure_directories_exists,
    BASE_DIR,
)
from database import init_db

# استيراد المسارات
from api_routes import router as api_router
from main_routes import router as main_router
from pdf_routes import router as pdf_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    دورة حياة التطبيق
    """
    # ===== عند البدء =====
    print("\n" + "=" * 60)
    print(f"جاري تشغيل {APP_TITLE} v{APP_VERSION}")
    print("=" * 60)

    # إنشاء المجلدات المطلوبة
    ensure_directories_exists()

    # تهيئة قاعدة البيانات
    try:
        init_db()
        print("✅ تم تهيئة قاعدة البيانات بنجاح")
    except Exception as e:
        print(f"⚠️ خطأ أثناء تهيئة قاعدة البيانات: {e}")

    print("✅ التطبيق جاهز للعمل")
    print("=" * 60 + "\n")

    yield

    # ===== عند الإغلاق =====
    print("تم إيقاف التطبيق")


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan
)

# مجلد القوالب
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ربط الملفات الثابتة
static_dir = os.path.join(BASE_DIR, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# تسجيل المسارات
app.include_router(main_router)
app.include_router(api_router)
app.include_router(pdf_router)

# مرجع صحي بسيط
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": APP_TITLE,
        "version": APP_VERSION
    }
