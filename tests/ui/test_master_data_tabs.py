"""Change 4: Master Data in four horizontal tabs; every card in exactly one tab; save-on-blur kept; the registers are composed and read only."""
import re
from collections import Counter

from playwright.sync_api import expect

from .helpers import api, company_id, go_to, open_company

TABS = ["General Info & Registration", "Capital Structure & Financials", "Charges & Borrowings", "Statutory Registers"]

# every card the page showed before the change (plus Capital events, added when Change 7 took it out of the sidebar)
FORMER_CARDS = ["Company profile", "Directors & KMP", "Share capital", "Share classes", "Capital events", "Financials by year",
                "Registrar & Transfer Agent", "Business activities", "Holding / subsidiary / associate companies", "Statutory auditors",
                "Shareholders and their holdings"]


def open_master(page, tab=None):
    open_company(page)
    go_to(page, "masterdata", tab)
    page.wait_for_selector("#pageTitle:has-text('Master Data')")
    page.wait_for_selector(".tab-host .rec-tab")


def visible_pane_count(page):
    return page.eval_on_selector_all(".tab-pane", "els => els.filter(e => !e.classList.contains('d-none')).length")


def test_four_tabs_with_the_exact_labels_and_one_pane_at_a_time(open_app):
    page = open_app()
    open_master(page)
    assert page.eval_on_selector_all(".tab-host .rec-tab", "els => els.map(e => e.textContent.trim())") == TABS
    assert page.inner_text(".rec-tab.active") == TABS[0] and visible_pane_count(page) == 1
    for tab in TABS[1:]:
        page.click(f".rec-tab:text-is('{tab}')")
        assert visible_pane_count(page) == 1 and page.inner_text(".rec-tab.active") == tab


def test_every_former_card_is_in_exactly_one_tab(open_app):
    page = open_app()
    open_master(page)
    titles = Counter()
    for tab in TABS:
        page.click(f".rec-tab:text-is('{tab}')")
        page.wait_for_selector(".tab-pane:not(.d-none) .md-card")
        page.wait_for_load_state("networkidle")
        for t in page.eval_on_selector_all(".tab-pane:not(.d-none) .md-card h3.md-h", "els => els.map(e => e.childNodes[0].textContent.trim())"):
            titles[t] += 1
    for card in FORMER_CARDS:
        assert titles[card] == 1, (card, titles)


def test_a_tab_loads_its_data_only_when_first_opened(open_app):
    page = open_app()
    seen = []
    page.on("request", lambda r: seen.append(r.url))
    open_master(page)
    page.wait_for_load_state("networkidle")
    assert not any("v_shareholding_percent" in u or "/entities/s185_loan" in u for u in seen)           # the registers tab has not been opened
    assert page.eval_on_selector("[data-pane='registers']", "e => e.innerHTML.trim() === ''")
    page.click(".rec-tab:text-is('Statutory Registers')")
    page.wait_for_selector("[data-pane='registers'] .md-card")
    assert any("v_shareholding_percent" in u for u in seen) and any("/entities/s185_loan" in u for u in seen)


def test_the_profile_still_saves_each_field_as_you_leave_it(open_app):
    page = open_app()
    open_master(page)
    page.wait_for_selector("#mdProfile [data-f='website']")
    cid = company_id(page)
    before = api(page, "GET", f"/entities/company/{cid}")["row"]
    try:
        page.fill("#mdProfile [data-f='website']", "https://example.test/ui-check")
        page.keyboard.press("Tab")                                                                         # leaving the field saves it
        expect(page.locator("#mdSaved")).to_have_text("✓ saved")
        assert api(page, "GET", f"/entities/company/{cid}")["row"]["website"] == "https://example.test/ui-check"
    finally:
        fresh = api(page, "GET", f"/entities/company/{cid}")["row"]
        api(page, "PATCH", f"/entities/company/{cid}", {"website": before["website"], "updated_at": fresh["updated_at"]})


def test_the_tab_survives_a_refresh_back_works_and_an_unknown_tab_opens_the_first(open_app):
    page = open_app()
    open_master(page)
    page.click(".rec-tab:text-is('Capital Structure & Financials')")
    assert re.search(r"#/company/\d+/masterdata/capital$", page.url)
    page.click(".rec-tab:text-is('Statutory Registers')")
    assert page.url.endswith("/masterdata/registers")
    page.go_back()
    expect(page.locator(".rec-tab.active")).to_have_text("Capital Structure & Financials")
    page.reload()
    page.wait_for_selector(".tab-host .rec-tab")
    expect(page.locator(".rec-tab.active")).to_have_text("Capital Structure & Financials")
    page.evaluate("h => { location.hash = h }", f"#/company/{company_id(page)}/masterdata/bogus")
    expect(page.locator(".rec-tab.active")).to_have_text(TABS[0])


def test_charges_tab_is_honest_about_the_missing_charge_register(open_app):
    page = open_app()
    open_master(page, "charges")
    pane = page.locator("[data-pane='charges']")
    expect(pane).to_contain_text("No charge register in the approved data model")
    expect(pane).to_contain_text("Loans and deposits")
    expect(pane).to_contain_text("External commercial borrowings")
    assert pane.locator("[data-view='foreign']").count() == 1                                         # the link to the foreign-investment tab


def test_statutory_registers_are_composed_read_only_and_exportable(open_app):
    page = open_app()
    open_master(page, "registers")
    page.wait_for_selector("[data-pane='registers'] .md-card")
    titles = page.eval_on_selector_all("[data-pane='registers'] h3.md-h", "els => els.map(e => e.textContent.trim())")
    assert titles[:5] == ["Register of directors and key managerial personnel", "Register of members", "Register of loans to directors (Sec 185)",
                          "Register of loans and investments (Sec 186)", "Register of contracts with related parties (Sec 188)"]
    assert titles[5:] == ["Register of charges", "Register of debenture holders", "Register of sweat equity shares"]       # honest placeholders
    assert page.locator("[data-pane='registers'] .no-source, [data-pane='registers'] :text('No source table')").count() == 3
    assert page.locator("[data-pane='registers'] [data-l='add'], [data-pane='registers'] tr[data-pk]").count() == 0           # read only: no Add, rows do not open an editor
    assert "Rajan Patel" in page.inner_text("[data-pane='registers']") and "General Public" in page.inner_text("[data-pane='registers']")
    with page.expect_download() as d:
        page.click("[data-export='members']")
    path = d.value.path()
    text = open(path, encoding="utf-8-sig").read()
    assert d.value.suggested_filename == "register_of_members.csv"
    assert text.splitlines()[0] == "Shareholder,Category,Class,Shares,Holding %" and "Rajan Patel" in text and "56.6667" in text


def test_a_read_only_client_sees_the_tabs_but_cannot_edit_the_profile(open_app):
    page = open_app("client@nexatech.co.in")
    page.click("tr.co-row")
    page.wait_for_selector("#pageTitle:has-text('Nexatech')")
    go_to(page, "masterdata")
    page.wait_for_selector("#mdProfile [data-f]")
    assert page.eval_on_selector_all("#mdProfile [data-f]", "els => els.every(e => e.disabled)")
    assert "read-only access" in page.inner_text("[data-pane='general']")
