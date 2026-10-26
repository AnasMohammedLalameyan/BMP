"""Change 6: one "Directors" link and panel. Server side: the register rows carry what the segments need.
Front-end side: every record type that used to have its own sidebar entry is reachable from the panel."""
import re
from pathlib import Path

from app.registry import ENTITIES, NAV

SCRIPTS = Path(__file__).resolve().parents[2] / "app" / "static" / "scripts"

FORMER_SIDEBAR_ENTRIES = {"director", "directorship", "directorship_role", "independent_director_term", "director_declaration",
                          "director_kyc", "director_residency", "director_other_directorship", "committee", "committee_member"}


def test_the_sidebar_has_one_directors_link_and_no_duplicate_children():
    people = next(g for g in NAV if g["id"] == "people")
    assert people["items"] == [{"view": "directors", "label": "Directors"}]
    in_nav = {i["entity"] for g in NAV for i in g["items"] if "entity" in i}
    assert not (FORMER_SIDEBAR_ENTRIES & in_nav)
    company = next(g for g in NAV if g["id"] == "company")
    assert {"entity": "auditor"} in company["items"]                                    # auditors stay under Company


def test_every_formerly_separate_director_record_type_is_reachable_inside_the_panel():
    """The panel draws each of them as a list (search, sort, CSV, archive and the record editor come with the list)."""
    panel = (SCRIPTS / "directors.js").read_text(encoding="utf-8")
    keys_in_panel = {k for k in ENTITIES if f'"{k}"' in panel}
    assert FORMER_SIDEBAR_ENTRIES <= keys_in_panel, FORMER_SIDEBAR_ENTRIES - keys_in_panel
    tabs = re.findall(r'\{ id: "(\w+)", label: "([^"]+)"', panel)
    assert [label for _, label in tabs] == ["Register", "DIN & KYC", "Appointments", "Resignations", "Board Committees",
                                              "Declarations & other directorships"]


def test_register_rows_carry_the_flags_the_segments_need(admin, owner):
    rows = admin.ok(admin.get("/companies/2/directors-register"))["rows"]
    assert rows and all("designation_code" in r and "on_committee" in r for r in rows)
    on_committee = {r["directorship_id"] for r in owner.execute(
        """SELECT cm.directorship_id FROM core.committee_member cm JOIN core.directorship ds ON ds.id = cm.directorship_id
           WHERE ds.company_id = 2 AND NOT cm.is_archived AND (cm.end_date IS NULL OR cm.end_date >= current_date)""")}
    assert {r["directorship_id"] for r in rows if r["on_committee"]} == on_committee
    rajan = next(r for r in rows if r["full_name"] == "Rajan Patel")
    assert rajan["designation"] == "Managing Director" and rajan["designation_code"] == "MD"
