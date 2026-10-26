"""Reads the live database catalog so the API never hard-codes a column list.

Every field the UI offers - its type, whether it is required, which table it points at,
which Standard List a dropdown comes from, which values a CHECK constraint allows - is
discovered here from PostgreSQL itself. If the schema gains a column, the API and the
forms gain it too, and the round-trip tests will exercise it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import psycopg

SCHEMAS = ("core", "activity", "ops")

SYSTEM_COLUMNS = ("created_at", "updated_at", "is_archived", "archived_at", "archived_by")

# Free-text columns that deserve a multi-line box rather than a one-line input.
TEXTAREA_NAMES = {
    "description", "details", "notes", "remarks", "address", "registered_address",
    "correspondence_address", "text", "instructions", "particulars", "reason", "content",
    "condition_note", "appeal_details", "inputs_needed", "decides", "trigger_description",
    "applies_to_description", "beneficiary_description", "nature_of_txn", "subject",
    "cessation_reason", "note", "exception_relied_on",
}

_KIND_BY_TYPE = {
    "int2": "int", "int4": "int", "int8": "int",
    "numeric": "decimal", "float4": "decimal", "float8": "decimal",
    "bool": "bool", "date": "date", "time": "time", "timestamptz": "datetime",
    "timestamp": "datetime", "jsonb": "json", "json": "json", "bytea": "bytea",
    "vector": "vector", "text": "text", "varchar": "text", "bpchar": "text",
}


@dataclass
class Column:
    name: str
    pg_type: str
    typname: str
    nullable: bool
    default: str | None
    generated: bool
    identity: bool
    comment: str | None
    kind: str
    precision: int | None = None
    scale: int | None = None
    dims: int | None = None
    is_pk: bool = False
    fk: dict | None = None          # {"schema","table","column"}
    lookup: str | None = None       # Standard List code that validates this column
    choices: list | None = None     # allowed values from a CHECK ... = ANY(ARRAY[...])
    fmt: str | None = None          # e.g. "financial_year"

    @property
    def system(self) -> bool:
        return self.name in SYSTEM_COLUMNS

    @property
    def writable(self) -> bool:
        return not (self.generated or self.identity or self.system)

    @property
    def required(self) -> bool:
        """Must be supplied on create: NOT NULL with nothing to fall back on."""
        return self.writable and not self.nullable and self.default is None


@dataclass
class Table:
    schema: str
    name: str
    is_view: bool
    comment: str | None
    columns: list[Column] = field(default_factory=list)
    pk: list[str] = field(default_factory=list)
    uniques: list[list[str]] = field(default_factory=list)

    @property
    def qname(self) -> str:
        return f"{self.schema}.{self.name}"

    @property
    def ident(self) -> str:
        return f'"{self.schema}"."{self.name}"'

    def col(self, name: str) -> Column | None:
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def has(self, name: str) -> bool:
        return self.col(name) is not None

    @property
    def fks(self) -> list[Column]:
        return [c for c in self.columns if c.fk]

    @property
    def has_archive(self) -> bool:
        return self.has("is_archived")


class Catalog:
    def __init__(self, tables: list[Table]):
        self.tables = tables
        self.by_name: dict[str, Table] = {}
        for t in tables:
            # Table names are unique across the three schemas in this database.
            self.by_name.setdefault(t.name, t)

    def get(self, name: str) -> Table | None:
        return self.by_name.get(name)

    def base_tables(self) -> list[Table]:
        return [t for t in self.tables if not t.is_view]

    def views(self) -> list[Table]:
        return [t for t in self.tables if t.is_view]


_ENUM_RE = re.compile(r"CHECK \(\(\(?(\w+) = ANY \(ARRAY\[(.*?)\]\)\)\)?\)")
_LITERAL_RE = re.compile(r"'((?:[^']|'')*)'::text|(-?\d+)(?!\w)")
_FY_RE = re.compile(r"CHECK \(\((\w+) ~ ")
_LOOKUP_RE = re.compile(r"validate_lookup\('(\w+)', '(\w+)'\)")
_TYPMOD_NUM = re.compile(r"numeric\((\d+),(\d+)\)")
_TYPMOD_VEC = re.compile(r"vector\((\d+)\)")


def _kind(typname: str) -> str:
    return _KIND_BY_TYPE.get(typname, "text")


def load_catalog(conn: psycopg.Connection) -> Catalog:
    cols_sql = """
        SELECT c.oid AS reloid, n.nspname AS schema, c.relname AS table, c.relkind,
               obj_description(c.oid) AS table_comment,
               a.attnum, a.attname, format_type(a.atttypid, a.atttypmod) AS pg_type, t.typname,
               NOT a.attnotnull AS nullable, pg_get_expr(d.adbin, d.adrelid) AS default_expr,
               a.attgenerated <> '' AS generated, a.attidentity <> '' AS identity,
               col_description(c.oid, a.attnum) AS comment
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_type t ON t.oid = a.atttypid
        LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE n.nspname = ANY(%s) AND c.relkind IN ('r', 'v')
          AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY n.nspname, c.relname, a.attnum
    """
    tables: dict[int, Table] = {}
    attnum_name: dict[tuple[int, int], str] = {}
    for r in conn.execute(cols_sql, (list(SCHEMAS),)).fetchall():
        t = tables.get(r["reloid"])
        if t is None:
            t = tables[r["reloid"]] = Table(r["schema"], r["table"], r["relkind"] == "v", r["table_comment"])
        col = Column(
            name=r["attname"], pg_type=r["pg_type"], typname=r["typname"], nullable=r["nullable"],
            default=r["default_expr"], generated=r["generated"], identity=r["identity"],
            comment=r["comment"], kind=_kind(r["typname"]),
        )
        m = _TYPMOD_NUM.match(r["pg_type"])
        if m:
            col.precision, col.scale = int(m.group(1)), int(m.group(2))
        m = _TYPMOD_VEC.match(r["pg_type"])
        if m:
            col.dims = int(m.group(1))
        if col.kind == "text" and col.name in TEXTAREA_NAMES:
            col.kind = "textarea"
        t.columns.append(col)
        attnum_name[(r["reloid"], r["attnum"])] = r["attname"]

    oid_of = {id(t): oid for oid, t in tables.items()}
    by_qname = {t.qname: t for t in tables.values()}

    con_sql = """
        SELECT conrelid AS reloid, contype, conkey, confrelid, confkey,
               pg_get_constraintdef(oid) AS def
        FROM pg_constraint
        WHERE connamespace::regnamespace::text = ANY(%s) AND contype IN ('p', 'u', 'f', 'c')
    """
    for r in conn.execute(con_sql, (list(SCHEMAS),)).fetchall():
        t = tables.get(r["reloid"])
        if t is None:
            continue
        names = [attnum_name[(r["reloid"], n)] for n in (r["conkey"] or [])]
        if r["contype"] == "p":
            t.pk = names
            for n in names:
                t.col(n).is_pk = True
        elif r["contype"] == "u":
            t.uniques.append(names)
        elif r["contype"] == "f" and len(names) == 1:
            parent = tables.get(r["confrelid"])
            if parent is not None:
                pcol = attnum_name[(r["confrelid"], r["confkey"][0])]
                t.col(names[0]).fk = {"schema": parent.schema, "table": parent.name, "column": pcol}
        elif r["contype"] == "c":
            definition = r["def"]
            m = _ENUM_RE.search(definition)
            if m and t.col(m.group(1)):
                values: list = []
                for lit in _LITERAL_RE.finditer(m.group(2)):
                    values.append(lit.group(1).replace("''", "'") if lit.group(1) is not None else int(lit.group(2)))
                t.col(m.group(1)).choices = values
                continue
            m = _FY_RE.match(definition)
            if m and m.group(1) == "financial_year" and t.col("financial_year"):
                t.col("financial_year").fmt = "financial_year"

    trg_sql = """
        SELECT tgrelid AS reloid, pg_get_triggerdef(oid) AS def
        FROM pg_trigger WHERE NOT tgisinternal AND tgname LIKE 'validate_lookup%%'
    """
    for r in conn.execute(trg_sql).fetchall():
        t = tables.get(r["reloid"])
        m = _LOOKUP_RE.search(r["def"])
        if t is not None and m and t.col(m.group(2)):
            t.col(m.group(2)).lookup = m.group(1)

    del oid_of, by_qname
    return Catalog(sorted(tables.values(), key=lambda t: (t.schema, t.name)))
