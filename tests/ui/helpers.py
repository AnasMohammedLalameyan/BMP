"""Small helpers shared by the browser tests."""
import re

COMPANY = "BrightMed"


def open_company(page, name=COMPANY):
    page.click(f"tr.co-row:has-text('{name}')")
    page.wait_for_selector(f"#pageTitle:has-text('{name}')")


def company_id(page):
    return re.search(r"#/company/(\d+)", page.url).group(1)


def go_to(page, view, tab=None):
    """Open a screen of the open company through its address (what a pasted link does)."""
    page.evaluate("h => { location.hash = h }", f"#/company/{company_id(page)}/{view}" + (f"/{tab}" if tab else ""))


def api(page, method, path, body=None):
    """Call the API from the signed-in page (cookie + CSRF token), returning the JSON answer."""
    return page.evaluate("""async ([method, path, body]) => {
        const me = await (await fetch('/api/auth/me', {credentials: 'same-origin'})).json();
        const r = await fetch('/api' + path, {method, credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf},
                                              body: body ? JSON.stringify(body) : undefined});
        return await r.json();
    }""", [method, path, body])
