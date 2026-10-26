"""Change 2: the All Companies table has no Filings column and its columns fill the width."""
import pytest


@pytest.mark.parametrize("width", [1280, 1920])
def test_the_table_has_no_filings_header_and_no_sideways_scroll(open_app, width):
    page = open_app(width=width)
    heads = page.eval_on_selector_all(".all-companies-table thead th", "els => els.map(e => e.textContent.trim())")
    assert "Filings" not in heads and heads[0] == "Company"
    assert page.eval_on_selector_all(".all-companies-table tbody tr:first-child td", "els => els.length") == len(heads)
    t = page.eval_on_selector(".all-companies-table", "e => ({w: e.getBoundingClientRect().width, p: e.parentElement.getBoundingClientRect().width})")
    assert abs(t["w"] - t["p"]) < 2                                             # fills the card
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_other_screens_keep_their_filing_content(open_app):
    page = open_app()
    page.click("tr.co-row:has-text('BrightMed')")
    page.wait_for_selector("#pageTitle:has-text('BrightMed')")
    assert "filings recorded" in page.inner_text("#view").lower()               # the Overview tile is untouched
    page.click("#sideAcc .accordion-button:has-text('Financial & Legal')")
    page.click("#sideAcc a[data-view='entity:government_filing']")
    page.wait_for_selector("#pageTitle:has-text('Forms Filed')")
