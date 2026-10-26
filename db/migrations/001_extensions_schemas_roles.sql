-- 001_extensions_schemas_roles.sql
-- Creates extensions, schemas, and roles.
-- Must run as a superuser or as bmp_owner with CREATEROLE privilege.

-- ============================================================
-- EXTENSIONS
-- ============================================================
-- pgvector is REQUIRED (no silent fallback). It is not a "trusted" extension, so
-- scripts/setup_db.py creates it as superuser first; this line then only confirms it.
CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector (embeddings)
CREATE EXTENSION IF NOT EXISTS btree_gist;      -- GIST indexes on scalar types (exclusion constraints)
CREATE EXTENSION IF NOT EXISTS pgcrypto;        -- pgp_sym_encrypt / decrypt, gen_random_uuid

-- ============================================================
-- SCHEMAS
-- ============================================================
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS activity;
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS audit;

COMMENT ON SCHEMA core     IS 'User Database: companies, people, capital, governance, filings.';
COMMENT ON SCHEMA activity IS 'Activity Database: templates, steps, bindings — machine-readable workflow definitions.';
COMMENT ON SCHEMA ops      IS 'Operations: per-company instances of activities, task status.';
COMMENT ON SCHEMA audit    IS 'Audit log and trigger utility functions.';

-- ============================================================
-- ROLES
-- ============================================================
-- bmp_owner: owns all objects, runs migrations; superuser not required.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bmp_owner') THEN
        CREATE ROLE bmp_owner WITH LOGIN;
    END IF;
END $$;

-- bmp_app: the application role; cannot DELETE or TRUNCATE; subject to RLS.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bmp_app') THEN
        CREATE ROLE bmp_app WITH LOGIN;
    END IF;
END $$;

-- Passwords are set from .env at role-creation time by the DBA; never hardcoded here.

-- ============================================================
-- SCHEMA OWNERSHIP AND USAGE
-- ============================================================
ALTER SCHEMA core     OWNER TO bmp_owner;
ALTER SCHEMA activity OWNER TO bmp_owner;
ALTER SCHEMA ops      OWNER TO bmp_owner;
ALTER SCHEMA audit    OWNER TO bmp_owner;

GRANT USAGE ON SCHEMA core     TO bmp_app;
GRANT USAGE ON SCHEMA activity TO bmp_app;
GRANT USAGE ON SCHEMA ops      TO bmp_app;
-- audit schema: bmp_app can INSERT into audit.log (via trigger); no direct SELECT
GRANT USAGE ON SCHEMA audit TO bmp_app;

-- Default privileges: objects created by bmp_owner are accessible to bmp_app
ALTER DEFAULT PRIVILEGES FOR ROLE bmp_owner IN SCHEMA core
    GRANT SELECT, INSERT, UPDATE ON TABLES TO bmp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE bmp_owner IN SCHEMA activity
    GRANT SELECT, INSERT, UPDATE ON TABLES TO bmp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE bmp_owner IN SCHEMA ops
    GRANT SELECT, INSERT, UPDATE ON TABLES TO bmp_app;
-- Sequences: needed for IDENTITY columns
ALTER DEFAULT PRIVILEGES FOR ROLE bmp_owner IN SCHEMA core
    GRANT USAGE, SELECT ON SEQUENCES TO bmp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE bmp_owner IN SCHEMA activity
    GRANT USAGE, SELECT ON SEQUENCES TO bmp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE bmp_owner IN SCHEMA ops
    GRANT USAGE, SELECT ON SEQUENCES TO bmp_app;
