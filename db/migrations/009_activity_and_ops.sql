-- 009_activity_and_ops.sql
-- Activity schema (templates, steps, bindings) and ops schema (instances, tasks, confirmations).

-- ============================================================
-- ENTITY_FIELD_REGISTRY
-- Populated automatically from information_schema for all core tables.
-- ============================================================
CREATE TABLE IF NOT EXISTS activity.entity_field_registry (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name    text   NOT NULL,   -- schema-qualified, e.g. 'core.meeting'
    column_name   text   NOT NULL,
    description   text,
    is_calculated boolean NOT NULL DEFAULT false,
    UNIQUE (table_name, column_name)
);
COMMENT ON TABLE activity.entity_field_registry IS 'Registry of all core table columns. Populated from information_schema. Steps may only bind to registered fields.';
COMMENT ON COLUMN activity.entity_field_registry.is_calculated IS 'True for generated columns and view-derived values. step_data_binding rejects write on these.';

-- Populate from information_schema (core tables, mark generated columns)
INSERT INTO activity.entity_field_registry (table_name, column_name, description, is_calculated)
SELECT
    'core.' || c.table_name,
    c.column_name,
    NULL,
    (c.is_generated = 'ALWAYS')
FROM information_schema.columns c
WHERE c.table_schema = 'core'
  AND c.table_name NOT IN ('lookup_list','lookup_value') -- too generic
ON CONFLICT (table_name, column_name) DO NOTHING;

-- ============================================================
-- ACTIVITY_TEMPLATE
-- ============================================================
CREATE TABLE IF NOT EXISTS activity.activity_template (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code           text   NOT NULL,
    version        int    NOT NULL DEFAULT 1,
    name           text   NOT NULL,
    obligation_ref text,
    description    text,
    input_schema   jsonb,
    status         text   NOT NULL DEFAULT 'draft'
                       CHECK (status IN ('draft','active','retired')),
    effective_from date,
    reviewed_by    bigint REFERENCES core.app_user(id) ON DELETE RESTRICT,
    reviewed_on    date,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    UNIQUE (code, version)
);
COMMENT ON TABLE activity.activity_template IS 'Definition of a compliance activity (e.g. BOARD_MEETING). Versioned. Seeded with BOARD_MEETING v1.';
CREATE INDEX IF NOT EXISTS template_code_idx ON activity.activity_template (code);

-- ============================================================
-- STEP_TEMPLATE
-- ============================================================
CREATE TABLE IF NOT EXISTS activity.step_template (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    template_id          bigint NOT NULL REFERENCES activity.activity_template(id) ON DELETE RESTRICT,
    step_key             text   NOT NULL,
    seq                  int    NOT NULL,
    title                text   NOT NULL,
    step_type            text   NOT NULL CHECK (step_type IN (
                             'data_entry','document','notification','approval','check','filing','manual'
                         )),
    instructions         text,
    responsible_role     text,
    is_mandatory         boolean NOT NULL DEFAULT true,
    -- Deadline fields: all null or all set
    deadline_anchor      text,         -- e.g. 'meeting_date'
    deadline_offset_days int,
    deadline_direction   text CHECK (deadline_direction IN ('before','after')),
    ai_assisted          boolean NOT NULL DEFAULT false,
    requires_confirmation boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint,
    UNIQUE (template_id, step_key),
    UNIQUE (template_id, seq),
    CONSTRAINT deadline_all_or_none CHECK (
        (deadline_anchor IS NULL AND deadline_offset_days IS NULL AND deadline_direction IS NULL)
        OR (deadline_anchor IS NOT NULL AND deadline_offset_days IS NOT NULL AND deadline_direction IS NOT NULL)
    )
);
COMMENT ON TABLE activity.step_template IS 'Steps within an activity template. Each step has a type, deadline config and bindings.';
CREATE INDEX IF NOT EXISTS step_template_template_idx ON activity.step_template (template_id);

-- ============================================================
-- STEP_DEPENDENCY  (DAG)
-- ============================================================
CREATE TABLE IF NOT EXISTS activity.step_dependency (
    step_id         bigint NOT NULL REFERENCES activity.step_template(id) ON DELETE RESTRICT,
    depends_on_step_id bigint NOT NULL REFERENCES activity.step_template(id) ON DELETE RESTRICT,
    PRIMARY KEY (step_id, depends_on_step_id)
);
COMMENT ON TABLE activity.step_dependency IS 'DAG edges for step ordering. Same-template and no-cycle enforced by trigger.';

-- Trigger: same template and no cycles
CREATE OR REPLACE FUNCTION activity.check_step_dependency()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_template_a bigint;
    v_template_b bigint;
BEGIN
    SELECT template_id INTO v_template_a FROM activity.step_template WHERE id = NEW.step_id;
    SELECT template_id INTO v_template_b FROM activity.step_template WHERE id = NEW.depends_on_step_id;
    IF v_template_a <> v_template_b THEN
        RAISE EXCEPTION 'step_dependency: both steps must belong to the same template';
    END IF;
    IF NEW.step_id = NEW.depends_on_step_id THEN
        RAISE EXCEPTION 'step_dependency: cycle detected (a step cannot depend on itself)';
    END IF;
    -- Simple cycle check: does depends_on_step already depend (transitively) on step_id?
    IF EXISTS (
        WITH RECURSIVE chain(s) AS (
            SELECT depends_on_step_id FROM activity.step_dependency WHERE step_id = NEW.depends_on_step_id
            UNION ALL
            SELECT sd.depends_on_step_id FROM activity.step_dependency sd JOIN chain c ON sd.step_id = c.s
        )
        SELECT 1 FROM chain WHERE s = NEW.step_id
    ) THEN
        RAISE EXCEPTION 'step_dependency: cycle detected';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS check_step_dep_trg ON activity.step_dependency;
CREATE TRIGGER check_step_dep_trg
    BEFORE INSERT OR UPDATE ON activity.step_dependency
    FOR EACH ROW EXECUTE FUNCTION activity.check_step_dependency();

-- ============================================================
-- STEP_DATA_BINDING
-- ============================================================
CREATE TABLE IF NOT EXISTS activity.step_data_binding (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    step_id     bigint NOT NULL REFERENCES activity.step_template(id) ON DELETE RESTRICT,
    field_id    bigint NOT NULL REFERENCES activity.entity_field_registry(id) ON DELETE RESTRICT,
    mode        text   NOT NULL CHECK (mode IN ('read','write')),
    alias       text,
    row_filter  jsonb,
    note        text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE activity.step_data_binding IS 'Declares which core fields a step reads or writes. write on is_calculated=true is rejected by trigger.';

CREATE OR REPLACE FUNCTION activity.check_write_on_calculated()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_calc boolean;
BEGIN
    IF NEW.mode = 'write' THEN
        SELECT is_calculated INTO v_calc FROM activity.entity_field_registry WHERE id = NEW.field_id;
        IF v_calc THEN
            RAISE EXCEPTION 'step_data_binding: cannot write to a calculated field (field_id %)', NEW.field_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS check_write_calc_trg ON activity.step_data_binding;
CREATE TRIGGER check_write_calc_trg
    BEFORE INSERT OR UPDATE ON activity.step_data_binding
    FOR EACH ROW EXECUTE FUNCTION activity.check_write_on_calculated();

CREATE INDEX IF NOT EXISTS step_binding_step_idx  ON activity.step_data_binding (step_id);
CREATE INDEX IF NOT EXISTS step_binding_field_idx ON activity.step_data_binding (field_id);

-- ============================================================
-- STEP_EVIDENCE_REQUIREMENT
-- ============================================================
CREATE TABLE IF NOT EXISTS activity.step_evidence_requirement (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    step_id          bigint NOT NULL REFERENCES activity.step_template(id)   ON DELETE RESTRICT,
    document_type_id bigint NOT NULL REFERENCES core.document_type(id)       ON DELETE RESTRICT,
    is_mandatory     boolean NOT NULL DEFAULT true,
    condition_note   text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE activity.step_evidence_requirement IS 'Documents required by a step.';
CREATE INDEX IF NOT EXISTS step_ev_step_idx ON activity.step_evidence_requirement (step_id);

-- ============================================================
-- FUNCTION: activity.get_template_json(code, version)
-- Returns a single JSON document describing the full template.
-- ============================================================
CREATE OR REPLACE FUNCTION activity.get_template_json(
    p_code    text,
    p_version int DEFAULT NULL
)
RETURNS jsonb
LANGUAGE sql STABLE AS $$
    WITH tmpl AS (
        SELECT * FROM activity.activity_template
        WHERE code = p_code
          AND (p_version IS NULL OR version = p_version)
        ORDER BY version DESC
        LIMIT 1
    ),
    steps AS (
        SELECT st.*,
               jsonb_agg(
                   jsonb_build_object(
                       'depends_on_step_id', sd.depends_on_step_id
                   ) ORDER BY sd.depends_on_step_id
               ) FILTER (WHERE sd.depends_on_step_id IS NOT NULL) AS dependencies,
               jsonb_agg(
                   jsonb_build_object(
                       'field_id', sdb.field_id,
                       'table_name', efr.table_name,
                       'column_name', efr.column_name,
                       'mode', sdb.mode,
                       'alias', sdb.alias,
                       'row_filter', sdb.row_filter
                   ) ORDER BY sdb.id
               ) FILTER (WHERE sdb.id IS NOT NULL) AS bindings,
               jsonb_agg(
                   jsonb_build_object(
                       'document_type_id', ser.document_type_id,
                       'document_type_code', dt.code,
                       'is_mandatory', ser.is_mandatory,
                       'condition_note', ser.condition_note
                   ) ORDER BY ser.id
               ) FILTER (WHERE ser.id IS NOT NULL) AS evidence_requirements
        FROM activity.step_template st
        LEFT JOIN activity.step_dependency       sd  ON sd.step_id = st.id
        LEFT JOIN activity.step_data_binding     sdb ON sdb.step_id = st.id AND NOT sdb.is_archived
        LEFT JOIN activity.entity_field_registry efr ON efr.id = sdb.field_id
        LEFT JOIN activity.step_evidence_requirement ser ON ser.step_id = st.id AND NOT ser.is_archived
        LEFT JOIN core.document_type             dt  ON dt.id = ser.document_type_id
        WHERE st.template_id = (SELECT id FROM tmpl)
          AND NOT st.is_archived
        GROUP BY st.id
    )
    SELECT jsonb_build_object(
        'template',  (SELECT to_jsonb(t) FROM tmpl t),
        'steps',     COALESCE((SELECT jsonb_agg(to_jsonb(s) ORDER BY s.seq) FROM steps s), '[]'::jsonb)
    );
$$;

COMMENT ON FUNCTION activity.get_template_json IS 'Returns a complete JSON document for a template: template metadata, steps, dependencies, bindings, evidence requirements. Shape used by future MCP tools.';

-- ============================================================
-- OPS: ACTIVITY_INSTANCE
-- ============================================================
CREATE TABLE IF NOT EXISTS ops.activity_instance (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id  bigint NOT NULL REFERENCES core.company(id)             ON DELETE RESTRICT,
    template_id bigint NOT NULL REFERENCES activity.activity_template(id) ON DELETE RESTRICT,
    params      jsonb,
    created_by  bigint NOT NULL REFERENCES core.app_user(id)            ON DELETE RESTRICT,
    status      text   NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','completed','cancelled')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE ops.activity_instance IS 'One row per triggered compliance activity for a company.';
CREATE INDEX IF NOT EXISTS instance_company_idx  ON ops.activity_instance (company_id);
CREATE INDEX IF NOT EXISTS instance_template_idx ON ops.activity_instance (template_id);

-- ============================================================
-- OPS: TASK_INSTANCE
-- ============================================================
CREATE TABLE IF NOT EXISTS ops.task_instance (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance_id  bigint NOT NULL REFERENCES ops.activity_instance(id)    ON DELETE RESTRICT,
    step_id      bigint NOT NULL REFERENCES activity.step_template(id)   ON DELETE RESTRICT,
    status       text   NOT NULL DEFAULT 'not_started'
                     CHECK (status IN ('not_started','in_progress','completed','overdue','skipped')),
    due_date     date,
    completed_by bigint REFERENCES core.app_user(id) ON DELETE RESTRICT,
    completed_at timestamptz,
    notes        text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    is_archived  boolean     NOT NULL DEFAULT false,
    archived_at  timestamptz,
    archived_by  bigint,
    UNIQUE (instance_id, step_id)
);
COMMENT ON TABLE ops.task_instance IS 'One task per step per activity instance.';
CREATE INDEX IF NOT EXISTS task_instance_instance_idx ON ops.task_instance (instance_id);
CREATE INDEX IF NOT EXISTS task_instance_step_idx     ON ops.task_instance (step_id);
CREATE INDEX IF NOT EXISTS task_instance_status_idx   ON ops.task_instance (status);

-- ============================================================
-- OPS: TASK_RECORD_LINK
-- ============================================================
CREATE TABLE IF NOT EXISTS ops.task_record_link (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_instance_id bigint NOT NULL REFERENCES ops.task_instance(id) ON DELETE RESTRICT,
    entity_type      text   NOT NULL,
    entity_id        bigint NOT NULL,
    mode             text   NOT NULL CHECK (mode IN ('read','write')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    is_archived boolean     NOT NULL DEFAULT false,
    archived_at timestamptz,
    archived_by bigint
);
COMMENT ON TABLE ops.task_record_link IS 'Records which specific core rows each task involved.';
CREATE INDEX IF NOT EXISTS trl_task_idx   ON ops.task_record_link (task_instance_id);
CREATE INDEX IF NOT EXISTS trl_entity_idx ON ops.task_record_link (entity_type, entity_id);

-- ============================================================
-- OPS: CONFIRMATION
-- ============================================================
CREATE TABLE IF NOT EXISTS ops.confirmation (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_type   text   NOT NULL,
    subject_id     bigint NOT NULL,
    requested_by   bigint NOT NULL REFERENCES core.app_user(id) ON DELETE RESTRICT,
    confirmed_by   bigint REFERENCES core.app_user(id) ON DELETE RESTRICT,
    confirmed_at   timestamptz,
    status         text   NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','confirmed','rejected')),
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    is_archived    boolean     NOT NULL DEFAULT false,
    archived_at    timestamptz,
    archived_by    bigint
);
COMMENT ON TABLE ops.confirmation IS 'Confirmation gate — no outbound communication happens without a named person confirming. Phase 1: table only.';
CREATE INDEX IF NOT EXISTS confirmation_subject_idx ON ops.confirmation (subject_type, subject_id);

-- ============================================================
-- OPS: INSTANTIATE_ACTIVITY function
-- Creates an activity_instance and one task per step with computed due dates.
-- Plain deterministic SQL — no AI.
-- ============================================================
CREATE OR REPLACE FUNCTION ops.instantiate_activity(
    p_template_code text,
    p_company_id    bigint,
    p_params        jsonb,
    p_actor         bigint
)
RETURNS bigint   -- returns the new activity_instance.id
LANGUAGE plpgsql AS $$
DECLARE
    v_template      activity.activity_template;
    v_instance_id   bigint;
    v_step          activity.step_template;
    v_due_date      date;
    v_anchor_date   date;
BEGIN
    -- Resolve template (latest active version)
    SELECT * INTO v_template
    FROM activity.activity_template
    WHERE code = p_template_code
      AND status IN ('active','draft')
    ORDER BY version DESC
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No template found with code %', p_template_code;
    END IF;

    -- Set session user for audit
    PERFORM set_config('app.current_user_id', p_actor::text, true);

    -- Create the instance
    INSERT INTO ops.activity_instance (company_id, template_id, params, created_by, status)
    VALUES (p_company_id, v_template.id, p_params, p_actor, 'active')
    RETURNING id INTO v_instance_id;

    -- Create one task per step with computed due date
    FOR v_step IN
        SELECT * FROM activity.step_template
        WHERE template_id = v_template.id
          AND NOT is_archived
        ORDER BY seq
    LOOP
        v_due_date := NULL;
        IF v_step.deadline_anchor IS NOT NULL THEN
            -- Try to extract anchor date from params JSON
            BEGIN
                v_anchor_date := (p_params ->> v_step.deadline_anchor)::date;
            EXCEPTION WHEN others THEN
                v_anchor_date := NULL;
            END;

            IF v_anchor_date IS NOT NULL THEN
                IF v_step.deadline_direction = 'before' THEN
                    v_due_date := v_anchor_date - v_step.deadline_offset_days;
                ELSE
                    v_due_date := v_anchor_date + v_step.deadline_offset_days;
                END IF;
            END IF;
        END IF;

        INSERT INTO ops.task_instance (instance_id, step_id, status, due_date)
        VALUES (v_instance_id, v_step.id, 'not_started', v_due_date);
    END LOOP;

    RETURN v_instance_id;
END;
$$;

COMMENT ON FUNCTION ops.instantiate_activity IS 'Creates an activity_instance and one task_instance per step with computed due dates. p_params jsonb must include the anchor date key (e.g. meeting_date) if steps have deadline_anchor.';

-- Add deferred FK: evidence_link -> ops.task_instance
ALTER TABLE core.evidence_link
    ADD CONSTRAINT evidence_link_task_fk
    FOREIGN KEY (task_instance_id) REFERENCES ops.task_instance(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS evidence_link_task_idx ON core.evidence_link (task_instance_id);
