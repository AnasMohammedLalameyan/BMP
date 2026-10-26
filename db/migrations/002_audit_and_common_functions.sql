-- 002_audit_and_common_functions.sql
-- Creates the audit schema tables and all reusable trigger functions.

-- ============================================================
-- AUDIT LOG TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS audit.log (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_schema text        NOT NULL,
    table_name   text        NOT NULL,
    record_id    bigint,
    operation    text        NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE','TRUNCATE')),
    actor        bigint      NOT NULL,                 -- app_user.id that performed the write
    old_row      jsonb,
    new_row      jsonb,
    changed_at   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE audit.log IS 'Immutable change log. Every INSERT/UPDATE on business tables is recorded here via trigger.';
COMMENT ON COLUMN audit.log.actor IS 'References core.app_user.id — not a FK to allow cross-schema flexibility.';

-- Index for fast lookup by table and record
CREATE INDEX IF NOT EXISTS audit_log_table_record_idx ON audit.log (table_schema, table_name, record_id);
CREATE INDEX IF NOT EXISTS audit_log_actor_idx        ON audit.log (actor);
CREATE INDEX IF NOT EXISTS audit_log_changed_at_idx   ON audit.log (changed_at);

-- Block UPDATE and DELETE on audit.log itself
CREATE OR REPLACE FUNCTION audit.block_audit_log_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit.log is append-only; UPDATE and DELETE are not permitted.';
END;
$$;

DROP TRIGGER IF EXISTS block_update_delete_on_audit_log ON audit.log;
CREATE TRIGGER block_update_delete_on_audit_log
    BEFORE UPDATE OR DELETE ON audit.log
    FOR EACH ROW EXECUTE FUNCTION audit.block_audit_log_mutation();

-- ============================================================
-- FUNCTION: audit.block_delete()
-- Attached as BEFORE DELETE trigger on every business table.
-- ============================================================
CREATE OR REPLACE FUNCTION audit.block_delete()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
        'DELETE is not permitted on table %.%. Use is_archived = true to archive records.',
        TG_TABLE_SCHEMA, TG_TABLE_NAME;
END;
$$;

-- ============================================================
-- FUNCTION: audit.block_truncate()
-- Attached as BEFORE TRUNCATE trigger on every business table.
-- ============================================================
CREATE OR REPLACE FUNCTION audit.block_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
        'TRUNCATE is not permitted on table %.%.',
        TG_TABLE_SCHEMA, TG_TABLE_NAME;
END;
$$;

-- ============================================================
-- FUNCTION: audit.touch_updated_at()
-- BEFORE UPDATE trigger that refreshes the updated_at column.
-- ============================================================
CREATE OR REPLACE FUNCTION audit.touch_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

-- ============================================================
-- FUNCTION: audit.capture()
-- AFTER INSERT/UPDATE trigger.
-- Reads app.current_user_id from session config; rejects the write
-- if it is unset (NULL or empty string).
-- ============================================================
CREATE OR REPLACE FUNCTION audit.capture()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_actor bigint;
    v_record_id bigint;
BEGIN
    -- Resolve actor from session variable (set by the application before every write)
    v_actor := nullif(current_setting('app.current_user_id', true), '')::bigint;
    IF v_actor IS NULL THEN
        RAISE EXCEPTION
            'app.current_user_id must be set before writing to %.%',
            TG_TABLE_SCHEMA, TG_TABLE_NAME;
    END IF;

    -- Resolve record id (best effort — works when there is an "id" column)
    BEGIN
        IF TG_OP = 'INSERT' THEN
            v_record_id := (row_to_json(NEW) ->> 'id')::bigint;
        ELSE
            v_record_id := (row_to_json(OLD) ->> 'id')::bigint;
        END IF;
    EXCEPTION WHEN others THEN
        v_record_id := NULL;
    END;

    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit.log (table_schema, table_name, record_id, operation, actor, old_row, new_row)
        VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, v_record_id, 'INSERT', v_actor, NULL, row_to_json(NEW)::jsonb);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit.log (table_schema, table_name, record_id, operation, actor, old_row, new_row)
        VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, v_record_id, 'UPDATE', v_actor, row_to_json(OLD)::jsonb, row_to_json(NEW)::jsonb);
        RETURN NEW;
    END IF;
    RETURN NEW;
END;
$$;

-- ============================================================
-- FUNCTION: audit.validate_lookup()
-- BEFORE INSERT/UPDATE trigger (generic).
-- TG_ARGV[0] = lookup list code that the column value must belong to.
-- TG_ARGV[1] = column name in the new row that holds the lookup_value.id.
-- ============================================================
CREATE OR REPLACE FUNCTION audit.validate_lookup()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_list_code   text   := TG_ARGV[0];
    v_col_name    text   := TG_ARGV[1];
    v_value_id    bigint;
    v_ok          boolean;
BEGIN
    -- Extract the column value from NEW as JSON
    BEGIN
        v_value_id := (row_to_json(NEW) ->> v_col_name)::bigint;
    EXCEPTION WHEN others THEN
        v_value_id := NULL;
    END;

    -- NULL is acceptable (nullable FK)
    IF v_value_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM core.lookup_value lv
        JOIN core.lookup_list  ll ON ll.id = lv.list_id
        WHERE ll.code = v_list_code
          AND lv.id   = v_value_id
    ) INTO v_ok;

    IF NOT v_ok THEN
        RAISE EXCEPTION
            'lookup_value.id % does not belong to list "%" (column %, table %.%)',
            v_value_id, v_list_code, v_col_name, TG_TABLE_SCHEMA, TG_TABLE_NAME;
    END IF;

    RETURN NEW;
END;
$$;

-- Grant EXECUTE on audit functions to bmp_app (needed because capture() is SECURITY DEFINER)
GRANT EXECUTE ON FUNCTION audit.capture()          TO bmp_app;
GRANT EXECUTE ON FUNCTION audit.block_delete()     TO bmp_app;
GRANT EXECUTE ON FUNCTION audit.block_truncate()   TO bmp_app;
GRANT EXECUTE ON FUNCTION audit.touch_updated_at() TO bmp_app;
GRANT EXECUTE ON FUNCTION audit.validate_lookup()  TO bmp_app;

-- Allow bmp_app to INSERT into audit.log (via SECURITY DEFINER function)
GRANT INSERT ON audit.log TO bmp_app;
