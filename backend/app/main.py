from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal
from app.routers import admin, auth, portal, projects, vault, gitlab, credentials, monitoring, demo
from app.security import session_cookie_name, get_session, verify_csrf


settings = get_settings()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.portal_allowed_hosts)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Pydantic normally echoes rejected inputs, including submitted credentials.
    return JSONResponse(status_code=422, content={"detail": [
        {key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]})


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    settings = get_settings()
    path = request.url.path.removeprefix(request.scope.get("root_path", ""))
    # The mounted application owns its session and CSRF checks. Never resolve
    # its cookies against the production database in this outer middleware.
    if not settings.demo_mode and path.startswith("/api/demo-instance/"):
        return await call_next(request)
    unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
    csrf_exempt = path == "/api/auth/login" or (settings.demo_mode and path == "/api/demo/login")
    machine_report = path == "/api/monitoring/report" and request.method == "POST"
    if unsafe and csrf_exempt:
        origin = request.headers.get("origin")
        if origin:
            from urllib.parse import urlsplit

            parsed = urlsplit(origin)
            if parsed.netloc.lower() != request.headers.get("host", "").lower():
                return JSONResponse(status_code=403, content={"detail": "Fremder Anfrageursprung abgelehnt."})
    if unsafe and not csrf_exempt and not machine_report:
        with SessionLocal() as db:
            portal_session = get_session(db, request.cookies.get(session_cookie_name()))
            if portal_session is None:
                return JSONResponse(status_code=401, content={"detail": "Anmeldung erforderlich."})
            if not verify_csrf(portal_session, request.headers.get("x-csrf-token")):
                return JSONResponse(status_code=403, content={"detail": "CSRF-Prüfung fehlgeschlagen."})
            db.commit()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if settings.demo_mode:
        response.headers["X-Semaporter-Mode"] = "demo"
        response.headers["Cache-Control"] = "no-store"
    if settings.portal_cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/api/health", tags=["System"])
def health() -> dict[str, str]:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(portal.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(vault.router, prefix="/api")
app.include_router(gitlab.router, prefix="/api")
app.include_router(credentials.router, prefix="/api")
app.include_router(monitoring.router, prefix="/api")

app.include_router(demo.router, prefix="/api")

if settings.demo_enabled:
    from app.demo.application import DemoApplication
    demo_app = FastAPI(title="Semaporter Demo", docs_url=None, openapi_url=None)
    demo_app.add_exception_handler(RequestValidationError, validation_error)
    demo_app.middleware("http")(security_middleware)
    for module in (auth, admin, portal, projects, vault, gitlab, credentials, monitoring, demo):
        demo_app.include_router(module.router, prefix="/api")
    demo_app.get("/api/health")(health)
    app.mount("/api/demo-instance", DemoApplication(demo_app, settings))

