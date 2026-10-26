-- 007_core_financial_legal_filings.sql
-- Loans/deposits, remuneration, penalties, filings, yearly disclosures,
-- Sec 185/186/188 tables, ODI, ECB, portal access.

-- ============================================================
-- LOAN_DEPOSIT
-- Xlsx: "Loans & Deposits"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.loan_deposit (
    id                         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id                 bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    financial_year             text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    borrowing_type             text   NOT NULL,   -- e.g. 'Secured loans','Unsecured loans','Deposits'. Xlsx row 1.
    opening_principal          numeric(18,2),
    opening_interest_due       numeric(18,2),
    opening_interest_accrued   numeric(18,2),
    added_during_year          numeric(18,2),
    reduced_during_year        numeric(18,2),
    closing_principal          numeric(18,2),     -- computed in v_loan_totals; stored for convenience
    closing_interest_due       numeric(18,2),
    closing_interest_accrued   numeric(18,2),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.loan_deposit IS 'Outstanding borrowings in MGT-7 format: opening balance, movement, closing. Xlsx: "Loans & Deposits".';
CREATE INDEX IF NOT EXISTS loan_deposit_company_idx ON core.loan_deposit (company_id);

-- ============================================================
-- REMUNERATION
-- Xlsx: "Remuneration"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.remuneration (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id            bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    financial_year        text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    directorship_id       bigint REFERENCES core.directorship(id) ON DELETE RESTRICT,  -- NULL for non-directors
    person_name           text,                   -- denormalised for non-director KMPs
    salary                numeric(18,2),
    perquisites           numeric(18,2),
    profits_in_lieu       numeric(18,2),
    stock_options         numeric(18,2),
    sweat_equity          numeric(18,2),
    commission            numeric(18,2),
    sitting_fees          numeric(18,2),
    other_payments        numeric(18,2),
    -- total is a generated column (sum of components)
    total                 numeric(18,2) GENERATED ALWAYS AS (
                              COALESCE(salary,0) + COALESCE(perquisites,0) + COALESCE(profits_in_lieu,0)
                              + COALESCE(stock_options,0) + COALESCE(sweat_equity,0) + COALESCE(commission,0)
                              + COALESCE(sitting_fees,0) + COALESCE(other_payments,0)
                          ) STORED,
    ceiling               numeric(18,2),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.remuneration IS 'Remuneration paid to directors and KMPs per financial year. Total is a generated column. Xlsx: "Remuneration".';
COMMENT ON COLUMN core.remuneration.total IS 'Sum of all pay components. GENERATED ALWAYS — not manually writable.';
CREATE INDEX IF NOT EXISTS remuneration_company_idx      ON core.remuneration (company_id);
CREATE INDEX IF NOT EXISTS remuneration_directorship_idx ON core.remuneration (directorship_id);

-- ============================================================
-- PENALTY_ACTION
-- Xlsx: "Penalties & Legal Actions"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.penalty_action (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id       bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    relates_to       text   NOT NULL CHECK (relates_to IN ('company','directorship','officer')),
    directorship_id  bigint REFERENCES core.directorship(id) ON DELETE RESTRICT,
    action_type_id   bigint REFERENCES core.lookup_value(id)  ON DELETE RESTRICT, -- LEGAL_ACTION_TYPE list
    section          text,
    description      text,
    details          text,
    amount           numeric(18,2),
    authority_id     bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT,  -- AUTHORITY list
    appealed         boolean NOT NULL DEFAULT false,
    appeal_details   text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.penalty_action IS 'Penalties, prosecutions and compounding records. Xlsx: "Penalties & Legal Actions".';
CREATE INDEX IF NOT EXISTS penalty_company_idx ON core.penalty_action (company_id);

-- ============================================================
-- GOVERNMENT_FILING
-- Xlsx: "Government Filings Tracker"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.government_filing (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id     bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    form_name      text   NOT NULL,
    description    text,
    financial_year text   CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    due_date       date,
    filing_date    date,
    srn            text,
    fee_paid       numeric(18,2),
    status_id      bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT,  -- FILING_STATUS list
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.government_filing IS 'Government e-form filings tracker. Xlsx: "Government Filings Tracker".';
CREATE INDEX IF NOT EXISTS gov_filing_company_idx  ON core.government_filing (company_id);
CREATE INDEX IF NOT EXISTS gov_filing_due_date_idx ON core.government_filing (due_date);

-- Now add deferred FK from allotment
ALTER TABLE core.allotment
    ADD CONSTRAINT allotment_gov_filing_fk
    FOREIGN KEY (government_filing_id) REFERENCES core.government_filing(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS allotment_gov_filing_idx ON core.allotment (government_filing_id);

-- ============================================================
-- YEARLY_DISCLOSURE
-- Xlsx: "Other Yearly Disclosures"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.yearly_disclosure (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id     bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    financial_year text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    disclosure_type text  NOT NULL CHECK (disclosure_type IN (
        'register_closure','dividend','delisting','nominal_value_change',
        'directors_interest','independent_directors_declaration'
    )),
    details        jsonb,
    key_date       date,
    dividend_type_id bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT,  -- DIVIDEND_TYPE list; only for dividend rows
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.yearly_disclosure IS 'Other yearly disclosures required by MGT-7. Xlsx: "Other Yearly Disclosures".';
CREATE INDEX IF NOT EXISTS yearly_disc_company_idx ON core.yearly_disclosure (company_id);

-- ============================================================
-- S185_LOAN  (Sec 185 — Loans to Directors)
-- Xlsx: "Loans to Directors (Sec 185)"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.s185_loan (
    id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id               bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    beneficiary_description  text   NOT NULL,       -- who the loan/guarantee/security is for. Xlsx row 1.
    directorship_id          bigint REFERENCES core.directorship(id) ON DELETE RESTRICT,
    loan_type                text   NOT NULL CHECK (loan_type IN ('loan','guarantee','security')),
    amount                   numeric(18,2) NOT NULL,
    exception_relied_on      text,
    shareholder_approval     boolean,
    approval_date            date,
    approval_special_res_date date,
    board_meeting_id         bigint REFERENCES core.meeting(id) ON DELETE RESTRICT,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.s185_loan IS 'Loans, guarantees and securities for directors/connected persons under Section 185. Xlsx: "Loans to Directors (Sec 185)".';
CREATE INDEX IF NOT EXISTS s185_company_idx ON core.s185_loan (company_id);

-- ============================================================
-- S186_TRANSACTION  (Sec 186 — Loans, Guarantees, Investments)
-- Xlsx: "Loans & Investments (Sec 186)"
-- Running total is computed in v_s186_running_total view.
-- ============================================================
CREATE TABLE IF NOT EXISTS core.s186_transaction (
    id                        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id                bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    financial_year            text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    recipient_name            text   NOT NULL,
    transaction_type          text   NOT NULL CHECK (transaction_type IN ('loan','guarantee','security','investment')),
    amount                    numeric(18,2) NOT NULL,
    shareholder_approval      boolean NOT NULL DEFAULT false,
    approval_date             date,
    board_meeting_id          bigint REFERENCES core.meeting(id) ON DELETE RESTRICT,
    relationship_type_id      bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- RELATIONSHIP list
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.s186_transaction IS 'Loans, guarantees, investments by the company under Section 186. Running total computed by v_s186_running_total. Xlsx: "Loans & Investments (Sec 186)".';
CREATE INDEX IF NOT EXISTS s186_company_idx ON core.s186_transaction (company_id);

-- ============================================================
-- S188_RELATED_PARTY_TXN  (Sec 188)
-- Xlsx: "Related Party Txns (Sec 188)"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.s188_related_party_txn (
    id                         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id                 bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    financial_year             text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    related_party_name         text   NOT NULL,
    relationship_type_id       bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- RELATIONSHIP list
    related_directorship_id    bigint REFERENCES core.directorship(id) ON DELETE RESTRICT,
    nature_of_txn              text   NOT NULL,
    transaction_value          numeric(18,2),
    is_ordinary_course         boolean,
    is_arms_length             boolean,
    audit_committee_approval_date date,
    audit_committee_omnibus    boolean NOT NULL DEFAULT false,
    board_meeting_id           bigint REFERENCES core.meeting(id) ON DELETE RESTRICT,
    shareholder_approval       boolean NOT NULL DEFAULT false,
    shareholder_approval_date  date,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.s188_related_party_txn IS 'Related party transactions under Section 188. Xlsx: "Related Party Txns (Sec 188)".';
CREATE INDEX IF NOT EXISTS s188_company_idx ON core.s188_related_party_txn (company_id);

-- ============================================================
-- ODI  (Overseas Direct Investment)
-- Xlsx: "ODI Compliances"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.odi (
    id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id               bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    foreign_subsidiary_name  text   NOT NULL,
    uin                      text,   -- Unique Identification Number
    shares_purchased         bigint,
    country                  text,
    total_investment_inr     numeric(18,2),
    board_approval_date      date,
    filing_date              date,
    status_id                bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- FILING_STATUS list
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.odi IS 'ODI compliance records for companies with foreign subsidiaries. Xlsx: "ODI Compliances".';
CREATE INDEX IF NOT EXISTS odi_company_idx ON core.odi (company_id);

-- ============================================================
-- ODI_STEP_DOWN_SUBSIDIARY
-- Xlsx: "ODI Compliances" rows 4-5
-- ============================================================
CREATE TABLE IF NOT EXISTS core.odi_step_down_subsidiary (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    odi_id      bigint NOT NULL REFERENCES core.odi(id) ON DELETE RESTRICT,
    name        text   NOT NULL,
    level       int,
    country     text,
    parent_name text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.odi_step_down_subsidiary IS 'Step-down subsidiaries of the foreign subsidiary. Xlsx: "ODI Compliances" rows 4-5.';
CREATE INDEX IF NOT EXISTS odi_sds_odi_idx ON core.odi_step_down_subsidiary (odi_id);

-- ============================================================
-- ECB  (External Commercial Borrowings)
-- Xlsx: "ECB"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.ecb (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id       bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    lender_name      text   NOT NULL,
    lender_country   text   NOT NULL,
    lrn              text,   -- Loan Registration Number
    loan_amount      numeric(18,2) NOT NULL,
    currency         text   NOT NULL,
    interest_rate    numeric(9,4),
    draw_down_date   date,
    maturity_date    date,
    amount_inr       numeric(18,2),
    conversion_rate  numeric(18,6),
    status_id        bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- FILING_STATUS list
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.ecb IS 'External Commercial Borrowing records. Xlsx: "ECB".';
CREATE INDEX IF NOT EXISTS ecb_company_idx ON core.ecb (company_id);

-- ============================================================
-- PORTAL_ACCESS
-- Xlsx: "Portal Access"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.portal_access (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id       bigint REFERENCES core.company(id) ON DELETE RESTRICT,  -- NULL for firm-level portals
    portal_name      text   NOT NULL,
    username         text,
    held_by          text,
    notes            text,
    secret_encrypted bytea,   -- pgp_sym_encrypt(password, runtime_key); key never stored here
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.portal_access IS 'Government/bank portal access records. Passwords stored encrypted with pgp_sym_encrypt; key supplied at runtime. Xlsx: "Portal Access".';
COMMENT ON COLUMN core.portal_access.secret_encrypted IS 'pgp_sym_encrypt(password, session_key). Key is supplied at runtime and never stored.';
CREATE INDEX IF NOT EXISTS portal_access_company_idx ON core.portal_access (company_id);
