"""Change 3: the FY selector and the signed-in box sit together at the far right of the top bar, without overlap or sideways scroll."""
import pytest

from .helpers import open_company


def box(page, selector):
    return page.eval_on_selector(selector, "e => { const r = e.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom}; }")


@pytest.mark.parametrize("width", [1920, 1280, 1024])
def test_fy_and_user_box_are_on_the_far_right_and_do_not_overlap(open_app, width):
    page = open_app(width=width)
    open_company(page)
    fy, who = box(page, "#fyWrap"), box(page, ".app-topbar .who-box")
    assert fy["r"] <= who["l"] + 1                                   # FY first, user last
    assert width - who["r"] < 40                                     # user box at the far right edge
    others = [box(page, s) for s in ("#btnRefresh", "#btnPrint", "#fyWrap", ".app-topbar .dropdown", ".app-topbar .who-box")]
    for a, b in zip(others, others[1:]):
        assert a["r"] <= b["l"] + 1, (a, b)                          # nothing overlaps its neighbour
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_the_fy_selector_is_hidden_until_a_company_is_open(open_app):
    page = open_app()
    assert not page.is_visible("#fyWrap")
    assert page.is_visible("#whoName")                               # the user stays visible without a company
    open_company(page)
    assert page.is_visible("#fyWrap")


def test_sign_out_change_password_and_year_change_still_work(open_app):
    page = open_app()
    open_company(page)
    options = page.eval_on_selector_all("#fySelect option", "els => els.map(e => e.value)")
    assert len(options) >= 2
    page.select_option("#fySelect", options[-1])
    page.wait_for_selector("#pageTitle:has-text('BrightMed')")
    page.click(".app-topbar .dropdown-toggle")
    page.click("#btnChangePassword")
    page.wait_for_selector("#pwCur", state="visible")
    page.click(".modal.show [data-close]")
    page.wait_for_selector(".modal.show", state="detached")
    page.click(".app-topbar .dropdown-toggle")
    page.click("#btnSignOut")
    page.wait_for_selector("#loginView:not(.d-none)")
