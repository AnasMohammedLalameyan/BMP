"""Shared helpers for the AI tests: settings, a fake embedder, and small dummy documents. Dummy data only."""
import io
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from app.ai.settings import AiSettings


def make_ai(tmp: Path, **kw) -> AiSettings:
    base = dict(enabled=True, provider="groq", groq_api_key="test-key", model_extract="m1", model_chat="m2", model_fast="m3",
                base_url="", timeout_s=5, max_calls_per_minute=1000, max_input_tokens=3000, data_mode="dummy",
                zdr_confirmed=False, outside_india_approved=False, embedding_model="fake", index_dir=tmp / "idx",
                library_dir=tmp / "lib", smtp_host="localhost", smtp_port=1025, smtp_from="notices@example.test",
                smtp_sandbox=True)
    base.update(kw)
    return AiSettings(**base)


def fake_embed(texts):
    """Deterministic bag-of-words vectors: enough for similar texts to be near each other."""
    out = []
    for t in texts:
        v = [0.0] * 64
        for w in re.findall(r"[a-z0-9]+", t.lower()):
            v[hash_w(w) % 64] += 1.0
        n = sum(x * x for x in v) ** 0.5 or 1.0
        out.append([x / n for x in v])
    return out


def hash_w(w: str) -> int:
    h = 0
    for ch in w:
        h = (h * 131 + ord(ch)) % 1000003
    return h


def docx_bytes(lines):
    paras = "".join(f"<w:p><w:r><w:t>{escape(l)}</w:t></w:r></w:p>" for l in lines)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f"<w:document><w:body>{paras}</w:body></w:document>")
    return buf.getvalue()


MINUTES = [
    "Minutes of the Meeting of the Board of Directors of Dummy Co held on 12th September 2026",
    "The meeting commenced at 11.00 a.m. and concluded at 12.30 p.m.",
    "Mr. Rajan Patel was elected chairman of the meeting.",
    "1. To approve the appointment of the statutory auditor",
    "2. To note the disclosure of interest by directors",
    "DATE: 20.09.2026",
    "PLACE: Mumbai",
]
