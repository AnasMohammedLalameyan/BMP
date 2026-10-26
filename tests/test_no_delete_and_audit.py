"""
test_no_delete_and_audit.py — Verifies immutability, delete blocks, truncate blocks,
and the audit trail mechanism.
"""

import pytest
import psycopg


def test_delete_is_blocked_on_business_tables(app_cur):
    """Deleting from any business table must be rejected by block_delete_trg."""
    app_cur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    # Test sample of business tables
    tables = [
        ("core", "company"),
        ("core", "director"),
        ("core", "shareholder"),
        ("core", "meeting"),
        ("ops", "activity_instance"),
        ("ops", "task_instance"),
    ]

    for schema, table in tables:
        app_cur.execute(f"SAVEPOINT sp_{table};")
        try:
            app_cur.execute(f"DELETE FROM {schema}.{table};")
            pytest.fail(f"DELETE on {schema}.{table} should have failed!")
        except (psycopg.errors.RaiseException, psycopg.errors.InsufficientPrivilege) as exc:
            # Either the block_delete trigger fires (RaiseException) or bmp_app has no DELETE
            # privilege at all (InsufficientPrivilege) — both are acceptable protections.
            app_cur.execute(f"ROLLBACK TO SAVEPOINT sp_{table};")


def test_truncate_is_blocked_on_business_tables(owner_cur):
    """Truncating any business table must fail even for owner role."""
    tables = [
        ("core", "company"),
        ("core", "meeting"),
        ("core", "shareholder"),
    ]
    for schema, table in tables:
        owner_cur.execute(f"SAVEPOINT sp_trunc_{table};")
        try:
            owner_cur.execute(f"TRUNCATE TABLE {schema}.{table};")
            pytest.fail(f"TRUNCATE on {schema}.{table} should have failed!")
        except (psycopg.errors.RaiseException, psycopg.errors.FeatureNotSupported) as exc:
            # Either the block_truncate trigger fires (RaiseException) or a FK constraint
            # prevents it from reaching the trigger (FeatureNotSupported) — both block TRUNCATE.
            owner_cur.execute(f"ROLLBACK TO SAVEPOINT sp_trunc_{table};")


def test_audit_log_is_append_only(owner_cur):
    """audit.log must reject both UPDATE and DELETE."""
    owner_cur.execute("SAVEPOINT sp_audit_upd;")
    try:
        owner_cur.execute("UPDATE audit.log SET table_name = 'hacked' WHERE id = 1;")
        pytest.fail("UPDATE on audit.log should have failed!")
    except psycopg.errors.RaiseException as exc:
        assert "audit.log is append-only" in str(exc)
        owner_cur.execute("ROLLBACK TO SAVEPOINT sp_audit_upd;")

    owner_cur.execute("SAVEPOINT sp_audit_del;")
    try:
        owner_cur.execute("DELETE FROM audit.log WHERE id = 1;")
        pytest.fail("DELETE on audit.log should have failed!")
    except psycopg.errors.RaiseException as exc:
        assert "audit.log is append-only" in str(exc)
        owner_cur.execute("ROLLBACK TO SAVEPOINT sp_audit_del;")


def test_write_without_current_user_id_rejected(app_cur):
    """Writes to business tables without app.current_user_id must be rejected."""
    app_cur.execute("SELECT set_config('app.current_user_id', '', false);")

    with pytest.raises(psycopg.errors.RaiseException) as exc_info:
        app_cur.execute("""
            INSERT INTO core.shareholder (name, email)
            VALUES ('Unattributed Shareholder', 'unattributed@test.com');
        """)
    assert "app.current_user_id must be set" in str(exc_info.value)


def test_audit_trail_captures_old_and_new_values(owner_cur):
    """Updates must produce an audit.log entry with old_row, new_row and actor."""
    # Use owner_cur for all operations since owner bypasses RLS and can directly
    # verify audit.log in the same transaction.
    owner_cur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = owner_cur.fetchone()["id"]
    owner_cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    # Insert a new record as owner with user_id set
    owner_cur.execute("""
        INSERT INTO core.shareholder (name, email)
        VALUES ('Audit Test Shareholder', 'audit_test@example.com')
        RETURNING id;
    """)
    sh_id = owner_cur.fetchone()["id"]

    # Verify INSERT was captured in audit.log (same connection, so same transaction)
    owner_cur.execute("""
        SELECT * FROM audit.log
        WHERE table_schema = 'core' AND table_name = 'shareholder' AND record_id = %s AND operation = 'INSERT';
    """, (sh_id,))
    ins_log = owner_cur.fetchone()
    assert ins_log is not None
    assert ins_log["actor"] == admin_id
    assert ins_log["new_row"]["name"] == "Audit Test Shareholder"
    assert ins_log["old_row"] is None

    # Now UPDATE the record
    owner_cur.execute("""
        UPDATE core.shareholder
        SET name = 'Audit Test Shareholder Updated'
        WHERE id = %s;
    """, (sh_id,))

    # Verify UPDATE was captured in audit.log
    owner_cur.execute("""
        SELECT * FROM audit.log
        WHERE table_schema = 'core' AND table_name = 'shareholder' AND record_id = %s AND operation = 'UPDATE';
    """, (sh_id,))
    upd_log = owner_cur.fetchone()
    assert upd_log is not None
    assert upd_log["actor"] == admin_id
    assert upd_log["old_row"]["name"] == "Audit Test Shareholder"
    assert upd_log["new_row"]["name"] == "Audit Test Shareholder Updated"
