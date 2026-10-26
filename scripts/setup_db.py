"""
setup_db.py — Create the bmp database, roles, and run migrations/seeds.

Usage:
    python scripts/setup_db.py            # bootstrap db/roles & run pending migrations
    python scripts/setup_db.py --seed     # run migrations then seed data
    python scripts/setup_db.py --reset    # drop and recreate dev database (DEV ONLY)

Requires:
    DATABASE_URL in .env pointing to bmp_owner on the bmp database.
    DATABASE_URL_ADMIN in .env (optional superuser url to bootstrap db/roles).
"""

import argparse
import os
import sys
import re
from pathlib import Path
from urllib.parse import urlparse, unquote

try:
    import psycopg
    from psycopg import sql as pgsql
    from psycopg.rows import dict_row
except ImportError:
    print("ERROR: psycopg not installed. Run: pip install psycopg[binary]")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

MIGRATIONS_DIR = BASE_DIR / "db" / "migrations"
SEED_DIR = BASE_DIR / "db" / "seed"

DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_URL_APP = os.environ.get("DATABASE_URL_APP")
DATABASE_URL_ADMIN = os.environ.get("DATABASE_URL_ADMIN")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)


def clean_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def url_password(url: str, var_name: str) -> str:
    """Return the password embedded in a connection URL from .env (never hardcoded here)."""
    pwd = urlparse(clean_url(url)).password if url else None
    if not pwd:
        print(f"ERROR: {var_name} in .env must contain a password (postgresql+psycopg://user:password@host:port/db)")
        sys.exit(1)
    return unquote(pwd)


def ensure_extensions(admin_url: str) -> None:
    """Create the required extensions inside 'bmp' as superuser.

    'vector' (pgvector) is not a trusted extension, so the non-superuser bmp_owner
    cannot create it; it must be created here by the admin connection.
    """
    bmp_admin_url = admin_url.rsplit("/", 1)[0] + "/bmp"
    with psycopg.connect(bmp_admin_url, autocommit=True) as conn:
        for ext in ("vector", "btree_gist", "pgcrypto"):
            try:
                conn.execute(f"CREATE EXTENSION IF NOT EXISTS {ext};")
            except Exception as exc:
                print(f"ERROR: could not create extension '{ext}': {exc}")
                if ext == "vector":
                    print("       pgvector must be installed for your PostgreSQL version (see README).")
                sys.exit(1)
    print("  Extensions vector, btree_gist, pgcrypto present.")


def bootstrap_database_and_roles():
    """Connect via admin URL to ensure roles, the bmp database and its extensions exist."""
    if not DATABASE_URL_ADMIN:
        print("Notice: DATABASE_URL_ADMIN not set in .env; skipping role/database bootstrap "
              "(assuming roles, database and extensions already exist).")
        return
    admin_url = clean_url(DATABASE_URL_ADMIN)
    owner_pwd = url_password(DATABASE_URL, "DATABASE_URL")
    app_pwd = url_password(DATABASE_URL_APP, "DATABASE_URL_APP")

    print("Checking database and roles via admin connection...")
    try:
        admin_conn = psycopg.connect(admin_url, autocommit=True)
    except Exception as exc:
        print(f"  Notice: Cannot connect as admin ({exc}); assuming database already exists.")
        return

    with admin_conn.cursor() as cur:
        # Check / create roles (passwords come from .env)
        cur.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('bmp_owner', 'bmp_app');")
        existing_roles = {r[0] for r in cur.fetchall()}

        if "bmp_owner" not in existing_roles:
            print("  Creating role 'bmp_owner'...")
        cur.execute(pgsql.SQL("{} ROLE bmp_owner WITH LOGIN PASSWORD {} CREATEDB").format(
            pgsql.SQL("ALTER" if "bmp_owner" in existing_roles else "CREATE"), pgsql.Literal(owner_pwd)))

        if "bmp_app" not in existing_roles:
            print("  Creating role 'bmp_app'...")
        cur.execute(pgsql.SQL("{} ROLE bmp_app WITH LOGIN PASSWORD {}").format(
            pgsql.SQL("ALTER" if "bmp_app" in existing_roles else "CREATE"), pgsql.Literal(app_pwd)))

        # Check / create database
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'bmp';")
        if not cur.fetchone():
            print("  Creating database 'bmp'...")
            cur.execute("CREATE DATABASE bmp OWNER bmp_owner;")
            cur.execute("GRANT ALL PRIVILEGES ON DATABASE bmp TO bmp_owner;")

    admin_conn.close()
    ensure_extensions(admin_url)
    print("Bootstrap check completed.")


def reset_database():
    """DEV ONLY: Drop and recreate bmp database to satisfy no-delete constraints."""
    if not DATABASE_URL_ADMIN:
        print("ERROR: --reset needs DATABASE_URL_ADMIN in .env")
        sys.exit(1)
    admin_url = clean_url(DATABASE_URL_ADMIN)
    print("Resetting database 'bmp' (DEV ONLY)...")
    try:
        admin_conn = psycopg.connect(admin_url, autocommit=True)
        with admin_conn.cursor() as cur:
            # Terminate active connections to bmp
            cur.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = 'bmp' AND pid <> pg_backend_pid();
            """)
            cur.execute("DROP DATABASE IF EXISTS bmp;")
            cur.execute("CREATE DATABASE bmp OWNER bmp_owner;")
            cur.execute("GRANT ALL PRIVILEGES ON DATABASE bmp TO bmp_owner;")
        admin_conn.close()
        print("Database 'bmp' reset successfully.")
    except Exception as exc:
        print(f"ERROR resetting database: {exc}")
        sys.exit(1)


def get_conn(autocommit: bool = False) -> psycopg.Connection:
    url = clean_url(DATABASE_URL)
    try:
        conn = psycopg.connect(url, autocommit=autocommit)
        return conn
    except Exception as exc:
        # If connection failed as bmp_owner, try admin connection to bmp
        if DATABASE_URL_ADMIN:
            admin_bmp = clean_url(DATABASE_URL_ADMIN).rsplit("/", 1)[0] + "/bmp"
            try:
                conn = psycopg.connect(admin_bmp, autocommit=autocommit)
                return conn
            except Exception:
                pass
        raise exc


def ensure_migrations_table(conn: psycopg.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename   text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now()
        );
    """)


def get_applied(conn: psycopg.Connection) -> set:
    rows = conn.execute("SELECT filename FROM schema_migrations").fetchall()
    return {r[0] for r in rows}


def run_migrations(conn: psycopg.Connection) -> int:
    ensure_migrations_table(conn)
    applied = get_applied(conn)
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    ran = 0
    for f in files:
        if f.name in applied:
            print(f"  [skip] {f.name}")
            continue
        print(f"  [run ] {f.name} ...", end=" ", flush=True)
        sql = f.read_text(encoding="utf-8")
        try:
            conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)", (f.name,)
            )
            conn.commit()
            print("OK")
            ran += 1
        except Exception as exc:
            conn.rollback()
            print(f"\nFAILED: {exc}")
            raise
    return ran


def run_seeds(conn: psycopg.Connection) -> None:
    """Run each seed file once. Applied seed files are recorded in schema_seeds and skipped on
    later runs, so `--seed` is safe to repeat. To reload seed data, use `--reset --seed` (dev only)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_seeds (
            filename   text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now()
        );
    """)
    applied = {r[0] for r in conn.execute("SELECT filename FROM schema_seeds").fetchall()}
    files = sorted(SEED_DIR.glob("*.sql"))
    for f in files:
        if f.name in applied:
            print(f"  [skip] {f.name} (already seeded; use --reset --seed to reload)")
            continue
        print(f"  [seed] {f.name} ...", end=" ", flush=True)
        sql = f.read_text(encoding="utf-8")
        try:
            conn.execute(sql)
            conn.execute("INSERT INTO schema_seeds (filename) VALUES (%s)", (f.name,))
            conn.commit()
            print("OK")
        except Exception as exc:
            conn.rollback()
            print(f"\nFAILED: {exc}")
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="BMP database setup")
    parser.add_argument("--seed", action="store_true", help="Run seed scripts after migrations")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate database bmp (DEV ONLY)")
    args = parser.parse_args()

    if args.reset:
        reset_database()

    bootstrap_database_and_roles()

    print("Connecting to database 'bmp'...")
    try:
        conn = get_conn()
    except Exception as exc:
        print(f"ERROR: Cannot connect to bmp database: {exc}")
        sys.exit(1)

    print("Running migrations...")
    ran = run_migrations(conn)
    print(f"Migrations: {ran} applied.")

    if args.seed:
        print("Running seed scripts...")
        run_seeds(conn)

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
