"""Hash routing: every screen has an address; Back/Forward and pasted links work; removed or unknown views fall back."""
import re

from .helpers import COMPANY, open_company


def test_the_address_follows_the_screen_and_back_forward_work(open_app):
    page = open_app()
    assert page.url.endswith("#/companies")
    open_company(page)
    assert re.search(r"#/company/\d+/overview$", page.url)
    page.click("#sideAcc a[data-view='masterdata']")
    page.wait_for_selector("#pageTitle:has-text('Master Data')")
    assert re.search(r"#/company/\d+/masterdata", page.url)
    page.go_back()
    page.wait_for_selector("#pageTitle:has-text('BrightMed')")
    page.go_back()
    page.wait_for_selector("#pageTitle:has-text('Companies')")
    assert page.inner_text("#entityName") == "—" or not page.is_visible(".entity-box")
    page.go_forward()
    page.wait_for_selector("#pageTitle:has-text('BrightMed')")


def test_a_pasted_company_link_opens_that_company_and_screen(open_app):
    page = open_app()
    open_company(page)
    link = re.search(r"#/company/\d+", page.url).group(0)
    page.goto(page.url.split("#")[0] + link + "/rules")
    page.wait_for_selector("#pageTitle:has-text('Applicability Rules')")
    assert page.inner_text("#entityName").startswith(COMPANY)


def test_an_unknown_or_removed_view_falls_back_to_the_first_view(open_app):
    page = open_app()
    open_company(page)
    base = page.url.split("#")[0]
    cid = re.search(r"#/company/(\d+)", page.url).group(1)
    for bad in ("calc", "nonsense", "entity:no_such_table"):
        page.goto(f"{base}#/company/{cid}/{bad}")
        page.wait_for_selector("#pageTitle:has-text('BrightMed')")
        assert page.url.endswith(f"#/company/{cid}/overview"), bad


def test_a_link_to_a_company_the_user_cannot_open_lands_on_the_companies_page(open_app):
    page = open_app("client@nexatech.co.in")
    base = page.url.split("#")[0]
    page.goto(f"{base}#/company/2/overview")                    # BrightMed is not the client's company
    page.wait_for_selector("#pageTitle:has-text('Companies')")
    assert page.url.endswith("#/companies")


def test_no_calculated_values_text_in_the_sidebar_or_on_the_overview(open_app):
    page = open_app()
    open_company(page)
    assert "Calculated Values" not in page.inner_text("#sidebar") and "Calculated Values" not in page.inner_text("#view")
