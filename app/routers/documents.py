"""Evidence documents: upload (hashed, versioned, safely stored), link to a record or task, download."""
from __future__ import annotations

import hashlib
import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from starlette.responses import FileResponse

from ..access import UserCtx
from ..deps import current_user, session, writable_company
from ..errors import ApiError, bad_request, not_found
from ..responses import ok
from .entities import _check_entity_reference

router = APIRouter(tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".rtf", ".odt", ".ods",
                      ".png", ".jpg", ".jpeg", ".gif", ".tif", ".tiff"}
_SAFE = re.compile(r"[^A-Za-z0-9._ \-()]")


def _safe_name(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    base = _SAFE.sub("_", base).strip(" .") or "file"
    return base[:120]


def _resolve(storage: Path, relative: str) -> Path:
    full = (storage / relative).resolve()
    if storage.resolve() not in full.parents:
        raise ApiError(400, "bad_path", "Invalid file location")
    return full


@router.post("/documents/upload")
async def upload(request: Request, company_id: int = Form(...), file: UploadFile = File(...),
                 document_type_id: int | None = Form(None), entity_type: str | None = Form(None),
                 entity_id: int | None = Form(None), task_instance_id: int | None = Form(None),
                 note: str | None = Form(None), ctx: UserCtx = Depends(current_user)):
    settings = request.app.state.settings
    writable_company(ctx, company_id)
    name = _safe_name(file.filename or "file")
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise bad_request("This file type is not accepted. Allowed: " + ", ".join(sorted(ALLOWED_EXTENSIONS)),
                          {"file": "File type not accepted"})
    digest, size = hashlib.sha256(), 0
    tmp = settings.storage_dir / ".incoming"
    tmp.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp / f"{ctx.id}_{hashlib.sha1(name.encode()).hexdigest()[:8]}.part"
    try:
        with open(tmp_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise bad_request(f"The file is larger than {settings.max_upload_bytes // (1024 * 1024)} MB.",
                                      {"file": "Too large"})
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise bad_request("The file is empty.", {"file": "Empty file"})
        sha = digest.hexdigest()
        relative = f"{company_id}/{sha[:2]}/{sha}_{name}"
        final = _resolve(settings.storage_dir, relative)
        final.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.replace(final)
    finally:
        tmp_path.unlink(missing_ok=True)

    engine = request.app.state.engine
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    with session(request, ctx) as conn:
        version = conn.execute(
            "SELECT coalesce(max(version), 0) + 1 AS v FROM core.document WHERE company_id = %s AND filename = %s "
            "AND document_type_id IS NOT DISTINCT FROM %s", (company_id, name, document_type_id)).fetchone()["v"]
        doc = engine.create(conn, "document", ctx, {
            "company_id": company_id, "document_type_id": document_type_id, "filename": name, "storage_path": relative,
            "mime_type": mime, "sha256": sha, "version": version, "uploaded_by": ctx.id})
        link = None
        if entity_type and entity_id or task_instance_id:
            payload = {"document_id": doc["id"],
                       "entity_type": entity_type or ("task_instance" if task_instance_id else "document"),
                       "entity_id": entity_id or task_instance_id or doc["id"],
                       "task_instance_id": task_instance_id, "note": note}
            _check_entity_reference(request, ctx, conn, payload)
            link = engine.create(conn, "evidence_link", ctx, payload)
    return ok({"document": doc, "evidence_link": link, "size": size}, 201)


@router.get("/documents/{document_id}/download")
def download(document_id: int, request: Request, ctx: UserCtx = Depends(current_user)):
    settings = request.app.state.settings
    with session(request, ctx, readonly=True) as conn:
        doc = request.app.state.engine.get(conn, "document", ctx, str(document_id))
    if not doc["storage_path"]:
        raise not_found("File")
    path = _resolve(settings.storage_dir, doc["storage_path"])
    if not path.is_file():
        raise ApiError(404, "file_missing", "This document's file is not on the server.")
    if doc["sha256"]:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        if h.hexdigest() != doc["sha256"]:
            raise ApiError(409, "integrity", "The stored file no longer matches its recorded fingerprint.")
    return FileResponse(path, media_type=doc["mime_type"] or "application/octet-stream", filename=doc["filename"],
                        content_disposition_type="attachment")
