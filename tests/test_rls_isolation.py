"""
test_rls_isolation.py — Verifies Row-Level Security (RLS) under the bmp_app role.
Loops over every table with a company_id column to assert strict company isolation.
"""

import pytest


def test_client_user_sees_only_assigned_company(app_cur):
    """A client user assigned only to Company 1 cannot see Company 2 in any company-scoped table."""
    # Look up client user (app_user is not RLS-scoped by company, so this works)
    app_cur.execute("SELECT id FROM core.app_user WHERE email = 'client@nexatech.co.in';")
    client_id = app_cur.fetchone()["id"]

    # Set context to admin first so we can look up company IDs through RLS
    app_cur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    app_cur.execute("SELECT id FROM core.company WHERE cin = 'U72200DL2015PTC112001';")
    c1_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT id FROM core.company WHERE cin = 'L24100MH2010PLC178002';")
    c2_id = app_cur.fetchone()["id"]

    # Now switch to client user context
    app_cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(client_id),))

    # 1. Check core.company table
    app_cur.execute("SELECT id, name FROM core.company;")
    visible_companies = app_cur.fetchall()
    visible_company_ids = [c["id"] for c in visible_companies]

    assert c1_id in visible_company_ids, "Client must see their own company (Nexatech)"
    assert c2_id not in visible_company_ids, "Client must NOT see other companies (BrightMed)"
    assert len(visible_companies) == 1, "Client must see exactly 1 company"

    # 2. Dynamically test ALL tables in core and ops that have a company_id column
    app_cur.execute("""
        SELECT c.table_schema, c.table_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE c.column_name = 'company_id'
          AND c.table_schema IN ('core', 'ops')
          AND c.table_name NOT IN ('user_company_access')
          AND t.table_type = 'BASE TABLE'
        ORDER BY c.table_schema, c.table_name;
    """)
    scoped_tables = app_cur.fetchall()
    assert len(scoped_tables) > 10, "Expected multiple company-scoped tables"

    for row in scoped_tables:
        schema = row["table_schema"]
        table = row["table_name"]
        
        # Query table as client
        app_cur.execute(f"SELECT DISTINCT company_id FROM {schema}.{table};")
        rows = app_cur.fetchall()
        for r in rows:
            cid = r["company_id"]
            assert cid == c1_id, f"RLS violation on {schema}.{table}: client saw company_id={cid}, expected only {c1_id}"


def test_admin_user_sees_all_companies(app_cur):
    """An admin user with access to all companies can view all companies."""
    app_cur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = app_cur.fetchone()["id"]

    # Set context to admin
    app_cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    app_cur.execute("SELECT COUNT(*) AS cnt FROM core.company;")
    total_companies = app_cur.fetchone()["cnt"]
    assert total_companies >= 5, "Admin user must see all seeded companies"
