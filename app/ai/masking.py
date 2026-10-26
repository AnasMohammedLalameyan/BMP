"""Masking before any text leaves the server. PAN, DIN, phone numbers and email addresses become placeholders that
code swaps back afterwards; Aadhaar numbers are dropped for good (never sent, stored, shown or suggested)."""
from __future__ import annotations

import re

AADHAAR = re.compile(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)")
PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\d)(?:\+91[ -]?|0)?[6-9]\d{9}(?!\d)")
DIN = re.compile(r"(?i)(\bDIN\b\s*[:\-]?\s*)(\d{8})\b")
DROPPED = "[AADHAAR REMOVED]"


def mask(text: str) -> tuple[str, dict[str, str]]:
    """Return (masked text, {placeholder: original}). Aadhaar numbers are replaced and cannot be restored."""
    mapping: dict[str, str] = {}
    counters: dict[str, int] = {}

    def put(kind: str, original: str) -> str:
        for ph, orig in mapping.items():
            if orig == original and ph.startswith(f"[{kind}_"):
                return ph
        counters[kind] = counters.get(kind, 0) + 1
        ph = f"[{kind}_{counters[kind]}]"
        mapping[ph] = original
        return ph

    text = AADHAAR.sub(DROPPED, text)
    text = EMAIL.sub(lambda m: put("EMAIL", m.group(0)), text)
    text = DIN.sub(lambda m: m.group(1) + put("DIN", m.group(2)), text)
    text = PAN.sub(lambda m: put("PAN", m.group(0)), text)
    text = PHONE.sub(lambda m: put("PHONE", m.group(0)), text)
    return text, mapping


def unmask(text: str, mapping: dict[str, str]) -> str:
    for ph, original in mapping.items():
        text = text.replace(ph, original)
    return text
