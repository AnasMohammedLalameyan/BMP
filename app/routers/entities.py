"""Generic CRUD for every table (see crud.Engine), plus record history and CSV export."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Body, Depends, Query, Request
from starlette.responses import Response

from ..access import UserCtx
from ..crud import PAGE_MAX
from ..deps import current_user, privileged_session, session
from ..errors import ApiError, bad_request
from ..registry import ENTITIES
from ..responses import ok
from .meta import humanize

router = APIRouter(tags=["entities"])

# Records that are created by a dedicated workflow, not by a bare INSERT.
BLOCK_CREATE = {
    "company": "Add a company from the Companies page.",
    "activity_instance": "Start an activity from Activities & Tasks.",
    "task_instance": "Tasks are created automatically when an activity starts.",
}
# Fields that only the workflow endpoints may change.
LOCKED_FIELDS = {
    "task_instance": {"status", "completed_by", "completed_at"},
    "activity_instance": {"status", "template_id", "created_by", "params"},
    "confirmation": {"status", "confirmed_by", "confirmed_at", "requested_by"},
}


def _clean_filters(request: Request) -> dict:
    return {k[2:]: v for k, v in request.query_params.items() if k.startswith("f_")}


def _guard_locked(key: str, payload: dict, creating: bool) -> None:
    locked = LOCKED_FIELDS.get(key, set())
    touched = sorted(f for f in payload if f in locked)
    if touched and not (creating and key == "confirmation"):
        raise bad_request(f"{', '.join(touched)} can only be changed through its workflow action.",
                          {f: "Use the workflow action" for f in touched})


def _prepare_create(request: Request, ctx: UserCtx, conn, key: str, payload: dict) -> dict:
    payload = dict(payload)
    if key in BLOCK_CREATE:
        raise ApiError(405, "use_workflow", BLOCK_CREATE[key])
    _guard_locked(key, payload, creating=True)
    if key == "document":
        payload.setdefault("uploaded_by", ctx.id)
    if key == "confirmation":
        payload["requested_by"] = ctx.id
        payload["status"] = "pending"
    if key in ("evidence_link", "task_record_link"):
        _check_entity_reference(request, ctx, conn, payload)
    return payload


def _check_entity_reference(request: Request, ctx: UserCtx, conn, payload: dict) -> None:
    """entity_type/entity_id point at any record; the type must be a real table and the record visible."""
    etype, eid = payload.get("entity_type"), payload.get("entity_id")
    if etype in (None, "") or eid in (None, ""):
        return                                    # required-field validation reports it
    catalog = request.app.state.catalog
    t = catalog.get(str(etype))
    if t is None or t.is_view or etype not in ENTITIES:
        raise bad_request("entity_type must be the name of a record type, e.g. 'meeting' or 'directorship'",
                          {"entity_type": "Not a known record type"})
    request.app.state.engine.get(conn, str(etype), ctx, str(eid))     # 404 if not visible


@router.get("/entities/{key}")
def list_entity(key: str, request: Request, company_id: int | None = None, fy: str | None = None,
                q: str | None = None, archived: bool = False, sort: str | None = None, desc: bool = False,
                page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=PAGE_MAX),
                ctx: UserCtx = Depends(current_user)):
    with session(request, ctx, readonly=True) as conn:
        data = request.app.state.engine.list(
            conn, key, ctx, company_id=company_id, fy=fy, q=q, include_archived=archived,
            filters=_clean_filters(request), sort=sort, desc=desc, page=page, size=size)
    return ok(data)


@router.get("/entities/{key}/export.csv")
def export_csv(key: str, request: Request, company_id: int | None = None, fy: str | None = None,
               q: str | None = None, ctx: UserCtx = Depends(current_user)):
    engine = request.app.state.engine
    t, cfg = engine.entity(key)
    with session(request, ctx, readonly=True) as conn:
        data = engine.list(conn, key, ctx, company_id=company_id, fy=fy, q=q, filters=_clean_filters(request),
                           page=1, size=PAGE_MAX)
    cols = [c for c in t.columns if c.kind not in ("bytea", "vector")]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([humanize(c.name) for c in cols])
    for r in data["rows"]:
        w.writerow([_csv_cell(r["_labels"].get(c.name, r.get(c.name))) for c in cols])
    body = "﻿" + out.getvalue()          # BOM so Excel reads UTF-8 (rupee signs, dashes)
    return Response(body, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="{key}.csv"'})


def _csv_cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, (dict, list)):
        import json
        return json.dumps(v, ensure_ascii=False)
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") and not _is_number(s) else s   # CSV injection guard


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


@router.get("/entities/{key}/{pk}")
def get_entity(key: str, pk: str, request: Request, ctx: UserCtx = Depends(current_user)):
    with session(request, ctx, readonly=True) as conn:
        row = request.app.state.engine.get(conn, key, ctx, pk)
    return ok({"row": row})


@router.post("/entities/{key}")
def create_entity(key: str, request: Request, payload: dict = Body(...), ctx: UserCtx = Depends(current_user)):
    with session(request, ctx) as conn:
        payload = _prepare_create(request, ctx, conn, key, payload)
        row = request.app.state.engine.create(conn, key, ctx, payload)
    return ok({"row": row}, 201)


@router.patch("/entities/{key}/{pk}")
def update_entity(key: str, pk: str, request: Request, payload: dict = Body(...),
                  ctx: UserCtx = Depends(current_user)):
    _guard_locked(key, payload, creating=False)
    with session(request, ctx) as conn:
        if key in ("evidence_link", "task_record_link") and ("entity_type" in payload or "entity_id" in payload):
            merged = {**request.app.state.engine.get(conn, key, ctx, pk), **payload}
            _check_entity_reference(request, ctx, conn, merged)
        row = request.app.state.engine.update(conn, key, ctx, pk, payload)
    return ok({"row": row})


@router.post("/entities/{key}/{pk}/archive")
def archive_entity(key: str, pk: str, request: Request, ctx: UserCtx = Depends(current_user)):
    with session(request, ctx) as conn:
        row = request.app.state.engine.set_archived(conn, key, ctx, pk, True)
    return ok({"row": row})


@router.post("/entities/{key}/{pk}/restore")
def restore_entity(key: str, pk: str, request: Request, ctx: UserCtx = Depends(current_user)):
    with session(request, ctx) as conn:
        row = request.app.state.engine.set_archived(conn, key, ctx, pk, False)
    return ok({"row": row})


@router.get("/entities/{key}/{pk}/history")
def history(key: str, pk: str, request: Request, ctx: UserCtx = Depends(current_user)):
    """Every change ever made to this record: who, when, and the values before and after."""
    engine = request.app.state.engine
    t, _ = engine.entity(key)
    with session(request, ctx, readonly=True) as conn:
        row = engine.get(conn, key, ctx, pk)            # also proves the user may see it
    if "id" not in t.pk:
        return ok({"entries": []})
    with privileged_session(request, ctx, readonly=True) as conn:
        rows = conn.execute(
            """SELECT l.id, l.operation, l.changed_at, l.old_row, l.new_row, l.actor,
                      COALESCE(u.name, 'User #' || l.actor) AS actor_name
               FROM audit.log l LEFT JOIN core.app_user u ON u.id = l.actor
               WHERE l.table_schema = %s AND l.table_name = %s AND l.record_id = %s
               ORDER BY l.id DESC LIMIT 200""", (t.schema, t.name, row["id"])).fetchall()
    entries = []
    for r in rows:
        old, new = r["old_row"] or {}, r["new_row"] or {}
        changes = {k: {"from": old.get(k), "to": new.get(k)} for k in sorted(set(old) | set(new))
                   if old.get(k) != new.get(k) and k not in ("updated_at",) and not k.endswith("_encrypted")}
        entries.append({"id": r["id"], "operation": r["operation"], "at": r["changed_at"], "actor": r["actor_name"],
                        "changes": changes})
    return ok({"entries": entries})
