"""Activities Dashboard: reads and writes the normalised meeting tables in the shape the dashboard expects.

Everything that knows how a dashboard field maps to a database column lives in this module (see MEETING_COLUMNS,
MODE_TO_CODE and the _legacy / _meeting_values functions). Writes go through the application's entity engine, so
company access, validation, optimistic locking and the audit trigger work exactly as they do everywhere else.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from .access import UserCtx
from .errors import ApiError, bad_request, conflict
from .minutes_compliance import BY_KEY, REGISTERS, compute, standard_for

MODES = ["Physical", "Video conferencing", "OAVM"]
MODE_TO_CODE = {"Physical": "PHYSICAL", "Video conferencing": "VC", "OAVM": "VC"}      # OAVM is lossy: see log D3
CODE_TO_MODE = {"PHYSICAL": "Physical", "VC": "Video conferencing", "MIX": "Mix of both"}
MINUTES_STATUSES = ["Not drafted", "Draft circulated", "Finalised", "Signed", "Entered in Minutes Book"]
REG30 = ["NA", "Yes", "No"]

# dashboard field -> core.meeting column (text/date/int columns that are stored as they are typed)
MEETING_COLUMNS = {
    "notice_date": "notice_date", "invitees_present": "invitees_present", "leave_of_absence": "leave_of_absence",
    "attendance_sheet": "attendance_sheet", "minutes_status": "minutes_status",
    "draft_circulated": "draft_circulated_on", "signed_circulated": "signed_circulated_on",
    "entry_date": "entry_date", "signing_date": "signing_date", "signing_place": "signing_place",
    "signed_documents": "signed_documents", "comments": "remarks", "attendance_present": "attendance_present",
    "attendance_total": "attendance_total", "chairman": "chairperson_name",
}
DATE_FIELDS = {"notice_date", "draft_circulated", "signed_circulated", "entry_date", "signing_date"}
INT_FIELDS = {"attendance_present", "attendance_total"}
TEXT_LIMIT = {"signing_place": 200, "chairman": 200, "attendance_sheet": 500, "leave_of_absence": 500,
              "invitees_present": 1000, "signed_documents": 1000, "comments": 4000}

# which committee a register is: matched on the committee's name (companies word these differently)
COMMITTEE_PATTERN = {"audit": r"audit", "nrc": r"nominat|remunerat", "src": r"stakeholder|shareholder|investor",
                     "csr": r"\bcsr\b|corporate social", "rmc": r"\brisk\b"}
TYPE_REGISTER = {"BOARD": "board", "AGM": "agm", "EGM": "egm"}

_ids: dict = {}                     # lookup code -> id, resolved once per process (never hard-coded)


def fy_window(fy: str) -> tuple[date, date]:
    m = re.fullmatch(r"(\d{4})-(\d{2})", fy or "")
    if not m or int(m[2]) != (int(m[1]) + 1) % 100:
        raise bad_request("Financial year must look like 2025-26.", {"fy": "Invalid financial year"})
    y = int(m[1])
    return date(y, 4, 1), date(y + 1, 3, 31)


def fy_of(d: date) -> str:
    y = d.year if d.month >= 4 else d.year - 1
    return f"{y}-{(y + 1) % 100:02d}"


def register_of(type_code: str | None, committee_name: str | None) -> str | None:
    if type_code in TYPE_REGISTER:
        return TYPE_REGISTER[type_code]
    if type_code == "COMMITTEE" and committee_name:
        for key, pat in COMMITTEE_PATTERN.items():
            if re.search(pat, committee_name, re.I):
                return key
    return None


def registers_config() -> list[dict]:
    return [{"key": k, "name": n, "ref": ref, "min": mn, "committee": k in COMMITTEE_PATTERN,
             "standard": standard_for(k)} for k, n, ref, mn, _c, _t in REGISTERS]


def _lookup_id(conn, list_code: str, code: str) -> int:
    key = (list_code, code)
    if key not in _ids:
        row = conn.execute(
            "SELECT lv.id FROM core.lookup_value lv JOIN core.lookup_list ll ON ll.id = lv.list_id "
            "WHERE ll.code = %s AND lv.code = %s", (list_code, code)).fetchone()
        if row is None:
            raise ApiError(500, "lookup_missing", f"The standard list value {list_code}/{code} is missing.")
        _ids[key] = row["id"]
    return _ids[key]


def _check_register(register: str) -> None:
    if register not in BY_KEY:
        raise ApiError(404, "not_found", "Unknown register")


# ------------------------------------------------------------------ reading

def _time_text(start, end) -> str:
    def fmt(t):
        return t.strftime("%I:%M %p").lstrip("0") if t else ""
    if start and end:
        return f"{fmt(start)} to {fmt(end)}"
    return fmt(start) or fmt(end)


def _iso(v):
    return v.isoformat() if isinstance(v, (date, datetime)) else v


def fetch_year(conn, company_id: int, fy: str) -> list[dict]:
    """Every live meeting of the company whose date falls in the financial year, in the dashboard's shape."""
    start, end = fy_window(fy)
    rows = conn.execute(
        """SELECT m.*, lt.code AS type_code, vm.code AS venue_code, c.name AS committee_name, d.full_name AS chair_name
           FROM core.meeting m
           JOIN core.lookup_value lt ON lt.id = m.meeting_type_id
           LEFT JOIN core.lookup_value vm ON vm.id = m.venue_mode_id
           LEFT JOIN core.committee c ON c.id = m.committee_id
           LEFT JOIN core.directorship ds ON ds.id = m.chairperson_directorship_id
           LEFT JOIN core.director d ON d.id = ds.director_id
           WHERE m.company_id = %s AND NOT m.is_archived AND m.meeting_date BETWEEN %s AND %s
           ORDER BY m.meeting_date, m.id""", (company_id, start, end)).fetchall()
    ids = [r["id"] for r in rows]
    agenda: dict = {}
    attend: dict = {}
    if ids:
        for a in conn.execute(
                """SELECT id, meeting_id, item_no, text, reg30, forms, docs, bmp_comments FROM core.meeting_agenda_item
                   WHERE meeting_id = ANY(%s::bigint[]) AND NOT is_archived ORDER BY item_no, id""", (ids,)):
            agenda.setdefault(a["meeting_id"], []).append(a)
        for a in conn.execute(
                """SELECT a.meeting_id, a.directorship_id, a.attended, a.mode, d.full_name, ds.start_date, ds.end_date
                   FROM core.meeting_attendance a
                   JOIN core.directorship ds ON ds.id = a.directorship_id
                   JOIN core.director d ON d.id = ds.director_id
                   WHERE a.meeting_id = ANY(%s::bigint[]) AND NOT a.is_archived AND a.attendee_type = 'director'
                   ORDER BY d.full_name""", (ids,)):
            attend.setdefault(a["meeting_id"], []).append(a)
    return [_legacy(r, agenda.get(r["id"], []), attend.get(r["id"], [])) for r in rows
            if register_of(r["type_code"], r["committee_name"])]


def _legacy(m: dict, agenda: list[dict], attendance: list[dict]) -> dict:
    mode = CODE_TO_MODE.get(m["venue_code"]) if m["venue_code"] else None
    ticked = [a for a in attendance if a["attended"]]
    outside = [a["full_name"] for a in ticked
               if a["start_date"] > m["meeting_date"] or (a["end_date"] and a["end_date"] < m["meeting_date"])]
    return {
        "meeting_id": m["id"], "register": register_of(m["type_code"], m["committee_name"]),
        "meeting_date": _iso(m["meeting_date"]), "mode": mode, "notice_date": _iso(m["notice_date"]),
        "attendance_present": m["attendance_present"] if m["attendance_present"] is not None else len(ticked),
        "attendance_total": m["attendance_total"] if m["attendance_total"] is not None else len(attendance),
        "minutes_status": m["minutes_status"], "draft_circulated": _iso(m["draft_circulated_on"]),
        "signed_circulated": _iso(m["signed_circulated_on"]),
        "meeting_time": _time_text(m["start_time"], m["end_time"]),
        "chairman": m["chairperson_name"] or m["chair_name"] or "",
        "directors_present": ", ".join(a["full_name"] for a in ticked),
        "invitees_present": m["invitees_present"] or "", "leave_of_absence": m["leave_of_absence"] or "",
        "attendance_sheet": m["attendance_sheet"] or "", "entry_date": _iso(m["entry_date"]),
        "signing_date": _iso(m["signing_date"]), "signing_place": m["signing_place"],
        "signed_documents": m["signed_documents"] or "",
        "attendance": [{"directorship_id": a["directorship_id"], "attended": a["attended"], "mode": a["mode"]}
                       for a in attendance],
        "outside_directorship": outside,
        "agenda": [{"id": a["id"], "text": a["text"], "reg30": a["reg30"], "forms": a["forms"] or "",
                    "docs": a["docs"] or "", "comments": a["bmp_comments"] or ""} for a in agenda],
        "comments": m["remarks"] or "", "updated_at": m["updated_at"],
    }


def counts(conn, company_id: int, fy: str) -> dict:
    out = {k: 0 for k, *_ in REGISTERS}
    for m in fetch_year(conn, company_id, fy):
        out[m["register"]] += 1
    return {"counts": out}


def list_register(conn, company_id: int, fy: str, register: str) -> dict:
    _check_register(register)
    meetings = [m for m in fetch_year(conn, company_id, fy) if m["register"] == register]
    available = True
    if register in COMMITTEE_PATTERN:
        available = _committee_ids(conn, company_id, register) != []
    return {"meetings": meetings, "compliance": compute(register, meetings), "modes": MODES,
            "minutes_statuses": MINUTES_STATUSES, "committee_available": available,
            "standard": standard_for(register)}


def roster(conn, company_id: int, on: date) -> list[dict]:
    return conn.execute(
        """SELECT ds.id AS directorship_id, d.full_name,
                  (SELECT lv.label FROM core.directorship_role r JOIN core.lookup_value lv ON lv.id = r.designation_id
                    WHERE r.directorship_id = ds.id AND NOT r.is_archived
                    ORDER BY (r.end_date IS NULL) DESC, r.start_date DESC LIMIT 1) AS designation
           FROM core.directorship ds JOIN core.director d ON d.id = ds.director_id
           WHERE ds.company_id = %(cid)s AND NOT ds.is_archived AND ds.start_date <= %(d)s
             AND (ds.end_date IS NULL OR ds.end_date >= %(d)s) ORDER BY d.full_name""",
        {"cid": company_id, "d": on}).fetchall()


# ------------------------------------------------------------------ writing

def _committee_ids(conn, company_id: int, register: str) -> list[int]:
    pat = COMMITTEE_PATTERN[register]
    rows = conn.execute("SELECT id, name FROM core.committee WHERE company_id = %s AND NOT is_archived ORDER BY id",
                        (company_id,)).fetchall()
    return [r["id"] for r in rows if re.search(pat, r["name"], re.I)]


def _parse_date(v, field: str, errors: dict):
    if v in (None, ""):
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        errors[field] = "Use a valid date"
        return None


_T = re.compile(r"(\d{1,2}):(\d{2})\s*([AaPp][Mm])?")


def _parse_time(tok: str):
    m = _T.fullmatch(tok.strip())
    if not m:
        return None
    h, mi, ap = int(m[1]), int(m[2]), (m[3] or "").upper()
    if ap == "PM" and h < 12:
        h += 12
    if ap == "AM" and h == 12:
        h = 0
    if h > 23 or mi > 59:
        return None
    from datetime import time
    return time(h, mi)


def _times(text: str, errors: dict):
    text = (text or "").strip()
    if not text:
        return None, None
    parts = re.split(r"\s+(?:to|-|–)\s+", text, maxsplit=1, flags=re.I)
    start = _parse_time(parts[0])
    end = _parse_time(parts[1]) if len(parts) > 1 else None
    if start is None or (len(parts) > 1 and end is None):
        errors["meeting_time"] = "Use a form like 11:00 AM to 12:00 PM"
        return None, None
    return start, end


def _norm(name: str) -> str:
    return re.sub(r"[^a-z ]", "", re.sub(r"\b(mr|mrs|ms|dr|shri|smt)\b\.?", "", (name or "").lower())).strip()


def _meeting_values(body: dict, conn, company_id: int, on: date, errors: dict) -> dict:
    """Validate the whitelisted fields of a save and turn them into core.meeting columns."""
    v: dict = {"meeting_date": on, "financial_year": fy_of(on)}
    for field, col in MEETING_COLUMNS.items():
        if field not in body:
            continue
        raw = body[field]
        if field in DATE_FIELDS:
            v[col] = _parse_date(raw, field, errors)
        elif field in INT_FIELDS:
            if raw in (None, ""):
                v[col] = None
            else:
                try:
                    v[col] = int(raw)
                    if v[col] < 0:
                        raise ValueError
                except (TypeError, ValueError):
                    errors[field] = "Use a whole number"
        else:
            text = (str(raw).strip() if raw is not None else "") or None
            if text and len(text) > TEXT_LIMIT.get(field, 500):
                errors[field] = "Too long"
            if field == "minutes_status" and text and text not in MINUTES_STATUSES:
                errors[field] = "Not a valid status"
            v[col] = text
    if "mode" in body:
        mode = body["mode"] or None
        if mode and mode not in MODE_TO_CODE:
            errors["mode"] = "Not a valid mode"
        v["venue_mode_id"] = _lookup_id(conn, "MEETING_VENUE_MODE", MODE_TO_CODE[mode]) if mode in MODE_TO_CODE else None
    if "meeting_time" in body:
        v["start_time"], v["end_time"] = _times(body["meeting_time"], errors)
    return v


def _agenda_rows(body: dict, errors: dict) -> list[dict]:
    rows = []
    for i, a in enumerate(body.get("agenda") or []):
        if not isinstance(a, dict):
            continue
        text = str(a.get("text") or "").strip()
        if not text:
            continue                                  # rows with no text are dropped
        reg30 = a.get("reg30") or "NA"
        if reg30 not in REG30:
            errors[f"agenda.{i}.reg30"] = "Use NA, Yes or No"
        rows.append({"id": a.get("id"), "text": text[:4000], "reg30": reg30,
                     "forms": (str(a.get("forms") or "").strip() or None),
                     "docs": (str(a.get("docs") or "").strip() or None),
                     "bmp_comments": (str(a.get("comments") or "").strip() or None)})
    return rows


def _sync_agenda(conn, engine, ctx, meeting_id: int, rows: list[dict]) -> None:
    existing = {r["id"]: r for r in conn.execute(
        "SELECT id FROM core.meeting_agenda_item WHERE meeting_id = %s AND NOT is_archived", (meeting_id,))}
    keep = set()
    for n, r in enumerate(rows, 1):
        payload = {"item_no": n, "text": r["text"], "reg30": r["reg30"], "forms": r["forms"], "docs": r["docs"],
                   "bmp_comments": r["bmp_comments"]}
        if r["id"] in existing:
            engine.update(conn, "meeting_agenda_item", ctx, str(r["id"]), payload)
            keep.add(r["id"])
        else:
            engine.create(conn, "meeting_agenda_item", ctx, {"meeting_id": meeting_id, **payload})
    for aid in existing:
        if aid not in keep:
            engine.set_archived(conn, "meeting_agenda_item", ctx, str(aid), True)


def _sync_attendance(conn, engine, ctx, meeting_id: int, company_id: int, on: date, body: dict, mode_label, errors) -> None:
    if "attendance" not in body:
        return
    valid = {r["directorship_id"] for r in roster(conn, company_id, on)}
    wanted: dict[int, bool] = {}
    for a in body["attendance"] or []:
        try:
            did = int(a.get("directorship_id"))
        except (TypeError, ValueError):
            errors["attendance"] = "Each row needs a director"
            return
        if did not in valid:
            errors["attendance"] = "A director shown was not on the board on that date"
            return
        wanted[did] = wanted.get(did, False) or bool(a.get("attended"))      # one row per director, never two
    have: dict[int, list[int]] = {}
    for r in conn.execute("SELECT id, directorship_id FROM core.meeting_attendance WHERE meeting_id = %s "
                          "AND NOT is_archived AND attendee_type = 'director' ORDER BY id", (meeting_id,)):
        have.setdefault(r["directorship_id"], []).append(r["id"])
    for did, attended in wanted.items():
        ids = have.get(did, [])
        body_ = {"attended": attended, "mode": mode_label if attended else None}
        if ids:
            engine.update(conn, "meeting_attendance", ctx, str(ids[0]), body_)
            for extra in ids[1:]:
                engine.set_archived(conn, "meeting_attendance", ctx, str(extra), True)
        else:
            engine.create(conn, "meeting_attendance", ctx, {
                "meeting_id": meeting_id, "attendee_type": "director", "directorship_id": did, **body_})
    for did, ids in have.items():
        if did not in wanted:
            for aid in ids:
                engine.set_archived(conn, "meeting_attendance", ctx, str(aid), True)


def _chair_id(conn, company_id: int, on: date, name: str | None) -> int | None:
    if not name:
        return None
    target = _norm(name)
    for r in roster(conn, company_id, on):
        if _norm(r["full_name"]) == target:
            return r["directorship_id"]
    return None


def _finish_errors(errors: dict):
    if errors:
        raise bad_request("Some fields need attention.", errors)


def create_meeting(conn, engine, ctx: UserCtx, company_id: int, register: str, body: dict) -> dict:
    _check_register(register)
    errors: dict = {}
    on = _parse_date(body.get("meeting_date"), "meeting_date", errors)
    if on is None:
        errors.setdefault("meeting_date", "Date of meeting is required")
    _finish_errors(errors)
    values = _meeting_values(body, conn, company_id, on, errors)
    agenda = _agenda_rows(body, errors)
    _finish_errors(errors)

    type_code = BY_KEY[register][5]
    values["meeting_type_id"] = _lookup_id(conn, "MEETING_TYPE", type_code)
    values["company_id"] = company_id
    if register in COMMITTEE_PATTERN:
        ids = _committee_ids(conn, company_id, register)
        if not ids:
            raise conflict(f"This company has no {BY_KEY[register][1]} constituted. Add it in Master Data first.",
                           "no_committee")
        values["committee_id"] = ids[0]
    values["status"] = "held" if on <= date.today() else "planned"
    values["chairperson_directorship_id"] = _chair_id(conn, company_id, on, values.get("chairperson_name"))
    row = engine.create(conn, "meeting", ctx, values)
    mid = int(row["id"])
    _sync_agenda(conn, engine, ctx, mid, agenda)
    _sync_attendance(conn, engine, ctx, mid, company_id, on, body, CODE_TO_MODE.get(MODE_TO_CODE.get(body.get("mode"))), errors)
    _finish_errors(errors)
    return one(conn, company_id, mid)


def update_meeting(conn, engine, ctx: UserCtx, company_id: int, register: str, meeting_id: int, body: dict) -> dict:
    _check_register(register)
    current = one(conn, company_id, meeting_id)
    if current is None or current["register"] != register:
        raise ApiError(404, "not_found", "Meeting not found")
    errors: dict = {}
    on = _parse_date(body.get("meeting_date") or current["meeting_date"], "meeting_date", errors)
    _finish_errors(errors)
    values = _meeting_values(body, conn, company_id, on, errors)
    agenda = _agenda_rows(body, errors) if "agenda" in body else None
    _finish_errors(errors)
    if "chairman" in body:
        values["chairperson_directorship_id"] = _chair_id(conn, company_id, on, values.get("chairperson_name"))
    if body.get("updated_at"):
        values["updated_at"] = body["updated_at"]
    engine.update(conn, "meeting", ctx, str(meeting_id), values)
    if agenda is not None:
        _sync_agenda(conn, engine, ctx, meeting_id, agenda)
    mode = body.get("mode") or current["mode"]
    _sync_attendance(conn, engine, ctx, meeting_id, company_id, on, body, CODE_TO_MODE.get(MODE_TO_CODE.get(mode)), errors)
    _finish_errors(errors)
    return one(conn, company_id, meeting_id)


def one(conn, company_id: int, meeting_id: int) -> dict | None:
    row = conn.execute("SELECT meeting_date FROM core.meeting WHERE id = %s AND company_id = %s AND NOT is_archived",
                       (meeting_id, company_id)).fetchone()
    if row is None:
        return None
    fy = fy_of(row["meeting_date"])
    return next((m for m in fetch_year(conn, company_id, fy) if m["meeting_id"] == meeting_id), None)
