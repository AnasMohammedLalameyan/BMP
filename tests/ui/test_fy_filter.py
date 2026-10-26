"""Change 10: directors are filtered by the selected financial year, with a "Show Historical/Ceased Directors" switch.

The first test uses the seeded BrightMed board. The second creates a small throw-away company through the API (and archives it again,
because nothing is ever deleted) so that changing the year visibly changes the list."""
import re
from datetime import date, timedelta
from uuid import uuid4

from playwright.sync_api import expect

from .helpers import api, company_id, go_to, open_company

TOGGLE = "Show Historical/Ceased Directors"


def current_fy_window():
    today = date.today()
    start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)
    return f"{start.year}-{(start.year + 1) % 100:02d}", start, date(start.year + 1, 3, 31)


def test_the_register_hides_ceased_stints_by_default_and_the_switch_reveals_them_without_a_reload(open_app):
    page = open_app()
    open_company(page)
    page.select_option("#fySelect", "2024-25")
    go_to(page, "directors")
    expect(page.locator(".reg-table tbody tr")).to_have_count(4)                                              # Joshi's 2016-2021 stint hidden
    assert page.locator("tr.ceased").count() == 0
    assert TOGGLE in page.inner_text(".list-bar") and not page.is_checked("#showHistorical")
    assert "1 historical hidden" in page.inner_text(".list-bar")
    page.evaluate("window.__same_page = true")
    page.check("#showHistorical")
    assert page.locator(".reg-table tbody tr").count() == 5 and page.locator("tr.ceased").count() == 1      # existing ceased styling
    assert page.evaluate("window.__same_page === true")                                                       # no page reload
    page.reload()                                                                                              # remembered for the session
    page.wait_for_selector(".reg-table tbody tr")
    assert page.is_checked("#showHistorical") and page.locator(".reg-table tbody tr").count() == 5
    go_to(page, "masterdata")                                                                                  # the same switch in Master Data
    page.wait_for_selector("#mdHistorical")
    assert page.is_checked("#mdHistorical") and page.locator("#mdDirectors tbody tr").count() == 5
    assert page.locator("#mdDirectors tr.md-ceased").count() == 1
    page.uncheck("#mdHistorical")
    assert page.locator("#mdDirectors tbody tr").count() == 4 and page.locator("#mdDirectors tr.md-ceased").count() == 0


def test_changing_the_year_changes_the_list_with_a_ceased_badge_and_an_empty_state(open_app):
    fy, fy_start, fy_end = current_fy_window()
    page = open_app()
    tag = uuid4().hex[:8]
    cin = "U" + str(int(uuid4().int % 10 ** 20)).zfill(20)
    made = {"people": []}
    try:
        company = api(page, "POST", "/companies", {"cin": cin, "name": f"FY UI Test {tag}", "status": "active", "date_of_incorporation": "2001-04-01"})["row"]
        empty_company = api(page, "POST", "/companies", {"cin": "U" + str(int(uuid4().int % 10 ** 20)).zfill(20),
                                                           "name": f"FY UI Empty {tag}", "status": "active", "date_of_incorporation": "2001-04-01"})["row"]
        made["companies"] = [company["id"], empty_company["id"]]
        stints = [  # (name, start, end)
            (f"Serving {tag}", "2015-01-01", None),
            (f"Left on first day {tag}", "2015-01-01", fy_start.isoformat()),
            (f"Starts after year {tag}", (fy_end + timedelta(days=1)).isoformat(), None),
        ]
        for cid, name, start, end in [(company["id"], *s) for s in stints] + [(empty_company["id"], f"Long gone {tag}", "2010-01-01", "2012-01-01")]:
            person = api(page, "POST", "/entities/director", {"full_name": name})["row"]
            made["people"].append(person["id"])
            api(page, "POST", "/entities/directorship", {"company_id": cid, "director_id": person["id"], "start_date": start, **({"end_date": end} if end else {})})

        page.reload()                                                                                           # the page learns about the new companies
        page.wait_for_selector("#pageTitle:has-text('Companies')")
        page.evaluate("h => { location.hash = h }", f"#/company/{company['id']}/directors")
        page.wait_for_selector(".reg-table tbody tr")
        names = lambda: page.eval_on_selector_all(".reg-table tbody tr .co-name", "els => els.map(e => e.textContent.trim())")
        assert page.input_value("#fySelect") == fy                                                              # a company with no dated records opens on the current year
        assert sorted(names()) == sorted([f"Serving {tag}", f"Left on first day {tag}"])
        d, m, y = fy_start.day, fy_start.month, fy_start.year
        assert f"Ceased on {d:02d}-{m:02d}-{y}" in page.inner_text(".reg-table")                                # badge for the one who left in the year
        assert page.locator("tr.ceased").count() == 1
        page.check("#showHistorical")
        assert len(names()) == 3
        page.uncheck("#showHistorical")
        page.select_option("#fySelect", "")                                                                     # "All years": who is serving today
        expect(page.locator(".reg-table tbody")).not_to_contain_text("Left on first day")
        assert sorted(names()) == sorted([f"Serving {tag}", f"Starts after year {tag}"])                       # the list changed with the year
        assert "Ceased on" not in page.inner_text(".reg-table")

        page.evaluate("h => { location.hash = h }", f"#/company/{empty_company['id']}/directors")
        page.wait_for_selector(".reg-table")
        page.select_option("#fySelect", fy)
        expect(page.locator(".reg-table tbody")).to_contain_text(f"No directors were active in {fy}")
        page.select_option("#fySelect", "")
        expect(page.locator(".reg-table tbody")).to_contain_text("No current directors.")
    finally:
        for pid in made["people"]:
            api(page, "POST", f"/entities/director/{pid}/archive")
        for cid in made.get("companies", []):
            api(page, "POST", f"/entities/company/{cid}/archive")
