"""The Activity Log: who changed what, when, from which value to which value.

audit.log is deliberately closed to the application login (it is append-only and only the
database owner can read it), so this one router reads it on the privileged connection - read-only,
and narrowed to the companies the user may see.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from ..access import UserCtx
from ..deps import current_user, privileged_session, readable_company
from ..registry import ENTITIES, SCOPE
from ..responses import ok

router = APIRouter(tags=["audit"])

_SKIP_KEYS = {"updated_at", "created_at"}


def _company_expr(catalog, cid_param: str) -> str:
    """SQL that is true when an audit row belongs to the company: it carries the company_id, is the company
    itself, or is a child record whose parent carries it."""
    parts = [
        f"coalesce(l.new_row->>'company_id', l.old_row->>'company_id') = {cid_param}::text",
        f"(l.table_name = 'company' AND l.record_id = {cid_param})",
    ]
    for key, scope in SCOPE.items():
        if scope["type"] != "parent":
            continue
        parent = catalog.get(scope["parent"])
        if parent is None or not parent.has("company_id"):
            continue
        parts.append(
            f"(l.table_name = '{key}' AND EXISTS (SELECT 1 FROM {parent.ident} p WHERE p.id = "
            f"(coalesce(l.new_row, l.old_row)->>'{scope['fk']}')::bigint AND p.company_id = {cid_param}))")
    return "(" + " OR ".join(parts) + ")"


@router.get("/audit")
def audit(request: Request, company_id: int | None = None, table: str | None = None, q: str | None = None,
          limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), ctx: UserCtx = Depends(current_user)):
    catalog = request.app.state.catalog
    params: dict = {"limit": limit + 1, "offset": offset}
    where = []
    if company_id is not None:
        readable_company(ctx, company_id)
        params["cid"] = company_id
        where.append(_company_expr(catalog, "%(cid)s"))
    elif not ctx.is_admin:
        params["rids"] = ctx.readable
        where.append("EXISTS (SELECT 1 FROM unnest(%(rids)s::bigint[]) AS x(id) WHERE "
                     + _company_expr(catalog, "x.id") + ")")
    if table:
        params["table"] = table
        where.append("l.table_name = %(table)s")
    if q:
        params["q"] = "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(coalesce(u.name, '') ILIKE %(q)s OR l.table_name ILIKE %(q)s OR l.operation ILIKE %(q)s)")
    sql = f"""SELECT l.id, l.table_schema, l.table_name, l.record_id, l.operation, l.changed_at, l.actor,
                     coalesce(u.name, 'User #' || l.actor) AS actor_name, l.old_row, l.new_row
              FROM audit.log l LEFT JOIN core.app_user u ON u.id = l.actor
              {"WHERE " + " AND ".join(where) if where else ""}
              ORDER BY l.id DESC LIMIT %(limit)s OFFSET %(offset)s"""
    with privileged_session(request, ctx, readonly=True) as conn:
        rows = conn.execute(sql, params).fetchall()
    more = len(rows) > limit
    entries = []
    for r in rows[:limit]:
        old, new = r["old_row"] or {}, r["new_row"] or {}
        changes = {k: {"from": old.get(k), "to": new.get(k)} for k in sorted(set(old) | set(new))
                   if old.get(k) != new.get(k) and k not in _SKIP_KEYS and not k.endswith("_encrypted")}
        cfg = ENTITIES.get(r["table_name"])
        entries.append({"id": r["id"], "at": r["changed_at"], "actor": r["actor_name"], "operation": r["operation"],
                        "table": r["table_name"], "table_label": cfg["singular"] if cfg else r["table_name"],
                        "record_id": r["record_id"], "changes": changes})
    return ok({"entries": entries, "has_more": more, "offset": offset})
