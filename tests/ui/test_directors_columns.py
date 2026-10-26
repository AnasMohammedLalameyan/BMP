"""Change 9: Address and Phone Number in the director tables; a long address wraps inside 320 px."""
from .helpers import api, go_to, open_company

LONG = ("Plot 12, Sector 18, Industrial Estate, " * 6)[:200]


def test_register_and_master_data_show_address_and_phone_columns(open_app):
    page = open_app()
    open_company(page)
    go_to(page, "directors")
    page.wait_for_selector(".reg-table tbody tr")
    heads = page.eval_on_selector_all(".reg-table thead th", "els => els.map(e => e.textContent.trim())")
    assert "Address" in heads and "Phone Number" in heads
    assert page.eval_on_selector(".reg-table tbody tr td.cell-wrap", "e => e.textContent.trim()") not in ("", "—")
    go_to(page, "masterdata")
    page.wait_for_selector("#mdDirectors table")
    heads = page.eval_on_selector_all("#mdDirectors thead th", "els => els.map(e => e.textContent.trim())")
    assert "Address" in heads and "Phone Number" in heads


def test_a_200_character_address_wraps_inside_320px_and_the_page_never_scrolls_sideways(open_app):
    page = open_app(width=1280)
    open_company(page)
    reg = page.evaluate("fetch('/api/companies/' + location.hash.split('/')[2] + '/directors-register', {credentials: 'same-origin'}).then(r => r.json())")
    director_id = reg["rows"][0]["director_id"]
    row = api(page, "GET", f"/entities/director/{director_id}")["row"]
    original = row["address"]
    assert "row" in api(page, "PATCH", f"/entities/director/{director_id}", {"address": LONG, "updated_at": row["updated_at"]})
    try:
        for view in ("directors", "masterdata"):
            go_to(page, view)
            page.reload()
            page.wait_for_selector("td.cell-wrap:has-text('Plot 12')")
            width = page.eval_on_selector("td.cell-wrap:has-text('Plot 12')", "e => e.getBoundingClientRect().width")
            assert width <= 340, (view, width)                          # 320 px of text + the cell padding
            assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            assert page.eval_on_selector("td.cell-wrap:has-text('Plot 12')", "e => e.closest('.table-responsive').scrollWidth <= e.closest('.table-responsive').clientWidth")
    finally:
        fresh = api(page, "GET", f"/entities/director/{director_id}")["row"]
        api(page, "PATCH", f"/entities/director/{director_id}", {"address": original, "updated_at": fresh["updated_at"]})
