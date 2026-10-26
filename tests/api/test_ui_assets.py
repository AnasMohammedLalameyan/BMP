"""The front end: served correctly, internally consistent, and carrying the approved dashboard's look."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "app" / "static"
SCRIPTS = STATIC / "scripts"
TEMPLATE = Path(__file__).resolve().parents[2] / "app" / "templates" / "dashboard.html"


def test_the_dashboard_page_is_served_with_security_headers(anon):
    r = anon.http.get("/")
    assert r.status_code == 200 and "BMP &amp; Co. LLP" in r.text and 'id="loginForm"' in r.text
    h = r.headers
    assert "default-src 'self'" in h["content-security-policy"] and "script-src 'self'" in h["content-security-policy"]
    assert h["x-frame-options"] == "DENY" and h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "same-origin" and h["x-request-id"]
    assert anon.http.get("/api/health").headers["cache-control"] == "no-store"


def test_nothing_is_loaded_from_the_internet():
    html = TEMPLATE.read_text(encoding="utf-8")
    assert not re.search(r'(?:src|href)="https?://', html)                       # works with no internet access
    for js in SCRIPTS.glob("*.js"):
        assert "https://cdn" not in js.read_text(encoding="utf-8")


def test_the_approved_theme_is_carried_over_unchanged():
    old = Path(__file__).resolve().parents[3] / "Old_implementation_with_approved_ui" / "src" / "static" / "stylesheets" / "dashboard.css"
    if not old.exists():
        pytest.skip("old implementation folder not present")
    assert (STATIC / "stylesheets" / "dashboard.css").read_bytes() == old.read_bytes()
    css = (STATIC / "stylesheets" / "dashboard.css").read_text(encoding="utf-8")
    assert "--brand:#0f2747" in css and ".sidebar{" in css
    html = TEMPLATE.read_text(encoding="utf-8")
    for needle in ("app-topbar", "sb-brand", "entity-box", "side-scroll", "accordion", "content-head", "page-title", "toast-wrap"):
        assert needle in html                                                     # same structure as the approved shell


def test_every_static_file_the_page_references_exists_and_is_served(anon):
    html = anon.http.get("/").text
    for url in re.findall(r'(?:src|href)="(/static/[^"?]+)', html):
        assert anon.http.get(url).status_code == 200, url
    for js in SCRIPTS.glob("*.js"):
        assert anon.http.get(f"/static/scripts/{js.name}").status_code == 200


def test_every_javascript_import_resolves():
    names = {p.name for p in SCRIPTS.glob("*.js")}
    for js in SCRIPTS.glob("*.js"):
        for target in re.findall(r'from\s+"\./([\w.-]+)"', js.read_text(encoding="utf-8")):
            assert target in names, f"{js.name} imports missing {target}"
    imported = {t for js in SCRIPTS.glob("*.js") for t in re.findall(r'from\s+"\./([\w.-]+)"', js.read_text(encoding="utf-8"))}
    assert names - imported <= {"main.js", "activities-main.js"}, f"unused modules: {names - imported - {'main.js', 'minutes-main.js'}}"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
@pytest.mark.parametrize("js", sorted(SCRIPTS.glob("*.js")), ids=lambda p: p.name)
def test_every_javascript_module_is_syntactically_valid(js, tmp_path):
    copy = tmp_path / (js.stem + ".mjs")
    copy.write_text(js.read_text(encoding="utf-8"), encoding="utf-8")
    r = subprocess.run(["node", "--check", str(copy)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_every_element_the_main_script_looks_up_exists_in_the_page():
    html = TEMPLATE.read_text(encoding="utf-8")
    for name in ("main.js", "sidebar.js", "overview.js"):
        for ident in set(re.findall(r'\$\("#([\w-]+)"\)', (SCRIPTS / name).read_text(encoding="utf-8"))):
            if ident in ("sideAcc",):
                assert f'id="{ident}"' in html
            elif name == "main.js":
                assert f'id="{ident}"' in html, f"main.js looks for #{ident}, which the page does not have"


def test_user_supplied_text_is_escaped_before_it_reaches_the_page():
    """Every template string that interpolates data goes through esc(); a quick guard against a raw ${...} in innerHTML
    for the fields that come straight from the database."""
    risky = re.compile(r"\$\{(?:r|row|m|c|e|k|t|x|a|g)\.(?:name|full_name|filename|text|notes|venue|remarks|description|label)\}")
    for js in SCRIPTS.glob("*.js"):
        for line_no, line in enumerate(js.read_text(encoding="utf-8").splitlines(), 1):
            if "toast(" in line or ".textContent" in line:          # these write text, not HTML
                continue
            assert not risky.search(line), f"{js.name}:{line_no} interpolates database text without esc(): {line.strip()[:100]}"


def test_the_fy_selector_and_user_box_sit_in_the_right_hand_group_of_the_top_bar():
    html = TEMPLATE.read_text(encoding="utf-8")
    nav = html[html.index('<nav class="navbar app-topbar'):html.index("</nav>")]
    right = nav[nav.index("app-topbar-right"):]
    for ident in ("fySelect", "whoName", "whoSub", "btnRefresh", "btnPrint", "btnExport", "btnExportExcel", "btnChangePassword", "btnSignOut"):
        assert f'id="{ident}"' in right, ident
    assert right.index('id="fySelect"') < right.index('id="whoName"')                  # FY first, the user last (far right)
    side = html[html.index("<aside"):html.index("</aside>")]
    assert 'id="fySelect"' not in side and 'id="whoName"' not in side                  # moved out of the sidebar's company box


def test_every_element_id_the_scripts_rely_on_is_still_in_the_page():
    html = TEMPLATE.read_text(encoding="utf-8")
    for ident in ("fySelect", "whoName", "whoSub", "entityName", "entityMeta", "btnRefresh", "btnPrint", "btnExport", "btnExportExcel",
                  "btnChangePassword", "btnSignOut", "btnExitCompany", "navCompanies", "sideAcc", "view", "pageTitle", "pageSub", "crumb",
                  "search", "searchWrap", "overallBadge", "modalHost", "toast", "toastMsg"):
        assert f'id="{ident}"' in html, ident


def test_the_all_companies_table_has_no_filings_column_and_the_api_is_unchanged(admin):
    src = (SCRIPTS / "companies.js").read_text(encoding="utf-8")
    heads = re.findall(r"<th[^>]*>([^<]*)</th>", src)
    assert heads == ["Company", "Category", "Listing", "Directors", "Incorporated", "Your access", ""]
    row = src[src.index('<tr class="co-row"'):src.index("</tr>`")]
    assert row.count("<td") == len(heads) and "overdue" not in row                 # every header still has its cell
    # nothing else was touched: the Overview tile, the Forms Filed record list and the companies API keep their filing data
    assert "Filings recorded" in (SCRIPTS / "overview.js").read_text(encoding="utf-8")
    from app.registry import ENTITIES
    assert ENTITIES["government_filing"]["label"] == "Forms Filed (Government Filings)"
    first = admin.ok(admin.get("/companies"))["companies"][0]
    assert {"id", "name", "cin", "pan", "is_listed", "status", "date_of_incorporation", "category", "subcategory", "directors",
            "overdue_filings", "access_level"} <= set(first)


def test_the_text_calculated_values_appears_nowhere_in_the_user_interface():
    assert not (SCRIPTS / "calc.js").exists()
    sources = [TEMPLATE, STATIC.parent / "registry.py", *SCRIPTS.glob("*.js"), STATIC / "stylesheets" / "app.css"]
    for path in sources:
        assert "Calculated Values" not in path.read_text(encoding="utf-8"), path.name
    assert '"calc"' not in (SCRIPTS / "main.js").read_text(encoding="utf-8")
