"""Who the signed-in user is and which rows they may read or change.

Two layers protect company data:
  1. PostgreSQL row-level security on every table that carries a company_id (set up by
     the Phase 1 schema, driven by `app.current_user_id`).
  2. The rules below, applied by the API to everything else - the shared people tables,
     child tables with no company_id, the calculated views (which the database does not
     scope) and the access level (a read-only user must not write).
Both must agree; a test loops over every table to prove it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .registry import ENTITIES, SCOPE
from .schema_meta import Catalog

WRITE_LEVELS = ("write", "admin")


@dataclass
class UserCtx:
    id: int
    email: str
    name: str
    role: str | None
    access: dict[int, str] = field(default_factory=dict)      # company_id -> level
    privileged: bool = False                                  # set only by onboarding code

    @property
    def readable(self) -> list[int]:
        return sorted(self.access)

    @property
    def writable(self) -> list[int]:
        return sorted(c for c, lvl in self.access.items() if lvl in WRITE_LEVELS)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin" or any(lvl == "admin" for lvl in self.access.values())

    @property
    def is_staff(self) -> bool:
        """Anyone who can write to at least one company (BMP staff, as opposed to a client)."""
        return bool(self.writable) or self.is_admin

    def level_for(self, company_id: int) -> str | None:
        return self.access.get(company_id)

    def public(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "role": self.role,
                "is_admin": self.is_admin, "is_staff": self.is_staff,
                "access": {str(k): v for k, v in sorted(self.access.items())}}


def load_user(conn, user_id: int) -> UserCtx | None:
    row = conn.execute(
        """SELECT u.id, u.email, u.name, u.is_active, r.name AS role
           FROM core.app_user u LEFT JOIN core.role r ON r.id = u.role_id
           WHERE u.id = %s AND NOT u.is_archived""", (user_id,)).fetchone()
    if row is None or not row["is_active"]:
        return None
    access = {r["company_id"]: r["access_level"] for r in conn.execute(
        "SELECT company_id, access_level FROM core.user_company_access WHERE user_id = %s AND NOT is_archived",
        (user_id,)).fetchall()}
    return UserCtx(id=row["id"], email=row["email"], name=row["name"], role=row["role"], access=access)


def can_read_entity(key: str, ctx: UserCtx) -> bool:
    scope = SCOPE.get(key, {"type": "direct"})
    if scope["type"] == "admin":
        return ctx.is_admin
    return True


def can_write_entity(key: str, ctx: UserCtx) -> bool:
    mode = ENTITIES[key]["write"]
    if mode == "none":
        return False
    if ctx.privileged:
        return True
    if mode == "admin":
        return ctx.is_admin
    if mode == "company":
        return bool(ctx.writable)
    return ctx.is_staff            # staff, user


class Scope:
    """Builds SQL fragments (with named parameters) that restrict a table to what a user may see."""

    def __init__(self, catalog: Catalog):
        self.catalog = catalog
        self._n = 0

    def _alias(self) -> str:
        self._n += 1
        return f"s{self._n}"

    def row_scope(self, key: str, alias: str, ctx: UserCtx, mode: str, params: dict) -> str:
        """SQL that is true for rows of `key` (aliased `alias`) the user may `mode` ('read'|'write')."""
        if ctx.privileged:
            return "TRUE"
        params.setdefault("rids", ctx.readable)
        params.setdefault("wids", ctx.writable)
        params.setdefault("uid", ctx.id)
        ids = "%(rids)s::bigint[]" if mode == "read" else "%(wids)s::bigint[]"
        scope = SCOPE.get(key)
        table = self.catalog.get(key)
        if scope is None:
            if table is not None and table.has("company_id"):
                return f'{alias}."company_id" = ANY({ids})'
            return "FALSE"
        kind = scope["type"]
        if kind == "direct":
            return f'{alias}."{scope["column"]}" = ANY({ids})'
        if kind == "parent":
            p = self.catalog.get(scope["parent"])
            a2 = self._alias()
            inner = self.row_scope(scope["parent"], a2, ctx, mode, params)
            return (f'EXISTS (SELECT 1 FROM {p.ident} {a2} WHERE {a2}."id" = {alias}."{scope["fk"]}" '
                    f'AND ({inner}))')
        if kind == "masters":
            if ctx.is_staff:
                return "TRUE"
            if mode == "write":
                return "FALSE"
            parts = []
            for link_table, fk in scope["links"]:
                lt = self.catalog.get(link_table)
                a2 = self._alias()
                parts.append(f'EXISTS (SELECT 1 FROM {lt.ident} {a2} WHERE {a2}."{fk}" = {alias}."id" '
                             f'AND {a2}."company_id" = ANY({ids}))')
            return "(" + " OR ".join(parts) + ")"
        if kind == "global":
            return "TRUE" if (mode == "read" or ctx.is_admin) else "FALSE"
        if kind == "admin":
            return "TRUE" if ctx.is_admin else "FALSE"
        if kind == "user":
            cols = " OR ".join(f'{alias}."{c}" = %(uid)s' for c in scope["columns"])
            return f"({cols}{' OR TRUE' if ctx.is_admin else ''})"
        return "FALSE"

    def company_filter(self, key: str, alias: str, params: dict) -> str:
        """SQL restricting rows of `key` to one company (`%(cid)s` must be in params)."""
        scope = SCOPE.get(key)
        table = self.catalog.get(key)
        if scope is None:
            return f'{alias}."company_id" = %(cid)s' if table is not None and table.has("company_id") else "TRUE"
        kind = scope["type"]
        if kind == "direct":
            return f'{alias}."{scope["column"]}" = %(cid)s'
        if kind == "parent":
            p = self.catalog.get(scope["parent"])
            a2 = self._alias()
            inner = self.company_filter(scope["parent"], a2, params)
            return f'EXISTS (SELECT 1 FROM {p.ident} {a2} WHERE {a2}."id" = {alias}."{scope["fk"]}" AND ({inner}))'
        if kind == "masters":
            parts = []
            for link_table, fk in scope["links"]:
                lt = self.catalog.get(link_table)
                a2 = self._alias()
                parts.append(f'EXISTS (SELECT 1 FROM {lt.ident} {a2} WHERE {a2}."{fk}" = {alias}."id" '
                             f'AND {a2}."company_id" = %(cid)s)')
            return "(" + " OR ".join(parts) + ")"
        return "TRUE"
