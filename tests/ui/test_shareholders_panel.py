"""Change 7: one "Shareholders" link; a panel with the cap table, allotments, transfers and shareholders."""
import re

from playwright.sync_api import expect

from .helpers import api, company_id, go_to, open_company

TABS = ["Cap table", "Allotments", "Transfers", "Shareholders"]


def open_panel(page, tab=None):
    open_company(page)
    go_to(page, "shareholders", tab)
    page.wait_for_selector("#pageTitle:has-text('Shareholders')")
    page.wait_for_selector(".tab-host .rec-tab")


def test_the_sidebar_has_one_shareholders_link(open_app):
    page = open_app()
    open_company(page)
    page.click("#sideAcc .accordion-button:has-text('Capital & Members')")
    text = page.inner_text("#acc_capital")
    assert "Shareholders" in text
    for gone in ("Share Classes", "Share Capital Summary", "Capital Events", "Shareholdings", "Share Allotments", "Share Transfers"):
        assert gone not in text, gone


def test_the_panel_has_four_tabs_and_the_cap_table_shows_the_databases_percentages(open_app):
    page = open_app()
    open_panel(page)
    assert page.eval_on_selector_all(".tab-host .rec-tab", "els => els.map(e => e.textContent.trim())") == TABS
    page.wait_for_selector("table.cap-table [data-percent]")
    shown = page.eval_on_selector_all("table.cap-table tr:has([data-percent])", """els => els.map(e => [e.children[0].textContent.trim(),
        e.children[2].textContent.trim().replace(/,/g, ''), e.children[3].textContent.trim().replace('%', '')])""")
    calc = api(page, "GET", f"/calc/v_shareholding_percent?company_id={company_id(page)}")["rows"]
    assert len(shown) == len(calc) > 0
    by_name = {(r["shareholder_name"], str(r["number_of_shares"])): float(r["holding_percent"]) for r in calc}
    for name, shares, percent in shown:
        assert abs(by_name[(name, shares)] - float(percent)) < 1e-9, name                  # exactly the value the database calculated
    assert "shares in issue" in page.inner_text("table.cap-table")


def test_allotments_and_transfers_can_be_added_and_edited_inside_the_panel(open_app):
    page = open_app()
    open_panel(page)
    page.click(".rec-tab:text-is('Allotments')")
    page.click(".tab-pane:not(.d-none) [data-l='add']")
    page.wait_for_selector(".modal.show [data-r='save']", state="visible")
    assert page.inner_text(".modal.show .rec-title") == "New allotment"
    page.click(".modal.show [data-close] >> nth=0")
    page.wait_for_selector(".modal.show", state="detached")
    page.click(".rec-tab:text-is('Transfers')")
    expect(page.locator(".tab-pane:not(.d-none) [data-l='add']")).to_be_visible()
    page.click(".tab-pane:not(.d-none) tbody tr[data-pk] >> nth=0")                         # the seeded transfer opens in the editor
    page.wait_for_selector(".modal.show [data-r='save']", state="visible")
    page.click(".modal.show [data-close] >> nth=0")
    page.wait_for_selector(".modal.show", state="detached")


def test_a_read_only_client_sees_the_panel_without_add_buttons(open_app):
    page = open_app("client@nexatech.co.in")
    page.click("tr.co-row")
    page.wait_for_selector("#pageTitle:has-text('Nexatech')")
    go_to(page, "shareholders")
    page.wait_for_selector("table.cap-table")
    for tab in TABS[1:]:
        page.click(f".rec-tab:text-is('{tab}')")
        page.wait_for_selector(".tab-pane:not(.d-none) table")
        assert page.locator(".tab-pane:not(.d-none) [data-l='add']").count() == 0, tab
    assert page.locator("tr[data-person]").count() == 0


def test_the_capital_structure_link_and_master_data_hold_share_classes_summary_and_events(open_app):
    page = open_app()
    open_panel(page)
    page.click("#capStructure")
    page.wait_for_selector("#pageTitle:has-text('Master Data')")
    assert re.search(r"#/company/\d+/masterdata/capital$", page.url)
    for card in ("Share capital", "Share classes", "Capital events"):
        expect(page.locator(".md-card h3.md-h", has_text=card).first).to_be_visible()


def test_the_tab_is_in_the_address_and_back_works(open_app):
    page = open_app()
    open_panel(page)
    page.click(".rec-tab:text-is('Transfers')")
    assert page.url.endswith("/shareholders/transfers")
    page.go_back()
    expect(page.locator(".rec-tab.active")).to_have_text("Cap table")
