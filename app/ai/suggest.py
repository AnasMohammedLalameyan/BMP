"""Capability 1: read a company document and SUGGEST meeting details.

The model only reads; code decides what is trusted. Every value must come with a quote that appears word for word on
the stated page, must pass the same normalisation the form uses, and two independent passes are compared. Nothing is
saved here: the person reviews the suggestions and the existing Save does the writing.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from ..minutes_extract import _docs_for, _forms_for, display_title
from .llm import invoke_structured
from .masking import mask, unmask
from .schemas import MeetingExtraction
from .settings import AiSettings

PROMPTS = Path(__file__).parent / "prompts"

# key -> (label shown in words, kind)
FIELDS = {
    "meeting_date": ("Date of meeting", "date"), "notice_date": ("Date of notice", "date"),
    "meeting_time": ("Time", "time"), "mode": ("Mode", "mode"), "chairman": ("Chairman", "text"),
    "directors_present": ("Directors present", "text"), "invitees_present": ("Invitees present", "text"),
    "leave_of_absence": ("Leave of absence", "text"), "signing_date": ("Date of signing", "date"),
    "signing_place": ("Place of signing", "text"),
}

_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8").split("\n", 1)[1].strip()


# ------------------------------------------------------------------ normalisation (the same forms the screen uses)

def _iso(d: int, m: int, y: int) -> str | None:
    if y < 100:
        y += 2000
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def normalize_date(text: str) -> str | None:
    """12th Sept 2026, September 12, 2026, 12/09/2026, 12.09.26 and 2026-09-12 all become 2026-09-12."""
    t = (text or "").strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return _iso(int(m[3]), int(m[2]), int(m[1]))
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", t)
    if m:
        return _iso(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([A-Za-z]{3,9})\.?,?\s+(\d{4})", t)
    if m and m[2][:3].lower() in _MONTHS:
        return _iso(int(m[1]), _MONTHS.index(m[2][:3].lower()) + 1, int(m[3]))
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", t)
    if m and m[1][:3].lower() in _MONTHS:
        return _iso(int(m[2]), _MONTHS.index(m[1][:3].lower()) + 1, int(m[3]))
    return None


def _one_time(tok: str) -> str | None:
    m = re.fullmatch(r"\s*(\d{1,2})(?:[:.](\d{2}))?\s*([AaPp])\.?\s?[Mm]\.?\s*", tok)
    if not m:
        return None
    h, mi = int(m[1]), int(m[2] or 0)
    if not (1 <= h <= 12 and mi < 60):
        return None
    return f"{h}:{mi:02d} {'AM' if m[3].lower() == 'a' else 'PM'}"


def normalize_time(text: str) -> str | None:
    parts = re.split(r"\s+(?:to|-|–|till|until)\s+", (text or "").strip(), maxsplit=1, flags=re.I)
    first = _one_time(parts[0])
    if first is None:
        return None
    if len(parts) == 1:
        return first
    second = _one_time(parts[1])
    return f"{first} to {second}" if second else None


def normalize_mode(text: str) -> str | None:
    t = (text or "").lower()
    if "oavm" in t or "other audio" in t:
        return "OAVM"
    if any(w in t for w in ("video", " vc", "virtual", "online")) or t.strip() == "vc":
        return "Video conferencing"
    if "physical" in t or "in person" in t or "in-person" in t:
        return "Physical"
    return None


def normalize(kind: str, value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if kind == "date":
        return normalize_date(value)
    if kind == "time":
        return normalize_time(value)
    if kind == "mode":
        return normalize_mode(value)
    return re.sub(r"\s+", " ", value)[:1000]


# ------------------------------------------------------------------ verification

def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().casefold()


def verify_quote(quote: str, claimed_page: int, pages: list[str]) -> int | None:
    """The page the quote really appears on (word for word, spacing and case ignored), or None: the claim is rejected."""
    q = _squash(quote)
    if len(q) < 3:
        return None
    order = ([claimed_page - 1] if 1 <= claimed_page <= len(pages) else []) + list(range(len(pages)))
    for i in order:
        if q in _squash(pages[i]):
            return i + 1
    return None


def pieces(pages: list[str], max_tokens: int) -> list[str]:
    """Page-sized pieces of about max_tokens each (4 characters per token), every page labelled."""
    limit = max(800, max_tokens * 4 - 1200)
    out, cur = [], ""
    for n, text in enumerate(pages, 1):
        text = text.strip()
        chunks = [text[i:i + limit] for i in range(0, len(text), limit)] or [""]
        for c in chunks:
            block = f"=== Page {n} ===\n{c}\n"
            if cur and len(cur) + len(block) > limit:
                out.append(cur)
                cur = ""
            cur += block
    if cur:
        out.append(cur)
    return out


def _candidates(s: AiSettings, pages_masked: list[str], system: str, meta: dict) -> list[MeetingExtraction]:
    return [invoke_structured(s, "extract", system, piece, MeetingExtraction, meta=meta)
            for piece in pieces(pages_masked, s.max_input_tokens)]


def suggest_from_pages(s: AiSettings, pages: list[str], current: dict | None = None, *, meta: dict | None = None) -> dict:
    current = current or {}
    masked_pages, mapping = [], {}
    for p in pages:
        mp, mm = mask(p)
        masked_pages.append(mp)
        mapping.update(mm)
    pass1 = _candidates(s, masked_pages, prompt("extract_meeting_v1.txt"), meta or {})
    pass2 = _candidates(s, masked_pages, prompt("extract_meeting_v1_second.txt"), meta or {})

    fields = []
    for key, (label, kind) in FIELDS.items():
        seen: dict[str, dict] = {}                   # normalised value -> {count, quote, page, passes}
        for pass_no, results in enumerate((pass1, pass2)):
            for ext in results:
                f = getattr(ext, key)
                if f is None:
                    continue
                page = verify_quote(f.source_quote, f.page, masked_pages)
                value = normalize(kind, unmask(f.value, mapping))
                if page is None or value is None:
                    continue                          # a quote that is not in the page, or a value the form would refuse
                hit = seen.setdefault(value, {"passes": set(), "quote": f.source_quote, "page": page})
                hit["passes"].add(pass_no)
        if not seen:
            continue
        value, hit = max(seen.items(), key=lambda kv: len(kv[1]["passes"]))
        tier = "high" if len(hit["passes"]) == 2 else "check"
        if kind == "text" and _squash(value) not in _squash(unmask(hit["quote"], mapping)):
            tier = "unverified"                       # the value is not literally in its quote
        cur = (current.get(key) or "").strip()
        fields.append({"key": key, "label": label, "proposed": value, "current": cur, "tier": tier,
                       "quote": unmask(hit["quote"], mapping), "page": hit["page"],
                       "conflict": bool(cur) and _squash(cur) != _squash(value)})

    agenda, seen_items = [], {}
    for pass_no, results in enumerate((pass1, pass2)):
        for ext in results:
            for item in ext.agenda:
                page = verify_quote(item.source_quote, item.page, masked_pages)
                text = re.sub(r"\s+", " ", unmask(item.text, mapping)).strip()
                if page is None or len(text) < 4:
                    continue
                key = re.sub(r"\W+", "", text.lower())[:60]
                hit = seen_items.get(key)
                if hit is None:
                    hit = seen_items[key] = {"text": display_title(text), "quote": unmask(item.source_quote, mapping),
                                             "page": page, "passes": set()}
                    agenda.append(hit)
                hit["passes"].add(pass_no)
    out_agenda = []
    for it in agenda:
        forms, _ = _forms_for(it["text"])            # forms and documents come from the rules, never from the model
        docs, _ = _docs_for(it["text"], "")
        out_agenda.append({"text": it["text"], "forms": ", ".join(forms), "docs": ", ".join(docs),
                           "tier": "high" if len(it["passes"]) == 2 else "check", "quote": it["quote"], "page": it["page"]})
    return {"fields": fields, "agenda": out_agenda}
