"""Change 8: the ODI / ECB / DI / Foreign Investments tab."""
from playwright.sync_api import expect

from .helpers import go_to, open_company

LABEL = "ODI / ECB / DI / Foreign Investments"


def open_tab(page):
    go_to(page, "foreign")
    page.wait_for_selector("#foreign-investments-tab")
    page.wait_for_load_state("networkidle")


def test_the_sidebar_has_one_entry_with_the_exact_label_and_the_old_ones_are_gone(open_app):
    page = open_app()
    open_company(page)
    page.click("#sideAcc .accordion-button:has-text('Financial & Legal')")
    text = page.inner_text("#acc_fin")
    assert LABEL in text
    for gone in ("Overseas Direct Investment", "ODI Step-down", "External Commercial Borrowings", "Foreign Investment"):
        assert gone not in text.replace(LABEL, ""), gone
    page.click(f"#acc_fin :text-is('{LABEL}')")
    page.wait_for_selector("#foreign-investments-tab")
    assert page.url.endswith("/foreign")


def test_the_tab_shows_a_summary_strip_and_four_grids(open_app):
    page = open_app()
    open_company(page)
    open_tab(page)
    assert page.locator("#foreign-investments-tab [data-sum]").count() == 3
    assert page.locator("#foreign-investments-tab table").count() == 4
    assert "Loading" not in page.inner_text("#fiSummary")
    expect(page.locator("#pageTitle")).to_have_text(LABEL)


def test_admin_gets_add_buttons_and_a_client_does_not(open_app):
    page = open_app()
    open_company(page)
    open_tab(page)
    assert page.locator("#foreign-investments-tab [data-l='add']").count() == 4
    page = open_app("client@nexatech.co.in")
    page.click("tr.co-row")
    page.wait_for_selector("#pageTitle:has-text('Nexatech')")
    open_tab(page)
    assert page.locator("#foreign-investments-tab table").count() == 4
    assert page.locator("#foreign-investments-tab [data-l='add']").count() == 0
