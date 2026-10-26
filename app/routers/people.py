"""Directors & KMP register for one company, and adding a person to a board in one step.

A person (core.director) is entered once and reused ("Don't ask twice", matched on DIN). Each time
they serve on a company's board that is a separate stint (core.directorship), and their
designations within the stint are core.directorship_role rows - so history is never overwritten.
"""
from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Body, Depends, Query, Request

from ..access import Scope, UserCtx
from ..deps import current_user, readable_company, session, writable_company
from ..errors import ApiError, bad_request
from ..responses import ok

router = APIRouter(tags=["people"])

REGISTER_SQL = """
SELECT ds.id AS directorship_id, ds.director_id, d.full_name, d.din, d.gender, d.email, d.phone, d.address,
       d.date_of_birth, d.nationality, d.dsc_valid_until, d.updated_at AS director_updated_at,
       CASE WHEN d.date_of_birth IS NULL THEN NULL
            ELSE EXTRACT(YEAR FROM age(d.date_of_birth))::int END AS age_years,
       ds.start_date, ds.end_date, ds.cessation_reason, ds.is_board_member, ds.is_whole_time, ds.is_independent,
       ds.is_nominee, ds.is_additional, ds.is_alternate, ds.retires_by_rotation, ds.is_signatory, ds.shares_held,
       ds.updated_at AS directorship_updated_at,
       (SELECT lv.label FROM core.lookup_value lv WHERE lv.id = ds.director_category_id) AS category,
       (SELECT lv.label FROM core.directorship_role r JOIN core.lookup_value lv ON lv.id = r.designation_id
         WHERE r.directorship_id = ds.id AND NOT r.is_archived
         ORDER BY (r.end_date IS NULL) DESC, r.start_date DESC LIMIT 1) AS designation,
       (SELECT lv.code FROM core.directorship_role r JOIN core.lookup_value lv ON lv.id = r.designation_id
         WHERE r.directorship_id = ds.id AND NOT r.is_archived
         ORDER BY (r.end_date IS NULL) DESC, r.start_date DESC LIMIT 1) AS designation_code,
       EXISTS (SELECT 1 FROM core.committee_member cm WHERE cm.directorship_id = ds.id AND NOT cm.is_archived
                AND (cm.end_date IS NULL OR cm.end_date >= current_date)) AS on_committee,
       (ds.end_date IS NULL OR ds.end_date >= current_date) AS is_current
FROM core.directorship ds
JOIN core.director d ON d.id = ds.director_id
WHERE ds.company_id = %(cid)s AND NOT ds.is_archived {ceased}
ORDER BY (ds.end_date IS NULL OR ds.end_date >= current_date) DESC, ds.start_date, d.full_name
"""


def fy_window(fy: str) -> tuple[date, date]:
    """The April-March window of a financial year written like 2024-25 (the same convention as current_financial_year())."""
    m = re.fullmatch(r"(\d{4})-(\d{2})", fy or "")
    if not m or int(m.group(2)) != (int(m.group(1)) + 1) % 100:
        raise bad_request("Financial year must look like 2024-25.", {"fy": "Financial year must look like 2024-25."})
    year = int(m.group(1))
    return date(year, 4, 1), date(year + 1, 3, 31)


def active_in_window(start: date, end: date | None, window_start: date, window_end: date) -> bool:
    """A board stint was active in the window when it overlaps it: it began on or before the window's last day and had not
    ended before the window's first day. (Mirrored by activeInFy() in static/scripts/util.js.)"""
    return start <= window_end and (end is None or end >= window_start)


@router.get("/companies/{company_id}/directors-register")
def register(company_id: int, request: Request, include_ceased: bool = True, fy: str | None = None,
             include_inactive: bool = True, ctx: UserCtx = Depends(current_user)):
    """Every board stint. Optional `fy` (2024-25) adds `active_in_fy` / `ceased_in_fy` to each row; with `include_inactive=false`
    it also drops the stints that were not active in that year. Without `fy` the answer is exactly as before."""
    readable_company(ctx, company_id)
    window = fy_window(fy) if fy else None
    sql = REGISTER_SQL.format(ceased="" if include_ceased else "AND (ds.end_date IS NULL OR ds.end_date >= current_date)")
    with session(request, ctx, readonly=True) as conn:
        rows = conn.execute(sql, {"cid": company_id}).fetchall()
    if window:
        for r in rows:
            r["active_in_fy"] = active_in_window(r["start_date"], r["end_date"], *window)
            r["ceased_in_fy"] = r["end_date"] is not None and window[0] <= r["end_date"] <= window[1]
        if not include_inactive:
            rows = [r for r in rows if r["active_in_fy"]]
    return ok({"rows": rows})


@router.post("/companies/{company_id}/directors-register")
def add_to_board(company_id: int, request: Request, payload: dict = Body(...), ctx: UserCtx = Depends(current_user)):
    """payload: {director: {...} | director_id, directorship: {start_date, ...}, designation_id?, designation_start?}"""
    writable_company(ctx, company_id)
    engine = request.app.state.engine
    person = dict(payload.get("director") or {})
    director_id = payload.get("director_id")
    ship = dict(payload.get("directorship") or {})
    if not ship.get("start_date"):
        raise bad_request("Please give the appointment date.", {"directorship.start_date": "Required"})
    with session(request, ctx) as conn:
        created_person = False
        if director_id:
            engine.get(conn, "director", ctx, str(director_id))              # must exist and be visible
        else:
            din = (person.get("din") or "").strip()
            existing = None
            if din:
                existing = conn.execute("SELECT id FROM core.director WHERE din = %s AND NOT is_archived",
                                        (din,)).fetchone()
            if existing:
                director_id = existing["id"]
            else:
                if not person.get("full_name"):
                    raise bad_request("Please give the person's name.", {"director.full_name": "Required"})
                director_id = engine.create(conn, "director", ctx, person)["id"]
                created_person = True
        ship.update({"company_id": company_id, "director_id": director_id})
        directorship = engine.create(conn, "directorship", ctx, ship)
        role = None
        if payload.get("designation_id"):
            role = engine.create(conn, "directorship_role", ctx, {
                "directorship_id": directorship["id"], "designation_id": payload["designation_id"],
                "start_date": payload.get("designation_start") or ship["start_date"]})
        row = conn.execute(REGISTER_SQL.format(ceased="AND ds.id = %(did)s"),
                           {"cid": company_id, "did": directorship["id"]}).fetchone()
    return ok({"row": row, "person_created": created_person, "role": role["id"] if role else None}, 201)


ROLES_SQL = """
SELECT ds.director_id, ds.id AS directorship_id, ds.company_id, c.name AS company_name, ds.start_date, ds.end_date,
       ds.is_independent, (ds.end_date IS NULL OR ds.end_date >= current_date) AS is_current,
       (SELECT lv.label FROM core.directorship_role r JOIN core.lookup_value lv ON lv.id = r.designation_id
         WHERE r.directorship_id = ds.id AND NOT r.is_archived
         ORDER BY (r.end_date IS NULL) DESC, r.start_date DESC LIMIT 1) AS designation
FROM core.directorship ds JOIN core.company c ON c.id = ds.company_id
WHERE ds.director_id = ANY(%(ids)s::bigint[]) AND ds.company_id = ANY(%(rids)s::bigint[]) AND NOT ds.is_archived AND NOT c.is_archived
ORDER BY ds.start_date DESC, ds.id DESC
"""


@router.get("/people/directors")
def all_directors(request: Request, q: str | None = None, limit: int = Query(2000, ge=1, le=5000),
                  ctx: UserCtx = Depends(current_user)):
    """One row per person, with their roles in every company the signed-in user may open.

    Who is listed follows the existing rule for people records: staff see every person, a client only people linked to
    their own company. Roles are always limited to the companies the user can read."""
    params: dict = {"limit": limit}
    scope = Scope(request.app.state.catalog).row_scope("director", "d", ctx, "read", params)
    where = ["NOT d.is_archived", f"({scope})"]
    if q and q.strip():
        params["q"] = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("""(d.full_name ILIKE %(q)s OR d.din ILIKE %(q)s OR EXISTS (
            SELECT 1 FROM core.directorship s JOIN core.company sc ON sc.id = s.company_id
            WHERE s.director_id = d.id AND NOT s.is_archived AND s.company_id = ANY(%(rids)s::bigint[]) AND sc.name ILIKE %(q)s))""")
    with session(request, ctx, readonly=True) as conn:
        people = conn.execute(
            f"""SELECT d.id, d.full_name, d.din, d.gender, d.nationality, d.email, d.phone FROM core.director d
                WHERE {" AND ".join(where)} ORDER BY d.full_name, d.id LIMIT %(limit)s""", params).fetchall()
        roles = conn.execute(ROLES_SQL, {"ids": [p["id"] for p in people], "rids": ctx.readable}).fetchall() if people else []
    by_person: dict = {}
    for r in roles:
        by_person.setdefault(r["director_id"], []).append(r)
    for p in people:
        p["roles"] = by_person.get(p["id"], [])
    return ok({"people": people, "total": len(people)})

