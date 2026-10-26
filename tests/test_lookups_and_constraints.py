"""
test_lookups_and_constraints.py — Tests lookup validations, foreign key RESTRICT rules,
and technical CHECK constraints.
"""

import pytest
import psycopg


def test_lookup_validation_trigger_rejects_wrong_list(app_cur):
    """An attempt to assign a lookup_value from the wrong list must be rejected by validate_lookup."""
    app_cur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    # Get a lookup_value from a different list (e.g. AUDITOR_TYPE instead of COMPANY_CATEGORY)
    app_cur.execute("""
        SELECT lv.id FROM core.lookup_value lv
        JOIN core.lookup_list ll ON ll.id = lv.list_id
        WHERE ll.code = 'AUDITOR_TYPE'
        LIMIT 1;
    """)
    wrong_lv_id = app_cur.fetchone()["id"]

    # Attempt to use auditor type as company category
    with pytest.raises(psycopg.errors.RaiseException) as exc_info:
        app_cur.execute("""
            INSERT INTO core.company (cin, name, pan, date_of_incorporation, category_id)
            VALUES ('U11111DL2025PTC999999', 'Invalid Lookup Co', 'AAACI1111I', '2025-01-01', %s);
        """, (wrong_lv_id,))
    assert "Invalid lookup_value" in str(exc_info.value) or "does not belong to list" in str(exc_info.value)


def test_all_foreign_keys_have_on_delete_restrict(owner_cur):
    """Assert that NO foreign key in core, activity, or ops uses CASCADE, SET NULL, or SET DEFAULT."""
    owner_cur.execute("""
        SELECT
            conrelid::regclass AS table_name,
            conname AS constraint_name,
            confdeltype AS on_delete_action
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE c.contype = 'f'
          AND n.nspname IN ('core', 'activity', 'ops');
    """)
    fks = owner_cur.fetchall()
    assert len(fks) > 0, "Expected foreign keys in database"

    for fk in fks:
        action = fk["on_delete_action"]
        # 'r' = RESTRICT, 'a' = NO ACTION (which in Postgres is functionally restrict at commit time)
        # 'c' = CASCADE, 'n' = SET NULL, 'd' = SET DEFAULT
        assert action in ('r', 'a'), (
            f"Violation: Constraint {fk['constraint_name']} on {fk['table_name']} "
            f"has delete action '{action}', expected 'r' (RESTRICT) or 'a' (NO ACTION)!"
        )


def test_financial_year_check_constraint(app_cur):
    """Financial year must match regex format ^\\d{4}-\\d{2}$."""
    app_cur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    app_cur.execute("SELECT id FROM core.company LIMIT 1;")
    c_id = app_cur.fetchone()["id"]

    # Invalid financial year format (e.g. '2024-2025' or 'FY24')
    with pytest.raises(psycopg.errors.CheckViolation):
        app_cur.execute("""
            INSERT INTO core.company_financials (company_id, financial_year, turnover)
            VALUES (%s, '2024-2025', 1000000);
        """, (c_id,))
