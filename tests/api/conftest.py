"""Fixtures for the web-application tests.

Each test session builds a throwaway database (bmp_api_test) from the Phase 1 migrations and seed files, starts the
real FastAPI application against it, and signs in as three different people (an administrator, a manager with
write access to three companies, and a read-only client of one company). The demo database `bmp` is never touched.

The PostgreSQL administrator login (DATABASE_URL_ADMIN in .env) is needed once, to create the throwaway database.
"""
from __future__ import annotations

import itertools
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg
import pytest
from psycopg.rows import dict_row

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))

from dotenv import load_dotenv                                  # noqa: E402

load_dotenv(BASE / ".env")

from fastapi.testclient import TestClient                       # noqa: E402

from app.config import Settings                                  # noqa: E402
from app.main import create_app                                  # noqa: E402
from app.security import UsersStore                              # noqa: E402

TEST_DB = "bmp_api_test"
PASSWORDS = {"admin@bmpco.in": "Admin#Pass123", "manager@bmpco.in": "Manager#Pass123", "client@nexatech.co.in": "Client#Pass123"}


def _pg(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def _with_db(url: str, db: str) -> str:
    u = urlparse(_pg(url))
    return urlunparse(u._replace(path="/" + db))


@pytest.fixture(scope="session")
def dsn():
    admin, owner, app = (os.environ.get(k) for k in ("DATABASE_URL_ADMIN", "DATABASE_URL", "DATABASE_URL_APP"))
    if not (admin and owner and app):
        pytest.skip("DATABASE_URL_ADMIN, DATABASE_URL and DATABASE_URL_APP must be set in .env to run the web tests")
    return {"admin": _with_db(admin, "postgres"), "admin_test": _with_db(admin, TEST_DB),
            "owner": _with_db(owner, TEST_DB), "app": _with_db(app, TEST_DB)}


@pytest.fixture(scope="session")
def test_database(dsn):
    """Create bmp_api_test and load the Phase 1 schema and seed data into it."""
    with psycopg.connect(dsn["admin"], autocommit=True) as admin:
        admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()", (TEST_DB,))
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        admin.execute(f"CREATE DATABASE {TEST_DB} OWNER bmp_owner")
    with psycopg.connect(dsn["admin_test"], autocommit=True) as admin:
        for ext in ("vector", "btree_gist", "pgcrypto"):
            admin.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")
    with psycopg.connect(dsn["owner"]) as owner:
        for folder in ("migrations", "seed"):
            for f in sorted((BASE / "db" / folder).glob("*.sql")):
                owner.execute(f.read_text(encoding="utf-8"))
                owner.commit()
    yield TEST_DB
    with psycopg.connect(dsn["admin"], autocommit=True) as admin:
        admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()", (TEST_DB,))
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")


@pytest.fixture(scope="session")
def workdir(tmp_path_factory):
    return tmp_path_factory.mktemp("bmp_web")


def make_settings(dsn, workdir, **overrides) -> Settings:
    base = dict(
        env="development", secret_key="x" * 48, db_app=dsn["app"], db_privileged=dsn["owner"], session_max_age=3600,
        cookie_secure=False, storage_dir=workdir / "storage", max_upload_bytes=1024 * 1024, users_file=workdir / "users.json",
        allow_portal_secret=False, allow_aadhaar=False, encryption_key=None, pool_min=1, pool_max=6,
        login_max_failures=5, login_window_seconds=600, enforce_task_confirmation=True)
    base.update(overrides)
    return Settings(**base)


@pytest.fixture(scope="session")
def settings(dsn, test_database, workdir):
    s = make_settings(dsn, workdir)
    store = UsersStore(s.users_file)
    for email, pw in PASSWORDS.items():
        store.set_password(email, pw)
    return s


@pytest.fixture(scope="session")
def app(settings):
    application = create_app(settings)
    with TestClient(application):          # runs the start-up (pools, catalog) once for the whole session
        yield application


class Session:
    """A signed-in browser: cookies plus the CSRF header, with short helpers."""

    def __init__(self, app, email: str | None = None, password: str | None = None):
        self.http = TestClient(app)
        self.csrf = None
        if email:
            r = self.http.post("/api/auth/login", json={"email": email, "password": password})
            assert r.status_code == 200, r.text
            self.csrf = r.json()["csrf"]
            self.http.headers["X-CSRF-Token"] = self.csrf
            self.user = r.json()["user"]

    def get(self, path, **kw):
        return self.http.get("/api" + path, **kw)

    def post(self, path, json=None, **kw):
        return self.http.post("/api" + path, json=json if json is not None else {}, **kw)

    def patch(self, path, json, **kw):
        return self.http.patch("/api" + path, json=json, **kw)

    def put(self, path, json, **kw):
        return self.http.put("/api" + path, json=json, **kw)

    def ok(self, resp, status=200):
        assert resp.status_code == status, f"{resp.status_code}: {resp.text[:600]}"
        return resp.json()


@pytest.fixture(scope="session")
def anon(app):
    return Session(app)


@pytest.fixture(scope="session")
def admin(app):
    return Session(app, "admin@bmpco.in", PASSWORDS["admin@bmpco.in"])


@pytest.fixture(scope="session")
def manager(app):
    return Session(app, "manager@bmpco.in", PASSWORDS["manager@bmpco.in"])


@pytest.fixture(scope="session")
def client(app):
    return Session(app, "client@nexatech.co.in", PASSWORDS["client@nexatech.co.in"])


@pytest.fixture(scope="session")
def owner(dsn, test_database):
    """Direct owner connection to the test database, for assertions the API deliberately cannot make."""
    with psycopg.connect(dsn["owner"], row_factory=dict_row, autocommit=True) as conn:
        yield conn


@pytest.fixture(scope="session")
def uniq():
    counter = itertools.count(1)
    return lambda: next(counter)
