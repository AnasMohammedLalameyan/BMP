-- 013_minutes_status_check_form.sql (approved by the user 2026-10-26)
-- Re-states the CHECK added in 012 in the plain "col IN (...)" form that the application's metadata reader
-- turns into dropdown choices. Same allowed values; NULL still passes. Touches only the column added by 012.
ALTER TABLE core.meeting DROP CONSTRAINT IF EXISTS meeting_minutes_status_check;
ALTER TABLE core.meeting ADD CONSTRAINT meeting_minutes_status_check
    CHECK (minutes_status IN ('Not drafted','Draft circulated','Finalised','Signed','Entered in Minutes Book'));
