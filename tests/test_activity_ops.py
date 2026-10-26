"""
test_activity_ops.py — Tests workflow templates, step dependencies, data bindings,
and deterministic activity instantiation.
"""

import json
import pytest
import psycopg


def test_instantiate_activity_generates_tasks_with_correct_due_dates(app_cur):
    """ops.instantiate_activity creates 9 tasks for BOARD_MEETING with calculated statutory due dates."""
    # Must set current_user_id first — bmp_app role is subject to RLS
    app_cur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = app_cur.fetchone()["id"]
    app_cur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    app_cur.execute("SELECT id FROM core.company WHERE cin = 'L24100MH2010PLC178002';")
    c2_id = app_cur.fetchone()["id"]

    meeting_date_str = "2025-06-20"
    params = json.dumps({
        "meeting_date": meeting_date_str,
        "start_time": "10:00",
        "venue": "Nariman Point",
        "venue_mode": "PHYSICAL",
        "agenda_items": ["Adoption of accounts"]
    })

    # Call ops.instantiate_activity
    app_cur.execute("""
        SELECT ops.instantiate_activity('BOARD_MEETING', %s, %s::jsonb, %s) AS inst_id;
    """, (c2_id, params, admin_id))
    inst_id = app_cur.fetchone()["inst_id"]
    assert inst_id is not None

    # Fetch created tasks
    app_cur.execute("""
        SELECT s.seq, s.step_key, s.deadline_direction, s.deadline_offset_days, t.due_date, t.status
        FROM ops.task_instance t
        JOIN activity.step_template s ON s.id = t.step_id
        WHERE t.instance_id = %s
        ORDER BY s.seq;
    """, (inst_id,))
    tasks = app_cur.fetchall()
    assert len(tasks) == 9, "Expected exactly 9 tasks for BOARD_MEETING"

    task_map = {t["step_key"]: t for t in tasks}

    # Step 1: no deadline
    assert task_map["CONFIRM_DATE_VENUE"]["due_date"] is None

    # Step 3: 7 days before meeting_date (2025-06-20 - 7 days = 2025-06-13)
    assert str(task_map["DRAFT_NOTICE"]["due_date"]) == "2025-06-13"

    # Step 4: 7 days before meeting_date
    assert str(task_map["SEND_NOTICE"]["due_date"]) == "2025-06-13"

    # Step 5: at meeting_date (0 days offset)
    assert str(task_map["CONDUCT_MEETING"]["due_date"]) == "2025-06-20"

    # Step 7: 15 days after meeting_date (2025-06-20 + 15 days = 2025-07-05)
    assert str(task_map["DRAFT_MINUTES"]["due_date"]) == "2025-07-05"

    # Step 8: 30 days after meeting_date (2025-06-20 + 30 days = 2025-07-20)
    assert str(task_map["SIGN_MINUTES"]["due_date"]) == "2025-07-20"


def test_step_data_binding_rejects_writing_calculated_field(owner_cur):
    """step_data_binding must reject mode='write' on a field where is_calculated=true."""
    # Find or insert a calculated field in registry
    owner_cur.execute("""
        SELECT id FROM activity.entity_field_registry
        WHERE is_calculated = true
        LIMIT 1;
    """)
    calc_row = owner_cur.fetchone()
    if not calc_row:
        # Insert a calculated field for test
        owner_cur.execute("""
            INSERT INTO activity.entity_field_registry (table_name, column_name, is_calculated)
            VALUES ('core.test_table', 'calculated_col', true)
            RETURNING id;
        """)
        calc_id = owner_cur.fetchone()["id"]
    else:
        calc_id = calc_row["id"]

    owner_cur.execute("SELECT id FROM activity.step_template LIMIT 1;")
    step_id = owner_cur.fetchone()["id"]

    with pytest.raises(psycopg.errors.RaiseException) as exc_info:
        owner_cur.execute("""
            INSERT INTO activity.step_data_binding (step_id, field_id, mode)
            VALUES (%s, %s, 'write');
        """, (step_id, calc_id))
    # Match actual trigger error message from activity.check_write_on_calculated()
    assert "cannot write to a calculated field" in str(exc_info.value).lower()


def test_step_dependency_rejects_cycle(owner_cur):
    """step_dependency trigger must reject circular dependencies."""
    owner_cur.execute("""
        SELECT id, template_id FROM activity.step_template
        WHERE template_id = (SELECT id FROM activity.activity_template WHERE code='BOARD_MEETING')
        ORDER BY seq;
    """)
    steps = owner_cur.fetchall()
    s1_id = steps[0]["id"]
    s2_id = steps[1]["id"]
    # Chain has s2 depending on s1. Making s1 depend on s2 would create a cycle!
    with pytest.raises(psycopg.errors.RaiseException) as exc_info:
        owner_cur.execute("""
            INSERT INTO activity.step_dependency (step_id, depends_on_step_id)
            VALUES (%s, %s);
        """, (s1_id, s2_id))
    assert "circular dependency" in str(exc_info.value).lower() or "cycle" in str(exc_info.value).lower()


def test_get_template_json_shape(owner_cur):
    """activity.get_template_json returns complete JSON with template, steps, dependencies, bindings."""
    owner_cur.execute("SELECT activity.get_template_json('BOARD_MEETING') AS tmpl_json;")
    res = owner_cur.fetchone()["tmpl_json"]
    assert "template" in res
    assert "steps" in res
    assert res["template"]["code"] == "BOARD_MEETING"
    assert len(res["steps"]) == 9
    first_step = res["steps"][0]
    assert "bindings" in first_step
    assert "evidence_requirements" in first_step
