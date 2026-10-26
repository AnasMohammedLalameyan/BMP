"""Change 6: one "Directors" link; a tabbed panel; segment controls whose counts equal the rows shown; the add-director dialog still works."""
import re
from uuid import uuid4

from playwright.sync_api import expect

from .helpers import api, company_id, go_to, open_company

TABS = ["Register", "DIN & KYC", "Appointments", "Resignations", "Board Committees", "Declarations & other directorships"]


def open_directors(page, tab=None):
    open_company(page)
    page.select_option("#fySelect", "2024-25")
    page.wait_for_load_state("networkidle")                                                       # the year change redraws the screen once; let it finish
    go_to(page, "directors", tab)
    page.wait_for_selector("#pageTitle:has-text('Directors')")
    page.wait_for_selector(".tab-host .rec-tab")


def test_the_sidebar_has_one_directors_link_and_the_old_children_are_gone(open_app):
    page = open_app()
    open_company(page)
    page.click("#sideAcc .accordion-button:has-text('People & Roles')")
    links = page.eval_on_selector_all("#acc_people .side-link", "els => els.map(e => e.textContent.trim())")
    assert [re.sub(r"\d+$", "", l).strip() for l in links] == ["Directors"]
    page.click("#sideAcc .accordion-button:has-text('Governance')")
    assert "Committee" not in page.inner_text("#acc_gov")
    page.click("#sideAcc .accordion-button:has-text('Company')")
    assert "Auditors" in page.inner_text("#acc_company")                                        # auditors stay under Company


def test_the_panel_has_the_six_tabs_and_each_one_loads(open_app):
    page = open_app()
    open_directors(page)
    assert page.eval_on_selector_all(".tab-host .rec-tab", "els => els.map(e => e.textContent.trim())") == TABS
    assert page.get_attribute(".rec-tab.active", "aria-selected") == "true" and page.inner_text(".rec-tab.active") == "Register"
    expected = {"DIN & KYC": ["Persons on this board", "DIR-3 KYC by year", "Residency by year"],
                "Appointments": ["Board stints", "Designation history", "Independent director terms"],
                "Board Committees": ["Committees", "Committee members"],
                "Declarations & other directorships": ["Declarations", "Other directorships"]}
    for label, headings in expected.items():
        page.click(f".rec-tab:text-is('{label}')")
        pane = page.locator(".tab-pane:not(.d-none)")
        for h in headings:
            expect(pane).to_contain_text(h)
        assert pane.locator("table").count() == len(headings)                                       # every list is there
    page.click(".rec-tab:text-is('Resignations')")
    assert "Prashant Joshi" in page.inner_text(".tab-pane:not(.d-none)")                          # the 2021 resignation


def test_old_record_types_are_editable_from_inside_the_panel(open_app):
    page = open_app()
    open_directors(page, "appointments")
    page.click(".tab-pane:not(.d-none) section:has-text('Board stints') tbody tr[data-pk] >> nth=0")
    page.wait_for_selector(".modal.show [data-r='save']", state="visible")                        # the record editor opens, and admin may save
    page.click(".modal.show [data-close] >> nth=0")
    page.wait_for_selector(".modal.show", state="detached")
    page.click(".rec-tab:text-is('Board Committees')")
    expect(page.locator(".tab-pane:not(.d-none) section:has-text('Committees') [data-l='add']")).to_be_visible()


def test_segment_counts_equal_the_rows_shown(open_app):
    page = open_app()
    open_directors(page)
    for historical in (False, True):
        if historical:
            page.check("#showHistorical")
        buttons = page.eval_on_selector_all(".seg-btn", "els => els.map(e => [e.dataset.seg, Number(e.querySelector('.n').textContent)])")
        assert [b[0] for b in buttons] == ["all", "active", "ceased", "independent", "kmp", "committee"]
        for seg, count in buttons:
            page.click(f".seg-btn[data-seg='{seg}']")
            assert page.locator(".reg-table tbody tr[data-ship]").count() == count, (seg, historical)
        page.click(".seg-btn[data-seg='all']")
    assert page.locator(".seg-btn[data-seg='ceased'] .n").inner_text() == "1"                      # Joshi's 2016-2021 stint, once the history is shown
    assert "Active in FY 2024-25" in page.inner_text(".seg-bar")
    page.click(".seg-btn[data-seg='kmp']")
    assert "Rajan Patel" in page.inner_text(".reg-table")                                         # the managing director


def test_the_tab_is_in_the_address_survives_a_refresh_and_back_goes_to_the_previous_tab(open_app):
    page = open_app()
    open_directors(page)
    page.evaluate("window.__same_page = true")
    page.click(".rec-tab:text-is('Appointments')")
    assert re.search(r"#/company/\d+/directors/appointments$", page.url)
    page.click(".rec-tab:text-is('Board Committees')")
    assert page.url.endswith("/directors/committees")
    page.go_back()
    expect(page.locator(".rec-tab.active")).to_have_text("Appointments")
    page.go_back()
    expect(page.locator(".rec-tab.active")).to_have_text("Register")
    assert page.evaluate("window.__same_page === true")                                           # tab changes never reloaded the page
    page.go_forward()
    page.go_forward()
    expect(page.locator(".rec-tab.active")).to_have_text("Board Committees")
    page.reload()
    page.wait_for_selector(".tab-host .rec-tab")
    expect(page.locator(".rec-tab.active")).to_have_text("Board Committees")
    page.evaluate("h => { location.hash = h }", f"#/company/{company_id(page)}/directors/no-such-tab")
    expect(page.locator(".rec-tab.active")).to_have_text("Register")                              # unknown tab -> the first one


def test_the_tabs_work_with_the_keyboard(open_app):
    page = open_app()
    open_directors(page)
    page.focus(".rec-tab.active")
    page.keyboard.press("ArrowRight")
    expect(page.locator(".rec-tab.active")).to_have_text("DIN & KYC")
    assert page.get_attribute(".rec-tab.active", "aria-selected") == "true" and page.get_attribute(".rec-tab:text-is('Register')", "aria-selected") == "false"
    page.keyboard.press("End")
    expect(page.locator(".rec-tab.active")).to_have_text("Declarations & other directorships")
    page.keyboard.press("ArrowRight")                                                               # wraps round
    expect(page.locator(".rec-tab.active")).to_have_text("Register")
    page.keyboard.press("ArrowLeft")
    expect(page.locator(".rec-tab.active")).to_have_text("Declarations & other directorships")
    page.keyboard.press("Home")
    expect(page.locator(".rec-tab.active")).to_have_text("Register")


def test_add_director_still_creates_person_stint_and_designation_in_one_step(open_app):
    page = open_app()
    open_directors(page)
    name = f"Panel Test {uuid4().hex[:6]}"
    cid = company_id(page)
    try:
        page.click("#addDirector")
        page.wait_for_selector(".modal.show #personFields")
        page.fill(".modal.show #personFields [data-f='full_name']", name)
        page.fill(".modal.show #shipFields [data-f='start_date']", "2024-04-02")
        page.select_option(".modal.show #designation", label="Director")
        page.fill(".modal.show #designationStart", "2024-04-02")
        page.click(".modal.show #dSave")
        page.wait_for_selector(".modal.show", state="detached")
        expect(page.locator(".reg-table")).to_contain_text(name)
        row = next(r for r in api(page, "GET", f"/companies/{cid}/directors-register")["rows"] if r["full_name"] == name)
        assert row["designation"] == "Director" and row["start_date"] == "2024-04-02" and row["is_current"]        # person + stint + designation
    finally:
        rows = [r for r in api(page, "GET", f"/companies/{cid}/directors-register")["rows"] if r["full_name"] == name]
        for r in rows:
            api(page, "POST", f"/entities/directorship/{r['directorship_id']}/archive")
            api(page, "POST", f"/entities/director/{r['director_id']}/archive")
