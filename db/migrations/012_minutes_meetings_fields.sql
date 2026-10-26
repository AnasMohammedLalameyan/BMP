-- 012_minutes_meetings_fields.sql   (approved by the user 2026-10-26)
-- Additive only: nullable columns on core.meeting and core.meeting_agenda_item for the Minutes & Meetings
-- dashboard. No existing column, constraint, trigger, view or policy is altered. Existing audit and RLS
-- triggers on both tables cover the new columns automatically.
-- Applied through scripts/setup_db.py run_migrations().

ALTER TABLE core.meeting
    ADD COLUMN IF NOT EXISTS notice_date          date,
    ADD COLUMN IF NOT EXISTS chairperson_name     text,
    ADD COLUMN IF NOT EXISTS invitees_present     text,
    ADD COLUMN IF NOT EXISTS leave_of_absence     text,
    ADD COLUMN IF NOT EXISTS attendance_present   int CHECK (attendance_present IS NULL OR attendance_present >= 0),
    ADD COLUMN IF NOT EXISTS attendance_total     int CHECK (attendance_total   IS NULL OR attendance_total   >= 0),
    ADD COLUMN IF NOT EXISTS attendance_sheet     text,
    ADD COLUMN IF NOT EXISTS minutes_status       text
        CHECK (minutes_status IS NULL OR minutes_status IN
               ('Not drafted','Draft circulated','Finalised','Signed','Entered in Minutes Book')),
    ADD COLUMN IF NOT EXISTS draft_circulated_on  date,
    ADD COLUMN IF NOT EXISTS signed_circulated_on date,
    ADD COLUMN IF NOT EXISTS entry_date           date,
    ADD COLUMN IF NOT EXISTS signing_date         date,
    ADD COLUMN IF NOT EXISTS signing_place        text,
    ADD COLUMN IF NOT EXISTS signed_documents     text;

COMMENT ON COLUMN core.meeting.notice_date          IS 'Date the notice of the meeting was issued (not the AGM statutory due_date).';
COMMENT ON COLUMN core.meeting.chairperson_name     IS 'Chairman as written in the minutes; chairperson_directorship_id is set only when the name matches a director.';
COMMENT ON COLUMN core.meeting.invitees_present     IS 'Names of invitees present (comma separated).';
COMMENT ON COLUMN core.meeting.leave_of_absence     IS 'Leave of absence as recorded in the minutes.';
COMMENT ON COLUMN core.meeting.attendance_present   IS 'Present count as typed; the tick count in meeting_attendance is preferred for checks.';
COMMENT ON COLUMN core.meeting.attendance_total     IS 'Board size / total members on the day, as typed.';
COMMENT ON COLUMN core.meeting.minutes_status       IS 'Lifecycle of the minutes document. meeting.status (planned/held/cancelled) is a different concept.';
COMMENT ON COLUMN core.meeting.draft_circulated_on  IS 'SS-1: draft minutes circulated within 15 days.';
COMMENT ON COLUMN core.meeting.signing_date         IS 'SS-1: minutes signed within 30 days of the meeting.';

ALTER TABLE core.meeting_agenda_item
    ADD COLUMN IF NOT EXISTS reg30        text NOT NULL DEFAULT 'NA' CHECK (reg30 IN ('NA','Yes','No')),
    ADD COLUMN IF NOT EXISTS forms        text,
    ADD COLUMN IF NOT EXISTS docs         text,
    ADD COLUMN IF NOT EXISTS bmp_comments text;

COMMENT ON COLUMN core.meeting_agenda_item.reg30        IS 'SEBI LODR Reg 30 material-event flag (NA/Yes/No).';
COMMENT ON COLUMN core.meeting_agenda_item.forms        IS 'ROC forms to be filed for this item, comma separated (e.g. MGT-14, DIR-12).';
COMMENT ON COLUMN core.meeting_agenda_item.docs         IS 'Supporting documents to be checked, comma separated (not ROC filings).';
COMMENT ON COLUMN core.meeting_agenda_item.bmp_comments IS 'Reviewer comment on this item.';
