"""
test_overlap_constraints.py — Tests exclusion constraints:
1. directorship stints cannot overlap for same (company, director)
2. gap re-appointment succeeds
3. directorship_role cannot overlap
4. shareholding periods cannot overlap
"""

import pytest
import psycopg


def test_overlapping_directorship_stint_is_rejected(app_cur):
    """An attempt to insert a directorship stint overlapping an existing stint must fail."""
    app_cur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    # Company 1 and Director 1
    app_cur.execute("SELECT id FROM core.company WHERE cin = 'U72200DL2015PTC112001';")
    c1_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT id FROM core.director WHERE din = '12340001';")
    d1_id = app_cur.fetchone()["id"]

    # Arjun currently has an active stint starting 2015-03-12 (end_date NULL)
    # Attempting to insert an overlapping stint must trigger exclusion constraint
    with pytest.raises(psycopg.errors.ExclusionViolation):
        app_cur.execute("""
            INSERT INTO core.directorship (company_id, director_id, start_date, end_date)
            VALUES (%s, %s, '2020-01-01', '2022-01-01');
        """, (c1_id, d1_id))


def test_gap_reappointment_succeeds(app_cur):
    """A director who resigned can be reappointed after a gap without error."""
    app_cur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    # Create fresh director and company
    app_cur.execute("""
        INSERT INTO core.director (din, full_name, pan)
        VALUES ('99990001', 'Reappointment Test Director', 'AAPPT9991P')
        RETURNING id;
    """)
    dir_id = app_cur.fetchone()["id"]

    app_cur.execute("SELECT id FROM core.company WHERE cin = 'U72200DL2015PTC112001';")
    comp_id = app_cur.fetchone()["id"]

    # Stint 1: 2018-01-01 to 2020-12-31
    app_cur.execute("""
        INSERT INTO core.directorship (company_id, director_id, start_date, end_date, cessation_reason)
        VALUES (%s, %s, '2018-01-01', '2020-12-31', 'Resigned to pursue other interests');
    """, (comp_id, dir_id))

    # Stint 2 (reappointed after a gap): 2022-01-01 to NULL (current)
    app_cur.execute("""
        INSERT INTO core.directorship (company_id, director_id, start_date, end_date)
        VALUES (%s, %s, '2022-01-01', NULL);
    """, (comp_id, dir_id))

    # Verify both stints exist
    app_cur.execute("""
        SELECT COUNT(*) AS cnt FROM core.directorship
        WHERE company_id = %s AND director_id = %s;
    """, (comp_id, dir_id))
    assert app_cur.fetchone()["cnt"] == 2


def test_overlapping_designation_roles_rejected(app_cur):
    """Directorship role designations cannot overlap for the same directorship."""
    app_cur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    app_cur.execute("SELECT id FROM core.directorship LIMIT 1;")
    dst_id = app_cur.fetchone()["id"]

    app_cur.execute("SELECT id FROM core.lookup_value WHERE code = 'DIRECTOR' LIMIT 1;")
    desig_id = app_cur.fetchone()["id"]

    # Insert role stint 1
    app_cur.execute("""
        INSERT INTO core.directorship_role (directorship_id, designation_id, start_date, end_date)
        VALUES (%s, %s, '2020-01-01', '2022-12-31');
    """, (dst_id, desig_id))

    # Attempt to insert overlapping role stint
    with pytest.raises(psycopg.errors.ExclusionViolation):
        app_cur.execute("""
            INSERT INTO core.directorship_role (directorship_id, designation_id, start_date, end_date)
            VALUES (%s, %s, '2021-06-01', '2023-12-31');
        """, (dst_id, desig_id))


def test_overlapping_shareholding_periods_rejected(app_cur):
    """Shareholding history cannot have overlapping valid periods for same folio."""
    app_cur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    app_cur.execute("SELECT id FROM core.company LIMIT 1;")
    comp_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT id FROM core.shareholder LIMIT 1;")
    sh_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT id FROM core.share_class WHERE company_id = %s LIMIT 1;", (comp_id,))
    class_id = app_cur.fetchone()["id"]

    # Holding 1
    app_cur.execute("""
        INSERT INTO core.shareholding (company_id, shareholder_id, share_class_id, folio_number, number_of_shares, face_value, valid_from, valid_to)
        VALUES (%s, %s, %s, 'FOLIO-TEST-1', 1000, 10, '2020-01-01', '2022-12-31');
    """, (comp_id, sh_id, class_id))

    # Overlapping holding for same folio
    with pytest.raises(psycopg.errors.ExclusionViolation):
        app_cur.execute("""
            INSERT INTO core.shareholding (company_id, shareholder_id, share_class_id, folio_number, number_of_shares, face_value, valid_from, valid_to)
            VALUES (%s, %s, %s, 'FOLIO-TEST-1', 2000, 10, '2021-01-01', '2023-12-31');
        """, (comp_id, sh_id, class_id))
