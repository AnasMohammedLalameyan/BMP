"""Requirement: every field in the database is available through the application and stores its data exactly.

For every table the application may write to, this creates a record with EVERY writable field populated, reads it back and
compares each field, edits one, then archives and restores it. A final test proves the workflow-only tables and the
fields a person cannot type (calculated, system and workflow-set) behave as designed.
"""
import pytest

from tests.api.payloads import READ_ONLY, SKIP_SECRETS, WORKFLOW_COLUMNS, WORKFLOW_CREATED, Factory, same


@pytest.fixture(scope="module")
def meta(admin):
    return admin.ok(admin.get("/meta"))


@pytest.fixture(scope="module")
def factory(admin, owner, meta, uniq):
    return Factory(admin, owner, meta, uniq)


def creatable(meta):
    return sorted(k for k in meta["entities"] if k not in WORKFLOW_CREATED and k not in READ_ONLY)


def test_the_list_of_tables_covered_is_complete(meta):
    covered = set(creatable(meta)) | WORKFLOW_CREATED | READ_ONLY
    assert covered == set(meta["entities"]) and len(covered) == 65


@pytest.mark.parametrize("table", sorted(set(__import__("app.registry", fromlist=["ENTITIES"]).ENTITIES) - WORKFLOW_CREATED - READ_ONLY))
def test_every_field_round_trips(admin, factory, meta, table):
    ent = meta["entities"][table]
    writable = {c["name"] for c in ent["columns"] if c["writable"] and c["name"] not in SKIP_SECRETS}
    writable -= WORKFLOW_COLUMNS.get(table, set())
    variants = factory.payloads(table)

    # 1. between them the payloads populate every writable field
    sent_columns = set().union(*[set(p) for p in variants])
    assert writable <= sent_columns, f"{table}: fields not exercised: {sorted(writable - sent_columns)}"

    created = []
    for payload in variants:
        r = admin.post(f"/entities/{table}", payload)
        assert r.status_code == 201, f"{table}: {r.status_code} {r.text[:600]}"
        row = r.json()["row"]
        created.append(row)
        # 2. every value comes back exactly as stored
        cols = {c["name"]: c for c in ent["columns"]}
        for name, sent in payload.items():
            if not cols[name]["writable"]:
                continue
            assert same(cols[name], sent, row[name]), f"{table}.{name}: sent {sent!r}, stored {row[name]!r}"
        # 3. and again on a fresh read
        again = admin.ok(admin.get(f"/entities/{table}/{row['_pk']}"))["row"]
        for name, sent in payload.items():
            if cols[name]["writable"]:
                assert same(cols[name], sent, again[name]), f"{table}.{name} after reload"
        # 4. the system columns were filled in by the database, not by the caller
        if "created_at" in row:                      # (the step-dependency link table carries no system columns)
            assert row["created_at"] and row["updated_at"] and row["is_archived"] is False

    row = created[0]
    cols = {c["name"]: c for c in ent["columns"]}

    # 5. a stale edit is refused, a current edit is applied
    patchable = next((c for c in ent["columns"] if c["writable"] and c["kind"] in ("text", "int", "bool")
                      and not c.get("fk") and not c.get("lookup") and not c.get("choices") and not c.get("format")
                      and not c["pk"] and c["name"] not in ("code", "email", "din", "cin", "name", "step_key", "seq", "term_no", "version", "entity_type", "entity_id", "attendee_type", "mode")), None)
    if patchable:
        old = row[patchable["name"]]
        new = (not old) if patchable["kind"] == "bool" else (old + 1 if patchable["kind"] == "int" else f"{old}_edited")
        r = admin.patch(f"/entities/{table}/{row['_pk']}", {patchable["name"]: new, "updated_at": row["updated_at"]})
        assert r.status_code == 200, r.text
        edited = r.json()["row"]
        assert edited[patchable["name"]] == new and edited["updated_at"] != row["updated_at"]
        stale = admin.patch(f"/entities/{table}/{row['_pk']}", {patchable["name"]: old, "updated_at": row["updated_at"]})
        assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale"
        row = edited

    # 6. nothing is deleted: archive hides the record, restore brings it back
    if ent["archivable"]:
        arch = admin.ok(admin.post(f"/entities/{table}/{row['_pk']}/archive"))["row"]
        assert arch["is_archived"] is True and arch["archived_at"] and arch["archived_by"] == admin.user["id"]
        live = {x["_pk"] for x in admin.ok(admin.get(f"/entities/{table}", params={"size": 5000}))["rows"]}
        assert row["_pk"] not in live
        every = {x["_pk"] for x in admin.ok(admin.get(f"/entities/{table}", params={"size": 5000, "archived": "true"}))["rows"]}
        assert row["_pk"] in every
        back = admin.ok(admin.post(f"/entities/{table}/{row['_pk']}/restore"))["row"]
        assert back["is_archived"] is False and back["archived_at"] is None


def test_every_change_is_in_the_audit_trail_with_who_and_when(admin, factory, owner):
    row = factory.create("company_rta")
    entries = admin.ok(admin.get(f"/entities/company_rta/{row['id']}/history"))["entries"]
    assert entries and entries[0]["operation"] == "INSERT" and entries[0]["actor"] == admin.user["name"]
    admin.ok(admin.patch(f"/entities/company_rta/{row['id']}", {"phone": "999", "updated_at": row["updated_at"]}))
    entries = admin.ok(admin.get(f"/entities/company_rta/{row['id']}/history"))["entries"]
    assert entries[0]["operation"] == "UPDATE" and entries[0]["changes"]["phone"]["to"] == "999"
    assert owner.execute("SELECT actor FROM audit.log WHERE table_name = 'company_rta' AND record_id = %s ORDER BY id DESC LIMIT 1",
                         (row["id"],)).fetchone()["actor"] == admin.user["id"]


def test_the_database_refuses_what_the_forms_cannot_catch(admin, factory):
    """Rules the database enforces and the API only translates into plain language."""
    ok = factory.payloads("company_financials")[0]
    assert admin.post("/entities/company_financials", {**ok, "financial_year": "2024/25"}).status_code == 422
    r = admin.post("/entities/company_financials", {**ok, "financial_year": "2099-00"})
    assert r.status_code == 201
    dup = admin.post("/entities/company_financials", {**ok, "financial_year": "2099-00"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "duplicate"
    # an overlapping directorship stint is rejected by the exclusion constraint
    stint = factory.payloads("directorship")[0]
    first = admin.post("/entities/directorship", stint)
    assert first.status_code == 201
    clash = admin.post("/entities/directorship", {**stint, "start_date": stint["start_date"]})
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "overlap"
    # a lookup value from the wrong list is refused
    meeting = factory.payloads("meeting")[0]
    wrong = factory.lookup("DESIGNATION")
    r = admin.post("/entities/meeting", {**meeting, "meeting_type_id": wrong})
    assert r.status_code == 422 and "meeting_type_id" in r.json()["error"]["fields"]
    # required and malformed values name the field
    r = admin.post("/entities/company_rta", {"company_id": 1})
    assert r.status_code == 422 and {"name", "valid_from"} <= set(r.json()["error"]["fields"])
    r = admin.post("/entities/company_rta", {"company_id": 1, "name": "x", "valid_from": "31/12/2024"})
    assert r.status_code == 422 and "valid_from" in r.json()["error"]["fields"]
    r = admin.post("/entities/director", {**factory.payloads("director")[0], "din": "123"})
    assert r.status_code == 422                                        # DIN must be 8 digits
    r = admin.post("/entities/company_rta", {"company_id": 1, "name": "x", "valid_from": "2024-04-01", "nonsense": 1})
    assert r.status_code == 422 and "nonsense" in r.json()["error"]["fields"]


def test_calculated_and_system_columns_cannot_be_written(admin, factory):
    p = factory.payloads("remuneration")[0]
    row = admin.ok(admin.post("/entities/remuneration", {**p, "total": "999999", "is_archived": True, "created_at": "2001-01-01T00:00"}), 201)["row"]
    assert row["total"] != "999999.00" and row["is_archived"] is False and not row["created_at"].startswith("2001")
    expected = sum(float(p[k]) for k in ("salary", "perquisites", "profits_in_lieu", "stock_options", "sweat_equity", "commission",
                                          "sitting_fees", "other_payments"))
    assert float(row["total"]) == pytest.approx(expected)              # worked out by the database, never typed


def test_the_company_record_stores_every_field(admin, factory, meta):
    payload = factory.payloads("company")[0]
    row = admin.ok(admin.post("/companies", payload), 201)["row"]
    cols = {c["name"]: c for c in meta["entities"]["company"]["columns"]}
    writable = {n for n, c in cols.items() if c["writable"]}
    assert writable <= set(payload)
    for name, sent in payload.items():
        assert same(cols[name], sent, row[name]), name
    # the creating administrator was granted access, and the company is visible in their list
    assert row["id"] in [c["id"] for c in admin.ok(admin.get("/companies"))["companies"]]
    # the generic endpoint refuses to create a company outside the onboarding flow
    assert admin.post("/entities/company", payload).status_code == 405
    # edits and archive go through the normal record endpoints
    upd = admin.ok(admin.patch(f"/entities/company/{row['id']}", {"website": "https://x.test", "updated_at": row["updated_at"]}))["row"]
    assert upd["website"] == "https://x.test"


def test_workflow_tables_cannot_be_created_or_set_by_hand(admin, factory):
    for key in ("activity_instance", "task_instance"):
        assert admin.post(f"/entities/{key}", {}).status_code == 405
    task = factory.pick("task_instance")
    row = admin.ok(admin.get(f"/entities/task_instance/{task}"))["row"]
    r = admin.patch(f"/entities/task_instance/{task}", {"status": "completed", "updated_at": row["updated_at"]})
    assert r.status_code == 422                                          # only the workflow endpoint may move a task
    assert admin.post("/entities/entity_field_registry", {"table_name": "a", "column_name": "b"}).status_code == 403
