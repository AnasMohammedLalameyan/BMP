"""Activities & Tasks: the recipe (template), starting one for a company, and working through its tasks.

The database owns the mechanics: `ops.instantiate_activity` creates the instance and one task per
step with due dates computed from the meeting date. This router adds the workflow rules around moving
a task forward - a task cannot be completed before the steps it depends on, and a step that requires a
named person's confirmation cannot be completed until one has been recorded.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Body, Depends, Request
from psycopg.types.json import Jsonb

from ..access import UserCtx
from ..deps import current_user, readable_company, session, writable_company
from ..errors import ApiError, bad_request, conflict, forbidden, not_found
from ..responses import ok
from ..task_records import _entity_name, _label, _target_record

router = APIRouter(tags=["activities"])

TASK_STATUSES = ("not_started", "in_progress", "completed", "skipped")
DONE = ("completed", "skipped")


# ---- templates --------------------------------------------------------------------------
@router.get("/activities/templates")
def templates(request: Request, ctx: UserCtx = Depends(current_user)):
    with session(request, ctx, readonly=True) as conn:
        rows = conn.execute(
            """SELECT t.id, t.code, t.version, t.name, t.status, t.obligation_ref, t.description, t.effective_from,
                      t.reviewed_by, t.reviewed_on, t.input_schema,
                      (SELECT count(*) FROM activity.step_template s WHERE s.template_id = t.id AND NOT s.is_archived) AS steps
               FROM activity.activity_template t WHERE NOT t.is_archived AND t.status <> 'retired'
               ORDER BY t.code, t.version DESC""").fetchall()
    return ok({"templates": rows})


def _template_detail(conn, template_id: int) -> dict:
    t = conn.execute("SELECT * FROM activity.activity_template WHERE id = %s AND NOT is_archived", (template_id,)).fetchone()
    if t is None:
        raise not_found("Template")
    steps = conn.execute("SELECT * FROM activity.step_template WHERE template_id = %s AND NOT is_archived ORDER BY seq",
                         (template_id,)).fetchall()
    by_id = {s["id"]: s for s in steps}
    for s in steps:
        s["depends_on"] = [r["depends_on_step_id"] for r in conn.execute(
            "SELECT depends_on_step_id FROM activity.step_dependency WHERE step_id = %s ORDER BY 1", (s["id"],))]
        s["bindings"] = conn.execute(
            """SELECT b.id, b.mode, b.alias, b.row_filter, b.note, f.table_name, f.column_name, f.is_calculated
               FROM activity.step_data_binding b JOIN activity.entity_field_registry f ON f.id = b.field_id
               WHERE b.step_id = %s AND NOT b.is_archived ORDER BY b.id""", (s["id"],)).fetchall()
        s["evidence"] = conn.execute(
            """SELECT e.id, e.is_mandatory, e.condition_note, d.id AS document_type_id, d.name AS document_type
               FROM activity.step_evidence_requirement e JOIN core.document_type d ON d.id = e.document_type_id
               WHERE e.step_id = %s AND NOT e.is_archived ORDER BY e.id""", (s["id"],)).fetchall()
        s["deadline"] = (f'{s["deadline_offset_days"]} day(s) {s["deadline_direction"]} {s["deadline_anchor"]}'
                         if s["deadline_anchor"] else None)
    del by_id
    return {"template": t, "steps": steps}


@router.get("/activities/templates/{template_id}")
def template(template_id: int, request: Request, ctx: UserCtx = Depends(current_user)):
    with session(request, ctx, readonly=True) as conn:
        return ok(_template_detail(conn, template_id))


@router.get("/activities/templates/{code}/json")
def template_json(code: str, request: Request, version: int | None = None, ctx: UserCtx = Depends(current_user)):
    """The raw `activity.get_template_json` document (the shape a future MCP tool will return)."""
    with session(request, ctx, readonly=True) as conn:
        row = conn.execute("SELECT activity.get_template_json(%s, %s) AS doc", (code, version)).fetchone()
    if not row["doc"] or not row["doc"].get("template"):
        raise not_found("Template")
    return ok(row["doc"])


# ---- instances ---------------------------------------------------------------------------
def _validate_params(schema: dict | None, params: dict) -> dict:
    """Light check of the start form against the template's input_schema (required keys and dates)."""
    errors = {}
    props = (schema or {}).get("properties", {})
    for key in (schema or {}).get("required", []):
        v = params.get(key)
        if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v):
            errors[key] = "Required"
    for key, spec in props.items():
        v = params.get(key)
        if v in (None, "", []):
            continue
        if spec.get("format") == "date":
            try:
                date.fromisoformat(str(v)[:10])
            except ValueError:
                errors[key] = "Enter a date as YYYY-MM-DD"
        if spec.get("type") == "array" and not isinstance(v, list):
            errors[key] = "Enter a list"
    return errors


@router.post("/activities/instances")
def start_activity(request: Request, payload: dict = Body(...), ctx: UserCtx = Depends(current_user)):
    """payload: {template_code, company_id, params: {...}}"""
    code, company_id, params = payload.get("template_code"), payload.get("company_id"), payload.get("params") or {}
    if not code or not company_id:
        raise bad_request("template_code and company_id are required")
    writable_company(ctx, int(company_id))
    with session(request, ctx) as conn:
        tpl = conn.execute("SELECT id, input_schema FROM activity.activity_template WHERE code = %s AND NOT is_archived "
                           "AND status IN ('active', 'draft') ORDER BY version DESC LIMIT 1", (code,)).fetchone()
        if tpl is None:
            raise not_found("Template")
        errors = _validate_params(tpl["input_schema"], params)
        if errors:
            raise bad_request("Please correct the highlighted fields.", {f"params.{k}": v for k, v in errors.items()})
        new_id = conn.execute("SELECT ops.instantiate_activity(%s, %s, %s, %s) AS id",
                              (code, int(company_id), Jsonb(params), ctx.id)).fetchone()["id"]
        detail = _instance_detail(conn, request, ctx, new_id)
    return ok(detail, 201)


@router.get("/companies/{company_id}/activities")
def company_activities(company_id: int, request: Request, ctx: UserCtx = Depends(current_user)):
    readable_company(ctx, company_id)
    with session(request, ctx, readonly=True) as conn:
        rows = conn.execute(
            """SELECT i.id, i.status, i.params, i.created_at, i.updated_at, t.code, t.name, t.version, u.name AS created_by_name,
                      count(k.id) AS tasks,
                      count(k.id) FILTER (WHERE k.status IN ('completed', 'skipped')) AS done,
                      count(k.id) FILTER (WHERE k.status NOT IN ('completed', 'skipped') AND k.due_date < current_date) AS overdue,
                      min(k.due_date) FILTER (WHERE k.status NOT IN ('completed', 'skipped')) AS next_due
               FROM ops.activity_instance i
               JOIN activity.activity_template t ON t.id = i.template_id
               LEFT JOIN core.app_user u ON u.id = i.created_by
               LEFT JOIN ops.task_instance k ON k.instance_id = i.id AND NOT k.is_archived
               WHERE i.company_id = %s AND NOT i.is_archived
               GROUP BY i.id, t.code, t.name, t.version, u.name ORDER BY i.created_at DESC""", (company_id,)).fetchall()
    return ok({"instances": rows})


def _instance_detail(conn, request: Request, ctx: UserCtx, instance_id: int) -> dict:
    engine = request.app.state.engine
    inst = engine.get(conn, "activity_instance", ctx, str(instance_id))            # scope-checked
    tpl = _template_detail(conn, inst["template_id"])
    tasks = conn.execute(
        """SELECT k.*, u.name AS completed_by_name FROM ops.task_instance k LEFT JOIN core.app_user u ON u.id = k.completed_by
           WHERE k.instance_id = %s AND NOT k.is_archived""", (instance_id,)).fetchall()
    steps = {s["id"]: s for s in tpl["steps"]}
    task_by_step = {k["step_id"]: k for k in tasks}
    today = date.today()
    ids = [k["id"] for k in tasks]
    links: dict = {}
    evidence: dict = {}
    confirmations: dict = {}
    if ids:
        for r in conn.execute("SELECT * FROM ops.task_record_link WHERE task_instance_id = ANY(%s::bigint[]) AND NOT is_archived ORDER BY id",
                              (ids,)):
            links.setdefault(r["task_instance_id"], []).append(r)
        for r in conn.execute(
                """SELECT e.id, e.task_instance_id, e.note, d.id AS document_id, d.filename, d.version,
                          (SELECT t.name FROM core.document_type t WHERE t.id = d.document_type_id) AS document_type
                   FROM core.evidence_link e JOIN core.document d ON d.id = e.document_id
                   WHERE e.task_instance_id = ANY(%s::bigint[]) AND NOT e.is_archived AND NOT d.is_archived ORDER BY e.id""", (ids,)):
            evidence.setdefault(r["task_instance_id"], []).append(r)
        for r in conn.execute(
                """SELECT c.*, ru.name AS requested_by_name, cu.name AS confirmed_by_name FROM ops.confirmation c
                   LEFT JOIN core.app_user ru ON ru.id = c.requested_by LEFT JOIN core.app_user cu ON cu.id = c.confirmed_by
                   WHERE c.subject_type = 'task_instance' AND c.subject_id = ANY(%s::bigint[]) AND NOT c.is_archived
                   ORDER BY c.id""", (ids,)):
            confirmations.setdefault(r["subject_id"], []).append(r)
    out = []
    for step in tpl["steps"]:
        k = task_by_step.get(step["id"])
        if k is None:
            continue
        blockers = [steps[d]["title"] for d in step["depends_on"] if d in task_by_step
                    and task_by_step[d]["status"] not in DONE]
        k = dict(k)
        k["links"] = links.get(k["id"], [])
        # label each record the task touched ("meeting 5" -> "BM-1 - 2025-04-15")
        engine._labels(conn, request.app.state.catalog.get("task_record_link"), k["links"])
        k["evidence"] = evidence.get(k["id"], [])
        k["confirmations"] = confirmations.get(k["id"], [])
        k["step"] = step
        k["blocked_by"] = blockers
        k["is_overdue"] = bool(k["due_date"] and k["due_date"] < today and k["status"] not in DONE)
        k["confirmed"] = any(c["status"] == "confirmed" for c in k["confirmations"])
        out.append(k)
    inst["template_name"] = tpl["template"]["name"]
    inst["template_code"] = tpl["template"]["code"]
    inst["template_status"] = tpl["template"]["status"]
    return {"instance": inst, "tasks": out}


@router.get("/activities/instances/{instance_id}")
def instance(instance_id: int, request: Request, ctx: UserCtx = Depends(current_user)):
    with session(request, ctx, readonly=True) as conn:
        return ok(_instance_detail(conn, request, ctx, instance_id))


# ---- workflow actions ------------------------------------------------------------------------
@router.post("/activities/tasks/{task_id}/status")
def task_status(task_id: int, request: Request, payload: dict = Body(...), ctx: UserCtx = Depends(current_user)):
    """payload: {status, notes?}. Moves a task, enforcing step order and required confirmation."""
    new_status = payload.get("status")
    if new_status not in TASK_STATUSES:
        raise bad_request("status must be one of: " + ", ".join(TASK_STATUSES), {"status": "Not allowed"})
    engine = request.app.state.engine
    settings = request.app.state.settings
    with session(request, ctx) as conn:
        task = engine.get(conn, "task_instance", ctx, str(task_id))
        inst = engine.get(conn, "activity_instance", ctx, str(task["instance_id"]))
        writable_company(ctx, inst["company_id"])
        if inst["status"] == "cancelled":
            raise conflict("This activity was cancelled; reopen it first.")
        step = conn.execute("SELECT * FROM activity.step_template WHERE id = %s", (task["step_id"],)).fetchone()
        warnings = []
        if new_status == "completed":
            blockers = [r["title"] for r in conn.execute(
                """SELECT s.title FROM activity.step_dependency d
                   JOIN activity.step_template s ON s.id = d.depends_on_step_id
                   JOIN ops.task_instance k ON k.step_id = d.depends_on_step_id AND k.instance_id = %s
                   WHERE d.step_id = %s AND k.status NOT IN ('completed', 'skipped')""", (task["instance_id"], task["step_id"]))]
            if blockers:
                raise conflict("Finish the earlier step(s) first: " + "; ".join(blockers), "blocked")
            if step["requires_confirmation"] and settings.enforce_task_confirmation:
                confirmed = conn.execute(
                    "SELECT 1 FROM ops.confirmation WHERE subject_type = 'task_instance' AND subject_id = %s "
                    "AND status = 'confirmed' AND NOT is_archived", (task_id,)).fetchone()
                if not confirmed:
                    raise conflict("This step needs a named person's confirmation before it can be completed. "
                                   "Request and record the confirmation first.", "needs_confirmation")
            missing = conn.execute(
                """SELECT d.name FROM activity.step_evidence_requirement e JOIN core.document_type d ON d.id = e.document_type_id
                   WHERE e.step_id = %s AND e.is_mandatory AND NOT e.is_archived AND NOT EXISTS (
                     SELECT 1 FROM core.evidence_link l JOIN core.document x ON x.id = l.document_id
                     WHERE l.task_instance_id = %s AND x.document_type_id = e.document_type_id AND NOT l.is_archived)""",
                (task["step_id"], task_id)).fetchall()
            if missing:
                warnings.append("No evidence attached yet for: " + ", ".join(m["name"] for m in missing))
        body = {"status": new_status}
        if "notes" in payload:
            body["notes"] = payload["notes"]
        if new_status == "completed":
            body.update(completed_by=ctx.id, completed_at=_now_iso(conn))
        else:
            body.update(completed_by=None, completed_at=None)
        engine.update(conn, "task_instance", ctx, str(task_id), body)
        # roll the instance up: all steps done -> completed; reopened -> active
        remaining = conn.execute("SELECT count(*) AS n FROM ops.task_instance WHERE instance_id = %s AND NOT is_archived "
                                 "AND status NOT IN ('completed', 'skipped')", (task["instance_id"],)).fetchone()["n"]
        wanted = "completed" if remaining == 0 else "active"
        if inst["status"] != wanted:
            engine.update(conn, "activity_instance", ctx, str(inst["id"]), {"status": wanted})
        detail = _instance_detail(conn, request, ctx, inst["id"])
    detail["warnings"] = warnings
    return ok(detail)


def _now_iso(conn) -> str:
    return conn.execute("SELECT now() AS n").fetchone()["n"].isoformat()


@router.post("/activities/instances/{instance_id}/status")
def instance_status(instance_id: int, request: Request, payload: dict = Body(...), ctx: UserCtx = Depends(current_user)):
    """Cancel or reopen an activity. (Completion follows from its tasks.)"""
    wanted = payload.get("status")
    if wanted not in ("active", "cancelled"):
        raise bad_request("status must be 'active' or 'cancelled'", {"status": "Not allowed"})
    engine = request.app.state.engine
    with session(request, ctx) as conn:
        inst = engine.get(conn, "activity_instance", ctx, str(instance_id))
        writable_company(ctx, inst["company_id"])
        engine.update(conn, "activity_instance", ctx, str(instance_id), {"status": wanted})
        return ok(_instance_detail(conn, request, ctx, instance_id))


@router.post("/activities/tasks/{task_id}/confirmations")
def request_confirmation(task_id: int, request: Request, payload: dict = Body(default={}), ctx: UserCtx = Depends(current_user)):
    engine = request.app.state.engine
    with session(request, ctx) as conn:
        task = engine.get(conn, "task_instance", ctx, str(task_id))
        inst = engine.get(conn, "activity_instance", ctx, str(task["instance_id"]))
        writable_company(ctx, inst["company_id"])
        pending = conn.execute("SELECT 1 FROM ops.confirmation WHERE subject_type = 'task_instance' AND subject_id = %s "
                               "AND status = 'pending' AND NOT is_archived", (task_id,)).fetchone()
        if pending:
            raise conflict("A confirmation is already waiting for this task.")
        row = engine.create(conn, "confirmation", ctx, {"subject_type": "task_instance", "subject_id": task_id,
                                                        "requested_by": ctx.id, "status": "pending"})
    return ok({"confirmation": row}, 201)


@router.post("/confirmations/{confirmation_id}/{decision}")
def decide_confirmation(confirmation_id: int, decision: str, request: Request, ctx: UserCtx = Depends(current_user)):
    """A named person confirms or rejects. Someone other than the requester must decide (an administrator may decide their own)."""
    if decision not in ("confirm", "reject"):
        raise not_found()
    engine = request.app.state.engine
    with session(request, ctx) as conn:
        c = conn.execute("SELECT * FROM ops.confirmation WHERE id = %s AND NOT is_archived", (confirmation_id,)).fetchone()
        if c is None or c["subject_type"] != "task_instance":
            raise not_found("Confirmation")
        task = engine.get(conn, "task_instance", ctx, str(c["subject_id"]))              # must be able to see the subject
        inst = engine.get(conn, "activity_instance", ctx, str(task["instance_id"]))
        writable_company(ctx, inst["company_id"])
        if c["status"] != "pending":
            raise conflict("This confirmation has already been decided.")
        if c["requested_by"] == ctx.id and not ctx.is_admin:
            raise forbidden("Someone other than the person who asked must confirm this.")
        conn.execute("UPDATE ops.confirmation SET status = %s, confirmed_by = %s, confirmed_at = now() WHERE id = %s",
                     ("confirmed" if decision == "confirm" else "rejected", ctx.id, confirmation_id))
        row = conn.execute("SELECT * FROM ops.confirmation WHERE id = %s", (confirmation_id,)).fetchone()
    return ok({"confirmation": row})


# ---- task data capture -----------------------------------------------------------------------
@router.get("/activities/tasks/{task_id}/fields")
def task_fields(task_id: int, request: Request, ctx: UserCtx = Depends(current_user)):
    engine = request.app.state.engine
    with session(request, ctx, readonly=True) as conn:
        task = engine.get(conn, "task_instance", ctx, str(task_id))      # scope-checked
        binds = conn.execute(
            """SELECT b.id AS binding_id, b.alias, b.row_filter, f.table_name, f.column_name
               FROM activity.step_data_binding b
               JOIN activity.entity_field_registry f ON f.id = b.field_id
               WHERE b.step_id = %s AND b.mode = 'write' AND NOT b.is_archived
                 AND NOT f.is_calculated
               ORDER BY b.id""", (task["step_id"],)).fetchall()
        fields = []
        for b in binds:
            rec = _target_record(conn, request, task, b)
            fields.append({"binding_id": b["binding_id"],
                           "label": b["alias"] or _label(b["column_name"]),
                           "entity": _entity_name(b["table_name"]),
                           "column": b["column_name"],
                           "value": rec.get(b["column_name"]) if rec else None,
                           "version": rec.get("updated_at") if rec else None})
        return ok({"fields": fields})


@router.post("/activities/tasks/{task_id}/data")
def task_data(task_id: int, request: Request, payload: dict = Body(...),
              ctx: UserCtx = Depends(current_user)):
    engine = request.app.state.engine
    values = payload.get("values") or {}
    with session(request, ctx) as conn:
        task = engine.get(conn, "task_instance", ctx, str(task_id))
        inst = engine.get(conn, "activity_instance", ctx, str(task["instance_id"]))
        writable_company(ctx, inst["company_id"])
        if inst["status"] == "cancelled":
            raise conflict("This activity was cancelled; reopen it first.")
        allowed = {str(r["binding_id"]): r for r in conn.execute(
            """SELECT b.id AS binding_id, b.row_filter, f.table_name, f.column_name
               FROM activity.step_data_binding b
               JOIN activity.entity_field_registry f ON f.id = b.field_id
               WHERE b.step_id = %s AND b.mode = 'write' AND NOT b.is_archived
                 AND NOT f.is_calculated""", (task["step_id"],))}
        unknown = [k for k in values if k not in allowed]
        if unknown:    # whitelist: a client can only write what the step declares
            raise bad_request("Some fields do not belong to this step.",
                              {k: "Not allowed" for k in unknown})
        by_record: dict = {}
        for k, v in values.items():
            b = allowed[k]
            rec = _target_record(conn, request, task, b)
            if rec is None:
                raise conflict("The record this step updates does not exist yet.")
            by_record.setdefault((_entity_name(b["table_name"]), rec["id"], rec["updated_at"]), {})[b["column_name"]] = v
        for (entity, rec_id, version), body in by_record.items():
            engine.update(conn, entity, ctx, str(rec_id), {**body, "updated_at": version})   # validates + audits
        for (entity, rec_id, _), _ in by_record.items():
            exists = conn.execute(
                "SELECT 1 FROM ops.task_record_link WHERE task_instance_id = %s AND entity_type = %s AND entity_id = %s AND NOT is_archived",
                (task_id, entity, rec_id)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO ops.task_record_link (task_instance_id, entity_type, entity_id, mode) VALUES (%s, %s, %s, 'write')",
                    (task_id, entity, rec_id)
                )
        return ok({"saved": len(values)})
