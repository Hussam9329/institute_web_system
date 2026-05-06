# ============================================
# app.py - نقطة الدخول الرئيسية للتطبيق
# ============================================
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request as StarletteRequest

# ===== توافقية Flask: جعل request.args يعمل في FastAPI =====
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
from auth import auth_middleware, login_user, create_session_token, SESSION_COOKIE

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

# ===== وسيط المصادقة =====
app.middleware("http")(auth_middleware)

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

# ===== مسارات تسجيل الدخول والخروج =====

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    """صفحة تسجيل الدخول"""
    # إذا كان المستخدم مسجل الدخول بالفعل، وجّهه للرئيسية
    from auth import get_current_user
    user = get_current_user(request)
    if user:
        return RedirectResponse(url='/', status_code=303)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "app_title": APP_TITLE,
    })


@app.post("/api/login")
async def api_login(request: Request, username: str = Form(...), password: str = Form("")):
    """تسجيل الدخول - API"""
    user = login_user(username, password)
    if not user:
        # تحقق هل كان الطلب من نموذج HTML
        content_type = request.headers.get('content-type', '')
        if 'application/json' in content_type:
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "اسم المستخدم أو كلمة المرور غير صحيحة"}
            )
        return RedirectResponse(url='/login?error=invalid', status_code=303)

    # إنشاء جلسة
    token = create_session_token(user['id'])
    response = RedirectResponse(url='/', status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=86400 * 7,  # 7 أيام
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/api/logout")
async def api_logout(request: Request):
    """تسجيل الخروج"""
    response = RedirectResponse(url='/login', status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


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
