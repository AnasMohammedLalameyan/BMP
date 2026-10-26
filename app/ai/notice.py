"""Capability 3: draft a meeting notice for review, and send it only on an explicit approval.

Recipients and every statutory detail come from the database through code (always filtered by the meeting's company);
the model writes one short covering paragraph and never sees a name, an email or a date. Nothing is sent by drafting.
"""
from __future__ import annotations

import hashlib
import logging
import re
import smtplib
import threading
from datetime import date
from email.message import EmailMessage

from jinja2 import Environment, StrictUndefined

from ..errors import ApiError, conflict
from ..minutes_compliance import BY_KEY
from ..minutes_service import one
from .llm import invoke_structured
from .schemas import NoticeCover
from .settings import AiSettings
from .suggest import prompt

log = logging.getLogger("bmp.ai")

NOTICE = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True, autoescape=False).from_string(
    """NOTICE OF {{ title | upper }}

{{ company }}

Notice is hereby given that a {{ title }} of {{ company }} will be held on {{ when }}{{ where }}.
{% if venue %}
Venue: {{ venue }}
{% endif %}

Agenda
{% for a in agenda %}
{{ loop.index }}. {{ a }}
{% endfor %}
{% if notice_date %}

Date of notice: {{ notice_date }}
{% endif %}

By order of the Board
{{ company }}
""")

_SENT: set[str] = set()
_sent_lock = threading.Lock()


def _long(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d %B %Y").lstrip("0") if iso else ""


def gather(conn, company_id: int, register: str, meeting_id: int) -> dict:
    """The meeting and its recipients, read with the company named explicitly. Raises 404 if it is not this company's."""
    m = one(conn, company_id, meeting_id)
    if m is None or m["register"] != register:
        raise ApiError(404, "not_found", "Meeting not found")
    row = conn.execute("SELECT m.venue, m.committee_id, c.name AS company FROM core.meeting m "
                       "JOIN core.company c ON c.id = m.company_id WHERE m.id = %s AND m.company_id = %s",
                       (meeting_id, company_id)).fetchone()
    on = date.fromisoformat(m["meeting_date"])
    recipients: dict[str, dict] = {}

    def add(name, email, role):
        key = (email or name).strip().lower()
        if key and key not in recipients:
            recipients[key] = {"name": name, "email": (email or "").strip(), "role": role}

    if row["committee_id"]:
        who = conn.execute(
            """SELECT d.full_name, d.email FROM core.committee_member cm
               JOIN core.committee c ON c.id = cm.committee_id AND c.company_id = %(c)s
               JOIN core.directorship ds ON ds.id = cm.directorship_id AND ds.company_id = %(c)s
               JOIN core.director d ON d.id = ds.director_id
               WHERE cm.committee_id = %(cm)s AND NOT cm.is_archived AND cm.start_date <= %(d)s
                 AND (cm.end_date IS NULL OR cm.end_date >= %(d)s) ORDER BY d.full_name""",
            {"c": company_id, "cm": row["committee_id"], "d": on}).fetchall()
    else:
        who = conn.execute(
            """SELECT d.full_name, d.email FROM core.directorship ds JOIN core.director d ON d.id = ds.director_id
               WHERE ds.company_id = %(c)s AND NOT ds.is_archived AND ds.start_date <= %(d)s
                 AND (ds.end_date IS NULL OR ds.end_date >= %(d)s) ORDER BY d.full_name""",
            {"c": company_id, "d": on}).fetchall()
    for r in who:
        add(r["full_name"], r["email"], "Director")
    if register in ("agm", "egm"):
        for r in conn.execute(
                """SELECT DISTINCT s.name, s.email FROM core.shareholding h JOIN core.shareholder s ON s.id = h.shareholder_id
                   WHERE h.company_id = %(c)s AND NOT h.is_archived AND h.valid_from <= %(d)s
                     AND (h.valid_to IS NULL OR h.valid_to >= %(d)s) ORDER BY s.name""", {"c": company_id, "d": on}):
            add(r["name"], r["email"], "Shareholder")
        for r in conn.execute(
                """SELECT name, email FROM core.auditor WHERE company_id = %(c)s AND NOT is_archived
                     AND (account_period_from IS NULL OR account_period_from <= %(d)s)
                     AND (account_period_to IS NULL OR account_period_to >= %(d)s) ORDER BY name""",
                {"c": company_id, "d": on}):
            add(r["name"], r["email"], "Auditor")
    return {"meeting": m, "company": row["company"], "venue": row["venue"], "title": BY_KEY[register][1],
            "register": register, "recipients": list(recipients.values())}


def render(ctx: dict) -> tuple[str, str, list[str]]:
    """(subject, notice text, details still missing). Missing details are listed, never invented."""
    m = ctx["meeting"]
    missing = []
    agenda = [a["text"] for a in m["agenda"] if (a["text"] or "").strip()]
    if not agenda:
        missing.append("Agenda")
    if not m["meeting_time"]:
        missing.append("Time of the meeting")
    if m["mode"] == "Physical" and not ctx["venue"]:
        missing.append("Venue")
    if not m["mode"]:
        missing.append("Mode of the meeting")
    where = {"Physical": "", "Video conferencing": " through video conferencing",
             "OAVM": " through other audio visual means"}.get(m["mode"] or "", "")
    when = _long(m["meeting_date"]) + (f" at {m['meeting_time']}" if m["meeting_time"] else "")
    text = NOTICE.render(title=ctx["title"], company=ctx["company"], when=when, where=where, venue=ctx["venue"] or "",
                         agenda=agenda, notice_date=_long(m["notice_date"]))
    subject = f"Notice of {ctx['title']} - {ctx['company']} - {_long(m['meeting_date'])}"
    return subject, text.strip() + "\n", missing


def fingerprint(subject: str, notice: str, recipients: list[dict]) -> str:
    h = hashlib.sha256()
    for part in (subject, notice, *sorted(f"{r['name']}|{r['email']}" for r in recipients)):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def draft_cover(s: AiSettings, ctx: dict) -> str:
    """The model sees only the kind of meeting: no names, emails, dates or agenda."""
    out = invoke_structured(s, "chat", prompt("notice_cover_v1.txt"), f"Kind of meeting: {ctx['title']}", NoticeCover)
    cover = out.cover.strip()
    if re.search(r"\[[^\]]*\]", cover):                       # invented fill-in blanks: use the plain standard wording
        cover = ("Dear {recipient_name},\nPlease find below the formal notice of the meeting. "
                 "Kindly let us know if you have any questions.")
    if "{recipient_name}" not in cover:
        cover = "Dear {recipient_name},\n" + cover
    return cover[:1500]


def send(s: AiSettings, *, meeting_id: int, subject: str, notice: str, cover: str, recipients: list[dict],
         approver_id: int, smtp_factory=None) -> list[dict]:
    """One message per recipient. Sandbox (the default, and always in dummy-data mode) sends only to the local test
    mail server. A recipient without an email address is reported, not skipped silently. Never retried."""
    key = f"{meeting_id}:{fingerprint(subject, notice + cover, recipients)}"
    with _sent_lock:
        if key in _SENT:
            raise conflict("This notice has already been sent.", "already_sent")
        _SENT.add(key)
    sandbox = s.smtp_sandbox or s.data_mode != "real"
    host, port = ("localhost", s.smtp_port) if sandbox else (s.smtp_host, s.smtp_port)
    results = []
    smtp = None
    try:
        smtp = (smtp_factory or smtplib.SMTP)(host, port, timeout=10)
    except Exception as e:                                                   # noqa: BLE001
        log.warning("notice send: mail server unreachable (%s)", type(e).__name__)
    for r in recipients:
        if not r["email"]:
            results.append({"name": r["name"], "status": "no_email"})
            continue
        if smtp is None:
            results.append({"name": r["name"], "status": "failed"})
            continue
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = subject, s.smtp_from or "notices@localhost", r["email"]
        msg.set_content(cover.replace("{recipient_name}", r["name"]) + "\n\n" + notice)
        try:
            smtp.send_message(msg)
            results.append({"name": r["name"], "status": "sent"})
        except Exception as e:                                               # noqa: BLE001
            log.warning("notice send: failed for one recipient (%s)", type(e).__name__)
            results.append({"name": r["name"], "status": "failed"})
    if smtp is not None:
        try:
            smtp.quit()
        except Exception:                                                    # noqa: BLE001
            pass
    log.info("notice approved and sent meeting=%s approver=%s sandbox=%s sent=%d of %d", meeting_id, approver_id,
             sandbox, sum(1 for x in results if x["status"] == "sent"), len(results))
    return results
