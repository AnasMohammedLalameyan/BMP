#!/usr/bin/env python3
"""
scripts/manage_users.py - set sign-in passwords for the people in core.app_user.

The Phase 1 database deliberately has no password column, so passwords are kept (as salted scrypt hashes) in
a separate file - USERS_FILE, default instance/users.json - that the web application reads. A person can sign
in only when BOTH exist: a password here and an active row in core.app_user (which gives them a role and
company access).

Usage:
    python scripts/manage_users.py list                      # who is in the database, who has a password
    python scripts/manage_users.py set-password EMAIL        # prompts for the password
    python scripts/manage_users.py init-demo                 # one password for the three demo users (development only)
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import psycopg                                         # noqa: E402
from psycopg.rows import dict_row                      # noqa: E402

from app.config import Settings                        # noqa: E402
from app.security import MIN_PASSWORD_LENGTH, UsersStore   # noqa: E402

DEMO_USERS = ["admin@bmpco.in", "manager@bmpco.in", "client@nexatech.co.in"]


def db_users(settings):
    with psycopg.connect(settings.db_app, row_factory=dict_row) as conn:
        return conn.execute(
            """SELECT u.email, u.name, u.is_active, r.name AS role FROM core.app_user u
               LEFT JOIN core.role r ON r.id = u.role_id WHERE NOT u.is_archived ORDER BY u.email""").fetchall()


def ask(prompt_text):
    first = getpass.getpass(f"{prompt_text} (at least {MIN_PASSWORD_LENGTH} characters): ")
    if getpass.getpass("Repeat it: ") != first:
        sys.exit("The two entries do not match. Nothing was changed.")
    return first


def main():
    parser = argparse.ArgumentParser(description="Manage sign-in passwords")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sp = sub.add_parser("set-password")
    sp.add_argument("email")
    sub.add_parser("init-demo")
    args = parser.parse_args()

    settings = Settings.load()
    store = UsersStore(settings.users_file)
    users = {u["email"].lower(): u for u in db_users(settings)}

    if args.cmd == "list":
        have = set(store.emails())
        print(f"Credentials file: {settings.users_file}")
        for email, u in users.items():
            print(f"  {email:<28} {u['role'] or '-':<8} {'active' if u['is_active'] else 'inactive':<9} "
                  f"{'password set' if email in have else 'NO PASSWORD'}")
        return

    if args.cmd == "set-password":
        email = args.email.strip().lower()
        if email not in users:
            sys.exit(f"{email} is not a user in the database. Add them first (Administration > Users).")
        store.set_password(email, ask(f"New password for {email}"))
        print(f"Password set for {email}.")
        return

    if args.cmd == "init-demo":
        if settings.is_production:
            sys.exit("init-demo is for development only (APP_ENV=production).")
        pw = ask("Password to use for the demo users " + ", ".join(DEMO_USERS))
        for email in DEMO_USERS:
            if email in users:
                store.set_password(email, pw)
                print(f"  password set for {email}")
        print(f"Saved to {settings.users_file}")


if __name__ == "__main__":
    main()
