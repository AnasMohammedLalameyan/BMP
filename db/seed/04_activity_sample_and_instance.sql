-- db/seed/04_activity_sample_and_instance.sql
-- Seeds the BOARD_MEETING activity template, steps, dependencies, bindings,
-- evidence requirements, and creates one ops.activity_instance with steps 1-4
-- completed, step 5 in progress, task_record_link rows, and an evidence_link.

-- ============================================================
-- BOOTSTRAP: Set session user to seed system user
-- ============================================================
DO $$
DECLARE v_seed_user bigint;
BEGIN
    SELECT id INTO v_seed_user FROM core.app_user WHERE email = 'seed@system.internal';
    IF v_seed_user IS NOT NULL THEN
        PERFORM set_config('app.current_user_id', v_seed_user::text, false);
    END IF;
END $$;

-- ============================================================
-- ACTIVITY TEMPLATE: BOARD_MEETING v1
-- Durations are reasonable defaults from Companies Act 2013 (s.173)
-- and Secretarial Standard SS-1.
-- NOTE: Marked as "to be verified by a BMP professional".
-- ============================================================
INSERT INTO activity.activity_template (
    code,
    version,
    name,
    obligation_ref,
    description,
    input_schema,
    status,
    effective_from,
    reviewed_by,
    reviewed_on
)
VALUES (
    'BOARD_MEETING',
    1,
    'Board of Directors Meeting',
    'Companies Act 2013, Sec 173 & Secretarial Standard-1 (SS-1)',
    'Statutory workflow for convening, conducting, and minuting a Board of Directors meeting. Step durations are defaults to be verified by a BMP professional.',
    '{
        "type": "object",
        "required": ["meeting_date", "start_time", "venue", "venue_mode", "agenda_items"],
        "properties": {
            "meeting_date": {"type": "string", "format": "date", "description": "Scheduled date of board meeting"},
            "start_time": {"type": "string", "description": "Start time e.g. 11:00 AM"},
            "venue": {"type": "string", "description": "Meeting venue address or online conferencing details"},
            "venue_mode": {"type": "string", "description": "PHYSICAL, VC, or HYBRID"},
            "agenda_items": {"type": "array", "items": {"type": "string"}, "description": "List of agenda items"}
        }
    }'::jsonb,
    'draft',
    '2024-04-01',
    NULL,
    NULL
)
ON CONFLICT (code, version) DO NOTHING;

-- ============================================================
-- STEP TEMPLATES (9 steps in linear chain)
-- ============================================================
DO $$
DECLARE
    v_tmpl_id bigint;
BEGIN
    SELECT id INTO v_tmpl_id FROM activity.activity_template WHERE code = 'BOARD_MEETING' AND version = 1;

    -- Step 1: CONFIRM_DATE_VENUE
    INSERT INTO activity.step_template (
        template_id, step_key, seq, title, step_type, instructions,
        responsible_role, is_mandatory, deadline_anchor, deadline_offset_days,
        deadline_direction, ai_assisted, requires_confirmation
    ) VALUES (
        v_tmpl_id, 'CONFIRM_DATE_VENUE', 1, 'Confirm Date and Venue', 'data_entry',
        'Ascertain availability of directors and finalize meeting date, start time, venue, and attendance mode.',
        'Company Secretary', true, NULL, NULL, NULL, false, false
    ) ON CONFLICT (template_id, step_key) DO NOTHING;

    -- Step 2: PREPARE_AGENDA
    INSERT INTO activity.step_template (
        template_id, step_key, seq, title, step_type, instructions,
        responsible_role, is_mandatory, deadline_anchor, deadline_offset_days,
        deadline_direction, ai_assisted, requires_confirmation
    ) VALUES (
        v_tmpl_id, 'PREPARE_AGENDA', 2, 'Prepare Agenda Items', 'document',
        'Review previous meeting action items and draft numbered agenda items with explanatory notes.',
        'Company Secretary', true, NULL, NULL, NULL, false, false
    ) ON CONFLICT (template_id, step_key) DO NOTHING;

    -- Step 3: DRAFT_NOTICE
    INSERT INTO activity.step_template (
        template_id, step_key, seq, title, step_type, instructions,
        responsible_role, is_mandatory, deadline_anchor, deadline_offset_days,
        deadline_direction, ai_assisted, requires_confirmation
    ) VALUES (
        v_tmpl_id, 'DRAFT_NOTICE', 3, 'Draft Notice of Board Meeting', 'document',
        'Draft formal notice including date, time, venue, VC facility details, and full agenda notes.',
        'Company Secretary', true, 'meeting_date', 7, 'before', false, false
    ) ON CONFLICT (template_id, step_key) DO NOTHING;

    -- Step 4: SEND_NOTICE
    INSERT INTO activity.step_template (
        template_id, step_key, seq, title, step_type, instructions,
        responsible_role, is_mandatory, deadline_anchor, deadline_offset_days,
        deadline_direction, ai_assisted, requires_confirmation
    ) VALUES (
        v_tmpl_id, 'SEND_NOTICE', 4, 'Send Notice to Directors', 'notification',
        'Issue notice and agenda to all directors at registered email addresses at least 7 days before meeting.',
        'Company Secretary', true, 'meeting_date', 7, 'before', true, true
    ) ON CONFLICT (template_id, step_key) DO NOTHING;

    -- Step 5: CONDUCT_MEETING
    INSERT INTO activity.step_template (
        template_id, step_key, seq, title, step_type, instructions,
        responsible_role, is_mandatory, deadline_anchor, deadline_offset_days,
        deadline_direction, ai_assisted, requires_confirmation
    ) VALUES (
        v_tmpl_id, 'CONDUCT_MEETING', 5, 'Conduct Board Meeting', 'manual',
        'Check quorum per Sec 174 (1/3rd or 2 directors), elect Chairman if needed, and conduct business.',
        'Board of Directors', true, 'meeting_date', 0, 'before', false, false
    ) ON CONFLICT (template_id, step_key) DO NOTHING;

    -- Step 6: RECORD_ATTENDANCE
    INSERT INTO activity.step_template (
        template_id, step_key, seq, title, step_type, instructions,
        responsible_role, is_mandatory, deadline_anchor, deadline_offset_days,
        deadline_direction, ai_assisted, requires_confirmation
    ) VALUES (
        v_tmpl_id, 'RECORD_ATTENDANCE', 6, 'Record Attendance', 'data_entry',
        'Record presence of each director, invitee, and officer with mode of attendance (Physical/VC).',
        'Company Secretary', true, 'meeting_date', 0, 'after', false, false
    ) ON CONFLICT (template_id, step_key) DO NOTHING;

    -- Step 7: DRAFT_MINUTES
    INSERT INTO activity.step_template (
        template_id, step_key, seq, title, step_type, instructions,
        responsible_role, is_mandatory, deadline_anchor, deadline_offset_days,
        deadline_direction, ai_assisted, requires_confirmation
    ) VALUES (
        v_tmpl_id, 'DRAFT_MINUTES', 7, 'Draft Minutes of Meeting', 'document',
        'Circulate draft minutes to all directors within 15 days of the meeting for comments (SS-1 cl. 7.4).',
        'Company Secretary', true, 'meeting_date', 15, 'after', false, false
    ) ON CONFLICT (template_id, step_key) DO NOTHING;

    -- Step 8: SIGN_MINUTES
    INSERT INTO activity.step_template (
        template_id, step_key, seq, title, step_type, instructions,
        responsible_role, is_mandatory, deadline_anchor, deadline_offset_days,
        deadline_direction, ai_assisted, requires_confirmation
    ) VALUES (
        v_tmpl_id, 'SIGN_MINUTES', 8, 'Sign Minutes of Meeting', 'approval',
        'Chairman signs entered minutes in the minute book within 30 days of the meeting (SS-1 cl. 7.5).',
        'Chairman', true, 'meeting_date', 30, 'after', false, true
    ) ON CONFLICT (template_id, step_key) DO NOTHING;

    -- Step 9: UPDATE_REGISTERS_AND_FILINGS
    INSERT INTO activity.step_template (
        template_id, step_key, seq, title, step_type, instructions,
        responsible_role, is_mandatory, deadline_anchor, deadline_offset_days,
        deadline_direction, ai_assisted, requires_confirmation
    ) VALUES (
        v_tmpl_id, 'UPDATE_REGISTERS_AND_FILINGS', 9, 'Update Registers and Filings', 'check',
        'Update statutory registers and determine if any ROC e-forms (MGT-14, DIR-12) are required.',
        'Company Secretary', true, NULL, NULL, NULL, false, false
    ) ON CONFLICT (template_id, step_key) DO NOTHING;

END $$;

-- ============================================================
-- STEP DEPENDENCIES: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9
-- ============================================================
DO $$
DECLARE
    v_tmpl_id bigint;
    v_s1 bigint; v_s2 bigint; v_s3 bigint; v_s4 bigint;
    v_s5 bigint; v_s6 bigint; v_s7 bigint; v_s8 bigint; v_s9 bigint;
BEGIN
    SELECT id INTO v_tmpl_id FROM activity.activity_template WHERE code = 'BOARD_MEETING' AND version = 1;

    SELECT id INTO v_s1 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 1;
    SELECT id INTO v_s2 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 2;
    SELECT id INTO v_s3 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 3;
    SELECT id INTO v_s4 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 4;
    SELECT id INTO v_s5 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 5;
    SELECT id INTO v_s6 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 6;
    SELECT id INTO v_s7 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 7;
    SELECT id INTO v_s8 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 8;
    SELECT id INTO v_s9 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 9;

    INSERT INTO activity.step_dependency (step_id, depends_on_step_id) VALUES
        (v_s2, v_s1),
        (v_s3, v_s2),
        (v_s4, v_s3),
        (v_s5, v_s4),
        (v_s6, v_s5),
        (v_s7, v_s6),
        (v_s8, v_s7),
        (v_s9, v_s8)
    ON CONFLICT (step_id, depends_on_step_id) DO NOTHING;
END $$;

-- ============================================================
-- STEP DATA BINDINGS
-- ============================================================
DO $$
DECLARE
    v_tmpl_id bigint;
    v_s1 bigint; v_s2 bigint; v_s3 bigint; v_s4 bigint;
    v_s5 bigint; v_s6 bigint; v_s7 bigint; v_s8 bigint; v_s9 bigint;
    v_fld_id bigint;
BEGIN
    SELECT id INTO v_tmpl_id FROM activity.activity_template WHERE code = 'BOARD_MEETING' AND version = 1;

    SELECT id INTO v_s1 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 1;
    SELECT id INTO v_s2 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 2;
    SELECT id INTO v_s3 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 3;
    SELECT id INTO v_s4 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 4;
    SELECT id INTO v_s5 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 5;
    SELECT id INTO v_s6 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 6;
    SELECT id INTO v_s7 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 7;
    SELECT id INTO v_s8 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 8;
    SELECT id INTO v_s9 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 9;

    -- Step 1 writes meeting.meeting_date, venue, venue_mode_id, start_time
    FOR v_fld_id IN SELECT id FROM activity.entity_field_registry
        WHERE table_name = 'core.meeting' AND column_name IN ('meeting_date','venue','venue_mode_id','start_time')
    LOOP
        INSERT INTO activity.step_data_binding (step_id, field_id, mode, note)
        VALUES (v_s1, v_fld_id, 'write', 'Records meeting schedule details')
        ON CONFLICT DO NOTHING;
    END LOOP;

    -- Step 2 reads previous meeting, writes meeting_agenda_item
    FOR v_fld_id IN SELECT id FROM activity.entity_field_registry
        WHERE table_name = 'core.meeting' AND column_name = 'meeting_number'
    LOOP
        INSERT INTO activity.step_data_binding (step_id, field_id, mode, note)
        VALUES (v_s2, v_fld_id, 'read', 'Reads previous meeting reference')
        ON CONFLICT DO NOTHING;
    END LOOP;

    FOR v_fld_id IN SELECT id FROM activity.entity_field_registry
        WHERE table_name = 'core.meeting_agenda_item' AND column_name IN ('item_no','text')
    LOOP
        INSERT INTO activity.step_data_binding (step_id, field_id, mode, note)
        VALUES (v_s2, v_fld_id, 'write', 'Writes drafted agenda items')
        ON CONFLICT DO NOTHING;
    END LOOP;

    -- Step 3 reads company.name, directorship.id, meeting.meeting_date
    FOR v_fld_id IN SELECT id FROM activity.entity_field_registry
        WHERE (table_name = 'core.company' AND column_name = 'name')
           OR (table_name = 'core.directorship' AND column_name = 'id')
           OR (table_name = 'core.meeting' AND column_name = 'meeting_date')
    LOOP
        INSERT INTO activity.step_data_binding (step_id, field_id, mode, note)
        VALUES (v_s3, v_fld_id, 'read', 'Reads company, active directors, and date for notice')
        ON CONFLICT DO NOTHING;
    END LOOP;

    -- Step 4 reads director.email
    FOR v_fld_id IN SELECT id FROM activity.entity_field_registry
        WHERE table_name = 'core.director' AND column_name = 'email'
    LOOP
        INSERT INTO activity.step_data_binding (step_id, field_id, mode, note)
        VALUES (v_s4, v_fld_id, 'read', 'Reads director registered email for dispatch')
        ON CONFLICT DO NOTHING;
    END LOOP;

    -- Step 5 writes meeting.status
    FOR v_fld_id IN SELECT id FROM activity.entity_field_registry
        WHERE table_name = 'core.meeting' AND column_name = 'status'
    LOOP
        INSERT INTO activity.step_data_binding (step_id, field_id, mode, note)
        VALUES (v_s5, v_fld_id, 'write', 'Updates meeting status from planned to held')
        ON CONFLICT DO NOTHING;
    END LOOP;

    -- Step 6 writes meeting_attendance
    FOR v_fld_id IN SELECT id FROM activity.entity_field_registry
        WHERE table_name = 'core.meeting_attendance' AND column_name IN ('directorship_id','attended','mode')
    LOOP
        INSERT INTO activity.step_data_binding (step_id, field_id, mode, note)
        VALUES (v_s6, v_fld_id, 'write', 'Records director attendance and attendance mode')
        ON CONFLICT DO NOTHING;
    END LOOP;

    -- Step 7 reads agenda, attendance
    FOR v_fld_id IN SELECT id FROM activity.entity_field_registry
        WHERE (table_name = 'core.meeting_agenda_item' AND column_name = 'text')
           OR (table_name = 'core.meeting_attendance' AND column_name = 'attended')
    LOOP
        INSERT INTO activity.step_data_binding (step_id, field_id, mode, note)
        VALUES (v_s7, v_fld_id, 'read', 'Reads agenda discussions and attendance records for minutes')
        ON CONFLICT DO NOTHING;
    END LOOP;

    -- Step 8 reads meeting.id
    FOR v_fld_id IN SELECT id FROM activity.entity_field_registry
        WHERE table_name = 'core.meeting' AND column_name = 'id'
    LOOP
        INSERT INTO activity.step_data_binding (step_id, field_id, mode, note)
        VALUES (v_s8, v_fld_id, 'read', 'Links signed minutes to meeting record')
        ON CONFLICT DO NOTHING;
    END LOOP;

    -- Step 9 reads/writes government_filing
    FOR v_fld_id IN SELECT id FROM activity.entity_field_registry
        WHERE table_name = 'core.government_filing' AND column_name IN ('form_name','status_id')
    LOOP
        INSERT INTO activity.step_data_binding (step_id, field_id, mode, note)
        VALUES (v_s9, v_fld_id, 'write', 'Creates or updates ROC filings resulting from board resolutions')
        ON CONFLICT DO NOTHING;
    END LOOP;

END $$;

-- ============================================================
-- STEP EVIDENCE REQUIREMENTS
-- ============================================================
DO $$
DECLARE
    v_tmpl_id bigint;
    v_s3 bigint; v_s7 bigint; v_s8 bigint;
    v_doc_notice bigint; v_doc_agenda bigint;
    v_doc_draft_min bigint; v_doc_signed_min bigint;
BEGIN
    SELECT id INTO v_tmpl_id FROM activity.activity_template WHERE code = 'BOARD_MEETING' AND version = 1;

    SELECT id INTO v_s3 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 3;
    SELECT id INTO v_s7 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 7;
    SELECT id INTO v_s8 FROM activity.step_template WHERE template_id = v_tmpl_id AND seq = 8;

    SELECT id INTO v_doc_notice     FROM core.document_type WHERE code = 'BOARD_NOTICE';
    SELECT id INTO v_doc_agenda     FROM core.document_type WHERE code = 'BOARD_AGENDA';
    SELECT id INTO v_doc_draft_min  FROM core.document_type WHERE code = 'BOARD_MINUTES';
    SELECT id INTO v_doc_signed_min FROM core.document_type WHERE code = 'BOARD_MINUTES_SIGNED';

    -- Step 3 requires Notice and Agenda
    IF v_doc_notice IS NOT NULL THEN
        INSERT INTO activity.step_evidence_requirement (step_id, document_type_id, is_mandatory, condition_note)
        VALUES (v_s3, v_doc_notice, true, 'Signed or issued Notice of Board Meeting')
        ON CONFLICT DO NOTHING;
    END IF;

    IF v_doc_agenda IS NOT NULL THEN
        INSERT INTO activity.step_evidence_requirement (step_id, document_type_id, is_mandatory, condition_note)
        VALUES (v_s3, v_doc_agenda, true, 'Detailed agenda notes circulated with notice')
        ON CONFLICT DO NOTHING;
    END IF;

    -- Step 7 requires Draft Minutes
    IF v_doc_draft_min IS NOT NULL THEN
        INSERT INTO activity.step_evidence_requirement (step_id, document_type_id, is_mandatory, condition_note)
        VALUES (v_s7, v_doc_draft_min, true, 'Circulated draft minutes for director review')
        ON CONFLICT DO NOTHING;
    END IF;

    -- Step 8 requires Signed Minutes
    IF v_doc_signed_min IS NOT NULL THEN
        INSERT INTO activity.step_evidence_requirement (step_id, document_type_id, is_mandatory, condition_note)
        VALUES (v_s8, v_doc_signed_min, true, 'Final minutes entered in minute book and signed by Chairman')
        ON CONFLICT DO NOTHING;
    END IF;

END $$;

-- ============================================================
-- SEED ONE OPS.ACTIVITY_INSTANCE:
-- Board Meeting for Nexatech Solutions Private Limited (Company 1)
-- Instantiate via ops.instantiate_activity()
-- Steps 1-4 completed, Step 5 in progress, Steps 6-9 not started.
-- Linked records and evidence attached.
-- ============================================================
DO $$
DECLARE
    v_c1 bigint;
    v_admin_user bigint;
    v_seed_user bigint;
    v_inst_id bigint;
    v_tmpl_id bigint;
    v_step_id bigint;
    v_task_id bigint;
    v_t1 bigint; v_t2 bigint; v_t3 bigint; v_t4 bigint; v_t5 bigint;
    v_board_type bigint;
    v_physical bigint;
    v_dst_arjun bigint;
    v_dst_sunita bigint;
    v_dst_prashant bigint;
    v_meeting_id bigint;
    v_agenda_item_id bigint;
    v_doc_type_notice bigint;
    v_doc_id bigint;
    v_params jsonb := '{
        "meeting_date": "2025-04-15",
        "start_time": "11:00",
        "venue": "14, Connaught Place, New Delhi - 110001",
        "venue_mode": "PHYSICAL",
        "agenda_items": [
            "To grant leave of absence, if any",
            "To confirm minutes of previous meeting held on 2025-01-16",
            "To consider and approve audited financial statements for FY 2024-25",
            "To review statutory compliance status",
            "Any other business with permission of Chair"
        ]
    }'::jsonb;
BEGIN
    SELECT id INTO v_c1 FROM core.company WHERE cin = 'U72200DL2015PTC112001';
    SELECT id INTO v_admin_user FROM core.app_user WHERE email = 'admin@bmpco.in';
    SELECT id INTO v_seed_user  FROM core.app_user WHERE email = 'seed@system.internal';
    SELECT id INTO v_tmpl_id    FROM activity.activity_template WHERE code = 'BOARD_MEETING' AND version = 1;

    SELECT lv.id INTO v_board_type FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='MEETING_TYPE' AND lv.code='BOARD';
    SELECT lv.id INTO v_physical   FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id=lv.list_id WHERE ll.code='MEETING_VENUE_MODE' AND lv.code='PHYSICAL';

    SELECT id INTO v_dst_arjun    FROM core.directorship WHERE company_id=v_c1 AND director_id=(SELECT id FROM core.director WHERE din='12340001') AND end_date IS NULL;
    SELECT id INTO v_dst_sunita   FROM core.directorship WHERE company_id=v_c1 AND director_id=(SELECT id FROM core.director WHERE din='12340002') AND end_date IS NULL;
    SELECT id INTO v_dst_prashant FROM core.directorship WHERE company_id=v_c1 AND director_id=(SELECT id FROM core.director WHERE din='12340012') AND end_date IS NULL;

    SELECT id INTO v_doc_type_notice FROM core.document_type WHERE code = 'BOARD_NOTICE';

    -- Check if instance already exists
    SELECT id INTO v_inst_id FROM ops.activity_instance WHERE company_id = v_c1 AND template_id = v_tmpl_id;

    IF v_inst_id IS NULL THEN
        -- Instantiate via deterministic stored procedure
        v_inst_id := ops.instantiate_activity('BOARD_MEETING', v_c1, v_params, v_admin_user);
    END IF;

    -- Create or link the corresponding core.meeting record for Nexatech
    INSERT INTO core.meeting (
        company_id, meeting_type_id, financial_year, meeting_number,
        meeting_date, start_time, end_time, venue, venue_mode_id, status,
        chairperson_directorship_id
    )
    VALUES (
        v_c1, v_board_type, '2025-26', 'BM/2025-26/01',
        '2025-04-15', '11:00', '13:00',
        '14, Connaught Place, New Delhi - 110001', v_physical, 'planned',
        v_dst_arjun
    )
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_meeting_id FROM core.meeting WHERE company_id = v_c1 AND meeting_number = 'BM/2025-26/01';

    -- Seed agenda item
    INSERT INTO core.meeting_agenda_item (meeting_id, item_no, text)
    VALUES
        (v_meeting_id, 1, 'To grant leave of absence, if any'),
        (v_meeting_id, 2, 'To confirm minutes of previous meeting held on 2025-01-16'),
        (v_meeting_id, 3, 'To consider and approve audited financial statements for FY 2024-25'),
        (v_meeting_id, 4, 'To review statutory compliance status'),
        (v_meeting_id, 5, 'Any other business with permission of Chair')
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_agenda_item_id FROM core.meeting_agenda_item WHERE meeting_id = v_meeting_id AND item_no = 1;

    -- Fetch task IDs for this instance
    SELECT t.id INTO v_t1 FROM ops.task_instance t JOIN activity.step_template s ON s.id=t.step_id WHERE t.instance_id=v_inst_id AND s.seq=1;
    SELECT t.id INTO v_t2 FROM ops.task_instance t JOIN activity.step_template s ON s.id=t.step_id WHERE t.instance_id=v_inst_id AND s.seq=2;
    SELECT t.id INTO v_t3 FROM ops.task_instance t JOIN activity.step_template s ON s.id=t.step_id WHERE t.instance_id=v_inst_id AND s.seq=3;
    SELECT t.id INTO v_t4 FROM ops.task_instance t JOIN activity.step_template s ON s.id=t.step_id WHERE t.instance_id=v_inst_id AND s.seq=4;
    SELECT t.id INTO v_t5 FROM ops.task_instance t JOIN activity.step_template s ON s.id=t.step_id WHERE t.instance_id=v_inst_id AND s.seq=5;

    -- Update tasks 1-4 to completed, task 5 to in_progress
    UPDATE ops.task_instance
    SET status = 'completed',
        completed_by = v_admin_user,
        completed_at = '2025-04-01 10:30:00+00',
        notes = 'Meeting date, time and Connaught Place venue finalized with Chairman'
    WHERE id = v_t1;

    UPDATE ops.task_instance
    SET status = 'completed',
        completed_by = v_admin_user,
        completed_at = '2025-04-03 15:00:00+00',
        notes = '5 agenda items prepared and approved by Managing Director'
    WHERE id = v_t2;

    UPDATE ops.task_instance
    SET status = 'completed',
        completed_by = v_admin_user,
        completed_at = '2025-04-07 17:00:00+00',
        notes = 'Draft notice prepared with agenda notes per SS-1'
    WHERE id = v_t3;

    UPDATE ops.task_instance
    SET status = 'completed',
        completed_by = v_admin_user,
        completed_at = '2025-04-08 10:00:00+00',
        notes = 'Notice dispatched electronically to all 3 directors (7 days prior notice compliance verified)'
    WHERE id = v_t4;

    UPDATE ops.task_instance
    SET status = 'in_progress',
        notes = 'Board meeting is scheduled for 2025-04-15; meeting currently in session'
    WHERE id = v_t5;

    -- ============================================================
    -- OPS.TASK_RECORD_LINK: Association back to core User Database records
    -- ============================================================
    -- Task 1 links to core.meeting
    INSERT INTO ops.task_record_link (task_instance_id, entity_type, entity_id, mode)
    VALUES (v_t1, 'meeting', v_meeting_id, 'write')
    ON CONFLICT DO NOTHING;

    -- Task 2 links to core.meeting_agenda_item
    INSERT INTO ops.task_record_link (task_instance_id, entity_type, entity_id, mode)
    VALUES (v_t2, 'meeting_agenda_item', v_agenda_item_id, 'write')
    ON CONFLICT DO NOTHING;

    -- Task 3 links to core.meeting (read)
    INSERT INTO ops.task_record_link (task_instance_id, entity_type, entity_id, mode)
    VALUES (v_t3, 'meeting', v_meeting_id, 'read')
    ON CONFLICT DO NOTHING;

    -- Task 4 links to directors who received notice
    IF v_dst_arjun IS NOT NULL THEN
        INSERT INTO ops.task_record_link (task_instance_id, entity_type, entity_id, mode)
        VALUES (v_t4, 'directorship', v_dst_arjun, 'read')
        ON CONFLICT DO NOTHING;
    END IF;
    IF v_dst_sunita IS NOT NULL THEN
        INSERT INTO ops.task_record_link (task_instance_id, entity_type, entity_id, mode)
        VALUES (v_t4, 'directorship', v_dst_sunita, 'read')
        ON CONFLICT DO NOTHING;
    END IF;
    IF v_dst_prashant IS NOT NULL THEN
        INSERT INTO ops.task_record_link (task_instance_id, entity_type, entity_id, mode)
        VALUES (v_t4, 'directorship', v_dst_prashant, 'read')
        ON CONFLICT DO NOTHING;
    END IF;

    -- ============================================================
    -- CORE.DOCUMENT & CORE.EVIDENCE_LINK
    -- Durable link from a document to an ops task (FR-3)
    -- ============================================================
    INSERT INTO core.document (
        company_id, document_type_id, filename, storage_path,
        mime_type, sha256, version, uploaded_by, extracted_data
    )
    VALUES (
        v_c1,
        v_doc_type_notice,
        'Nexatech_BM_Notice_2025_04_15.pdf',
        '/storage/nexatech/governance/BM_Notice_2025_04_15.pdf',
        'application/pdf',
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        1,
        v_admin_user,
        '{"pages": 3, "notice_date": "2025-04-08", "meeting_date": "2025-04-15"}'::jsonb
    )
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_doc_id FROM core.document WHERE company_id = v_c1 AND filename = 'Nexatech_BM_Notice_2025_04_15.pdf';

    IF v_doc_id IS NOT NULL AND v_t3 IS NOT NULL THEN
        INSERT INTO core.evidence_link (document_id, entity_type, entity_id, task_instance_id, note)
        VALUES (
            v_doc_id,
            'meeting',
            v_meeting_id,
            v_t3,
            'Durable statutory evidence: Board Meeting Notice & Agenda circulated to directors per SS-1'
        )
        ON CONFLICT DO NOTHING;
    END IF;

END $$;
