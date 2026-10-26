"""The self-describing part of the API: entities, fields, dropdown lists, navigation."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query, Request

from ..access import UserCtx, can_read_entity, can_write_entity
from ..deps import current_user, session
from ..errors import ApiError
from ..registry import ENTITIES, NAV, SCOPE, VIEWS
from ..responses import ok

router = APIRouter(tags=["meta"])

_ACRONYMS = {
    "cin": "CIN", "din": "DIN", "pan": "PAN", "roc": "ROC", "dsc": "DSC", "nic": "NIC", "srn": "SRN",
    "frn": "FRN", "uin": "UIN", "lrn": "LRN", "firc": "FIRC", "ad": "AD", "inr": "INR", "rta": "RTA",
    "dp": "DP", "kyc": "KYC", "ecb": "ECB", "odi": "ODI", "gm": "GM", "id": "ID", "fii": "FII",
    "sebi": "SEBI", "url": "URL", "sha256": "SHA-256", "fy": "FY", "ind": "Ind", "as": "AS",
    "s185": "Sec 185", "s186": "Sec 186", "s188": "Sec 188", "sh4": "SH-4", "dir3": "DIR-3",
    "ca": "CA", "csr": "CSR", "mgt": "MGT",
}
_LABEL_OVERRIDES = {
    "aadhaar_encrypted": "Aadhaar number (encrypted)", "secret_encrypted": "Portal secret (encrypted)",
    "resident_over_182": "Resident in India over 182 days", "borrowings_banks_fi": "Borrowings from banks / FIs",
    "dir3_kyc_filed": "DIR-3 KYC filed", "gm_appointment_date": "General meeting appointment date",
    "ind_as_applicable": "Ind AS applicable", "relative_name": "Relative's name", "is_fii": "Is FII",
    "father_spouse": "Father / spouse name", "is_demat": "Held in demat form", "sh4_available": "SH-4 available",
    "involves_non_resident": "Involves a non-resident", "executed_by": "Executed by",
    "retires_by_rotation": "Retires by rotation", "profits_in_lieu": "Profits in lieu of salary",
    "meeting_number": "Meeting number", "text": "Text", "extracted_data": "Extracted data (from the file)",
    "storage_path": "Storage path", "id": "ID", "mode": "Mode", "pgp": "PGP",
}


def humanize(name: str) -> str:
    if name in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[name]
    base = name[:-3] if name.endswith("_id") and len(name) > 3 else name
    words = [_ACRONYMS.get(w, w) for w in base.split("_")]
    s = " ".join(words)
    return s[:1].upper() + s[1:]


def clean_help(comment: str | None) -> str | None:
    if not comment:
        return None
    parts = [p.strip() for p in re.split(r"(?<=\.)\s+", comment) if p.strip()]
    hidden = ("xlsx", "implementation log", "references lookup_list", "lookup_list code", "pgp_sym", "never stored in plaintext")
    parts = [p for p in parts if not any(h in p.lower() for h in hidden)]
    return " ".join(parts) or None


def _static_meta(request: Request) -> dict:
    """The parts of the metadata that do not depend on who is asking (built once)."""
    cached = getattr(request.app.state, "meta_static", None)
    if cached is not None:
        return cached
    catalog, settings = request.app.state.catalog, request.app.state.settings
    entities: dict = {}
    for key, cfg in ENTITIES.items():
        t = catalog.get(key)
        if t is None:
            continue
        cols = []
        for c in t.columns:
            item = {
                "name": c.name, "label": humanize(c.name), "kind": c.kind, "type": c.pg_type,
                "required": c.required, "nullable": c.nullable, "writable": c.writable, "system": c.system,
                "generated": c.generated, "pk": c.is_pk, "help": clean_help(c.comment),
            }
            if c.fk:
                item["fk"] = c.fk["table"]
            if c.lookup:
                item["lookup"] = c.lookup
            if c.choices is not None:
                item["choices"] = c.choices
            if c.fmt:
                item["format"] = c.fmt
            if c.scale is not None:
                item["scale"] = c.scale
            if c.dims:
                item["dims"] = c.dims
            if c.kind == "bytea":
                flag = {"aadhaar_encrypted": settings.allow_aadhaar, "secret_encrypted": settings.allow_portal_secret}
                item["secret"] = True
                item["secret_enabled"] = bool(flag.get(c.name, False))
            cols.append(item)
        entities[key] = {
            "key": key, "schema": t.schema, "label": cfg["label"], "singular": cfg["singular"],
            "list": [c for c in cfg["list"] if t.has(c)],
            "searchable": bool(cfg.get("search")),
            "sections": [{"title": s, "columns": [c for c in cs if t.has(c)]} for s, cs in cfg.get("sections", [])],
            "children": [{"entity": e, "fk": fk, "label": lab} for e, fk, lab in cfg.get("children", [])],
            "pk": t.pk, "fy": t.has("financial_year"), "archivable": t.has_archive,
            "write_mode": cfg["write"], "scope": SCOPE.get(key, {"type": "direct"})["type"],
            "company_scoped": SCOPE.get(key, {"type": "direct"})["type"] in ("direct", "parent", "masters"),
            "columns": cols,
        }
    views = {}
    for name, label in VIEWS.items():
        v = catalog.get(name)
        if v is not None:
            views[name] = {"label": label, "columns": [{"name": c.name, "label": humanize(c.name), "kind": c.kind}
                                                       for c in v.columns if c.name != "company_id"]}
    request.app.state.meta_static = {"entities": entities, "views": views}
    return request.app.state.meta_static


def _lookups(request: Request, ctx: UserCtx) -> dict:
    with session(request, ctx, readonly=True) as conn:
        rows = conn.execute(
            """SELECT l.code AS list, v.id, v.code, v.label FROM core.lookup_value v
               JOIN core.lookup_list l ON l.id = v.list_id
               WHERE NOT v.is_archived AND NOT l.is_archived ORDER BY l.code, v.sort_order, v.label""").fetchall()
    out: dict = {}
    for r in rows:
        out.setdefault(r["list"], []).append({"id": r["id"], "code": r["code"], "label": r["label"]})
    return out


@router.get("/meta")
def meta(request: Request, ctx: UserCtx = Depends(current_user)):
    static = _static_meta(request)
    entities = {}
    for key, e in static["entities"].items():
        if not can_read_entity(key, ctx):
            continue
        entities[key] = {**e, "can_write": can_write_entity(key, ctx)}
    nav = []
    for group in NAV:
        items = []
        for item in group["items"]:
            if "entity" in item:
                if item["entity"] in entities:
                    items.append({"entity": item["entity"], "label": entities[item["entity"]]["label"]})
            else:
                items.append(item)
        if items:
            nav.append({**group, "items": items})
    return ok({"entities": entities, "views": static["views"], "nav": nav, "lookups": _lookups(request, ctx),
               "user": ctx.public(), "policy": {
                   "aadhaar_storage": request.app.state.settings.allow_aadhaar,
                   "portal_secret_storage": request.app.state.settings.allow_portal_secret}})


@router.get("/options/{entity}")
def options(entity: str, request: Request, q: str | None = None, company_id: int | None = None,
            ids: str | None = None, limit: int = Query(40, ge=1, le=200), ctx: UserCtx = Depends(current_user)):
    id_list = None
    if ids:
        try:
            id_list = [int(x) for x in ids.split(",") if x.strip()]
        except ValueError:
            raise ApiError(422, "validation", "ids must be a comma-separated list of numbers")
    with session(request, ctx, readonly=True) as conn:
        rows = request.app.state.engine.options(conn, entity, ctx, q=q, company_id=company_id, ids=id_list, limit=limit)
    return ok({"options": rows})
