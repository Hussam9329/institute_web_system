# ============================================
# app.py - نقطة الدخول الرئيسية للتطبيق
# ============================================

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from config import (
    APP_TITLE, APP_VERSION, APP_DESCRIPTION,
    HOST, PORT, DEBUG,
    ensure_directories_exists
)
from database import init_db

# استيراد المسارات
from routes.main_routes import router as main_router
from routes.api_routes import router as api_router
from routes.pdf_routes import router as pdf_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    دورة حياة التطبيق
    - يتم تشغيله عند بدء التشغيل
    - يتم تنظيفه عند الإيقاف
    """
    # ===== عند البدء =====
    print("\n" + "="*60)
    print(f"🚀 جاري تشغيل {APP_TITLE} v{APP_VERSION}")
    print("="*60 + "\n")
    
    # إنشاء المجلدات المطلوبة
    ensure_directories_exists()
    
    # تهيئة قاعدة البيانات
    init_db()
    
    print("\n✅ التطبيق جاهز للاستخدام!")
    print(f"📍 افتح المتصفح على: http://{HOST}:{PORT}\n")
    
    yield  # التطبيق يعمل هنا
    
    # ===== عند الإيقاف =====
    print("\n👋 تم إيقاف التطبيق")


# ===== إنشاء تطبيق FastAPI =====
app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    lifespan=lifespan
)

# ===== تسجيل المسارات =====
app.include_router(main_router)
app.include_router(api_router)
app.include_router(pdf_router)

# ===== خدمة الملفات الثابتة =====
app.mount("/static", StaticFiles(directory="static"), name="static")


# ===== الصفحة الرئيسية للـ API =====
@app.get("/api/health")
async def health_check():
    """فحص صحة التطبيق"""
    return {
        "status": "ok",
        "app": APP_TITLE,
        "version": APP_VERSION
    }


# ===== تشغيل التطبيق (للتشغيل المباشر) =====
if __name__ == "__main__":
    import uvicorn
    
    print(f"\n{'='*60}")
    print(f"🏫 {APP_TITLE}")
    print(f"📌 الإصدار: {APP_VERSION}")
    print(f"{'='*60}\n")
    
    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        reload=DEBUG
    )