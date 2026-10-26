"""Capability 2: turn a sentence into a pre-filled "Add meeting" form. The model parses; code matches the company
against the companies this person may WRITE to, checks the register and every date, and asks when anything is missing.
Nothing is created: the person reviews the pre-filled form and saves it with the normal Save."""
from __future__ import annotations

import re

from ..minutes_compliance import BY_KEY
from .llm import invoke_structured
from .masking import mask
from .schemas import IntakePlan
from .settings import AiSettings
from .suggest import normalize_date, normalize_mode, normalize_time, prompt

LABEL = {"register": "Which meeting (board, a committee, AGM or EGM)", "company": "Which company",
         "meeting_date": "Date of the meeting"}


def match_company(name: str | None, companies: list[dict]) -> tuple[dict | None, str | None]:
    """(company, question). Only companies the person can write to are candidates; ambiguity is asked, never guessed."""
    if not name:
        return None, None
    n = re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()
    exact = [c for c in companies if re.sub(r"[^a-z0-9 ]", "", c["name"].lower()).strip() == n]
    hits = exact or [c for c in companies if n and (n in c["name"].lower() or
                                                    all(t in c["name"].lower() for t in n.split()))]
    if len(hits) == 1:
        return hits[0], None
    if not hits:
        return None, f"I could not find a company called \"{name}\" that you can add meetings to."
    return None, "That could be any of: " + ", ".join(c["name"] for c in hits) + ". Which one?"


def plan(s: AiSettings, text: str, companies: list[dict], chosen: dict | None, *, meta: dict | None = None) -> dict:
    masked, _ = mask(text[:2000])
    raw = invoke_structured(s, "extract", prompt("intake_v1.txt"), masked, IntakePlan, meta=meta)
    missing: list[str] = []
    question = None
    company = chosen
    if company is None:
        company, question = match_company(raw.company, companies)
        if company is None and question is None:
            missing.append(LABEL["company"])
    register = raw.register_key if raw.register_key in BY_KEY else None
    if register is None:
        missing.append(LABEL["register"])
    fields = {}
    for key, norm in (("meeting_date", normalize_date), ("notice_date", normalize_date),
                      ("meeting_time", normalize_time), ("mode", normalize_mode)):
        v = norm(getattr(raw, key) or "")
        if v:
            fields[key] = v
    if (raw.chairman or "").strip():
        fields["chairman"] = re.sub(r"\s+", " ", raw.chairman).strip()[:200]
    if "meeting_date" not in fields:
        missing.append(LABEL["meeting_date"])
    agenda = [re.sub(r"\s+", " ", a).strip()[:500] for a in raw.agenda if a and a.strip()][:30]
    return {"register": register, "company_id": company["id"] if company else None,
            "company_name": company["name"] if company else None, "fields": fields, "agenda": agenda,
            "missing": missing, "question": question}
