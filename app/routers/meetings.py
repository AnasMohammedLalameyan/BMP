"""Minutes & Meetings: the meetings book for a company, one meeting in full, and attendance by roster."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request

from ..access import UserCtx
from ..deps import current_user, readable_company, session
from ..errors import ApiError, bad_request, forbidden
from ..responses import ok

router = APIRouter(tags=["meetings"])

MEETING_SQL = """
SELECT m.*, (SELECT lv.label FROM core.lookup_value lv WHERE lv.id = m.meeting_type_id) AS meeting_type,
       (SELECT lv.code FROM core.lookup_value lv WHERE lv.id = m.meeting_type_id) AS meeting_type_code,
       (SELECT lv.label FROM core.lookup_value lv WHERE lv.id = m.venue_mode_id) AS venue_mode,
       (SELECT c.name FROM core.committee c WHERE c.id = m.committee_id) AS committee,
       (SELECT d.full_name FROM core.directorship ds JOIN core.director d ON d.id = ds.director_id
         WHERE ds.id = m.chairperson_directorship_id) AS chairperson
FROM core.meeting m WHERE NOT m.is_archived AND {where} ORDER BY m.meeting_date DESC, m.id DESC
"""


def _attach(conn, meetings: list[dict]) -> None:
    ids = [m["id"] for m in meetings]
    agenda: dict = {}
    attend: dict = {}
    if ids:
        for r in conn.execute("SELECT id, meeting_id, item_no, text FROM core.meeting_agenda_item "
                              "WHERE meeting_id = ANY(%s::bigint[]) AND NOT is_archived ORDER BY item_no", (ids,)):
            agenda.setdefault(r["meeting_id"], []).append(r)
        for r in conn.execute(
                """SELECT a.id, a.meeting_id, a.attendee_type, a.directorship_id, a.shareholder_id, a.attended, a.mode,
                          coalesce(d.full_name, s.name) AS name
                   FROM core.meeting_attendance a
                   LEFT JOIN core.directorship ds ON ds.id = a.directorship_id
                   LEFT JOIN core.director d ON d.id = ds.director_id
                   LEFT JOIN core.shareholder s ON s.id = a.shareholder_id
                   WHERE a.meeting_id = ANY(%s::bigint[]) AND NOT a.is_archived ORDER BY name""", (ids,)):
            attend.setdefault(r["meeting_id"], []).append(r)
    for m in meetings:
        m["agenda"] = agenda.get(m["id"], [])
        m["attendance"] = attend.get(m["id"], [])


@router.get("/companies/{company_id}/meetings-book")
def meetings_book(company_id: int, request: Request, fy: str | None = None, ctx: UserCtx = Depends(current_user)):
    readable_company(ctx, company_id)
    where = "m.company_id = %(cid)s" + (" AND m.financial_year = %(fy)s" if fy else "")
    with session(request, ctx, readonly=True) as conn:
        meetings = conn.execute(MEETING_SQL.format(where=where), {"cid": company_id, "fy": fy}).fetchall()
        _attach(conn, meetings)
    return ok({"meetings": meetings})


@router.get("/meetings/{meeting_id}/detail")
def meeting_detail(meeting_id: int, request: Request, ctx: UserCtx = Depends(current_user)):
    with session(request, ctx, readonly=True) as conn:
        meetings = conn.execute(MEETING_SQL.format(where="m.id = %(id)s AND m.company_id = ANY(%(ids)s::bigint[])"),
                                {"id": meeting_id, "ids": ctx.readable}).fetchall()
        if not meetings:
            raise ApiError(404, "not_found", "Meeting not found")
        m = meetings[0]
        _attach(conn, meetings)
        # directors on the board on the day of the meeting - the roster to tick attendance against
        m["roster"] = conn.execute(
            """SELECT ds.id AS directorship_id, d.full_name,
                      (SELECT lv.label FROM core.directorship_role r JOIN core.lookup_value lv ON lv.id = r.designation_id
                        WHERE r.directorship_id = ds.id AND NOT r.is_archived
                        ORDER BY (r.end_date IS NULL) DESC, r.start_date DESC LIMIT 1) AS designation
               FROM core.directorship ds JOIN core.director d ON d.id = ds.director_id
               WHERE ds.company_id = %(cid)s AND NOT ds.is_archived AND ds.start_date <= %(d)s
                 AND (ds.end_date IS NULL OR ds.end_date >= %(d)s) ORDER BY d.full_name""",
            {"cid": m["company_id"], "d": m["meeting_date"]}).fetchall()
        m["documents"] = conn.execute(
            """SELECT doc.id, doc.filename, doc.version, e.note,
                      (SELECT t.name FROM core.document_type t WHERE t.id = doc.document_type_id) AS document_type
               FROM core.evidence_link e JOIN core.document doc ON doc.id = e.document_id
               WHERE e.entity_type = 'meeting' AND e.entity_id = %(id)s AND NOT e.is_archived AND NOT doc.is_archived
               ORDER BY doc.created_at""", {"id": meeting_id}).fetchall()
    return ok({"meeting": m})


@router.put("/meetings/{meeting_id}/attendance")
def save_attendance(meeting_id: int, request: Request, payload: dict = Body(...), ctx: UserCtx = Depends(current_user)):
    """payload: {"rows": [{"directorship_id": 12, "attended": true, "mode": "Physical"}, ...]}
    Creates or updates one attendance row per director; never deletes (set attended=false instead)."""
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise bad_request("rows must be a list")
    engine = request.app.state.engine
    saved = 0
    with session(request, ctx) as conn:
        meeting = engine.get(conn, "meeting", ctx, str(meeting_id))
        if meeting["company_id"] not in ctx.writable:
            raise forbidden("You have read-only access to this company")
        for item in rows:
            did = item.get("directorship_id")
            if not did:
                raise bad_request("Each row needs a directorship_id")
            existing = conn.execute(
                "SELECT id FROM core.meeting_attendance WHERE meeting_id = %s AND directorship_id = %s AND NOT is_archived",
                (meeting_id, did)).fetchone()
            body = {"attended": bool(item.get("attended")), "mode": item.get("mode") or None}
            if existing:
                engine.update(conn, "meeting_attendance", ctx, str(existing["id"]), body)
            else:
                engine.create(conn, "meeting_attendance", ctx, {
                    "meeting_id": meeting_id, "attendee_type": "director", "directorship_id": did, **body})
            saved += 1
        attended = conn.execute("SELECT count(*) AS n FROM core.meeting_attendance WHERE meeting_id = %s "
                                "AND attended AND NOT is_archived", (meeting_id,)).fetchone()["n"]
    return ok({"saved": saved, "attended": attended})
