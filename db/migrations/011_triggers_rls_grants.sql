-- 011_triggers_rls_grants.sql
-- Attaches triggers to all business tables, enables RLS, and finalises grants.

-- ============================================================
-- HELPER: attach triggers to all tables in core, activity, ops
-- (excluding audit.log, schema_migrations, lookup_list/value which are managed separately)
-- ============================================================
DO $$
DECLARE
    r record;
    -- Tables to SKIP for the delete-block (audit.log is handled separately,
    -- role_permission has no 'id' column so skip it from audit trigger)
    skip_tables text[] := ARRAY[
        'audit.log',
        'schema_migrations',
        'activity.step_dependency',    -- junction table, no id in trigger context needed
        'core.role_permission'         -- composite PK, no id column
    ];
    tbl text;
    has_updated_at boolean;
BEGIN
    FOR r IN
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('core','activity','ops')
          AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name
    LOOP
        tbl := r.table_schema || '.' || r.table_name;

        -- Skip certain tables
        IF tbl = ANY(skip_tables) THEN
            CONTINUE;
        END IF;

        -- 1. BEFORE DELETE — block deletes
        EXECUTE format(
            'DROP TRIGGER IF EXISTS block_delete_trg ON %I.%I;
             CREATE TRIGGER block_delete_trg
                 BEFORE DELETE ON %I.%I
                 FOR EACH ROW EXECUTE FUNCTION audit.block_delete();',
            r.table_schema, r.table_name,
            r.table_schema, r.table_name
        );

        -- 2. BEFORE TRUNCATE — block truncates
        EXECUTE format(
            'DROP TRIGGER IF EXISTS block_truncate_trg ON %I.%I;
             CREATE TRIGGER block_truncate_trg
                 BEFORE TRUNCATE ON %I.%I
                 FOR EACH STATEMENT EXECUTE FUNCTION audit.block_truncate();',
            r.table_schema, r.table_name,
            r.table_schema, r.table_name
        );

        -- 3. AFTER INSERT OR UPDATE — audit capture
        EXECUTE format(
            'DROP TRIGGER IF EXISTS audit_capture_trg ON %I.%I;
             CREATE TRIGGER audit_capture_trg
                 AFTER INSERT OR UPDATE ON %I.%I
                 FOR EACH ROW EXECUTE FUNCTION audit.capture();',
            r.table_schema, r.table_name,
            r.table_schema, r.table_name
        );

        -- 4. BEFORE UPDATE — touch updated_at (only if column exists)
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = r.table_schema
              AND table_name   = r.table_name
              AND column_name  = 'updated_at'
        ) INTO has_updated_at;

        IF has_updated_at THEN
            EXECUTE format(
                'DROP TRIGGER IF EXISTS touch_updated_at_trg ON %I.%I;
                 CREATE TRIGGER touch_updated_at_trg
                     BEFORE UPDATE ON %I.%I
                     FOR EACH ROW EXECUTE FUNCTION audit.touch_updated_at();',
                r.table_schema, r.table_name,
                r.table_schema, r.table_name
            );
        END IF;

    END LOOP;
END $$;

-- ============================================================
-- LOOKUP VALIDATION TRIGGERS
-- Attach audit.validate_lookup() to every *_id lookup FK column.
-- Format: validate_lookup_<col>_trg
-- ============================================================
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT * FROM (VALUES
            -- (table_schema, table_name, list_code, column_name)
            ('core','company',             'COMPANY_CATEGORY',    'category_id'),
            ('core','company',             'COMPANY_SUBCATEGORY', 'subcategory_id'),
            ('core','company_relationship','RELATIONSHIP',        'relationship_type_id'),
            ('core','directorship',        'DIRECTOR_CATEGORY',   'director_category_id'),
            ('core','directorship_role',   'DESIGNATION',         'designation_id'),
            ('core','director_other_directorship','OTHER_COMPANY_TYPE','company_type_id'),
            ('core','auditor',             'AUDITOR_TYPE',        'auditor_type_id'),
            ('core','meeting',             'MEETING_TYPE',        'meeting_type_id'),
            ('core','meeting',             'MEETING_VENUE_MODE',  'venue_mode_id'),
            ('core','share_class',         'CLASS_OF_SHARES',     'class_id'),
            ('core','share_class',         'DEBENTURE_TYPE',      'debenture_type_id'),
            ('core','capital_event',       'CAPITAL_INCREASE_REASON','reason_id'),
            ('core','shareholder',         'SHAREHOLDER_CATEGORY','category_id'),
            ('core','penalty_action',      'LEGAL_ACTION_TYPE',   'action_type_id'),
            ('core','penalty_action',      'AUTHORITY',           'authority_id'),
            ('core','government_filing',   'FILING_STATUS',       'status_id'),
            ('core','yearly_disclosure',   'DIVIDEND_TYPE',       'dividend_type_id'),
            ('core','foreign_investment',  'FOREIGN_INVESTMENT_TYPE','type_id'),
            ('core','foreign_investment',  'FILING_STATUS',       'status_id'),
            ('core','s186_transaction',    'RELATIONSHIP',        'relationship_type_id'),
            ('core','s188_related_party_txn','RELATIONSHIP',      'relationship_type_id'),
            ('core','odi',                 'FILING_STATUS',       'status_id'),
            ('core','ecb',                 'FILING_STATUS',       'status_id')
        ) AS t(tschema, tname, list_code, col_name)
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS validate_lookup_%s_trg ON %I.%I;
             CREATE TRIGGER validate_lookup_%s_trg
                 BEFORE INSERT OR UPDATE ON %I.%I
                 FOR EACH ROW EXECUTE FUNCTION audit.validate_lookup(%L, %L);',
            r.col_name, r.tschema, r.tname,
            r.col_name, r.tschema, r.tname,
            r.list_code, r.col_name
        );
    END LOOP;
END $$;

-- ============================================================
-- ROW-LEVEL SECURITY
-- Enable RLS on every table that has a company_id column.
-- Policy: bmp_app role sees only rows for companies in user_company_access.
-- Superusers and bmp_owner bypass RLS automatically.
-- ============================================================
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT c.table_schema, c.table_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE c.column_name = 'company_id'
          AND c.table_schema IN ('core','ops')
          AND c.table_name NOT IN ('user_company_access')
          AND t.table_type = 'BASE TABLE'
        GROUP BY c.table_schema, c.table_name
    LOOP
        -- Enable RLS (bmp_app is subject to it; table owner bmp_owner bypasses per guidelines)
        EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY;', r.table_schema, r.table_name);
        EXECUTE format('ALTER TABLE %I.%I NO FORCE ROW LEVEL SECURITY;', r.table_schema, r.table_name);

        -- Drop old policy if exists
        EXECUTE format('DROP POLICY IF EXISTS bmp_app_company_isolation ON %I.%I;', r.table_schema, r.table_name);

        -- Create SELECT/INSERT/UPDATE policy for bmp_app
        EXECUTE format(
            $pol$
            CREATE POLICY bmp_app_company_isolation ON %I.%I
                FOR ALL
                TO bmp_app
                USING (
                    company_id IN (
                        SELECT uca.company_id
                        FROM core.user_company_access uca
                        WHERE uca.user_id = nullif(current_setting('app.current_user_id', true), '')::bigint
                    )
                )
                WITH CHECK (
                    company_id IN (
                        SELECT uca.company_id
                        FROM core.user_company_access uca
                        WHERE uca.user_id = nullif(current_setting('app.current_user_id', true), '')::bigint
                    )
                );
            $pol$,
            r.table_schema, r.table_name
        );
    END LOOP;
END $$;

-- RLS on core.company itself
ALTER TABLE core.company ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.company NO FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bmp_app_company_isolation ON core.company;
CREATE POLICY bmp_app_company_isolation ON core.company
    FOR ALL
    TO bmp_app
    USING (
        id IN (
            SELECT uca.company_id
            FROM core.user_company_access uca
            WHERE uca.user_id = nullif(current_setting('app.current_user_id', true), '')::bigint
        )
    )
    WITH CHECK (
        id IN (
            SELECT uca.company_id
            FROM core.user_company_access uca
            WHERE uca.user_id = nullif(current_setting('app.current_user_id', true), '')::bigint
        )
    );

-- ============================================================
-- FINAL GRANTS
-- Ensure bmp_app has SELECT, INSERT, UPDATE on all tables in all schemas.
-- DELETE and TRUNCATE are NOT granted — enforced at trigger + role level.
-- ============================================================
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('core','activity','ops')
          AND table_type = 'BASE TABLE'
    LOOP
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE ON %I.%I TO bmp_app;',
            r.table_schema, r.table_name
        );
    END LOOP;
END $$;

-- Grant EXECUTE on ops function to bmp_app
GRANT EXECUTE ON FUNCTION ops.instantiate_activity TO bmp_app;
GRANT EXECUTE ON FUNCTION activity.get_template_json TO bmp_app;

-- Grant SELECT on all views to bmp_app
DO $$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT table_schema, table_name
        FROM information_schema.views
        WHERE table_schema IN ('core','activity','ops')
    LOOP
        EXECUTE format('GRANT SELECT ON %I.%I TO bmp_app;', r.table_schema, r.table_name);
    END LOOP;
END $$;
