-- 004_core_company_people.sql
-- Company master, company-level sub-tables, director/KMP master, directorship stints.

-- ============================================================
-- COMPANY  (xlsx: "Company Details")
-- ============================================================
CREATE TABLE IF NOT EXISTS core.company (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- Basic identification
    cin                   text NOT NULL UNIQUE CHECK (length(cin) = 21),
    name                  text NOT NULL,
    pan                   text,
    date_of_incorporation date NOT NULL,
    roc                   text,
    -- Category (lookup)
    category_id           bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT,
    subcategory_id        bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT,
    -- Addresses
    registered_address    text,
    correspondence_address text,
    phone                 text,
    fax                   text,
    email                 text,
    website               text,
    -- Listing / size indicators
    is_listed             boolean NOT NULL DEFAULT false,
    market_value_rank     int,         -- rank in listed universe (for SEBI rules)
    ind_as_applicable     boolean NOT NULL DEFAULT false,
    -- Status
    status                text NOT NULL DEFAULT 'active'
                              CHECK (status IN ('active','struck_off','liquidated','amalgamated')),
    -- Standard audit columns
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.company IS 'One row per client company. Central entity of the platform. Xlsx: "Company Details".';
COMMENT ON COLUMN core.company.cin                   IS 'Corporate Identification Number. 21 chars. Xlsx row 2.';
COMMENT ON COLUMN core.company.category_id           IS 'Public/Private. References lookup_list code COMPANY_CATEGORY. Xlsx row 5.';
COMMENT ON COLUMN core.company.subcategory_id        IS 'Government/Small/OPC etc. References lookup_list code COMPANY_SUBCATEGORY. Xlsx row 6.';
COMMENT ON COLUMN core.company.market_value_rank     IS 'Rank by market capitalisation among listed companies; used for SEBI top-1000 rules.';
COMMENT ON COLUMN core.company.ind_as_applicable     IS 'Whether Indian Accounting Standards (Ind AS) apply. Xlsx row 9 (implied).';

CREATE INDEX IF NOT EXISTS company_status_idx ON core.company (status);

-- ============================================================
-- COMPANY_RTA  (Registrar & Transfer Agent)
-- ============================================================
CREATE TABLE IF NOT EXISTS core.company_rta (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id  bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    name        text   NOT NULL,
    address     text,
    phone       text,
    email       text,
    sebi_reg_no text,
    valid_from  date   NOT NULL,
    valid_to    date,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.company_rta IS 'Registrar and Transfer Agent details, with period of engagement.';
CREATE INDEX IF NOT EXISTS company_rta_company_idx ON core.company_rta (company_id);

-- ============================================================
-- COMPANY_BUSINESS_ACTIVITY
-- ============================================================
CREATE TABLE IF NOT EXISTS core.company_business_activity (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id      bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    description     text   NOT NULL,
    nic_code        text,
    turnover_percent numeric(9,4) CHECK (turnover_percent BETWEEN 0 AND 100),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.company_business_activity IS 'Business activities of the company. Xlsx: "Company Details" row 19.';
CREATE INDEX IF NOT EXISTS company_ba_company_idx ON core.company_business_activity (company_id);

-- ============================================================
-- COMPANY_RELATIONSHIP
-- ============================================================
CREATE TABLE IF NOT EXISTS core.company_relationship (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id          bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    relationship_type_id bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT,  -- RELATIONSHIP list
    related_name        text   NOT NULL,
    related_cin         text,
    related_company_id  bigint REFERENCES core.company(id) ON DELETE RESTRICT,   -- nullable internal link
    stake_percent       numeric(9,4),
    valid_from          date,
    valid_to            date,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.company_relationship IS 'Holding/subsidiary/associate relationships. Xlsx: "Company Details" rows 21-24.';
CREATE INDEX IF NOT EXISTS company_rel_company_idx ON core.company_relationship (company_id);

-- ============================================================
-- COMPANY_FINANCIALS  (per financial year)
-- ============================================================
CREATE TABLE IF NOT EXISTS core.company_financials (
    id                        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id                bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    financial_year            text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    -- P&L and balance sheet figures
    turnover                  numeric(18,2),
    net_worth                 numeric(18,2),
    net_profit                numeric(18,2),
    free_reserves             numeric(18,2),
    securities_premium        numeric(18,2),
    borrowings_banks_fi       numeric(18,2),
    public_deposits           numeric(18,2),
    debentures_outstanding    numeric(18,2),
    csr_spend                 numeric(18,2),
    s185_limit                numeric(18,2),
    s186_limit                numeric(18,2),   -- higher of the two computed limits; a view also computes it
    total_security_holders    int,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    UNIQUE (company_id, financial_year)
);
COMMENT ON TABLE core.company_financials IS 'Annual financial figures per company per year. Used by rule evaluation views. Xlsx: "Company Details" rows 13-18, 26-30.';
CREATE INDEX IF NOT EXISTS company_fin_company_idx ON core.company_financials (company_id);

-- ============================================================
-- DIRECTOR  (individual master)
-- Xlsx: "Directors & Key Managers"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.director (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    din               text UNIQUE CHECK (din ~ '^\d{8}$'),  -- 8-digit DIN; NULL for non-director KMPs
    full_name         text NOT NULL,
    pan               text,
    relative_name     text,                -- father's/mother's/spouse's name. Xlsx row 4.
    aadhaar_encrypted bytea,              -- pgp_sym_encrypt(aadhaar, session_key). Xlsx row 5.
    date_of_birth     date,
    gender            text CHECK (gender IN ('M','F','Other')),
    nationality       text,
    address           text,
    email             text,
    phone             text,
    occupation        text,
    dsc_valid_until   date,               -- Digital Signature Certificate expiry. Xlsx row 20 (implied).
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.director IS 'Individual master record for directors and KMPs. One row per person, not per company. Xlsx: "Directors & Key Managers".';
COMMENT ON COLUMN core.director.din               IS 'Director Identification Number. 8 digits. NULL for non-director KMPs (CS, CFO). Xlsx row 2.';
COMMENT ON COLUMN core.director.aadhaar_encrypted IS 'Aadhaar encrypted with pgp_sym_encrypt. Key supplied at runtime. Never stored in plaintext. Xlsx row 5.';
COMMENT ON COLUMN core.director.dsc_valid_until   IS 'Digital Signature Certificate expiry date. Xlsx row 20.';

CREATE INDEX IF NOT EXISTS director_pan_idx ON core.director (pan);

-- ============================================================
-- DIRECTOR_RESIDENCY
-- ============================================================
CREATE TABLE IF NOT EXISTS core.director_residency (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    director_id          bigint NOT NULL REFERENCES core.director(id) ON DELETE RESTRICT,
    financial_year       text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    resident_over_182    boolean NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    UNIQUE (director_id, financial_year)
);
COMMENT ON TABLE core.director_residency IS 'Whether a director was resident in India for >182 days in a financial year. Used by v_rule_resident_director. Xlsx row 26.';
CREATE INDEX IF NOT EXISTS dir_residency_dir_idx ON core.director_residency (director_id);

-- ============================================================
-- DIRECTOR_KYC
-- ============================================================
CREATE TABLE IF NOT EXISTS core.director_kyc (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    director_id      bigint NOT NULL REFERENCES core.director(id) ON DELETE RESTRICT,
    financial_year   text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    dir3_kyc_filed   boolean NOT NULL DEFAULT false,
    filed_on         date,
    srn              text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    UNIQUE (director_id, financial_year)
);
COMMENT ON TABLE core.director_kyc IS 'DIR-3 KYC filing status per director per year. Xlsx row 21.';
CREATE INDEX IF NOT EXISTS dir_kyc_dir_idx ON core.director_kyc (director_id);

-- ============================================================
-- DIRECTORSHIP  (one row per stint on a company's board)
-- Xlsx: "Directors & Key Managers" — all per-company fields
-- ============================================================
CREATE TABLE IF NOT EXISTS core.directorship (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id           bigint NOT NULL REFERENCES core.company(id)  ON DELETE RESTRICT,
    director_id          bigint NOT NULL REFERENCES core.director(id) ON DELETE RESTRICT,
    start_date           date   NOT NULL,
    end_date             date,
    cessation_reason     text,
    -- Flags
    is_whole_time        boolean NOT NULL DEFAULT false,
    is_independent       boolean NOT NULL DEFAULT false,
    is_nominee           boolean NOT NULL DEFAULT false,
    is_additional        boolean NOT NULL DEFAULT false,
    is_alternate         boolean NOT NULL DEFAULT false,
    retires_by_rotation  boolean NOT NULL DEFAULT false,
    is_signatory         boolean NOT NULL DEFAULT false,
    is_board_member      boolean NOT NULL DEFAULT true,  -- false for non-director KMPs
    director_category_id bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- DIRECTOR_CATEGORY list
    shares_held          bigint,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    -- Prevent overlapping stints for same (company, director)
    EXCLUDE USING gist (
        company_id  WITH =,
        director_id WITH =,
        daterange(start_date, end_date, '[]') WITH &&
    )
);
COMMENT ON TABLE core.directorship IS 'One row per stint of a director/KMP at a company. A resigned-and-reappointed person has two rows. Xlsx: "Directors & Key Managers" cols date-related.';
COMMENT ON COLUMN core.directorship.end_date         IS 'NULL if still serving. Xlsx row 18.';
COMMENT ON COLUMN core.directorship.cessation_reason IS 'Why the stint ended (resignation, removal, expiry of term, death, etc.). Xlsx row 19.';
COMMENT ON COLUMN core.directorship.is_board_member  IS 'False for non-director KMPs (CS, CFO without director designation). Xlsx row 33.';

CREATE INDEX IF NOT EXISTS directorship_company_idx  ON core.directorship (company_id);
CREATE INDEX IF NOT EXISTS directorship_director_idx ON core.directorship (director_id);

-- ============================================================
-- DIRECTORSHIP_ROLE  (designation history within a stint)
-- ============================================================
CREATE TABLE IF NOT EXISTS core.directorship_role (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    directorship_id  bigint NOT NULL REFERENCES core.directorship(id) ON DELETE RESTRICT,
    designation_id   bigint NOT NULL REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- DESIGNATION list
    start_date       date   NOT NULL,
    end_date         date,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    -- Prevent overlapping roles within the same directorship
    EXCLUDE USING gist (
        directorship_id WITH =,
        designation_id  WITH =,
        daterange(start_date, end_date, '[]') WITH &&
    )
);
COMMENT ON TABLE core.directorship_role IS 'Designation history within a stint (e.g. Director -> Managing Director). Xlsx row 9.';
CREATE INDEX IF NOT EXISTS dir_role_directorship_idx ON core.directorship_role (directorship_id);

-- ============================================================
-- INDEPENDENT_DIRECTOR_TERM
-- ============================================================
CREATE TABLE IF NOT EXISTS core.independent_director_term (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    directorship_id  bigint NOT NULL REFERENCES core.directorship(id) ON DELETE RESTRICT,
    term_no          int    NOT NULL CHECK (term_no IN (1, 2)),
    start_date       date   NOT NULL,
    end_date         date,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    UNIQUE (directorship_id, term_no)
);
COMMENT ON TABLE core.independent_director_term IS 'First and second 5-year terms for independent directors. Total years served computed in v_independent_director_years. Xlsx row 22-24.';
CREATE INDEX IF NOT EXISTS ind_term_directorship_idx ON core.independent_director_term (directorship_id);

-- ============================================================
-- DIRECTOR_OTHER_DIRECTORSHIP
-- ============================================================
CREATE TABLE IF NOT EXISTS core.director_other_directorship (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    director_id         bigint NOT NULL REFERENCES core.director(id) ON DELETE RESTRICT,
    other_company_name  text   NOT NULL,
    cin                 text,
    company_type_id     bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- OTHER_COMPANY_TYPE list
    designation         text,
    start_date          date,
    end_date            date,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.director_other_directorship IS 'Other directorships held by a person (outside this system). Used for Sec 165 directorship-limit check. Xlsx row 30-32.';
CREATE INDEX IF NOT EXISTS dir_other_dir_idx ON core.director_other_directorship (director_id);

-- ============================================================
-- DIRECTOR_DECLARATION
-- ============================================================
CREATE TABLE IF NOT EXISTS core.director_declaration (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    directorship_id  bigint NOT NULL REFERENCES core.directorship(id) ON DELETE RESTRICT,
    declaration_type text   NOT NULL CHECK (declaration_type IN ('interest_disclosure','non_disqualification','independence')),
    financial_year   text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    on_file          boolean NOT NULL DEFAULT false,
    document_id      bigint,   -- FK to core.document set in migration 008
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.director_declaration IS 'Annual interest, non-disqualification and independence declarations. Xlsx rows 34-36.';
CREATE INDEX IF NOT EXISTS dir_declaration_directorship_idx ON core.director_declaration (directorship_id);

-- ============================================================
-- AUDITOR
-- Xlsx: "Auditors"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.auditor (
    id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id               bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    auditor_type_id          bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- AUDITOR_TYPE list
    name                     text   NOT NULL,
    pan                      text,
    frn                      text,                -- Firm Registration Number
    address                  text,
    email                    text,
    board_recommendation_date date,
    gm_appointment_date       date,
    account_period_from       date,
    account_period_to         date,
    term_years               int,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.auditor IS 'Auditor engagement records per company. Xlsx: "Auditors".';
COMMENT ON COLUMN core.auditor.frn              IS 'Firm Registration Number (ICAI). Xlsx row 4.';
COMMENT ON COLUMN core.auditor.board_recommendation_date IS 'Date the Board recommended the auditor. Xlsx row 3.';
COMMENT ON COLUMN core.auditor.gm_appointment_date       IS 'Date the General Meeting appointed the auditor. Xlsx row 4.';

CREATE INDEX IF NOT EXISTS auditor_company_idx ON core.auditor (company_id);

-- ============================================================
-- FK: core.rule_evaluation.company_id -> core.company
-- (deferred because company was created after rule_evaluation in migration 003)
-- ============================================================
ALTER TABLE core.rule_evaluation
    ADD CONSTRAINT rule_evaluation_company_fk
    FOREIGN KEY (company_id) REFERENCES core.company(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS rule_evaluation_company_fk_idx ON core.rule_evaluation (company_id);
