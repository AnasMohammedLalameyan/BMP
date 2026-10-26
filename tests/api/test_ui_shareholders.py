"""Change 7: one "Shareholders" link and panel. The cap table shows the database's own calculated percentages."""
import re
from decimal import Decimal
from pathlib import Path

from app.registry import ENTITIES, NAV

SCRIPTS = Path(__file__).resolve().parents[2] / "app" / "static" / "scripts"

FORMER_ENTRIES = {"share_class", "capital_snapshot", "capital_event", "shareholder", "shareholding", "allotment", "share_transfer"}


def test_the_sidebar_has_one_shareholders_link_and_the_old_entries_are_gone():
    capital = next(g for g in NAV if g["id"] == "capital")
    assert {"view": "shareholders", "label": "Shareholders"} in capital["items"]
    in_nav = {i["entity"] for g in NAV for i in g["items"] if "entity" in i}
    assert not (FORMER_ENTRIES & in_nav)


def test_every_formerly_separate_capital_record_type_is_still_reachable():
    panel = (SCRIPTS / "shareholders.js").read_text(encoding="utf-8")
    master = (SCRIPTS / "masterdata.js").read_text(encoding="utf-8")
    for key in ("shareholding", "allotment", "share_transfer", "shareholder"):                  # in the Shareholders panel
        assert f'"{key}"' in panel, key
    for key in ("share_class", "capital_snapshot", "capital_event"):                            # the company's capital: Master Data
        assert f'"{key}"' in master, key
    assert all(k in ENTITIES for k in FORMER_ENTRIES)


def test_the_browser_never_computes_a_percentage():
    src = (SCRIPTS / "shareholders.js").read_text(encoding="utf-8")
    assert not re.search(r"\*\s*100|/\s*(?:r\.)?total|toFixed|Math\.round", src)
    assert "/calc/v_shareholding_percent" in src and "holding_percent" in src


def test_cap_table_percentages_are_the_core_views_values_and_add_up(admin, owner):
    rows = admin.ok(admin.get("/calc/v_shareholding_percent", params={"company_id": 2}))["rows"]
    direct = owner.execute("SELECT * FROM core.v_shareholding_percent WHERE company_id = 2").fetchall()
    key = lambda r: (r["shareholder_id"], r["share_class_id"])
    assert {key(r): (r["number_of_shares"], Decimal(str(r["holding_percent"]))) for r in rows} == \
           {key(r): (r["number_of_shares"], r["holding_percent"]) for r in direct}              # exactly what the database calculates
    assert rows
    by_class = {}
    for r in rows:
        by_class.setdefault(r["share_class_id"], []).append(r)
        expected = (Decimal(r["number_of_shares"]) * 100 / Decimal(str(r["total_shares"]))).quantize(Decimal("0.0001"))
        assert Decimal(str(r["holding_percent"])) == expected                                   # the view's arithmetic, checked independently
    for holders in by_class.values():
        assert sum(r["number_of_shares"] for r in holders) == Decimal(str(holders[0]["total_shares"]))
        assert abs(sum(Decimal(str(r["holding_percent"])) for r in holders) - 100) < Decimal("0.01")   # a complete class adds up to 100 %


def test_the_cap_table_data_is_scoped_to_the_users_companies(client, manager):
    assert client.get("/calc/v_shareholding_percent", params={"company_id": 2}).status_code == 404
    assert manager.get("/calc/v_shareholding_percent", params={"company_id": 1}).status_code == 404
    own = client.ok(client.get("/calc/v_shareholding_percent", params={"company_id": 1}))["rows"]
    assert own and {r["company_id"] for r in own} == {1}
