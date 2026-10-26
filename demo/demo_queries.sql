-- =============================================================================
-- demo/demo_queries.sql — BMP Compliance Platform Phase 1 Demo Queries
--
-- These queries correspond to the 12 demo items in guidelines.md § 9.
-- Run via: python scripts/run_demo.py
--          or execute manually in psql connected as bmp_owner on the bmp database.
--
-- Note: Queries that require app.current_user_id must set it first (see below).
-- =============================================================================

-- Set a known actor before any write or RLS-scoped read
-- SELECT set_config('app.current_user_id', '<id>', false);

-- =============================================================================
-- 1. STRUCTURE
-- =============================================================================

-- Schema overview
SELECT table_schema AS schema,
       COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema IN ('core', 'activity', 'ops', 'audit')
  AND table_type = 'BASE TABLE'
GROUP BY table_schema
ORDER BY table_schema;

-- Installed extensions
SELECT extname AS extension, extversion AS version
FROM pg_extension
WHERE extname IN ('vector', 'btree_gist', 'pgcrypto')
ORDER BY extname;

-- =============================================================================
-- 2. DIRECTOR HISTORY
-- =============================================================================

-- All stints for resigned-then-reappointed director (DIN 12340012, Prashant Joshi)
SELECT d.full_name, c.name AS company,
       ds.start_date, ds.end_date,
       CASE WHEN ds.end_date IS NULL THEN 'ACTIVE' ELSE 'RESIGNED' END AS status,
       ds.cessation_reason
FROM core.directorship ds
JOIN core.director d ON d.id = ds.director_id
JOIN core.company c ON c.id = ds.company_id
WHERE d.din = '12340012'
ORDER BY ds.start_date;

-- Current active directors
SELECT full_name, din, company_name, current_designation,
       appointment_date, is_independent
FROM core.v_current_directors
ORDER BY company_name, full_name;

-- Full history (all stints, including ended ones, with duration)
SELECT full_name, din, company_name,
       start_date, end_date, cessation_reason, duration_months, is_current
FROM core.v_director_history
ORDER BY full_name, start_date;

-- =============================================================================
-- 3. OVERLAP PROTECTION (expect ExclusionViolation — run in a transaction + rollback)
-- =============================================================================

BEGIN;
INSERT INTO core.directorship (company_id, director_id, start_date, end_date)
SELECT c.id, d.id, '2021-01-01', '2023-01-01'
FROM core.company c, core.director d
WHERE c.cin = 'U72200DL2015PTC112001' AND d.din = '12340001';
-- Should raise: ERROR: conflicting key value violates exclusion constraint
ROLLBACK;

-- =============================================================================
-- 4. NO DELETION (run each in its own block to observe the error)
-- =============================================================================

-- Attempt DELETE (will fail with RaiseException or InsufficientPrivilege)
BEGIN;
DELETE FROM core.company WHERE id = 1;
ROLLBACK;

-- Attempt TRUNCATE (will fail with RaiseException or FeatureNotSupported)
BEGIN;
TRUNCATE TABLE core.meeting;
ROLLBACK;

-- Correct approach: soft-archive
-- UPDATE core.company
--   SET is_archived = true, archived_at = now(), archived_by = <user_id>
--   WHERE id = <target>;

-- =============================================================================
-- 5. AUDIT TRAIL
-- =============================================================================

-- (a) Attempt a write without an actor (expect: app.current_user_id must be set ...)
BEGIN;
SELECT set_config('app.current_user_id', '', false);
INSERT INTO core.shareholder (name, email) VALUES ('Ghost', 'ghost@test.com');
ROLLBACK;

-- (b) Write with an actor, then show the audit log with old and new values
BEGIN;
SELECT set_config('app.current_user_id',
                  (SELECT id::text FROM core.app_user WHERE email = 'admin@bmpco.in'), false);
INSERT INTO core.shareholder (name, email) VALUES ('Audit Demo', 'auditdemo@example.com');
UPDATE core.shareholder SET name = 'Audit Demo (Updated)' WHERE email = 'auditdemo@example.com';
SELECT operation, old_row->>'name' AS old_name, new_row->>'name' AS new_name, actor, changed_at
FROM audit.log
WHERE table_name = 'shareholder' AND new_row->>'email' = 'auditdemo@example.com'
ORDER BY id;
ROLLBACK;   -- demo data is discarded (the audit rows roll back with it)

-- =============================================================================
-- 6. CALCULATED VALUES
-- =============================================================================

-- Shareholding percentage per holder (calculated in view, never stored)
SELECT shareholder_name, company_name, shareholder_category,
       number_of_shares, holding_percent
FROM core.v_shareholding_percent
ORDER BY company_name, holding_percent DESC;

-- Top shareholders (view ranks holders inside each company and share class)
SELECT company_name, shareholder_name, holding_percent, rank_in_class
FROM core.v_top10_shareholders
ORDER BY company_name, rank_in_class;

-- Director age (no age column stored in core.director)
SELECT full_name, din, date_of_birth, age_years
FROM core.v_director_age
ORDER BY full_name;

-- Board attendance percentage per director (and whether they attended the last AGM)
SELECT company_id, full_name, board_meetings_entitled, board_meetings_attended,
       board_attendance_percent, attended_last_agm
FROM core.v_director_attendance_summary
WHERE board_meetings_entitled > 0
ORDER BY company_id, full_name;

-- Committee attendance percentage
SELECT committee_name, full_name, meetings_attended, meetings_held, attendance_percent
FROM core.v_committee_attendance_percent
ORDER BY committee_name, full_name;

-- =============================================================================
-- 7. RULES AS DATA
-- =============================================================================

-- List all rule definitions
SELECT code, name, law_reference, frequency,
       applies_to_description, responsible_party
FROM core.rule_definition
ORDER BY code;

-- Sample rule evaluations
SELECT c.name AS company, rd.code AS rule,
       re.financial_year, re.applies, re.status, re.notes
FROM core.rule_evaluation re
JOIN core.rule_definition rd ON rd.id = re.rule_id
JOIN core.company c ON c.id = re.company_id
ORDER BY c.name, rd.code;

-- =============================================================================
-- 8. ACTIVITY DEFINITION
-- =============================================================================

SELECT activity.get_template_json('BOARD_MEETING');

-- Individual step details
SELECT s.seq, s.step_key, s.title, s.step_type,
       s.deadline_direction, s.deadline_offset_days,
       s.is_mandatory, s.responsible_role
FROM activity.step_template s
JOIN activity.activity_template t ON t.id = s.template_id
WHERE t.code = 'BOARD_MEETING'
ORDER BY s.seq;

-- =============================================================================
-- 9. ACTIVITY INSTANCE
-- =============================================================================

-- All instances
SELECT ai.id, c.name AS company,
       ai.params->>'meeting_date' AS meeting_date,
       ai.params->>'venue' AS venue,
       ai.created_at
FROM ops.activity_instance ai
JOIN core.company c ON c.id = ai.company_id
ORDER BY ai.id;

-- Tasks per instance with linked records
SELECT s.seq, s.step_key, t.status, t.due_date,
       t.completed_at,
       COUNT(DISTINCT trl.id) AS linked_records,
       COUNT(DISTINCT el.id) AS evidence_links
FROM ops.task_instance t
JOIN activity.step_template s ON s.id = t.step_id
LEFT JOIN ops.task_record_link trl ON trl.task_instance_id = t.id
LEFT JOIN core.evidence_link el ON el.task_instance_id = t.id
WHERE t.instance_id = 1                         -- change to actual id
GROUP BY s.seq, s.step_key, t.status, t.due_date, t.completed_at
ORDER BY s.seq;

-- =============================================================================
-- 10. ISOLATION (RLS)
-- =============================================================================

-- IMPORTANT: run this section connected as bmp_app (psql -U bmp_app -d bmp).
-- The owner role bmp_owner bypasses row-level security and would show all 5 companies.
SELECT set_config('app.current_user_id',
                  (SELECT id::text FROM core.app_user WHERE email = 'client@nexatech.co.in'), false);
SELECT id, name FROM core.company ORDER BY name;      -- expect 1 company

-- Switch to admin and see all:
SELECT set_config('app.current_user_id',
                  (SELECT id::text FROM core.app_user WHERE email = 'admin@bmpco.in'), false);
SELECT id, name FROM core.company ORDER BY name;      -- expect 5 companies

-- =============================================================================
-- 11. VECTOR READINESS
-- =============================================================================

-- Show document_chunk schema
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'core' AND table_name = 'document_chunk'
ORDER BY ordinal_position;

-- Show indexes (including the HNSW vector index)
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'core' AND tablename = 'document_chunk';

-- Dummy vector insert (1536-dim) and nearest-neighbour query — rolled back
BEGIN;
SELECT set_config('app.current_user_id',
                  (SELECT id::text FROM core.app_user WHERE email = 'admin@bmpco.in'), false);
INSERT INTO core.document_chunk (document_id, chunk_no, content, embedding)
SELECT id, 0, 'Demo chunk for vector test',
       ('[' || array_to_string(array_fill(0.1::float4, ARRAY[1536]), ',') || ']')::vector
FROM core.document
LIMIT 1
RETURNING id, content;
SELECT id, embedding <=> ('[' || array_to_string(array_fill(0.1::float4, ARRAY[1536]), ',') || ']')::vector
       AS cosine_distance
FROM core.document_chunk ORDER BY 2 LIMIT 1;
ROLLBACK;

-- =============================================================================
-- 12. TRACEABILITY COVERAGE
-- =============================================================================

-- Field-to-column coverage is checked outside SQL. Run: python scripts/check_traceability.py

-- Verify no CASCADE FKs exist
SELECT conname, conrelid::regclass AS table_name, confrelid::regclass AS ref_table,
       confdeltype AS on_delete_action
FROM pg_constraint
WHERE contype = 'f'
  AND confdeltype != 'r'          -- 'r' = RESTRICT (the only permitted action)
ORDER BY table_name;
-- Expect: zero rows
