"""Builds a valid record - with EVERY writable field filled in - for any table, from the live metadata.

Values are generated from each column's type, required-ness, dropdown list, allowed choices and the table it
points at; a handful of tables need hand-written help where the database has cross-column rules (one-of-two
references, unique pairs, date ranges that must not overlap). The round-trip test then proves each field is
stored exactly as sent.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

END_NAMES = {"end_date", "valid_to", "dissolved_on", "account_period_to", "voting_closes", "maturity_date", "reviewed_on"}
SKIP_SECRETS = {"aadhaar_encrypted", "secret_encrypted"}        # storage policy is tested separately


class Factory:
    def __init__(self, admin, owner, meta, uniq):
        self.admin, self.owner, self.meta, self.uniq = admin, owner, meta, uniq
        self.ent = meta["entities"]
        self.admin_id = admin.user["id"]
        self._cache: dict[str, int] = {}

    # ---- values -----------------------------------------------------------------------------------
    def fy(self, n):
        return f"{2100 + n}-{(2101 + n) % 100:02d}"

    def year(self, n):
        return 2100 + 2 * n

    def lookup(self, code, i=0):
        vals = self.meta["lookups"][code]
        return vals[i % len(vals)]["id"]

    def pick(self, table, company=1):
        """An existing, non-archived row id (preferring the given company)."""
        cols = {c["name"] for c in self.ent[table]["columns"]}
        sql = f"SELECT id FROM {self.ent[table]['schema']}.{table} WHERE TRUE"
        if "is_archived" in cols:
            sql += " AND NOT is_archived"
        if "company_id" in cols:
            sql += f" AND company_id = {int(company)}"
        row = self.owner.execute(sql + " ORDER BY id LIMIT 1").fetchone()
        return row["id"] if row else None

    def ensure(self, table, company=1):
        found = self.pick(table, company)
        if found:
            return found
        return self.create(table, company=company)["id"]

    def fresh(self, table, company=1):
        return self.create(table, company=company)["id"]

    # ---- one column -------------------------------------------------------------------------------
    def value(self, table, col, n, company):
        name, kind = col["name"], col["kind"]
        if col.get("lookup"):
            return self.lookup(col["lookup"], n)
        if col.get("fk"):
            parent = col["fk"]
            if parent == "app_user":
                return self.admin_id
            if parent == "company":
                return company if name == "company_id" else (2 if company != 2 else 3)
            return self.ensure(parent, company)
        if col.get("choices"):
            return col["choices"][0]
        if kind == "text" or kind == "textarea":
            if col.get("format") == "financial_year":
                return self.fy(n)
            return f"{name}_{n}"[:48]
        if kind == "int":
            return 7 + (n % 5)
        if kind == "decimal":
            return "12.34"
        if kind == "bool":
            return True
        if kind == "date":
            y = self.year(n) + (1 if name in END_NAMES else 0)
            return f"{y}-03-15"
        if kind == "time":
            return "10:30:00"
        if kind == "datetime":
            return f"{self.year(n)}-03-15T10:30"
        if kind == "json":
            return {"k": f"v{n}", "n": n}
        if kind == "vector":
            return [0.01] * (col.get("dims") or 1536)
        raise AssertionError(f"no generator for {table}.{name} ({kind})")

    # ---- a whole record -------------------------------------------------------------------------------
    def payloads(self, table, company=1) -> list[dict]:
        """One or more payloads that, together, populate every writable field of `table`."""
        n = self.uniq()
        cols = [c for c in self.ent[table]["columns"] if c["writable"] and c["name"] not in SKIP_SECRETS]
        base = {c["name"]: self.value(table, c, n, company) for c in cols}
        if "company_id" in base:
            base["company_id"] = company
        hook = getattr(self, f"_fix_{table}", None)
        out = hook(base, n, company) if hook else [base]
        return out if isinstance(out, list) else [out]

    def create(self, table, company=1, **over):
        payload = self.payloads(table, company)[0]
        payload.update(over)
        r = self.admin.post(f"/entities/{table}", payload)
        assert r.status_code == 201, f"{table}: {r.status_code} {r.text[:500]}"
        return r.json()["row"]

    # ---- tables that need help ------------------------------------------------------------------------
    def _fix_app_user(self, p, n, c):
        p["email"] = f"user{n}@example.test"
        return p

    def _fix_director(self, p, n, c):
        p["din"] = f"{70000000 + n}"
        p["gender"] = "F"
        p["pan"] = f"ABCDE{n % 9000 + 1000}F"
        return p

    def _fix_company(self, p, n, c):
        p["cin"] = f"U{n:020d}"
        p["status"] = "active"
        return p

    def _fix_foreign_investment(self, p, n, c):
        gpr = dict(p, allotment_id=self.ensure("allotment", c), type_id=self.lookup("FOREIGN_INVESTMENT_TYPE", 0))
        gpr.pop("share_transfer_id", None)
        trs = dict(p, share_transfer_id=self.ensure("share_transfer", c), type_id=self.lookup("FOREIGN_INVESTMENT_TYPE", 1))
        trs.pop("allotment_id", None)
        return [gpr, trs]

    def _fix_directorship(self, p, n, c):
        # seeded stints are open-ended, so a new date range for an existing person would overlap; use a new person
        p["director_id"] = self.fresh("director", c)
        return p

    def _fix_directorship_role(self, p, n, c):
        p["directorship_id"] = self.fresh("directorship", c)
        return p

    def _fix_independent_director_term(self, p, n, c):
        p["directorship_id"] = self.fresh("directorship", c)
        p["term_no"] = 1
        return p

    def _fix_evidence_link(self, p, n, c):
        p["entity_type"] = "meeting"
        p["entity_id"] = self.ensure("meeting", c)
        p["task_instance_id"] = self.pick("task_instance", c)
        return p

    def _fix_task_record_link(self, p, n, c):
        p["entity_type"] = "directorship"
        p["entity_id"] = self.ensure("directorship", c)
        p["task_instance_id"] = self.pick("task_instance", c)
        p["mode"] = "read"
        return p

    def _fix_role_permission(self, p, n, c):
        p["role_id"] = self.fresh("role", c)
        p["permission_id"] = self.fresh("permission", c)
        return p

    def _fix_user_company_access(self, p, n, c):
        p["user_id"] = self.fresh("app_user", c)
        p["company_id"] = 1
        p["access_level"] = "read"
        return p

    def _fix_lookup_value(self, p, n, c):
        p["list_id"] = self.fresh("lookup_list", c)
        return p

    def _fix_step_template(self, p, n, c):
        p["template_id"] = self.fresh("activity_template", c)
        p["seq"] = 1000 + n
        p["deadline_anchor"], p["deadline_offset_days"], p["deadline_direction"] = "meeting_date", 7, "before"
        return p

    def _fix_step_dependency(self, p, n, c):
        tpl = self.fresh("activity_template", c)
        mk = lambda seq: self.admin.post("/entities/step_template", {
            "template_id": tpl, "step_key": f"S{n}_{seq}", "seq": seq, "title": f"Step {seq}", "step_type": "manual"}).json()["row"]["id"]
        p["step_id"], p["depends_on_step_id"] = mk(2), mk(1)
        return p

    def _fix_step_data_binding(self, p, n, c):
        p["step_id"] = self.fresh("step_template", c)
        field = self.owner.execute("SELECT id FROM activity.entity_field_registry WHERE NOT is_calculated ORDER BY id LIMIT 1").fetchone()
        p["field_id"] = field["id"]
        p["mode"] = "read"
        return p

    def _fix_activity_template(self, p, n, c):
        p["code"] = f"TPL_{n}"
        p["version"] = 1
        p["status"] = "draft"
        return p

    def _fix_meeting_attendance(self, p, n, c):
        p["attendee_type"] = "director"
        p["directorship_id"] = self.ensure("directorship", c)
        p["shareholder_id"] = self.ensure("shareholder", c)
        return p

    def _fix_document_chunk(self, p, n, c):
        p["document_id"] = self.ensure("document", c)
        return p

    def _fix_document(self, p, n, c):
        p["sha256"] = f"{n:064x}"
        p["version"] = 2
        return p

    def _fix_rule_definition(self, p, n, c):
        p["code"] = f"RULE_{n}"
        return p

    def _fix_document_type(self, p, n, c):
        p["code"] = f"DT_{n}"
        return p

    def _fix_permission(self, p, n, c):
        p["code"] = f"perm.{n}"
        return p

    def _fix_role(self, p, n, c):
        p["name"] = f"role_{n}"
        return p

    def _fix_lookup_list(self, p, n, c):
        p["code"] = f"LIST_{n}"
        return p

    def _fix_company_relationship(self, p, n, c):
        p["related_company_id"] = 2
        return p

    def _fix_confirmation(self, p, n, c):
        return {"subject_type": "task_instance", "subject_id": self.pick("task_instance", c)}


# tables the generic create endpoint deliberately refuses (a workflow creates them) or that are read-only
WORKFLOW_CREATED = {"company", "activity_instance", "task_instance"}
READ_ONLY = {"entity_field_registry"}
# columns of creatable tables that only a workflow action may set (proved in the workflow tests instead)
WORKFLOW_COLUMNS = {"confirmation": {"requested_by", "confirmed_by", "confirmed_at", "status"}}


def same(col, sent, got):
    """Does the stored value equal what was sent?"""
    k = col["kind"]
    if sent is None:
        return got is None
    if k == "decimal":
        return Decimal(str(sent)) == Decimal(str(got))
    if k == "time":
        return str(got)[:5] == str(sent)[:5]
    if k == "datetime":
        return datetime.fromisoformat(str(got)).replace(tzinfo=None) == datetime.fromisoformat(str(sent)).replace(tzinfo=None)
    if k == "date":
        return str(got)[:10] == str(sent)[:10]
    if k == "vector":
        return got == len(sent)                                  # the API reports the stored dimension count
    if k == "json":
        return got == sent
    return got == sent
