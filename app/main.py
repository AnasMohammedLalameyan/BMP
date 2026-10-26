"""BMP Compliance Platform - application factory.

Run it with:   uvicorn app.main:app            (development)
               uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2   (production)
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from .config import Settings
from .crud import Engine
from .db import Database
from .errors import ApiError, map_db_error
from .responses import ApiResponse
from .schema_meta import load_catalog
from .security import LoginThrottle, UsersStore

APP_DIR = Path(__file__).resolve().parent
VERSION = "1.0.0"
MAX_JSON_BYTES = 2 * 1024 * 1024          # every endpoint except file upload
log = logging.getLogger("bmp")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.db_app, name="app", min_size=settings.pool_min, max_size=settings.pool_max)
        db.open()
        priv = None
        if settings.db_privileged:
            priv = Database(settings.db_privileged, name="privileged", min_size=0, max_size=3)
            priv.open()
        with db.tx(None, readonly=True) as conn:
            catalog = load_catalog(conn)
        app.state.settings = settings
        app.state.db = db
        app.state.db_privileged = priv
        app.state.catalog = catalog
        app.state.engine = Engine(catalog, settings)
        app.state.users = UsersStore(settings.users_file)
        app.state.throttle = LoginThrottle(settings.login_max_failures, settings.login_window_seconds)
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        log.info("BMP Compliance Platform %s started (%s)", VERSION, settings.env)
        try:
            yield
        finally:
            if priv:
                priv.close()
            db.close()

    app = FastAPI(
        title="BMP Compliance Platform API", version=VERSION, lifespan=lifespan,
        docs_url=None if settings.is_production else "/api/docs", redoc_url=None,
        openapi_url=None if settings.is_production else "/api/openapi.json",
    )
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie="bmp_session",
                       max_age=settings.session_max_age, same_site="lax", https_only=settings.cookie_secure)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        started = time.perf_counter()
        request_id = uuid.uuid4().hex[:12]
        length = request.headers.get("content-length")
        too_big = (length and length.isdigit() and int(length) > MAX_JSON_BYTES
                   and not request.url.path.endswith(("/documents/upload", "/minutes/parse")))
        if too_big:
            return ApiResponse({"error": {"code": "too_large", "message": "The request is too large."}}, 413)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/api/") and request.url.path != "/api/health":
            who = request.session.get("uid") if "session" in request.scope else None
            log.info("%s %s %s %s %.0fms user=%s", request_id, request.method, request.url.path, response.status_code,
                     (time.perf_counter() - started) * 1000, who)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", CSP)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        elif request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    # ---- errors: always a JSON body {"error": {...}} ----------------------------------
    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        return ApiResponse(exc.body(), exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = {".".join(str(p) for p in e["loc"][1:]) or "body": e["msg"] for e in exc.errors()}
        return ApiResponse({"error": {"code": "validation", "message": "The request is not valid.", "fields": fields}}, 422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        return ApiResponse({"error": {"code": "http_%d" % exc.status_code, "message": str(exc.detail)}}, exc.status_code)

    @app.exception_handler(psycopg.Error)
    async def db_error(_: Request, exc: psycopg.Error):
        mapped = map_db_error(exc)
        return ApiResponse(mapped.body(), mapped.status)

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception):
        log.exception("unhandled error", exc_info=exc)
        return ApiResponse({"error": {"code": "internal", "message": "Something went wrong. The error has been logged."}}, 500)

    # ---- routes ---------------------------------------------------------------------------
    from .routers import activities, ai, audit, auth, companies, documents, entities, meetings, meta, minutes_api, notifications, people, views

    for module in (auth, meta, entities, companies, people, notifications, meetings, views, activities, documents, audit, minutes_api, ai):
        app.include_router(module.router, prefix="/api")

    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

    @app.get("/", include_in_schema=False)
    def index(request: Request):
        return templates.TemplateResponse(request, "dashboard.html", {"version": VERSION})

    @app.get("/activities-dashboard", include_in_schema=False)
    def activities_dashboard(request: Request):
        return templates.TemplateResponse(request, "activities_dashboard.html", {"version": VERSION})

    @app.get("/api/health", include_in_schema=False)
    def health(request: Request):
        up = request.app.state.db.ping()
        from .ai.settings import AiSettings
        return ApiResponse({"status": "ok" if up else "degraded", "database": up, "version": VERSION,
                            "ai": (getattr(request.app.state, "ai_settings", None) or AiSettings.load()).status()["enabled"]},
                           200 if up else 503)

    return app


def _default_app() -> FastAPI:
    return create_app()


# `uvicorn app.main:app` - created lazily so importing this module (tests) needs no environment.
def __getattr__(name: str):
    if name == "app":
        global _app
        try:
            return _app
        except NameError:
            _app = _default_app()
            return _app
    raise AttributeError(name)
