"""Change 8: ODI, ECB and DI / foreign investment records live in one "ODI / ECB / DI / Foreign Investments" view (tracking only)."""
from pathlib import Path

from app.registry import ENTITIES, NAV

SCRIPTS = Path(__file__).resolve().parents[2] / "app" / "static" / "scripts"
LABEL = "ODI / ECB / DI / Foreign Investments"
FORMER = {"odi", "odi_step_down_subsidiary", "ecb", "foreign_investment"}


def test_one_nav_entry_with_the_exact_label_and_no_old_entries():
    items = [i for g in NAV for i in g["items"]]
    assert [i for i in items if i.get("label") == "ODI / ECB / DI / Foreign Investments"] == [{"view": "foreign", "label": LABEL}]
    assert not (FORMER & {i["entity"] for i in items if "entity" in i})
    assert FORMER <= set(ENTITIES)                                              # the record types themselves are untouched


def test_the_view_mounts_every_former_record_type_and_is_registered():
    src = (SCRIPTS / "foreign.js").read_text(encoding="utf-8")
    for key in FORMER:
        assert f'"{key}"' in src, key
    assert 'id="foreign-investments-tab"' in src
    main = (SCRIPTS / "main.js").read_text(encoding="utf-8")
    assert '"foreign"' in main and "foreign.render()" in main


def test_each_record_type_is_still_readable_through_the_api(admin):
    for key in FORMER:
        assert admin.get(f"/entities/{key}", params={"company_id": 1}).status_code == 200, key


def test_the_view_has_no_inline_html_from_database_text_and_no_rules():
    src = (SCRIPTS / "foreign.js").read_text(encoding="utf-8")
    assert "<script" not in src and "onclick" not in src
    assert "/rules" not in src and "activity_template" not in src               # tracking only (D8)
