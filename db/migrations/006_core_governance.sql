-- 006_core_governance.sql
-- Committees, meetings, agenda items, attendance, circular resolutions, postal ballot.

-- ============================================================
-- COMMITTEE
-- Xlsx: "Committees"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.committee (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id        bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    name              text   NOT NULL,
    constituted_on    date,
    dissolved_on      date,
    meeting_frequency text,
    description       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.committee IS 'Board committees (Audit, NRC, SRC, CSR, Risk, etc.) per company. Xlsx: "Committees".';
CREATE INDEX IF NOT EXISTS committee_company_idx ON core.committee (company_id);

-- ============================================================
-- COMMITTEE_MEMBER
-- ============================================================
CREATE TABLE IF NOT EXISTS core.committee_member (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    committee_id     bigint NOT NULL REFERENCES core.committee(id)    ON DELETE RESTRICT,
    directorship_id  bigint NOT NULL REFERENCES core.directorship(id) ON DELETE RESTRICT,
    is_chairperson   boolean NOT NULL DEFAULT false,
    start_date       date    NOT NULL,
    end_date         date,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.committee_member IS 'Members of each committee with period and chairperson flag. Xlsx: "Committees" rows 4-6.';
CREATE INDEX IF NOT EXISTS comm_member_committee_idx    ON core.committee_member (committee_id);
CREATE INDEX IF NOT EXISTS comm_member_directorship_idx ON core.committee_member (directorship_id);

-- ============================================================
-- MEETING
-- Xlsx: "Board Meetings" and "General Meetings (AGM & EGM)" and "Committee Meetings & Attendance"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.meeting (
    id                        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id                bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    meeting_type_id           bigint NOT NULL REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- MEETING_TYPE list
    committee_id              bigint REFERENCES core.committee(id) ON DELETE RESTRICT,  -- NULL for board/general meetings
    financial_year            text   NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    meeting_number            text,                   -- e.g. 'BM-1', 'AGM 1'. Xlsx rows 2.
    meeting_date              date   NOT NULL,
    start_time                time,
    end_time                  time,
    venue                     text,
    venue_mode_id             bigint REFERENCES core.lookup_value(id) ON DELETE RESTRICT, -- MEETING_VENUE_MODE list
    chairperson_directorship_id bigint REFERENCES core.directorship(id) ON DELETE RESTRICT,
    status                    text   NOT NULL DEFAULT 'planned'
                                CHECK (status IN ('planned','held','cancelled')),
    remarks                   text,
    -- General meetings only
    members_entitled          int,                   -- total members entitled to vote. Xlsx row 12.
    members_attended          int,
    due_date                  date,                  -- AGM statutory due date. Xlsx row 3 notes.
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.meeting IS 'One record per meeting (board, committee, AGM, EGM, postal ballot meeting). Xlsx: "Board Meetings", "General Meetings", "Committee Meetings".';
COMMENT ON COLUMN core.meeting.meeting_number IS 'E.g. BM-1, AGM 1. Xlsx row 2.';
COMMENT ON COLUMN core.meeting.due_date       IS 'Statutory due date — e.g. AGM must be held within 6 months of FY end.';

CREATE INDEX IF NOT EXISTS meeting_company_idx   ON core.meeting (company_id);
CREATE INDEX IF NOT EXISTS meeting_date_idx      ON core.meeting (meeting_date);
CREATE INDEX IF NOT EXISTS meeting_type_idx      ON core.meeting (meeting_type_id);
CREATE INDEX IF NOT EXISTS meeting_committee_idx ON core.meeting (committee_id);

-- ============================================================
-- MEETING_AGENDA_ITEM
-- ============================================================
CREATE TABLE IF NOT EXISTS core.meeting_agenda_item (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    meeting_id  bigint NOT NULL REFERENCES core.meeting(id) ON DELETE RESTRICT,
    item_no     int    NOT NULL,
    text        text   NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.meeting_agenda_item IS 'Agenda items for a meeting. Xlsx: "Board Meetings" row 6.';
CREATE INDEX IF NOT EXISTS agenda_meeting_idx ON core.meeting_agenda_item (meeting_id);

-- ============================================================
-- MEETING_ATTENDANCE
-- Xlsx: "Board Meetings" rows 9-11, "Committee Meetings & Attendance"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.meeting_attendance (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    meeting_id       bigint NOT NULL REFERENCES core.meeting(id) ON DELETE RESTRICT,
    attendee_type    text   NOT NULL CHECK (attendee_type IN ('director','member','invitee')),
    directorship_id  bigint REFERENCES core.directorship(id) ON DELETE RESTRICT,  -- for directors
    shareholder_id   bigint REFERENCES core.shareholder(id)  ON DELETE RESTRICT,  -- for members
    attended         boolean NOT NULL DEFAULT false,
    mode             text,   -- physical / VC
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    -- Ensure the right FK is set for the attendee type
    CONSTRAINT attendance_type_fk_check CHECK (
        (attendee_type = 'director'  AND directorship_id IS NOT NULL) OR
        (attendee_type = 'member'    AND shareholder_id  IS NOT NULL) OR
        (attendee_type = 'invitee')
    )
);
COMMENT ON TABLE core.meeting_attendance IS 'Attendance record per meeting per person. Xlsx: "Board Meetings" rows 9-11, "Committee Meetings & Attendance".';
CREATE INDEX IF NOT EXISTS attendance_meeting_idx      ON core.meeting_attendance (meeting_id);
CREATE INDEX IF NOT EXISTS attendance_directorship_idx ON core.meeting_attendance (directorship_id);
CREATE INDEX IF NOT EXISTS attendance_shareholder_idx  ON core.meeting_attendance (shareholder_id);

-- ============================================================
-- CIRCULAR_RESOLUTION
-- Xlsx: "Circular Resolutions"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.circular_resolution (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id           bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    reference            text,
    circulated_on        date   NOT NULL,
    subject              text   NOT NULL,
    text                 text,
    passed_on            date,
    noted_in_meeting_id  bigint REFERENCES core.meeting(id) ON DELETE RESTRICT,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.circular_resolution IS 'Resolutions passed by circulation under Sec 175. Xlsx: "Circular Resolutions".';
CREATE INDEX IF NOT EXISTS circ_res_company_idx ON core.circular_resolution (company_id);

-- ============================================================
-- CIRCULAR_RESOLUTION_RESPONSE
-- Xlsx: "Circular Resolutions" rows 4-5
-- ============================================================
CREATE TABLE IF NOT EXISTS core.circular_resolution_response (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resolution_id   bigint NOT NULL REFERENCES core.circular_resolution(id) ON DELETE RESTRICT,
    directorship_id bigint NOT NULL REFERENCES core.directorship(id) ON DELETE RESTRICT,
    response        text   CHECK (response IN ('assented','dissented','no_response')),
    responded_on    date,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.circular_resolution_response IS 'Each director''s response to a circular resolution. Xlsx: "Circular Resolutions" rows 4-5.';
CREATE INDEX IF NOT EXISTS circ_resp_resolution_idx   ON core.circular_resolution_response (resolution_id);
CREATE INDEX IF NOT EXISTS circ_resp_directorship_idx ON core.circular_resolution_response (directorship_id);

-- ============================================================
-- POSTAL_BALLOT
-- Xlsx: "Postal Ballot"
-- ============================================================
CREATE TABLE IF NOT EXISTS core.postal_ballot (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id            bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    particulars           text   NOT NULL,
    reason                text,
    notice_date           date,
    voting_opens          date,
    voting_closes         date,
    scrutinizer           text,
    votes_for             bigint,
    votes_against         bigint,
    votes_invalid         bigint,
    passed                boolean,
    result_declared_date  date,
    result_filed_date     date,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE core.postal_ballot IS 'Postal ballot records. Xlsx: "Postal Ballot".';
CREATE INDEX IF NOT EXISTS postal_ballot_company_idx ON core.postal_ballot (company_id);

-- ============================================================
-- Add deferred FKs from earlier migrations that reference core.meeting
-- ============================================================
ALTER TABLE core.allotment
    ADD CONSTRAINT allotment_board_meeting_fk
    FOREIGN KEY (board_meeting_id) REFERENCES core.meeting(id) ON DELETE RESTRICT;

ALTER TABLE core.share_transfer
    ADD CONSTRAINT share_transfer_board_meeting_fk
    FOREIGN KEY (board_meeting_id) REFERENCES core.meeting(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS allotment_board_meeting_idx     ON core.allotment (board_meeting_id);
CREATE INDEX IF NOT EXISTS share_transfer_board_meeting_idx ON core.share_transfer (board_meeting_id);
