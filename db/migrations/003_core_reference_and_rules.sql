-- 003_core_reference_and_rules.sql
-- Lookup lists, lookup values, document types, rule definitions, rule evaluations.

-- ============================================================
-- LOOKUP LISTS & VALUES  (generic dropdown system)
-- ============================================================
CREATE TABLE IF NOT EXISTS core.lookup_list (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code        text   NOT NULL UNIQUE,           -- internal key, e.g. 'COMPANY_CATEGORY'
    name        text   NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.lookup_list IS 'Master list of dropdown categories. Each row defines a named set of fixed options.';

CREATE TABLE IF NOT EXISTS core.lookup_value (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    list_id     bigint NOT NULL REFERENCES core.lookup_list(id) ON DELETE RESTRICT,
    code        text   NOT NULL,                  -- e.g. 'PUBLIC'
    label       text   NOT NULL,                  -- e.g. 'Public Company'
    sort_order  int    NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    UNIQUE (list_id, code)
);
COMMENT ON TABLE core.lookup_value IS 'Individual options within a lookup list. FK columns reference lookup_value.id and are validated by audit.validate_lookup().';

CREATE INDEX IF NOT EXISTS lookup_value_list_id_idx ON core.lookup_value (list_id);

-- ============================================================
-- DOCUMENT TYPES
-- ============================================================
CREATE TABLE IF NOT EXISTS core.document_type (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code             text   NOT NULL UNIQUE,
    name             text   NOT NULL,
    applies_to_entity text,    -- e.g. 'meeting', 'directorship', 'foreign_investment'
    is_mandatory     boolean NOT NULL DEFAULT false,
    description      text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.document_type IS 'Registry of document types required or used across the platform. Seeded from xlsx sheets (Board Meetings, General Meetings, Auditors, ODI, ECB, etc.).';

-- ============================================================
-- RULE DEFINITIONS  (xlsx sheet: "When Something Becomes Required")
-- ============================================================
CREATE TABLE IF NOT EXISTS core.rule_definition (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code                  text   NOT NULL UNIQUE,    -- e.g. 'CSR_SPENDING'
    name                  text   NOT NULL,
    law_reference         text,
    applies_to_description text,
    trigger_description   text,
    inputs_needed         text,
    decides               text,
    responsible_party     text,
    frequency             text,
    is_active             boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.rule_definition IS 'Applicability rules sourced from xlsx "When Something Becomes Required". Each row is one rule/limit; evaluation is done in rule_evaluation or computed views.';
COMMENT ON COLUMN core.rule_definition.code              IS 'Short snake-case code; used by application and views.';
COMMENT ON COLUMN core.rule_definition.trigger_description IS 'Plain-English description of when the rule kicks in. Xlsx col: "When it kicks in".';
COMMENT ON COLUMN core.rule_definition.inputs_needed       IS 'What data fields are checked. Xlsx col: "What we need to know to check this".';
COMMENT ON COLUMN core.rule_definition.decides             IS 'What the rule determines. Xlsx col: "What it decides".';

-- ============================================================
-- RULE EVALUATIONS  (per-company, per-year results)
-- ============================================================
CREATE TABLE IF NOT EXISTS core.rule_evaluation (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id     bigint NOT NULL,    -- FK set after core.company is created (011)
    rule_id        bigint NOT NULL REFERENCES core.rule_definition(id) ON DELETE RESTRICT,
    financial_year text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    evaluated_on   timestamptz NOT NULL DEFAULT now(),
    applies        boolean,
    status         text CHECK (status IN ('met','pending','action_required','not_applicable')),
    inputs         jsonb,
    notes          text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    is_archived    boolean     NOT NULL DEFAULT false,
    archived_at    timestamptz,
    archived_by    bigint,
    UNIQUE (company_id, rule_id, financial_year, evaluated_on)
);
COMMENT ON TABLE core.rule_evaluation IS 'Recorded results of rule evaluations per company per financial year. Manual entries in Phase 1; automated in later phases.';

CREATE INDEX IF NOT EXISTS rule_evaluation_company_idx ON core.rule_evaluation (company_id);
CREATE INDEX IF NOT EXISTS rule_evaluation_rule_idx    ON core.rule_evaluation (rule_id);
