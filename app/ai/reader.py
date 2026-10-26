"""Text of a stored document, page by page. PDFs via PyMuPDF (pypdf as fallback), Word files via the standard library.
A page with no text is a scan: it is reported, never guessed at (there is no OCR)."""
from __future__ import annotations

from pathlib import Path

from ..errors import ApiError
from ..minutes_extract import _docx_lines

SCANNED = "This document looks scanned and cannot be read yet. Please use a text-based PDF or a Word copy."


def read_pages(path: Path, filename: str) -> list[str]:
    name = (filename or "").lower()
    if name.endswith(".docx"):
        return ["\n".join(_docx_lines(path.read_bytes()))]
    if name.endswith(".pdf"):
        pages = _pdf_pages(path)
        if not any(p.strip() for p in pages) or sum(len(p) for p in pages) < 40 * max(len(pages), 1):
            raise ApiError(422, "scanned_document", SCANNED)
        return pages
    if name.endswith((".txt", ".md")):
        return [path.read_text(encoding="utf-8", errors="replace")]
    raise ApiError(400, "unsupported", "Only Word (.docx), PDF and text documents can be read.")


def _pdf_pages(path: Path) -> list[str]:
    try:
        import pymupdf
        with pymupdf.open(str(path)) as doc:
            return [page.get_text() for page in doc]
    except ImportError:
        from pypdf import PdfReader
        return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]
