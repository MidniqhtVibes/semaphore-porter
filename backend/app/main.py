from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal
from app.routers import admin, auth, portal
from app.security import SESSION_COOKIE, get_session, verify_csrf


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.portal_allowed_hosts)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
    csrf_exempt = request.url.path in {"/api/auth/login"}
    if unsafe and csrf_exempt:
        origin = request.headers.get("origin")
        if origin:
            from urllib.parse import urlsplit

            parsed = urlsplit(origin)
            if parsed.netloc.lower() != request.headers.get("host", "").lower():
                return JSONResponse(status_code=403, content={"detail": "Fremder Anfrageursprung abgelehnt."})
    if unsafe and not csrf_exempt:
        with SessionLocal() as db:
            portal_session = get_session(db, request.cookies.get(SESSION_COOKIE))
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

