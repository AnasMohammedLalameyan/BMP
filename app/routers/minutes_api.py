"""Activities Dashboard API: eight registers of meetings, roster, minutes parser and Excel export.

Company access is enforced here on every route (read for GET, write/admin for changes) and again by row-level
security in the database. Statics are declared before the /minutes/{register} routes so they are not shadowed.
"""
from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Body, Depends, File, Form, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from .. import minutes_service as svc
from ..access import UserCtx
from ..deps import current_user, readable_company, session, writable_company
from ..errors import ApiError, bad_request
from ..minutes_compliance import REGISTERS
from ..minutes_excel import build_meetings_workbook
from ..minutes_extract import ScannedPdfError, parse_minutes
from ..responses import ok

router = APIRouter(prefix="/minutes", tags=["minutes"])

MAX_MINUTES_BYTES = 10 * 1024 * 1024
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/registers")
def registers(ctx: UserCtx = Depends(current_user)):
    return ok({"registers": svc.registers_config(), "modes": svc.MODES, "minutes_statuses": svc.MINUTES_STATUSES})


@router.get("/counts")
def counts(company_id: int, fy: str, request: Request, ctx: UserCtx = Depends(current_user)):
    readable_company(ctx, company_id)
    with session(request, ctx, readonly=True) as conn:
        return ok(svc.counts(conn, company_id, fy))


@router.get("/roster")
def roster(company_id: int, date: date, request: Request, ctx: UserCtx = Depends(current_user)):    # noqa: A002
    readable_company(ctx, company_id)
    with session(request, ctx, readonly=True) as conn:
        return ok({"roster": svc.roster(conn, company_id, date)})


@router.get("/export.xlsx")
def export(company_id: int, fy: str, request: Request, register: str | None = None,
           ctx: UserCtx = Depends(current_user)):
    readable_company(ctx, company_id)
    if register is not None:
        svc._check_register(register)
    with session(request, ctx, readonly=True) as conn:
        meetings = svc.fetch_year(conn, company_id, fy)
        row = conn.execute("SELECT name FROM core.company WHERE id = %s", (company_id,)).fetchone()
    regs = [{"key": k, "name": n} for k, n, *_ in REGISTERS if register in (None, k)]
    data = build_meetings_workbook({"company_name": row["name"] if row else "", "financial_year": fy,
                                    "registers": regs,
                                    "meetings": [m for m in meetings if register in (None, m["register"])]})
    safe = re.sub(r"[^A-Za-z0-9]+", "_", row["name"] if row else "company").strip("_")
    return Response(data, media_type=XLSX, headers={
        "Content-Disposition": f'attachment; filename="Minutes_{safe}_{fy}.xlsx"'})


@router.post("/parse")
async def parse(request: Request, company_id: int = Form(...), file: UploadFile = File(...),
                ctx: UserCtx = Depends(current_user)):
    """Reads an uploaded Word/PDF minutes file and returns suggestions. Saves nothing and keeps nothing."""
    writable_company(ctx, company_id)
    name = (file.filename or "").strip()
    if not name.lower().endswith((".docx", ".pdf")):
        raise ApiError(400, "unsupported", "Please upload a Word (.docx) or PDF file.")
    raw = await file.read(MAX_MINUTES_BYTES + 1)
    if not raw:
        raise bad_request("The file is empty.", {"file": "Empty file"})
    if len(raw) > MAX_MINUTES_BYTES:
        raise ApiError(413, "too_large", "The file is larger than 10 MB.")
    try:
        result = await run_in_threadpool(parse_minutes, name, raw)
    except ScannedPdfError as e:
        raise ApiError(422, "scanned_pdf", str(e))
    except ValueError as e:
        raise ApiError(400, "unsupported", str(e))
    result["source"] = name
    return ok(result)


@router.get("/{register}")
def list_meetings(register: str, company_id: int, fy: str, request: Request, ctx: UserCtx = Depends(current_user)):
    readable_company(ctx, company_id)
    svc._check_register(register)
    with session(request, ctx, readonly=True) as conn:
        return ok(svc.list_register(conn, company_id, fy, register))


@router.post("/{register}")
def create(register: str, company_id: int, request: Request, body: dict = Body(...),
           ctx: UserCtx = Depends(current_user)):
    writable_company(ctx, company_id)
    with session(request, ctx) as conn:
        meeting = svc.create_meeting(conn, request.app.state.engine, ctx, company_id, register, body)
    return ok({"meeting": meeting}, 201)


@router.put("/{register}/{meeting_id}")
def update(register: str, meeting_id: int, request: Request, company_id: int | None = None,
           body: dict = Body(...), ctx: UserCtx = Depends(current_user)):
    # the company comes from the query (as on create) or the body; either way it is checked against the user's access
    cid = company_id if company_id is not None else body.get("company_id")
    try:
        cid = int(cid)
    except (TypeError, ValueError):
        raise bad_request("company_id is required", {"company_id": "Required"})
    writable_company(ctx, cid)
    with session(request, ctx) as conn:
        meeting = svc.update_meeting(conn, request.app.state.engine, ctx, cid, register, meeting_id, body)
    return ok({"meeting": meeting})
