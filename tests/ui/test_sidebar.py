"""Change 1: the sidebar has two states; All Directors and Notifications; the bell."""
import re

from playwright.sync_api import expect

from .helpers import open_company

THREE = ["All Companies", "All Directors", "Notifications"]


def global_links(page):
    return page.eval_on_selector_all("#sidebar .side-scroll a", "els => els.filter(e => e.offsetParent !== null).map(e => e.textContent.trim())")


def test_with_no_company_open_the_sidebar_shows_exactly_the_three_links(open_app):
    page = open_app()
    assert global_links(page) == THREE
    assert "sidebar-global-only" in page.get_attribute("#sidebar", "class")
    assert page.eval_on_selector("#sideAcc", "e => e.children.length") == 0           # no company-specific entry exists in the DOM
    assert page.eval_on_selector_all("#sidebar .accordion-item, #sidebar [data-chip]", "els => els.length") == 0
    assert not page.is_visible(".entity-box") and not page.is_visible("#navCompanies") and not page.is_visible("#sidebar .accordion")
    assert page.is_visible("#whoName") and not page.is_visible("#fyWrap")              # the user stays visible; the year needs a company


def test_opening_and_closing_a_company_swaps_the_sidebar(open_app):
    page = open_app()
    open_company(page)
    assert "sidebar-global-only" not in page.get_attribute("#sidebar", "class")
    assert page.is_visible("#sidebar .accordion") and page.is_visible(".entity-box") and page.is_visible("#navCompanies")
    assert page.inner_text("#navCompanies").strip().lower() == "all companies"           # the back link
    assert page.eval_on_selector("#sideGlobal", "e => e.children.length") == 0
    page.click("#btnExitCompany")
    page.wait_for_selector("#pageTitle:has-text('Companies')")
    assert global_links(page) == THREE and page.url.endswith("#/companies")


def test_all_directors_has_an_address_and_back_forward_and_pasted_links_work(open_app):
    page = open_app()
    page.click("#sideGlobal a[data-view='all-directors']")
    page.wait_for_selector("#pageTitle:has-text('All Directors')")
    assert page.url.endswith("#/directors")
    page.wait_for_selector("tr[data-person]")
    page.go_back()
    page.wait_for_selector("#pageTitle:has-text('Companies')")
    page.go_forward()
    page.wait_for_selector("#pageTitle:has-text('All Directors')")
    base = page.url.split("#")[0]
    page.goto(base + "#/notifications")
    page.wait_for_selector("#pageTitle:has-text('Notifications')")
    page.goto(base + "#/directors")
    page.wait_for_selector("#pageTitle:has-text('All Directors')")
    assert global_links(page) == THREE


def test_all_directors_search_and_roles_across_companies(open_app):
    page = open_app()
    page.click("#sideGlobal a[data-view='all-directors']")
    page.wait_for_selector("tr[data-person]")
    assert page.locator("tr[data-person]").count() == 12
    page.fill("#adSearch", "joshi")
    expect(page.locator("tr[data-person]")).to_have_count(1)
    text = page.inner_text("tr[data-person]")
    assert "Prashant Joshi" in text and "BrightMed" in text and "Nexatech" in text         # roles in two companies on one row
    page.click(".role-chip:has-text('Nexatech')")
    expect(page).to_have_url(re.compile(r"#/company/\d+/directors$"))


def test_a_read_only_client_sees_only_their_own_companys_people(open_app):
    page = open_app("client@nexatech.co.in")
    page.click("#sideGlobal a[data-view='all-directors']")
    page.wait_for_selector("tr[data-person]")
    text = page.inner_text("#view")
    assert "Nexatech" in text and "BrightMed" not in text and "Skyward" not in text
    assert 0 < page.locator("tr[data-person]").count() < 12


def test_the_bell_shows_the_total_and_the_screen_lists_the_items(open_app):
    page = open_app()
    total = page.evaluate("fetch('/api/notifications', {credentials: 'same-origin'}).then(r => r.json()).then(d => d.total)")
    assert total > 0
    expect(page.locator("#notifCount")).to_have_text(str(total))
    page.click("#btnNotifications")
    page.wait_for_selector("#pageTitle:has-text('Notifications')")
    assert page.url.endswith("#/notifications") and global_links(page) == THREE
    assert page.locator(".att-item").count() == total
    page.click(".att-item:has-text('MGT-7 overdue')")
    page.wait_for_selector("#pageTitle:has-text('Forms Filed')")
    assert re.search(r"#/company/\d+/entity:government_filing$", page.url)
    assert "sidebar-global-only" not in page.get_attribute("#sidebar", "class")           # the item opened the company
