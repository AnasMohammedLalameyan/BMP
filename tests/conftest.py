"""
tests/conftest.py — Pytest fixtures for BMP Compliance Platform database tests.
"""

import os
import pytest
import psycopg
from psycopg.rows import dict_row
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_URL_APP = os.environ.get("DATABASE_URL_APP")


def clean_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture(scope="session")
def owner_conn():
    """Connection as bmp_owner (bypasses RLS, used for setup / assertion checks)."""
    conn = psycopg.connect(clean_url(DATABASE_URL), autocommit=False)
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def owner_cur(owner_conn):
    """Cursor as bmp_owner inside an isolated transaction that rolls back after test."""
    cur = owner_conn.cursor(row_factory=dict_row)
    # Set seed user as default actor
    cur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = cur.fetchone()["id"]
    cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))
    yield cur
    owner_conn.rollback()


@pytest.fixture(scope="function")
def app_conn():
    """Connection as bmp_app (application role, subject to RLS and delete restrictions)."""
    conn = psycopg.connect(clean_url(DATABASE_URL_APP), autocommit=False)
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def app_cur(app_conn):
    """Cursor as bmp_app inside a rolling-back transaction."""
    cur = app_conn.cursor(row_factory=dict_row)
    yield cur
    app_conn.rollback()
