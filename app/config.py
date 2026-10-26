"""Runtime settings, read once from the environment (and the project's .env file).

Nothing here is a secret default: the only value that may be generated is the session
signing key, and only when APP_ENV=development (sessions then end when the server
restarts). In production the process refuses to start without it.
"""
from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

log = logging.getLogger("bmp.config")


def _pg(name: str) -> str | None:
    value = os.environ.get(name)
    return value.replace("postgresql+psycopg://", "postgresql://") if value else None


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _path(name: str, default: str) -> Path:
    raw = os.environ.get(name) or default
    p = Path(raw)
    return p if p.is_absolute() else (BASE_DIR / p)


@dataclass(frozen=True)
class Settings:
    env: str
    secret_key: str
    db_app: str                      # bmp_app: every normal request (subject to RLS, no DELETE)
    db_privileged: str | None        # bmp_owner: audit-log reads and company onboarding only
    session_max_age: int
    cookie_secure: bool
    storage_dir: Path
    max_upload_bytes: int
    users_file: Path
    allow_portal_secret: bool
    allow_aadhaar: bool
    encryption_key: str | None
    pool_min: int
    pool_max: int
    login_max_failures: int
    login_window_seconds: int
    enforce_task_confirmation: bool

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @classmethod
    def load(cls) -> "Settings":
        env = (os.environ.get("APP_ENV") or "development").strip().lower()
        if env not in {"development", "production"}:
            raise RuntimeError("APP_ENV must be 'development' or 'production'")

        secret = os.environ.get("APP_SECRET_KEY", "").strip()
        if not secret:
            if env == "production":
                raise RuntimeError("APP_SECRET_KEY must be set when APP_ENV=production")
            secret = secrets.token_urlsafe(48)
            log.warning("APP_SECRET_KEY not set: using a temporary key (sessions end on restart)")
        elif len(secret) < 32 and env == "production":
            raise RuntimeError("APP_SECRET_KEY must be at least 32 characters in production")

        db_app = _pg("DATABASE_URL_APP")
        if not db_app:
            raise RuntimeError("DATABASE_URL_APP is not set (the bmp_app login, see .env.example)")

        allow_portal = _bool("ALLOW_PORTAL_SECRET_STORAGE", False)
        allow_aadhaar = _bool("ALLOW_AADHAAR_STORAGE", False)
        enc_key = os.environ.get("APP_ENCRYPTION_KEY", "").strip() or None
        if (allow_portal or allow_aadhaar) and not enc_key:
            raise RuntimeError(
                "APP_ENCRYPTION_KEY must be set when ALLOW_PORTAL_SECRET_STORAGE or "
                "ALLOW_AADHAAR_STORAGE is enabled")

        return cls(
            env=env,
            secret_key=secret,
            db_app=db_app,
            db_privileged=_pg("DATABASE_URL_PRIVILEGED") or _pg("DATABASE_URL"),
            session_max_age=_int("SESSION_MAX_AGE_SECONDS", 8 * 3600),
            cookie_secure=_bool("COOKIE_SECURE", env == "production"),
            storage_dir=_path("STORAGE_DIR", "storage"),
            max_upload_bytes=_int("MAX_UPLOAD_MB", 25) * 1024 * 1024,
            users_file=_path("USERS_FILE", "instance/users.json"),
            allow_portal_secret=allow_portal,
            allow_aadhaar=allow_aadhaar,
            encryption_key=enc_key,
            pool_min=_int("DB_POOL_MIN", 1),
            pool_max=_int("DB_POOL_MAX", 10),
            login_max_failures=_int("LOGIN_MAX_FAILURES", 5),
            login_window_seconds=_int("LOGIN_WINDOW_SECONDS", 600),
            enforce_task_confirmation=_bool("ENFORCE_TASK_CONFIRMATION", True),
        )
