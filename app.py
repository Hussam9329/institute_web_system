# ============================================
# app.py - نقطة الدخول الرئيسية للتطبيق
# ============================================
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from config import (
    APP_TITLE, APP_VERSION, APP_DESCRIPTION,
    HOST, PORT, DEBUG,
    APP_TITLE,
    APP_VERSION,
    APP_DESCRIPTION,
    ensure_directories_exists,
    BASE_DIR
    BASE_DIR,
)
from database import init_db

# استيراد المسارات
from routes.main_routes import router as main_router
from routes.api_routes import router as api_router
from routes.pdf_routes import router as pdf_router
from api_routes import router as api_router
from main_routes import router as main_router
from pdf_routes import router as pdf_router


@asynccontextmanager
@@ -28,71 +30,54 @@ async def lifespan(app: FastAPI):
    دورة حياة التطبيق
    """
    # ===== عند البدء =====
    print("\n" + "="*60)
    print("\n" + "=" * 60)
    print(f"جاري تشغيل {APP_TITLE} v{APP_VERSION}")
    print("="*60 + "\n")
    
    print("=" * 60)

    # إنشاء المجلدات المطلوبة
    ensure_directories_exists()
    

    # تهيئة قاعدة البيانات
    try:
        init_db()
        print("تم تهيئة قاعدة البيانات بنجاح")
        print("✅ تم تهيئة قاعدة البيانات بنجاح")
    except Exception as e:
        print(f"تحذير: لم يتم تهيئة قاعدة البيانات: {e}")
    
    print("\nالتطبيق جاهز للاستخدام!")
    print(f"افتح المتصفح على: http://{HOST}:{PORT}\n")
    
    yield  # التطبيق يعمل هنا
    
    # ===== عند الإيقاف =====
    print("\nتم إيقاف التطبيق")


# ===== إنشاء تطبيق FastAPI =====
        print(f"⚠️ خطأ أثناء تهيئة قاعدة البيانات: {e}")

    print("✅ التطبيق جاهز للعمل")
    print("=" * 60 + "\n")

    yield

    # ===== عند الإغلاق =====
    print("تم إيقاف التطبيق")


app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan
)

# ===== تسجيل المسارات =====
app.include_router(main_router)
app.include_router(api_router)
app.include_router(pdf_router)
# مجلد القوالب
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ===== خدمة الملفات الثابتة =====
# ربط الملفات الثابتة
static_dir = os.path.join(BASE_DIR, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# تسجيل المسارات
app.include_router(main_router)
app.include_router(api_router)
app.include_router(pdf_router)

# ===== الصفحة الرئيسية للـ API =====
@app.get("/api/health")
# مرجع صحي بسيط
@app.get("/health")
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
    print(f"{APP_TITLE}")
    print(f"الإصدار: {APP_VERSION}")
    print(f"{'='*60}\n")
    
    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        reload=DEBUG
    )
