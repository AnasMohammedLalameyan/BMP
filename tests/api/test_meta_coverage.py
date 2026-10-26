"""Every table, column, key, dropdown and view of the Phase 1 database is described by the API and reachable from the UI."""
from app.registry import ENTITIES, NAV, VIEWS

# screens that are hand-built rather than generic table pages; the tables behind them are still fully editable
DEDICATED = {"company": "Companies page / Master Data", "meeting": "Minutes & Meetings", "document": "Documents & Evidence",
             "rule_evaluation": "Applicability Rules", "activity_instance": "Activities & Tasks", "task_instance": "Activities & Tasks",
             # the client asked for one "Directors" link: these now live inside that panel (test_ui_directors_panel.py checks the panel lists them)
             "director": "Directors panel (DIN & KYC)", "committee": "Directors panel (Board Committees)",
             # one "Shareholders" link: holders, allotments and transfers sit in that panel, the company's capital in Master Data
             # (test_ui_shareholders.py checks the panel / Master Data lists them)
             "shareholder": "Shareholders panel", "share_transfer": "Shareholders panel (Transfers)",
             "share_class": "Master Data (capital)", "capital_snapshot": "Master Data (capital)", "capital_event": "Master Data (capital)",
             # one "ODI / ECB / DI / Foreign Investments" tab (test_ui_foreign.py checks the view lists them)
             "odi": "ODI / ECB / DI / Foreign Investments", "ecb": "ODI / ECB / DI / Foreign Investments",
             "foreign_investment": "ODI / ECB / DI / Foreign Investments"}


def db_columns(owner):
    rows = owner.execute("""SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema IN ('core','activity','ops') AND table_name IN
          (SELECT table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE' AND table_schema IN ('core','activity','ops'))
        ORDER BY table_name, ordinal_position""").fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["table_name"], []).append(r["column_name"])
    return out


def test_every_database_table_has_a_registry_entry(owner):
    tables = {r["table_name"] for r in owner.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema IN ('core','activity','ops') AND table_type = 'BASE TABLE'")}
    assert tables == set(ENTITIES), f"missing: {tables - set(ENTITIES)}, extra: {set(ENTITIES) - tables}"
    assert len(tables) == 65


def test_meta_lists_every_column_of_every_table_for_an_admin(admin, owner):
    meta = admin.ok(admin.get("/meta"))
    cols = db_columns(owner)
    assert set(meta["entities"]) == set(cols)
    for table, names in cols.items():
        assert [c["name"] for c in meta["entities"][table]["columns"]] == names, table


def test_every_foreign_key_dropdown_and_choice_is_described(admin, owner):
    meta = admin.ok(admin.get("/meta"))
    fks = owner.execute("""SELECT c.conrelid::regclass::text AS tbl, a.attname AS col, c.confrelid::regclass::text AS parent
        FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
        WHERE c.contype = 'f' AND c.connamespace::regnamespace::text IN ('core','activity','ops')""").fetchall()
    assert len(fks) == 123
    for r in fks:
        table, parent = r["tbl"].split(".")[-1], r["parent"].split(".")[-1]
        col = next(c for c in meta["entities"][table]["columns"] if c["name"] == r["col"])
        assert col.get("fk") == parent or col.get("lookup"), (table, r["col"])
    lookups = owner.execute("SELECT tgrelid::regclass::text AS tbl, pg_get_triggerdef(oid) AS d FROM pg_trigger WHERE tgname LIKE 'validate_lookup%'").fetchall()
    assert len(lookups) == 23
    for r in lookups:
        import re
        lst, colname = re.search(r"validate_lookup\('(\w+)', '(\w+)'\)", r["d"]).groups()
        col = next(c for c in meta["entities"][r["tbl"].split(".")[-1]]["columns"] if c["name"] == colname)
        assert col["lookup"] == lst and lst in meta["lookups"] and meta["lookups"][lst], (r["tbl"], colname)
    # the 19 Standard Lists and their values are all offered
    assert len(meta["lookups"]) == 19 and sum(len(v) for v in meta["lookups"].values()) == 102


def test_check_constraints_become_choices(admin):
    cols = {c["name"]: c for c in admin.ok(admin.get("/meta"))["entities"]["meeting"]["columns"]}
    assert cols["status"]["choices"] == ["planned", "held", "cancelled"]
    assert cols["financial_year"]["format"] == "financial_year"
    assert cols["meeting_date"]["required"] is True and cols["meeting_number"]["required"] is False


def test_calculated_and_system_columns_are_marked_read_only(admin):
    ent = admin.ok(admin.get("/meta"))["entities"]
    total = next(c for c in ent["remuneration"]["columns"] if c["name"] == "total")
    assert total["generated"] is True and total["writable"] is False
    for col in ent["company"]["columns"]:
        if col["name"] in ("id", "created_at", "updated_at", "is_archived", "archived_at", "archived_by"):
            assert col["writable"] is False


def test_all_13_calculated_views_are_offered(admin):
    meta = admin.ok(admin.get("/meta"))
    assert set(meta["views"]) == set(VIEWS) and len(VIEWS) == 13


def test_every_table_is_reachable_from_the_user_interface():
    in_nav = {i["entity"] for g in NAV for i in g["items"] if "entity" in i}
    as_child = {c[0] for cfg in ENTITIES.values() for c in cfg.get("children", [])}
    unreachable = set(ENTITIES) - in_nav - as_child - set(DEDICATED)
    assert not unreachable, f"no screen for: {unreachable}"
    assert all(i["entity"] in ENTITIES for g in NAV for i in g["items"] if "entity" in i)


def test_every_entity_has_a_label_columns_and_a_row_sentence(admin):
    meta = admin.ok(admin.get("/meta"))["entities"]
    for key, e in meta.items():
        assert e["label"] and e["singular"] and e["list"], key
        assert all(c in {x["name"] for x in e["columns"]} for c in e["list"]), key


def test_a_read_only_client_does_not_see_admin_entities(client):
    ent = client.ok(client.get("/meta"))["entities"]
    assert "app_user" not in ent and "user_company_access" not in ent
    assert ent["meeting"]["can_write"] is True or ent["meeting"]["can_write"] is False   # exposed; the server enforces per company


def test_the_calculated_values_screen_is_gone_but_the_13_views_are_still_served(admin):
    """Change 5: the screen and its sidebar entry were removed at the client's request; the database views and /api/calc stay."""
    assert not any(i.get("view") == "calc" or i.get("label") == "Calculated Values" for g in NAV for i in g["items"])
    meta = admin.ok(admin.get("/meta"))
    assert not any(i.get("view") == "calc" for g in meta["nav"] for i in g["items"])
    assert set(meta["views"]) == set(VIEWS) and len(VIEWS) == 13
    for view in VIEWS:
        assert admin.ok(admin.get(f"/calc/{view}", params={"company_id": 2}))["view"] == view
