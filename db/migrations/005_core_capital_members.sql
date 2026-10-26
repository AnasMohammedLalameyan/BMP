-- 005_core_capital_members.sql
-- Share classes, capital snapshots, shareholders, holdings, allotments, transfers, foreign investment.

-- ============================================================
-- SHARE_CLASS
-- Xlsx: "Share Capital Summary" row 1
-- ============================================================
CREATE TABLE IF NOT EXISTS core.share_class (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id        bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    class_id          bigint NOT NULL REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- CLASS_OF_SHARES list
    nominal_value     numeric(18,2) NOT NULL,
    debenture_type_id bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- DEBENTURE_TYPE list; NULL for equity
    description       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.share_class IS 'A class of shares or debentures for a company. Xlsx: "Share Capital Summary" row 1.';
CREATE INDEX IF NOT EXISTS share_class_company_idx ON core.share_class (company_id);

-- ============================================================
-- CAPITAL_SNAPSHOT  (opening/closing per class per year)
-- Xlsx: "Share Capital Summary" rows 2-5
-- ============================================================
CREATE TABLE IF NOT EXISTS core.capital_snapshot (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id         bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    share_class_id     bigint NOT NULL REFERENCES core.share_class(id) ON DELETE RESTRICT,
    financial_year     text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    snapshot_type      text   NOT NULL CHECK (snapshot_type IN ('opening','closing')),
    as_of_date         date   NOT NULL,
    authorised_shares  bigint,
    authorised_amount  numeric(18,2),
    issued_shares      bigint,
    issued_amount      numeric(18,2),
    subscribed_shares  bigint,
    subscribed_amount  numeric(18,2),
    paid_up_shares     bigint,
    paid_up_amount     numeric(18,2),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.capital_snapshot IS 'Authorised, issued, subscribed and paid-up capital per class per financial year (opening and closing). Xlsx: "Share Capital Summary" rows 2-5.';
CREATE INDEX IF NOT EXISTS cap_snap_company_idx    ON core.capital_snapshot (company_id);
CREATE INDEX IF NOT EXISTS cap_snap_class_idx      ON core.capital_snapshot (share_class_id);

-- ============================================================
-- CAPITAL_EVENT  (changes during year)
-- Xlsx: "Share Capital Summary" rows 2-6 (movement sub-rows)
-- ============================================================
CREATE TABLE IF NOT EXISTS core.capital_event (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id     bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    financial_year text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    event_type     text   NOT NULL CHECK (event_type IN ('split','consolidation','increase','decrease')),
    reason_id      bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- CAPITAL_INCREASE/DECREASE list
    event_date     date   NOT NULL,
    details        text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.capital_event IS 'Events that change the capital structure (split, consolidation, increase, decrease). Xlsx: "Share Capital Summary".';
CREATE INDEX IF NOT EXISTS cap_event_company_idx ON core.capital_event (company_id);

-- ============================================================
-- SHAREHOLDER  (master)
-- Xlsx: "Shareholders"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.shareholder (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            text   NOT NULL,
    father_spouse   text,
    pan             text,
    email           text,
    address         text,
    category_id     bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- SHAREHOLDER_CATEGORY list
    is_fii          boolean NOT NULL DEFAULT false,
    is_foreign      boolean NOT NULL DEFAULT false,
    country         text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.shareholder IS 'Master record for each shareholder. One row per person/entity. Xlsx: "Shareholders".';
COMMENT ON COLUMN core.shareholder.category_id IS 'Promoter-Indian, Promoter-Foreign, Public etc. Xlsx row 9.';

-- ============================================================
-- SHAREHOLDING  (current and historical)
-- Xlsx: "Shareholders" rows 1-13
-- A change in holding creates a new row and closes the old one.
-- ============================================================
CREATE TABLE IF NOT EXISTS core.shareholding (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id        bigint NOT NULL REFERENCES core.company(id)  ON DELETE RESTRICT,
    shareholder_id    bigint NOT NULL REFERENCES core.shareholder(id) ON DELETE RESTRICT,
    share_class_id    bigint NOT NULL REFERENCES core.share_class(id) ON DELETE RESTRICT,
    folio_number      text,
    is_demat          boolean NOT NULL DEFAULT false,
    client_id         text,
    dp_id             text,
    number_of_shares  bigint NOT NULL CHECK (number_of_shares > 0),
    face_value        numeric(18,2) NOT NULL,
    distinctive_from  text,
    distinctive_to    text,
    pledged_percent   numeric(9,4),
    valid_from        date   NOT NULL,
    valid_to          date,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    -- Prevent overlapping holding periods for same (company, shareholder, class, folio)
    EXCLUDE USING gist (
        company_id     WITH =,
        shareholder_id WITH =,
        share_class_id WITH =,
        folio_number   WITH =,
        daterange(valid_from, valid_to, '[]') WITH &&
    )
);
COMMENT ON TABLE core.shareholding IS 'One row per holding period. Change in holding = new row + close old one. Current = valid_to IS NULL. Xlsx: "Shareholders".';
COMMENT ON COLUMN core.shareholding.valid_to IS 'NULL when this is the current holding. Set to the date of the next change when superseded.';

CREATE INDEX IF NOT EXISTS shareholding_company_idx    ON core.shareholding (company_id);
CREATE INDEX IF NOT EXISTS shareholding_shlder_idx     ON core.shareholding (shareholder_id);
CREATE INDEX IF NOT EXISTS shareholding_class_idx      ON core.shareholding (share_class_id);
CREATE INDEX IF NOT EXISTS shareholding_current_idx    ON core.shareholding (company_id, shareholder_id) WHERE valid_to IS NULL;

-- ============================================================
-- ALLOTMENT
-- Xlsx: "Share Allotments"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.allotment (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id            bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    round_reference       text,
    shareholder_id        bigint NOT NULL REFERENCES core.shareholder(id) ON DELETE RESTRICT,
    share_class_id        bigint NOT NULL REFERENCES core.share_class(id) ON DELETE RESTRICT,
    number_of_shares      bigint NOT NULL CHECK (number_of_shares > 0),
    allotment_date        date   NOT NULL,
    face_value            numeric(18,2) NOT NULL,
    premium_per_share     numeric(18,2) NOT NULL DEFAULT 0,
    issue_price           numeric(18,2) NOT NULL,
    face_value_amount     numeric(18,2) NOT NULL,
    premium_amount        numeric(18,2) NOT NULL DEFAULT 0,
    total_amount          numeric(18,2) NOT NULL,
    distinctive_from      text,
    distinctive_to        text,
    client_id             text,
    dp_id                 text,
    certificate_no        text,
    stamp_duty_payable    numeric(18,2),
    stamp_duty_paid       numeric(18,2),
    stamp_duty_paid_on    date,
    board_meeting_id      bigint,   -- FK to core.meeting set in migration 006
    government_filing_id  bigint,   -- FK to core.government_filing set in migration 007
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.allotment IS 'One record per share allotment transaction. Xlsx: "Share Allotments".';
CREATE INDEX IF NOT EXISTS allotment_company_idx      ON core.allotment (company_id);
CREATE INDEX IF NOT EXISTS allotment_shareholder_idx  ON core.allotment (shareholder_id);
CREATE INDEX IF NOT EXISTS allotment_class_idx        ON core.allotment (share_class_id);

-- ============================================================
-- SHARE_TRANSFER
-- Xlsx: "Share Transfers"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.share_transfer (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id          bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    transferor_id       bigint NOT NULL REFERENCES core.shareholder(id) ON DELETE RESTRICT,
    transferee_id       bigint NOT NULL REFERENCES core.shareholder(id) ON DELETE RESTRICT,
    share_class_id      bigint NOT NULL REFERENCES core.share_class(id) ON DELETE RESTRICT,
    number_of_shares    bigint NOT NULL CHECK (number_of_shares > 0),
    transfer_date       date   NOT NULL,
    board_meeting_id    bigint,   -- FK to core.meeting set in migration 006
    face_value          numeric(18,2),
    consideration       numeric(18,2),
    stamp_duty_paid     numeric(18,2),
    distinctive_from    text,
    distinctive_to      text,
    client_id           text,
    dp_id               text,
    transferee_folio    text,
    sh4_available       boolean NOT NULL DEFAULT false,
    involves_non_resident boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.share_transfer IS 'One record per share transfer. Xlsx: "Share Transfers".';
CREATE INDEX IF NOT EXISTS share_transfer_company_idx    ON core.share_transfer (company_id);
CREATE INDEX IF NOT EXISTS share_transfer_transferor_idx ON core.share_transfer (transferor_id);
CREATE INDEX IF NOT EXISTS share_transfer_transferee_idx ON core.share_transfer (transferee_id);

-- ============================================================
-- FOREIGN_INVESTMENT
-- Xlsx: "Foreign Investment — Shares Iss" (FC-GPR) and "Foreign Investment — Shares Tra" (FC-TRS)
-- ============================================================
CREATE TABLE IF NOT EXISTS core.foreign_investment (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id           bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    type_id              bigint NOT NULL REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- FOREIGN_INVESTMENT_TYPE list
    -- Either allotment_id (FC-GPR) or share_transfer_id (FC-TRS) — exactly one
    allotment_id         bigint REFERENCES core.allotment(id)     ON DELETE RESTRICT,
    share_transfer_id    bigint REFERENCES core.share_transfer(id) ON DELETE RESTRICT,
    foreign_currency     text   NOT NULL,
    foreign_amount       numeric(18,2) NOT NULL,
    conversion_rate      numeric(18,6) NOT NULL,
    amount_inr           numeric(18,2) NOT NULL,
    firc_number          text,
    ad_bank              text,
    board_approval_date  date,
    funds_received_date  date,
    filing_due_date      date,
    filing_date          date,
    approval_date        date,
    status_id            bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- FILING_STATUS list
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    -- Exactly one of allotment_id or share_transfer_id must be set
    CONSTRAINT fi_one_reference CHECK (
        (allotment_id IS NOT NULL AND share_transfer_id IS NULL)
        OR (allotment_id IS NULL AND share_transfer_id IS NOT NULL)
    )
);
COMMENT ON TABLE core.foreign_investment IS 'FC-GPR (new shares to foreign investor) and FC-TRS (transfer involving non-resident). Xlsx: Foreign Investment sheets.';
COMMENT ON COLUMN core.foreign_investment.type_id            IS 'FC-GPR or FC-TRS from FOREIGN_INVESTMENT_TYPE lookup.';
COMMENT ON COLUMN core.foreign_investment.allotment_id       IS 'Set for FC-GPR; NULL for FC-TRS.';
COMMENT ON COLUMN core.foreign_investment.share_transfer_id  IS 'Set for FC-TRS; NULL for FC-GPR.';

CREATE INDEX IF NOT EXISTS fi_company_idx       ON core.foreign_investment (company_id);
CREATE INDEX IF NOT EXISTS fi_allotment_idx     ON core.foreign_investment (allotment_id);
CREATE INDEX IF NOT EXISTS fi_transfer_idx      ON core.foreign_investment (share_transfer_id);
