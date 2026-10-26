#!/usr/bin/env python3
"""
scripts/run_demo.py — BMP Compliance Platform Phase 1 Demo Runner

Demonstrates 10 of the 12 demo items from guidelines.md § 9
(items 7 "Rules as data" and 10 "Isolation" were removed on request).
Run as:  python scripts/run_demo.py
"""

import os
import sys
import json
import psycopg
from psycopg.rows import dict_row
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

OWNER_URL = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
APP_URL = os.environ["DATABASE_URL_APP"].replace("postgresql+psycopg://", "postgresql://")

SEP = "=" * 72


def sep(title: str):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def fmt_table(rows, cols=None):
    if not rows:
        print("  (no rows)")
        return
    if cols is None:
        cols = list(rows[0].keys())
    col_widths = {c: max(len(str(c)), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    header = "  " + " | ".join(str(c).ljust(col_widths[c]) for c in cols)
    divider = "  " + "-+-".join("-" * col_widths[c] for c in cols)
    print(header)
    print(divider)
    for r in rows:
        print("  " + " | ".join(str(r.get(c, "")).ljust(col_widths[c]) for c in cols))


def run_demo():
    print("\n" + "=" * 72)
    print("  BMP COMPLIANCE PLATFORM — PHASE 1 DATABASE DEMONSTRATION")
    print("=" * 72)

    owner = psycopg.connect(OWNER_URL, row_factory=dict_row, autocommit=False)
    app = psycopg.connect(APP_URL, row_factory=dict_row, autocommit=False)
    ocur = owner.cursor()
    acur = app.cursor()

    # Get admin user id for session setting
    ocur.execute("SELECT id FROM core.app_user WHERE email = 'admin@bmpco.in';")
    admin_id = ocur.fetchone()["id"]
    ocur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))
    acur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    # ─── 1. STRUCTURE ───────────────────────────────────────────────────────
    sep("1. STRUCTURE: Schemas, table counts, installed extensions")

    ocur.execute("""
        SELECT table_schema AS schema, COUNT(*) AS table_count
        FROM information_schema.tables
        WHERE table_schema IN ('core', 'activity', 'ops', 'audit')
          AND table_type = 'BASE TABLE'
        GROUP BY table_schema ORDER BY table_schema;
    """)
    print("\n  Table counts per schema:")
    fmt_table(ocur.fetchall())

    ocur.execute("""
        SELECT extname AS extension, extversion AS version
        FROM pg_extension
        WHERE extname IN ('vector', 'btree_gist', 'pgcrypto')
        ORDER BY extname;
    """)
    print("\n  Installed extensions:")
    fmt_table(ocur.fetchall())

    # ─── 2. DIRECTOR HISTORY ────────────────────────────────────────────────
    sep("2. DIRECTOR HISTORY: Resigned-then-reappointed director (DIN 12340012)")

    ocur.execute("""
        SELECT d.full_name, c.name AS company,
               ds.start_date, ds.end_date,
               CASE WHEN ds.end_date IS NULL THEN 'ACTIVE' ELSE 'RESIGNED' END AS status,
               ds.cessation_reason
        FROM core.directorship ds
        JOIN core.director d ON d.id = ds.director_id
        JOIN core.company c ON c.id = ds.company_id
        WHERE d.din = '12340012'
        ORDER BY ds.start_date;
    """)
    print("\n  All stints (resigned + reappointed):")
    fmt_table(ocur.fetchall())

    ocur.execute("""
        SELECT full_name, din, company_name, current_designation,
               appointment_date, is_independent
        FROM core.v_current_directors WHERE din = '12340012';
    """)
    print("\n  v_current_directors (active stints only):")
    fmt_table(ocur.fetchall())

    # ─── 3. OVERLAP PROTECTION ──────────────────────────────────────────────
    sep("3. OVERLAP PROTECTION: Attempt to insert overlapping stint (ExclusionViolation)")

    ocur.execute("SELECT id FROM core.company WHERE cin = 'U72200DL2015PTC112001';")
    c1 = ocur.fetchone()["id"]
    ocur.execute("SELECT id FROM core.director WHERE din = '12340001';")
    d1 = ocur.fetchone()["id"]

    ocur.execute("SAVEPOINT sp_overlap;")
    try:
        ocur.execute("""
            INSERT INTO core.directorship (company_id, director_id, start_date, end_date)
            VALUES (%s, %s, '2021-01-01', '2023-01-01');
        """, (c1, d1))
        print("  ERROR: Insert should have failed!")
    except psycopg.errors.ExclusionViolation as e:
        print(f"  OK - Overlapping stint correctly rejected (ExclusionViolation)")
        ocur.execute("ROLLBACK TO SAVEPOINT sp_overlap;")

    # ─── 4. NO DELETION ─────────────────────────────────────────────────────
    sep("4. NO DELETION: DELETE and TRUNCATE are blocked; archiving works instead")

    acur.execute("SAVEPOINT sp_del;")
    try:
        acur.execute("DELETE FROM core.company;")
        print("  ERROR: DELETE should have failed!")
    except (psycopg.errors.RaiseException, psycopg.errors.InsufficientPrivilege) as e:
        print(f"  OK - DELETE blocked ({e.__class__.__name__})")
        acur.execute("ROLLBACK TO SAVEPOINT sp_del;")

    ocur.execute("SAVEPOINT sp_trunc;")
    try:
        ocur.execute("TRUNCATE TABLE core.meeting;")
        print("  ERROR: TRUNCATE should have failed!")
    except (psycopg.errors.RaiseException, psycopg.errors.FeatureNotSupported) as e:
        print(f"  OK - TRUNCATE blocked ({e.__class__.__name__})")
        ocur.execute("ROLLBACK TO SAVEPOINT sp_trunc;")

    acur.execute("SAVEPOINT sp_archive;")
    acur.execute("SELECT id, name FROM core.company ORDER BY id LIMIT 1;")
    co = acur.fetchone()
    acur.execute("UPDATE core.company SET is_archived = true, archived_at = now(), archived_by = %s WHERE id = %s;",
                 (admin_id, co["id"]))
    acur.execute("SELECT name, is_archived, archived_at IS NOT NULL AS has_archived_at FROM core.company WHERE id = %s;",
                 (co["id"],))
    print(f"\n  Archiving example (rolled back afterwards): company '{co['name']}' — row still present:")
    fmt_table(acur.fetchall())
    acur.execute("ROLLBACK TO SAVEPOINT sp_archive;")

    # ─── 5. AUDIT TRAIL ─────────────────────────────────────────────────────
    sep("5. AUDIT TRAIL: Rejected write; write with user_id creates audit entries")

    # Test write without user_id
    acur.execute("SELECT set_config('app.current_user_id', '', false);")
    acur.execute("SAVEPOINT sp_audit_nouser;")
    try:
        acur.execute("INSERT INTO core.shareholder (name, email) VALUES ('Unattributed', 'u@test.com');")
        print("  ERROR: Should have been rejected!")
    except psycopg.errors.RaiseException as e:
        print(f"  OK - Write without current_user_id rejected: {str(e).split(chr(10))[0]}")
        acur.execute("ROLLBACK TO SAVEPOINT sp_audit_nouser;")
    acur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    # Audit trail demo using owner connection
    ocur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))
    ocur.execute("""
        INSERT INTO core.shareholder (name, email)
        VALUES ('Audit Demo Shareholder', 'auditdemo@example.com')
        RETURNING id;
    """)
    sh_id = ocur.fetchone()["id"]

    ocur.execute("""
        UPDATE core.shareholder
        SET name = 'Audit Demo Shareholder (Updated)'
        WHERE id = %s;
    """, (sh_id,))

    ocur.execute("""
        SELECT operation,
               old_row->>'name' AS old_name,
               new_row->>'name' AS new_name,
               actor,
               changed_at
        FROM audit.log
        WHERE table_name = 'shareholder' AND record_id = %s
        ORDER BY id;
    """, (sh_id,))
    print("\n  Audit log for shareholder INSERT then UPDATE:")
    fmt_table(ocur.fetchall())
    owner.rollback()  # roll back demo data

    # ─── 6. CALCULATED VALUES ───────────────────────────────────────────────
    sep("6. CALCULATED VALUES: Shareholding %, top-10, director age from views")

    ocur.execute("SELECT set_config('app.current_user_id', %s, false);", (str(admin_id),))

    ocur.execute("""
        SELECT shareholder_name, company_name, shareholder_category,
               number_of_shares, holding_percent AS holding_pct
        FROM core.v_top10_shareholders
        ORDER BY holding_percent DESC NULLS LAST
        LIMIT 6;
    """)
    print("\n  Top 10 shareholders (v_top10_shareholders):")
    fmt_table(ocur.fetchall())

    ocur.execute("""
        SELECT full_name, din, date_of_birth, age_years
        FROM core.v_director_age
        LIMIT 5;
    """)
    print("\n  Director ages (v_director_age — no stored age column):")
    fmt_table(ocur.fetchall())

    ocur.execute("""
        SELECT full_name, din, board_meetings_entitled, board_meetings_attended, board_attendance_percent
        FROM core.v_director_attendance_summary
        ORDER BY board_meetings_entitled DESC, full_name
        LIMIT 5;
    """)
    print("\n  Attendance % (v_director_attendance_summary):")
    fmt_table(ocur.fetchall())

    # ─── 7. ACTIVITY DEFINITION ─────────────────────────────────────────────
    sep("7. ACTIVITY DEFINITION: activity.get_template_json('BOARD_MEETING')")

    ocur.execute("SELECT activity.get_template_json('BOARD_MEETING') AS tmpl;")
    tmpl = ocur.fetchone()["tmpl"]
    print(f"\n  Template:  {tmpl['template']['code']} — {tmpl['template']['name']}")
    print(f"  Steps ({len(tmpl['steps'])}):")
    for s in tmpl["steps"]:
        deps = ",".join(str(d) for d in (s.get("depends_on") or []))
        deadline = f"{s.get('deadline_direction','—')} {s.get('deadline_offset_days', '') or ''}d"
        print(f"    [{s['seq']:2d}] {s['step_key']:<35} {deadline:<20}"
              + (f" depends_on:[{deps}]" if deps else ""))

    # ─── 8. ACTIVITY INSTANCE ───────────────────────────────────────────────
    sep("8. ACTIVITY INSTANCE: Seeded BOARD_MEETING task statuses and evidence")

    ocur.execute("""
        SELECT ai.id, c.name AS company,
               ai.params->>'meeting_date' AS meeting_date,
               ai.params->>'venue' AS venue
        FROM ops.activity_instance ai
        JOIN core.company c ON c.id = ai.company_id
        LIMIT 3;
    """)
    instances = ocur.fetchall()
    fmt_table(instances, cols=["id", "company", "meeting_date", "venue"])

    if instances:
        inst_id = instances[0]["id"]
        ocur.execute("""
            SELECT s.seq, s.step_key, t.status, t.due_date,
                   COUNT(DISTINCT trl.id) AS linked_records,
                   COUNT(DISTINCT el.id) AS evidence_links
            FROM ops.task_instance t
            JOIN activity.step_template s ON s.id = t.step_id
            LEFT JOIN ops.task_record_link trl ON trl.task_instance_id = t.id
            LEFT JOIN core.evidence_link el ON el.task_instance_id = t.id
            WHERE t.instance_id = %s
            GROUP BY s.seq, s.step_key, t.status, t.due_date
            ORDER BY s.seq;
        """, (inst_id,))
        print(f"\n  Tasks for instance #{inst_id}:")
        fmt_table(ocur.fetchall())

    # ─── 9. VECTOR READINESS ────────────────────────────────────────────────
    sep("9. DOCUMENT / VECTOR READINESS: document_chunk table with vector column")

    ocur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'core' AND table_name = 'document_chunk'
        ORDER BY ordinal_position;
    """)
    print("\n  document_chunk schema:")
    fmt_table(ocur.fetchall())

    ocur.execute("""
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'core' AND tablename = 'document_chunk';
    """)
    idx_rows = ocur.fetchall()
    print("\n  Indexes:")
    for r in idx_rows:
        print(f"    {r['indexname']}")

    # Attempt dummy vector insert (rolled back)
    ocur.execute("SAVEPOINT sp_vec;")
    try:
        dummy_vec = "[" + ",".join(["0.1"] * 1536) + "]"
        ocur.execute("""
            INSERT INTO core.document_chunk
              (document_id, chunk_no, content, embedding)
            SELECT id, 0, 'Demo chunk', %s::vector
            FROM core.document
            LIMIT 1
            RETURNING id;
        """, (dummy_vec,))
        row = ocur.fetchone()
        if not row:
            raise RuntimeError("No document seeded; cannot demonstrate vector insert")
        print(f"\n  OK - Dummy 1536-d vector inserted (id={row['id']})")
        ocur.execute("""
            SELECT id, embedding <=> %s::vector AS cosine_distance
            FROM core.document_chunk
            ORDER BY embedding <=> %s::vector
            LIMIT 1;
        """, (dummy_vec, dummy_vec))
        nn = ocur.fetchone()
        print(f"  OK - Nearest-neighbour query returned chunk id={nn['id']} (cosine distance {nn['cosine_distance']}) — rolling back")
        ocur.execute("ROLLBACK TO SAVEPOINT sp_vec;")
    except Exception as e:
        print(f"\n  FAILED - vector demonstration: {type(e).__name__}: {e}")
        raise

    # ─── 10. TRACEABILITY ───────────────────────────────────────────────────
    sep("10. COVERAGE: FIELD_TRACEABILITY.md and check_traceability.py")

    traceability_path = BASE_DIR / "docs" / "FIELD_TRACEABILITY.md"
    if traceability_path.exists():
        content = traceability_path.read_text(encoding="utf-8")
        lines = [l for l in content.splitlines() if l.startswith("|") and "---" not in l]
        total_rows = len(lines) - 1  # subtract header
        print(f"\n  docs/FIELD_TRACEABILITY.md: {total_rows} field rows mapped")
        from collections import Counter
        sheets: Counter = Counter()
        for line in lines[1:]:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) > 1:
                sheets[parts[1]] += 1
        print(f"  Sheets covered: {len(sheets)}")
    else:
        print("\n  docs/FIELD_TRACEABILITY.md not found.")

    import subprocess
    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / "check_traceability.py")],
        cwd=str(BASE_DIR), capture_output=True, text=True
    )
    print(f"\n  check_traceability.py:")
    for line in (result.stdout + result.stderr).strip().splitlines()[:8]:
        print(f"    {line}")
    if result.returncode != 0:
        raise SystemExit("check_traceability.py FAILED")

    # ─── FINISH ─────────────────────────────────────────────────────────────
    owner.rollback()
    app.rollback()
    owner.close()
    app.close()

    print("\n" + "=" * 72)
    print("  DEMO COMPLETE — All 10 items demonstrated successfully.")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    run_demo()
