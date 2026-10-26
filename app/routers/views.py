"""Calculated values (the database views, scoped per user) and the applicability rules."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from ..access import UserCtx
from ..deps import current_user, readable_company, session
from ..errors import not_found
from ..registry import VIEWS
from ..responses import ok
from .companies import current_financial_year

router = APIRouter(tags=["calculated"])


@router.get("/calc/{view}")
def calc_view(view: str, request: Request, company_id: int | None = None, limit: int = Query(1000, ge=1, le=5000),
              ctx: UserCtx = Depends(current_user)):
    if view not in VIEWS:
        raise not_found("View")
    if company_id is not None:
        readable_company(ctx, company_id)
    with session(request, ctx, readonly=True) as conn:
        data = request.app.state.engine.view_rows(conn, view, ctx, company_id=company_id, limit=limit)
    return ok({**data, "label": VIEWS[view]})


@router.get("/companies/{company_id}/rules")
def rules(company_id: int, request: Request, fy: str | None = None, ctx: UserCtx = Depends(current_user)):
    """Every rule with the latest evaluation recorded for this company and year (if any)."""
    readable_company(ctx, company_id)
    fy = fy or current_financial_year()
    with session(request, ctx, readonly=True) as conn:
        rows = conn.execute(
            """SELECT r.id AS rule_id, r.code, r.name, r.law_reference, r.applies_to_description, r.trigger_description,
                      r.inputs_needed, r.decides, r.responsible_party, r.frequency,
                      e.id AS evaluation_id, e.status, e.applies, e.evaluated_on, e.notes, e.inputs, e.updated_at
               FROM core.rule_definition r
               LEFT JOIN LATERAL (SELECT * FROM core.rule_evaluation x
                                  WHERE x.rule_id = r.id AND x.company_id = %(cid)s AND x.financial_year = %(fy)s
                                    AND NOT x.is_archived ORDER BY x.evaluated_on DESC LIMIT 1) e ON TRUE
               WHERE r.is_active AND NOT r.is_archived ORDER BY r.code""", {"cid": company_id, "fy": fy}).fetchall()
        computed = {
            "RESIDENT_DIRECTOR": request.app.state.engine.view_rows(conn, "v_rule_resident_director", ctx,
                                                                   company_id=company_id)["rows"],
            "WOMAN_DIRECTOR": request.app.state.engine.view_rows(conn, "v_rule_woman_director", ctx,
                                                                company_id=company_id)["rows"],
        }
    return ok({"fy": fy, "rules": rows, "computed": computed})
