# ============================================
# app.py - نقطة الدخول الرئيسية للتطبيق
# ============================================
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request as StarletteRequest

# ===== توافقية Flask: جعل request.args يعمل في FastAPI =====
# في Starlette/FastAPI query parameters تُ accessed عبر request.query_params
# بينما في Flask تُ accessed عبر request.args
# نضيف خاصية args كـ alias لـ query_params
if not hasattr(StarletteRequest, 'args'):
    @property
    def _request_args(self):
        return self.query_params
    StarletteRequest.args = _request_args

from config import (
    APP_TITLE, APP_VERSION, APP_DESCRIPTION,
    HOST, PORT, DEBUG,
    ensure_directories_exists,
    BASE_DIR
)
from database import init_db

# استيراد المسارات
from routes.main_routes import router as main_router
from routes.api_routes import router as api_router
from routes.pdf_routes import router as pdf_router
from routes.report_routes import router as report_router
from routes.permissions_routes import router as permissions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    دورة حياة التطبيق
    """
    # ===== عند البدء =====
    print("\n" + "=" * 60)
    print(f"جاري تشغيل {APP_TITLE} v{APP_VERSION}")
    print("=" * 60 + "\n")

    # إنشاء المجلدات المطلوبة
    try:
        ensure_directories_exists()
    except:
        pass

    # تهيئة قاعدة البيانات
    try:
        init_db()
        print("تم تهيئة قاعدة البيانات بنجاح")
    except Exception as e:
        print(f"تحذير: لم يتم تهيئة قاعدة البيانات: {e}")

    print("\nالتطبيق جاهز للاستخدام!")

    yield  # التطبيق يعمل هنا

    # ===== عند الإيقاف =====
    print("\nتم إيقاف التطبيق")


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
app.include_router(report_router)
app.include_router(permissions_router)

# مجلد القوالب
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ===== خدمة الملفات الثابتة =====
static_dir = os.path.join(BASE_DIR, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ===== الصفحة الرئيسية للـ API =====
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
