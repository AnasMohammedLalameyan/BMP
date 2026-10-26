"""AI assistant endpoints for the Activities Dashboard (meeting registers). Everything here SUGGESTS or DRAFTS; nothing
here writes company data: values are saved by the existing meeting endpoints under the signed-in person's session.

Each endpoint is tied to ONE company: taken from the meeting on the server, or checked against the person's access when
they name it. Reads are always filtered by that company explicitly, on top of row-level security.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Depends, Request
from starlette.concurrency import run_in_threadpool

from ..access import UserCtx
from ..ai import graph, index, intake, notice, qa
from ..ai.reader import read_pages
from ..ai.settings import AiSettings
from ..ai.suggest import suggest_from_pages
from ..deps import current_user, readable_company, session, writable_company
from ..errors import ApiError, bad_request, conflict, not_found
from ..minutes_compliance import BY_KEY
from ..minutes_service import one
from ..responses import ok

router = APIRouter(prefix="/ai", tags=["ai"])


def settings_of(request: Request) -> AiSettings:
    s = getattr(request.app.state, "ai_settings", None)
    if s is None:
        s = request.app.state.ai_settings = AiSettings.load()
    return s


def require_ai(request: Request) -> AiSettings:
    s = settings_of(request)
    if not s.status()["enabled"]:
        raise ApiError(503, "ai_unavailable", "AI is unavailable right now. You can continue by hand.")
    return s


def _register(register: str) -> str:
    if register not in BY_KEY:
        raise not_found("Register")
    return register


def _company_documents(conn, company_id: int) -> list[dict]:
    return conn.execute("SELECT id, filename, storage_path, updated_at FROM core.document "
                        "WHERE company_id = %s AND NOT is_archived ORDER BY filename", (company_id,)).fetchall()


def _meeting_company(conn, meeting_id: int) -> int:
    row = conn.execute("SELECT company_id FROM core.meeting WHERE id = %s AND NOT is_archived", (meeting_id,)).fetchone()
    if row is None:
        raise not_found("Meeting")
    return row["company_id"]


def _stored_path(request: Request, rel: str) -> Path:
    base = request.app.state.settings.storage_dir.resolve()
    full = (base / rel).resolve()
    if base not in full.parents:
        raise ApiError(400, "bad_path", "Invalid file location")
    return full


@router.get("/status")
def status(request: Request, ctx: UserCtx = Depends(current_user)):
    return ok(settings_of(request).status())


@router.get("/documents")
def documents(company_id: int, request: Request, ctx: UserCtx = Depends(current_user)):
    """The company's stored documents (name only) for the 'suggest from a document' picker."""
    require_ai(request)
    readable_company(ctx, company_id)
    with session(request, ctx, readonly=True) as conn:
        docs = _company_documents(conn, company_id)
    return ok({"documents": [{"id": d["id"], "name": d["filename"]} for d in docs]})


@router.post("/suggest")
def suggest(request: Request, body: dict = Body(...), ctx: UserCtx = Depends(current_user)):
    s = require_ai(request)
    try:
        company_id, document_id = int(body.get("company_id")), int(body.get("document_id"))
    except (TypeError, ValueError):
        raise bad_request("company_id and document_id are required")
    writable_company(ctx, company_id)
    meeting_id = body.get("meeting_id")
    with session(request, ctx, readonly=True) as conn:
        doc = next((d for d in _company_documents(conn, company_id) if d["id"] == document_id), None)
        if doc is None:
            raise not_found("Document")                    # a document of another company is simply not found
        current = {}
        if meeting_id:
            m = one(conn, company_id, int(meeting_id))
            if m is None:
                raise not_found("Meeting")
            current = {k: m.get(k) for k in ("meeting_date", "notice_date", "meeting_time", "mode", "chairman",
                                             "directors_present", "invitees_present", "leave_of_absence",
                                             "signing_date", "signing_place")}
    # the database transaction is closed before the (slow) model calls
    pages = read_pages(_stored_path(request, doc["storage_path"]), doc["filename"])
    meta = {"company": company_id, "fields": "meeting"}
    result = graph.run(s, "suggest", {"suggest": lambda: suggest_from_pages(s, pages, current, meta=meta)})["result"]
    return ok({"document": doc["filename"], **result})


@router.post("/intake")
def intake_plan(request: Request, body: dict = Body(...), ctx: UserCtx = Depends(current_user)):
    s = require_ai(request)
    text = str(body.get("text") or "").strip()
    if not text:
        raise bad_request("Please describe the meeting.", {"text": "Required"})
    chosen_id = body.get("company_id")
    with session(request, ctx, readonly=True) as conn:
        companies = conn.execute("SELECT id, name FROM core.company WHERE id = ANY(%s::bigint[]) AND NOT is_archived "
                                 "ORDER BY name", (ctx.writable,)).fetchall()
    chosen = None
    if chosen_id:
        writable_company(ctx, int(chosen_id))
        chosen = next((c for c in companies if c["id"] == int(chosen_id)), None)

    handlers = {
        "intake": lambda: intake.plan(s, text, companies, chosen, meta={"fields": "text"}),
        "ask": lambda: {"declined": True, "answer": [], "redirect": "ask",
                        "message": "That looks like a question. Use the Ask box on the register instead."},
    }
    out = graph.run(s, None, handlers, text=text)
    if out["intent"] == "intake":
        return ok({"kind": "intake", **out["result"]})
    return ok({"kind": out["intent"] if out["intent"] in ("ask",) else "other",
               "message": out["result"].get("message") or "I can only help to fill in a meeting record from a description."})


def _notice_context(request, ctx, meeting_id, register):
    with session(request, ctx, readonly=True) as conn:
        company_id = _meeting_company(conn, meeting_id)
        writable_company(ctx, company_id)
        return company_id, notice.gather(conn, company_id, register, meeting_id)


@router.post("/meetings/{meeting_id}/{register}/notice/draft")
def notice_draft(meeting_id: int, register: str, request: Request, ctx: UserCtx = Depends(current_user)):
    s = require_ai(request)
    _register(register)
    company_id, gathered = _notice_context(request, ctx, meeting_id, register)
    subject, text, missing = notice.render(gathered)
    recips = [{**r, "has_email": bool(r["email"])} for r in gathered["recipients"]]

    def work():
        return {"subject": subject, "notice": text, "recipients": recips, "missing": missing,
                "cover": notice.draft_cover(s, gathered),
                "fingerprint": notice.fingerprint(subject, text, gathered["recipients"]),
                "sandbox": s.smtp_sandbox or s.data_mode != "real"}

    return ok(graph.run(s, "notice", {"notice": work})["result"])


@router.post("/meetings/{meeting_id}/{register}/notice/send")
def notice_send(meeting_id: int, register: str, request: Request, body: dict = Body(...),
                ctx: UserCtx = Depends(current_user)):
    s = require_ai(request)
    _register(register)
    if body.get("approve") is not True:
        raise bad_request("Sending needs an explicit approval.", {"approve": "Not approved"})
    cover = str(body.get("cover") or "").strip()[:1500]
    if not cover:
        raise bad_request("The covering text is empty.", {"cover": "Required"})
    company_id, gathered = _notice_context(request, ctx, meeting_id, register)        # recipients are recomputed here
    subject, text, missing = notice.render(gathered)
    if missing:
        raise bad_request("The notice is incomplete: " + ", ".join(missing) + ".", {"notice": "Incomplete"})
    if body.get("fingerprint") != notice.fingerprint(subject, text, gathered["recipients"]):
        raise conflict("The meeting or its recipients changed since you reviewed the notice. Please review it again.",
                       "changed")
    results = notice.send(s, meeting_id=meeting_id, subject=subject, notice=text, cover=cover,
                          recipients=gathered["recipients"], approver_id=ctx.id)
    return ok({"results": results, "sent": sum(1 for r in results if r["status"] == "sent")})


@router.post("/{register}/ask")
def ask(register: str, request: Request, body: dict = Body(...), ctx: UserCtx = Depends(current_user)):
    s = require_ai(request)
    _register(register)
    question = str(body.get("question") or "").strip()[:500]
    if not question:
        raise bad_request("Please type a question.", {"question": "Required"})
    try:
        company_id = int(body.get("company_id"))
    except (TypeError, ValueError):
        raise bad_request("company_id is required")
    readable_company(ctx, company_id)
    with session(request, ctx, readonly=True) as conn:
        docs = _company_documents(conn, company_id)

    def work():
        storage = request.app.state.settings.storage_dir
        skipped = index.ensure_company(s, company_id, docs, storage)
        has_library = index.ensure_library(s)
        passages = index.query(s, company_id, question)
        res = qa.answer(s, question, passages, meta={"company": company_id})
        res["library"] = has_library
        res["unreadable_documents"] = skipped
        return res

    return ok(graph.run(s, "ask", {"ask": work})["result"])
