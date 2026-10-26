"""Generic list / get / create / update / archive over any table, driven by the catalog.

Rules this module enforces on top of what the database already enforces:
  * a user only reads or changes rows inside their own scope (see access.Scope);
  * a read-only user cannot write, and nobody can write to a read-only entity;
  * rows are never deleted - "removing" archives (and can be undone with restore);
  * an edit carries the `updated_at` the user last saw, so two people cannot silently
    overwrite each other (409 when it moved);
  * a foreign-key value must point at a row the user can see (the database's own FK
    check ignores row-level security, so without this a user could link to another
    company's records);
  * sensitive encrypted columns are only written when the policy flag allows it.
"""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import psycopg

from .access import Scope, UserCtx, can_read_entity, can_write_entity
from .coerce import FieldError, coerce, is_blank
from .config import Settings
from .errors import ApiError, bad_request, conflict, forbidden, not_found
from .registry import ENTITIES, SCOPE
from .schema_meta import Catalog, Column, Table

POLICY_FLAGS = {"aadhaar_encrypted": "allow_aadhaar", "secret_encrypted": "allow_portal_secret"}
PAGE_MAX = 5000


def jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    return value


def pk_of(t: Table, row: dict) -> str:
    return "~".join(str(row[c]) for c in t.pk)


class Engine:
    def __init__(self, catalog: Catalog, settings: Settings):
        self.catalog = catalog
        self.settings = settings

    # ---- lookup helpers ------------------------------------------------------------
    def entity(self, key: str) -> tuple[Table, dict]:
        cfg = ENTITIES.get(key)
        t = self.catalog.get(key)
        if cfg is None or t is None or t.is_view:
            raise not_found("Entity")
        return t, cfg

    def _read(self, key: str, ctx: UserCtx) -> None:
        if not can_read_entity(key, ctx):
            raise not_found("Entity")          # do not reveal that it exists

    def _write(self, key: str, ctx: UserCtx) -> None:
        if not can_write_entity(key, ctx):
            raise forbidden("You do not have permission to change this")

    def _parse_pk(self, t: Table, pk: str) -> dict:
        parts = str(pk).split("~")
        if len(parts) != len(t.pk):
            raise not_found()
        out = {}
        for name, raw in zip(t.pk, parts):
            try:
                out[name] = coerce(t.col(name), raw)
            except FieldError:
                raise not_found()
        return out

    def _select(self, t: Table, alias: str = "t") -> str:
        parts = []
        for c in t.columns:
            if c.kind == "bytea":
                parts.append(f'({alias}."{c.name}" IS NOT NULL) AS "{c.name}"')   # never send ciphertext
            elif c.kind == "vector":
                parts.append(f'vector_dims({alias}."{c.name}") AS "{c.name}"')
            else:
                parts.append(f'{alias}."{c.name}"')
        return ", ".join(parts)

    def _pk_where(self, t: Table, pkvals: dict, params: dict, alias: str = "t") -> str:
        parts = []
        for i, (name, val) in enumerate(pkvals.items()):
            params[f"pk{i}"] = val
            parts.append(f'{alias}."{name}" = %(pk{i})s')
        return " AND ".join(parts)

    # ---- labels --------------------------------------------------------------------
    def _labels(self, conn, t: Table, rows: list[dict]) -> None:
        for r in rows:
            r["_labels"] = {}
        for col in t.fks:
            ids = sorted({r[col.name] for r in rows if r.get(col.name) is not None})
            if not ids:
                continue
            parent = self.catalog.get(col.fk["table"])
            pcfg = ENTITIES.get(col.fk["table"])
            label = pcfg["label_sql"] if pcfg else "'#' || p.id"
            sql = (f'SELECT p."{col.fk["column"]}" AS id, ({label}) AS label FROM {parent.ident} p '
                   f'WHERE p."{col.fk["column"]}" = ANY(%s::bigint[])')
            found = {r["id"]: r["label"] for r in conn.execute(sql, (ids,)).fetchall()}
            for r in rows:
                v = r.get(col.name)
                if v is not None and v in found:
                    r["_labels"][col.name] = found[v]
        # polymorphic references: entity_type + entity_id
        if t.has("entity_type") and t.has("entity_id"):
            by_type: dict[str, set] = {}
            for r in rows:
                if r.get("entity_type") in ENTITIES and r.get("entity_id") is not None:
                    by_type.setdefault(r["entity_type"], set()).add(r["entity_id"])
            for etype, ids in by_type.items():
                pt = self.catalog.get(etype)
                if pt is None or pt.is_view or not pt.has("id"):
                    continue
                sql = (f'SELECT p."id" AS id, ({ENTITIES[etype]["label_sql"]}) AS label FROM {pt.ident} p '
                       f'WHERE p."id" = ANY(%s::bigint[])')
                found = {r["id"]: r["label"] for r in conn.execute(sql, (sorted(ids),)).fetchall()}
                for r in rows:
                    if r.get("entity_type") == etype and r.get("entity_id") in found:
                        r["_labels"]["entity_id"] = found[r["entity_id"]]

    # ---- read ----------------------------------------------------------------------
    def list(self, conn, key: str, ctx: UserCtx, *, company_id: int | None = None, fy: str | None = None,
             q: str | None = None, include_archived: bool = False, filters: dict | None = None,
             sort: str | None = None, desc: bool | None = None, page: int = 1, size: int = 25) -> dict:
        t, cfg = self.entity(key)
        self._read(key, ctx)
        size = max(1, min(int(size), PAGE_MAX))
        page = max(1, int(page))
        sc, params = Scope(self.catalog), {}
        where = [sc.row_scope(key, "t", ctx, "read", params)]
        if t.has_archive and not include_archived:
            where.append('NOT t."is_archived"')
        if company_id is not None:
            params["cid"] = company_id
            where.append(sc.company_filter(key, "t", params))
        if fy and t.has("financial_year"):
            params["fy"] = fy
            where.append('t."financial_year" = %(fy)s')
        for i, (name, val) in enumerate((filters or {}).items()):
            col = t.col(name)
            if col is None or col.kind in ("bytea", "vector"):
                raise bad_request(f"Cannot filter on {name}")
            try:
                params[f"f{i}"] = coerce(col, val)
            except FieldError as e:
                raise bad_request(e.message, {name: e.message})
            where.append(f't."{name}" = %(f{i})s' if params[f"f{i}"] is not None else f't."{name}" IS NULL')
        if q and cfg.get("search"):
            params["q"] = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            where.append("(" + " OR ".join(f't."{c}"::text ILIKE %(q)s' for c in cfg["search"]
                                           if t.has(c)) + ")")
        order_col, order_desc = self._order(t, cfg, sort, desc)
        order_sql = f't."{order_col}" {"DESC" if order_desc else "ASC"} NULLS LAST'
        tie = ", ".join(f't."{c}"' for c in t.pk)
        base = f'FROM {t.ident} t WHERE {" AND ".join(where)}'
        total = conn.execute(f"SELECT count(*) AS n {base}", params).fetchone()["n"]
        params["limit"], params["offset"] = size, (page - 1) * size
        rows = conn.execute(
            f'SELECT {self._select(t)} {base} ORDER BY {order_sql}, {tie} LIMIT %(limit)s OFFSET %(offset)s',
            params).fetchall()
        self._labels(conn, t, rows)
        for r in rows:
            r["_pk"] = pk_of(t, r)
        return {"entity": key, "total": total, "page": page, "size": size, "rows": rows}

    def count(self, conn, key: str, ctx: UserCtx, *, company_id: int | None = None, fy: str | None = None) -> int:
        """Number of live (non-archived) rows of `key` the user may see, optionally for one company / year."""
        t, _ = self.entity(key)
        self._read(key, ctx)
        sc, params = Scope(self.catalog), {}
        where = [sc.row_scope(key, "t", ctx, "read", params)]
        if t.has_archive:
            where.append('NOT t."is_archived"')
        if company_id is not None:
            params["cid"] = company_id
            where.append(sc.company_filter(key, "t", params))
        if fy and t.has("financial_year"):
            params["fy"] = fy
            where.append('t."financial_year" = %(fy)s')
        return conn.execute(f'SELECT count(*) AS n FROM {t.ident} t WHERE {" AND ".join(where)}', params).fetchone()["n"]

    def _order(self, t: Table, cfg: dict, sort: str | None, desc: bool | None) -> tuple[str, bool]:
        if sort and t.col(sort) and t.col(sort).kind not in ("bytea", "vector"):
            return sort, bool(desc)
        default = cfg.get("order") or t.pk[0]
        d = default.startswith("-")
        name = default.lstrip("-")
        return (name if t.col(name) else t.pk[0]), d

    def get(self, conn, key: str, ctx: UserCtx, pk: str) -> dict:
        t, _ = self.entity(key)
        self._read(key, ctx)
        pkvals = self._parse_pk(t, pk)
        params: dict = {}
        sc = Scope(self.catalog)
        scope_sql = sc.row_scope(key, "t", ctx, "read", params)
        where = self._pk_where(t, pkvals, params)
        row = conn.execute(f'SELECT {self._select(t)} FROM {t.ident} t WHERE {where} AND ({scope_sql})',
                           params).fetchone()
        if row is None:
            raise not_found()
        self._labels(conn, t, [row])
        row["_pk"] = pk_of(t, row)
        return row

    def options(self, conn, key: str, ctx: UserCtx, *, q: str | None = None, company_id: int | None = None,
                ids: list[int] | None = None, limit: int = 40) -> list[dict]:
        t, cfg = self.entity(key)
        self._read(key, ctx)
        if "id" not in t.pk:
            return []
        sc, params = Scope(self.catalog), {}
        where = [sc.row_scope(key, "p", ctx, "read", params)]
        if t.has_archive:
            where.append('NOT p."is_archived"')
        if company_id is not None:
            params["cid"] = company_id
            where.append(sc.company_filter(key, "p", params))
        if ids:
            params["ids"] = ids
            where.append('p."id" = ANY(%(ids)s::bigint[])')
        if q:
            params["q"] = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            where.append(f'({cfg["label_sql"]}) ILIKE %(q)s')
        params["limit"] = max(1, min(limit, 200))
        rows = conn.execute(
            f'SELECT p."id" AS id, ({cfg["label_sql"]}) AS label FROM {t.ident} p '
            f'WHERE {" AND ".join(where)} ORDER BY label LIMIT %(limit)s', params).fetchall()
        return rows

    # ---- write ---------------------------------------------------------------------
    def _prepare(self, t: Table, payload: dict, *, creating: bool, ctx: UserCtx) -> dict:
        values: dict[str, object] = {}
        errors: dict[str, str] = {}
        for name, raw in payload.items():
            if name.startswith("_"):
                continue
            col = t.col(name)
            if col is None:
                errors[name] = "Unknown field"
                continue
            if not col.writable:
                continue                         # generated / identity / system columns are ignored
            if col.kind == "bytea" and not is_blank(raw):
                flag = POLICY_FLAGS.get(col.name)
                if not flag or not getattr(self.settings, flag):
                    raise ApiError(403, "policy",
                                   "Storing this value is switched off by policy (see ALLOW_*_STORAGE in the "
                                   "server settings).", {name: "Storage disabled by policy"})
            try:
                values[name] = coerce(col, raw)
            except FieldError as e:
                errors[name] = e.message
        if creating:
            for col in t.columns:
                if col.required and values.get(col.name) is None and col.name not in errors:
                    errors[col.name] = "Required"
        if errors:
            raise bad_request("Please correct the highlighted fields.", errors)
        return values

    def _expr(self, col: Column, param: str) -> str:
        if col.kind == "vector":
            return f"%({param})s::vector"
        if col.kind == "bytea":
            return f"pgp_sym_encrypt(%({param})s, %(enc_key)s)"
        return f"%({param})s"

    def _record_company(self, conn, t: Table, values: dict, existing: dict | None) -> int | None:
        """The company a record belongs to: its own company_id, or - for a child table - its parent's company."""
        if t.has("company_id"):
            v = values.get("company_id", (existing or {}).get("company_id"))
            return v
        scope = SCOPE.get(t.name)
        if scope and scope["type"] == "parent":
            parent_id = values.get(scope["fk"], (existing or {}).get(scope["fk"]))
            if parent_id is None:
                return None
            parent = self.catalog.get(scope["parent"])
            if parent.has("company_id"):
                row = conn.execute(f'SELECT "company_id" AS c FROM {parent.ident} WHERE "id" = %s', (parent_id,)).fetchone()
                return row["c"] if row else None
            grand = SCOPE.get(parent.name)
            if grand and grand["type"] == "parent":
                row = conn.execute(f'SELECT * FROM {parent.ident} WHERE "id" = %s', (parent_id,)).fetchone()
                return self._record_company(conn, parent, {}, row) if row else None
        return None

    def _check_refs(self, conn, t: Table, values: dict, ctx: UserCtx, record_company: int | None = None) -> None:
        """Every foreign-key value must point at a row the user can see, in the same company as the record
        itself; lookups must be on the right list."""
        sc = Scope(self.catalog)
        errors = {}
        for col in t.columns:
            val = values.get(col.name)
            if val is None:
                continue
            if col.lookup:
                ok = conn.execute(
                    "SELECT 1 FROM core.lookup_value v JOIN core.lookup_list l ON l.id = v.list_id "
                    "WHERE l.code = %s AND v.id = %s", (col.lookup, val)).fetchone()
                if not ok:
                    errors[col.name] = f"Choose a value from the list '{col.lookup}'"
                continue
            if col.fk:
                if col.fk["table"] == "app_user":
                    if val != ctx.id and not ctx.is_admin:
                        errors[col.name] = "You can only name yourself"
                    continue
                parent = self.catalog.get(col.fk["table"])
                params: dict = {"v": val}
                scope_sql = sc.row_scope(parent.name, "p", ctx, "read", params)
                same_company = ""
                # a record may only point at records of its own company (e.g. a meeting's chairperson must be
                # a director of that same company); shared people records and reference data are exempt
                if (record_company is not None and parent.has("company_id") and parent.name != "company"):
                    params["rc"] = record_company
                    same_company = ' AND p."company_id" = %(rc)s'
                ok = conn.execute(
                    f'SELECT 1 FROM {parent.ident} p WHERE p."{col.fk["column"]}" = %(v)s AND ({scope_sql}){same_company}',
                    params).fetchone()
                if not ok:
                    errors[col.name] = ("That record belongs to a different company" if same_company
                                        else "That record does not exist or is not available to you")
        if errors:
            raise bad_request("Please correct the highlighted fields.", errors)

    def _params(self, t: Table, values: dict) -> dict:
        params = {f"p_{n}": v for n, v in values.items()}
        params["enc_key"] = self.settings.encryption_key
        return params

    def create(self, conn, key: str, ctx: UserCtx, payload: dict) -> dict:
        t, _ = self.entity(key)
        self._write(key, ctx)
        values = self._prepare(t, payload, creating=True, ctx=ctx)
        if t.has("company_id") and not ctx.privileged and values.get("company_id") not in ctx.writable:
            raise forbidden("You do not have write access to that company")
        self._check_refs(conn, t, values, ctx, self._record_company(conn, t, values, None))
        cols = [t.col(n) for n in values]
        sql = (f'INSERT INTO {t.ident} ({", ".join(chr(34) + c.name + chr(34) for c in cols)}) '
               f'VALUES ({", ".join(self._expr(c, "p_" + c.name) for c in cols)}) '
               f'RETURNING {", ".join(chr(34) + p + chr(34) for p in t.pk)}'
               ) if cols else f'INSERT INTO {t.ident} DEFAULT VALUES RETURNING {", ".join(chr(34) + p + chr(34) for p in t.pk)}'
        new = conn.execute(sql, self._params(t, values)).fetchone()
        pk = "~".join(str(new[p]) for p in t.pk)
        # the new row must fall inside what this user may write (covers child tables with no company_id)
        self._assert_writable(conn, key, t, ctx, pk)
        return self.get(conn, key, ctx, pk)

    def _assert_writable(self, conn, key: str, t: Table, ctx: UserCtx, pk: str) -> None:
        params: dict = {}
        scope_sql = Scope(self.catalog).row_scope(key, "t", ctx, "write", params)
        where = self._pk_where(t, self._parse_pk(t, pk), params)
        if conn.execute(f'SELECT 1 FROM {t.ident} t WHERE {where} AND ({scope_sql})', params).fetchone() is None:
            raise forbidden("You do not have write access to that company")

    def update(self, conn, key: str, ctx: UserCtx, pk: str, payload: dict) -> dict:
        t, _ = self.entity(key)
        self._write(key, ctx)
        pkvals = self._parse_pk(t, pk)
        version = payload.get("updated_at") if t.has("updated_at") else None
        values = self._prepare(t, {k: v for k, v in payload.items() if k != "updated_at"}, creating=False, ctx=ctx)
        locked = [n for n in values if t.col(n).is_pk or n == "company_id"]
        if locked:
            where_pk = {}
            current = conn.execute(
                f'SELECT {", ".join(chr(34) + n + chr(34) for n in locked)} FROM {t.ident} t WHERE '
                f'{self._pk_where(t, pkvals, where_pk)}', where_pk).fetchone()
            for name in locked:
                if current is None or current[name] != values[name]:
                    raise bad_request(f"{name} cannot be changed once created", {name: "Cannot be changed"})
                del values[name]                  # unchanged: nothing to write
        if not values:
            return self.get(conn, key, ctx, pk)
        existing_params: dict = {}
        existing = conn.execute(f'SELECT * FROM {t.ident} t WHERE {self._pk_where(t, pkvals, existing_params)}',
                                existing_params).fetchone()
        self._check_refs(conn, t, values, ctx, self._record_company(conn, t, values, existing) if existing else None)
        params = self._params(t, values)
        sets = ", ".join(f'"{c}" = {self._expr(t.col(c), "p_" + c)}' for c in values)
        sc = Scope(self.catalog)
        scope_sql = sc.row_scope(key, "t", ctx, "write", params)
        where = [self._pk_where(t, pkvals, params), f"({scope_sql})"]
        if version:
            params["ver"] = version
            where.append('t."updated_at" = %(ver)s::timestamptz')
        cur = conn.execute(f'UPDATE {t.ident} AS t SET {sets} WHERE {" AND ".join(where)}', params)
        if cur.rowcount == 0:
            self._diagnose(conn, key, t, ctx, pkvals, version)
        return self.get(conn, key, ctx, pk)

    def _diagnose(self, conn, key: str, t: Table, ctx: UserCtx, pkvals: dict, version) -> None:
        params: dict = {}
        sc = Scope(self.catalog)
        read_sql = sc.row_scope(key, "t", ctx, "read", params)
        where = self._pk_where(t, pkvals, params)
        if conn.execute(f'SELECT 1 FROM {t.ident} t WHERE {where} AND ({read_sql})', params).fetchone() is None:
            raise not_found()
        params2: dict = {}
        write_sql = sc.row_scope(key, "t", ctx, "write", params2)
        where2 = self._pk_where(t, pkvals, params2)
        if conn.execute(f'SELECT 1 FROM {t.ident} t WHERE {where2} AND ({write_sql})', params2).fetchone() is None:
            raise forbidden("You have read-only access to this record")
        raise conflict("This record was changed by someone else. Reload it and try again.", "stale")

    def set_archived(self, conn, key: str, ctx: UserCtx, pk: str, archived: bool) -> dict:
        t, _ = self.entity(key)
        self._write(key, ctx)
        if not t.has_archive:
            raise bad_request("This kind of record cannot be archived")
        pkvals = self._parse_pk(t, pk)
        params: dict = {"uid": ctx.id}
        scope_sql = Scope(self.catalog).row_scope(key, "t", ctx, "write", params)
        where = self._pk_where(t, pkvals, params)
        if archived:
            sets = 'is_archived = true, archived_at = now(), archived_by = %(uid)s'
        else:
            sets = 'is_archived = false, archived_at = NULL, archived_by = NULL'
        cur = conn.execute(f'UPDATE {t.ident} AS t SET {sets} WHERE {where} AND ({scope_sql})', params)
        if cur.rowcount == 0:
            self._diagnose(conn, key, t, ctx, pkvals, None)
        return self.get(conn, key, ctx, pk)

    # ---- calculated views ---------------------------------------------------------------
    def view_rows(self, conn, view: str, ctx: UserCtx, *, company_id: int | None, limit: int = 1000) -> dict:
        """Rows of a calculated view, restricted to what the user may see.

        The database views are not scoped by row-level security (they run with their owner's
        rights), so the restriction is applied here."""
        v = self.catalog.get(view)
        if v is None or not v.is_view:
            raise not_found("View")
        params: dict = {"rids": ctx.readable}
        if ctx.privileged:
            where = ["TRUE"]
        elif v.has("company_id"):
            where = ['v."company_id" = ANY(%(rids)s::bigint[])']
        elif v.has("committee_id"):
            where = ['EXISTS (SELECT 1 FROM core.committee c WHERE c.id = v."committee_id" '
                     'AND c.company_id = ANY(%(rids)s::bigint[]))']
        elif v.has("director_id"):
            sc = Scope(self.catalog)
            where = [sc.row_scope("director", "d", ctx, "read", params)]
            where = [f'EXISTS (SELECT 1 FROM core.director d WHERE d.id = v."director_id" AND ({where[0]}))']
        else:
            where = ["FALSE"]
        if company_id is not None:
            if v.has("company_id"):
                params["cid"] = company_id
                where.append('v."company_id" = %(cid)s')
            elif v.has("committee_id"):
                params["cid"] = company_id
                where.append('EXISTS (SELECT 1 FROM core.committee c WHERE c.id = v."committee_id" AND c.company_id = %(cid)s)')
            elif v.has("director_id"):
                params["cid"] = company_id
                where.append('EXISTS (SELECT 1 FROM core.directorship ds WHERE ds.director_id = v."director_id" '
                             'AND ds.company_id = %(cid)s)')
        params["limit"] = limit
        rows = conn.execute(f'SELECT v.* FROM {v.ident} v WHERE {" AND ".join(where)} LIMIT %(limit)s',
                            params).fetchall()
        return {"view": view, "columns": [c.name for c in v.columns], "rows": rows}
