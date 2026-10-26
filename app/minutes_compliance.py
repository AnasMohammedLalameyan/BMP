"""Secretarial Standards checks for a register's meetings in one financial year. Pure: no database.

Each meeting is the legacy payload dict (see minutes_service). Status values:
  ok        the standard is met
  attention the standard is not met
  unknown   the data the check needs was not recorded (neither pass nor fail)
A shortfall in the NUMBER of meetings is shown only by the `min` chip: it cannot be told apart from
"meetings not entered yet", so it never turns another check into a violation.
"""
from __future__ import annotations

import math
from datetime import date

MAX_GAP_DAYS = 120
NOTICE_DAYS_SS1 = 7
NOTICE_CLEAR_DAYS_SS2 = 21
MINUTES_SIGN_DAYS = 30
DRAFT_CIRCULATE_DAYS = 15

REGISTERS = [
    # key, name, statutory reference, minimum meetings a year, committee name (None = not a committee), meeting type code
    ("board", "Board Meetings", "Sec 173 / SS-1", 4, None, "BOARD"),
    ("audit", "Audit Committee", "Sec 177 / Reg 18", 4, "Audit Committee", "COMMITTEE"),
    ("nrc", "Nomination & Remuneration Committee", "Sec 178 / Reg 19", 1, "Nomination and Remuneration Committee", "COMMITTEE"),
    ("src", "Stakeholders Relationship Committee", "Sec 178 / Reg 20", 1, "Stakeholders Relationship Committee", "COMMITTEE"),
    ("csr", "CSR Committee", "Sec 135", 1, "CSR Committee", "COMMITTEE"),
    ("rmc", "Risk Management Committee", "Reg 21", 2, "Risk Management Committee", "COMMITTEE"),
    ("agm", "Annual General Meeting", "Sec 96 / SS-2", 1, None, "AGM"),
    ("egm", "Extraordinary General Meeting", "Sec 100 / SS-2", 0, None, "EGM"),
]
BY_KEY = {r[0]: r for r in REGISTERS}


def _d(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _chip(key, label, status, detail=""):
    return {"key": key, "label": label, "status": status, "detail": detail}


def standard_for(register: str) -> str:
    return "SS-2" if register in ("agm", "egm") else "SS-1"


def _quorum(meetings):
    """(judged, short): present is the count of ticked attendees, preferred over the typed number."""
    judged = short = 0
    for m in meetings:
        att = m.get("attendance") or []
        ticked = sum(1 for a in att if a.get("attended"))
        present = ticked if ticked else m.get("attendance_present")
        if present is None:
            continue
        total = m.get("attendance_total") or len(att) or present
        judged += 1
        if present < max(2, math.ceil(total / 3)):
            short += 1
    return judged, short


def compute(register: str, meetings: list[dict]) -> list[dict]:
    minimum = BY_KEY[register][3]
    n = len(meetings)
    out = []
    if minimum > 0:
        out.append(_chip("min", f"At least {minimum} meeting{'s' if minimum != 1 else ''} a year",
                         "ok" if n >= minimum else "attention", f"{n} recorded"))
    if n == 0:
        return out

    dated = sorted(((_d(m.get("meeting_date")), m) for m in meetings if _d(m.get("meeting_date"))),
                   key=lambda t: t[0])

    if register in ("board", "audit") and len(dated) >= 2:
        worst = max((b[0] - a[0]).days for a, b in zip(dated, dated[1:]))
        out.append(_chip("gap", f"Gap of {MAX_GAP_DAYS} days or less between meetings",
                         "ok" if worst <= MAX_GAP_DAYS else "attention", f"longest gap {worst} days"))

    ss2 = standard_for(register) == "SS-2"
    pairs = [(_d(m.get("notice_date")), _d(m.get("meeting_date"))) for m in meetings]
    pairs = [(nd, md) for nd, md in pairs if nd and md]
    label = f"Notice of {NOTICE_CLEAR_DAYS_SS2} clear days" if ss2 else f"Notice of {NOTICE_DAYS_SS1} days"
    if not pairs:
        out.append(_chip("notice", label, "unknown", "notice dates not recorded"))
    else:
        def short_notice(nd, md):
            diff = (md - nd).days
            return diff - 1 < NOTICE_CLEAR_DAYS_SS2 if ss2 else diff < NOTICE_DAYS_SS1
        bad = sum(1 for nd, md in pairs if short_notice(nd, md))
        out.append(_chip("notice", label, "attention" if bad else "ok",
                         f"{bad} of {len(pairs)} short notice" if bad else f"{len(pairs)} meeting(s) OK"))

    if register == "board":
        judged, short = _quorum(meetings)
        if not judged:
            out.append(_chip("quorum", "Quorum present (Sec 174)", "unknown", "attendance not recorded"))
        else:
            out.append(_chip("quorum", "Quorum present (Sec 174)", "attention" if short else "ok",
                             f"{short} of {judged} short of quorum" if short else f"{judged} meeting(s) OK"))
        with_att = [m for m in meetings if m.get("attendance")]
        if not with_att:
            out.append(_chip("board_register", "Only directors in office shown present", "unknown",
                             "attendance not recorded"))
        else:
            outside = [m for m in with_att if m.get("outside_directorship")]
            out.append(_chip("board_register", "Only directors in office shown present",
                             "attention" if outside else "ok",
                             f"{len(outside)} meeting(s) to verify" if outside else f"{len(with_att)} meeting(s) OK"))

    signed = [(_d(m.get("meeting_date")), _d(m.get("signing_date"))) for m in meetings]
    signed = [(md, sd) for md, sd in signed if md and sd]
    lab = f"Minutes signed within {MINUTES_SIGN_DAYS} days"
    if not signed:
        out.append(_chip("minutes", lab, "unknown", "signing dates not recorded"))
    else:
        late = sum(1 for md, sd in signed if (sd - md).days > MINUTES_SIGN_DAYS)
        out.append(_chip("minutes", lab, "attention" if late else "ok",
                         f"{late} of {len(signed)} signed late" if late else f"{len(signed)} meeting(s) OK"))

    if register == "board":
        drafts = [(_d(m.get("meeting_date")), _d(m.get("draft_circulated"))) for m in meetings]
        drafts = [(md, dd) for md, dd in drafts if md and dd]
        if drafts:
            late = sum(1 for md, dd in drafts if (dd - md).days > DRAFT_CIRCULATE_DAYS)
            out.append(_chip("draft", f"Draft minutes circulated within {DRAFT_CIRCULATE_DAYS} days",
                             "attention" if late else "ok",
                             f"{late} of {len(drafts)} late" if late else f"{len(drafts)} meeting(s) OK"))
    return out
