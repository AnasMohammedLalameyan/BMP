"""Capability 4: answer a question from retrieved passages, with checked citations. Code, not the model, decides what is
shown: a claim survives only if it cites a passage that was really retrieved and quotes words that are really in it."""
from __future__ import annotations

import re

from .llm import invoke_structured
from .masking import mask, unmask
from .schemas import AskAnswer
from .settings import AiSettings
from .suggest import prompt

DECLINED = "I could not find this in the company's documents or the statute library."
STATUTE_NOTE = "Statute text can change: please check the current official text before relying on this."


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().casefold()


def answer(s: AiSettings, question: str, passages: list[dict], *, meta: dict | None = None) -> dict:
    if not passages:
        return {"declined": True, "message": DECLINED, "answer": [], "note": None}
    masked_q, mq = mask(question)
    labelled, mapping = {}, dict(mq)
    lines = []
    for i, p in enumerate(passages, 1):
        cid = f"c{i}"
        mtext, mm = mask(p["text"])
        mapping.update(mm)
        labelled[cid] = (p, mtext)
        lines.append(f"[{cid}] {mtext}")
    out = invoke_structured(s, "chat", prompt("ask_v1.txt"), f"Question: {masked_q}\n\nPassages:\n" + "\n\n".join(lines),
                            AskAnswer, meta=meta)
    claims = []
    if not out.insufficient:
        for c in out.claims:
            hit = labelled.get(c.chunk_id)
            if hit is None or len(_squash(c.quote)) < 8 or _squash(c.quote) not in _squash(hit[1]):
                continue                                    # cited a passage that was not retrieved, or quoted words not in it
            if not c.text.strip():
                continue
            p = hit[0]["meta"]
            where = p["section_ref"] if p["source"] == "library" else (f"{p['filename']}, page {p['page']}")
            if p["source"] == "library":
                where = f"Library: {where}"
            claims.append({"text": unmask(c.text.strip(), mapping), "citation": where, "quote": unmask(c.quote.strip(), mapping),
                           "source": p["source"]})
    if not claims:
        return {"declined": True, "message": DECLINED, "answer": [], "note": None}
    return {"declined": False, "message": None, "answer": claims,
            "note": STATUTE_NOTE if any(c["source"] == "library" for c in claims) else None}
