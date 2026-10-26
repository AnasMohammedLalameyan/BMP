# UI Changes — Implementation Log
Branch: ui-changes-client-review | Started: 2026-10-07 | Author: Claude Code (Claude Sonnet 5.5)

## 1. Environment & baseline

- OS: Windows 11 Pro (10.0.26200). Python 3.12.10, Node v24.18.0, PostgreSQL 18.3 (+ pgvector 0.8.6), git 2.53.0.
- **Python environment:** the project's own `venv/` has no packages installed (`import fastapi` fails). I did **not** install into it;
  all commands below ran with an existing environment built from `requirements.txt` (fastapi 0.142.2, psycopg 3.3.6, pytest 9.1.1,
  uvicorn 0.54.0). Environment, not code.
- **Git:** the folder was **not a git repository** (`fatal: not a git repository`). I ran `git init`, set `core.autocrlf=false` (so no file
  is ever rewritten with different line endings — important for the byte-identical `dashboard.css`), committed everything tracked by the
  existing `.gitignore` as the baseline commit (`9a530f7`), and created the working branch `ui-changes-client-review`.
  `git status` after the baseline commit: clean.
- **pytest temp folder:** the first `python -m pytest` crashed before running any test with
  `PermissionError: [WinError 5] Access is denied: ...\Temp\pytest-of-Anant Sharma\pytest-current` (a stale link left from 1 Oct that I
  could not remove). Environment fix: run pytest with `--basetemp=<short folder>` (set once through `PYTEST_ADDOPTS`).
  A *long* base-temp path makes five upload tests fail with `FileNotFoundError` (Windows 260-character limit), so the folder must be short.
- **Local `bmp` database is empty:** `bmp` holds the 11 migrations but **no seed data** (0 companies, 0 lookups; schema last rebuilt
  2026-10-01 13:18). With the stock `.env`, 17 of the 19 Phase 1 database tests fail (`TypeError: 'NoneType' object is not subscriptable`)
  and the baseline is red:

  ```
  python -m pytest   (stock .env, empty bmp)   ->   10 failed, 290 passed, 7 errors   (= 17 database tests failing)
  ```

  I did not touch the user's `bmp` database. Instead I built a **throw-away, fully seeded development database `bmp_ui_dev`**
  (migrations 001–011 + seeds 01–05, same owner/app roles) and point the tests and the running app at it with environment variables
  (`DATABASE_URL`, `DATABASE_URL_APP`, `USERS_FILE`, `STORAGE_DIR`; `.env` is untouched). Nothing in the repository refers to it.
- **Baseline (before any change), against `bmp_ui_dev`:**

  ```
  python -m pytest   ->   ======================= 307 passed, 1 warning in 18.71s =======================
  ```
- `dashboard.css` sha256 (before): `420fec8ec2d96970c5237ac322a8b0c6cd9a26cbc3a82bbf6ede8a9c0ea90220`
- **Brief vs repository differences found while reading (repository wins):**
  - State names: the brief says `state.company` / `state.year`; the code uses `state.companyId` / `state.fy` (and `company()` helper).
  - `.who-box` and `#fySelect` are inside the sidebar `.entity-box` as the brief says. `.side-companies-group` does not exist in the template
    (the "All companies" link is `a#navCompanies.side-top`); the safety-net CSS selector is still added as requested.
  - There is no `state.tab`; I add one.
- **Inventory** (`grep -rn "Filings\|col-ex\|ex-counts\|ex-more" app/static app/templates`, excluding the frozen stylesheet/vendor):

  | Hit | What it is | Change 2 touches it? |
  |---|---|---|
  | `app/static/scripts/companies.js:29` `<th>Filings</th>` (+ body cell line 21, overdue-filings pill) | the **All Companies** table | **Yes (only this)** |
  | `app/static/scripts/overview.js:29` tile "Filings recorded" | Overview tile | No |
  | `app/templates/dashboard.html:109` title text "...filings, financials..." | tooltip on the FY selector | No |
  | `dashboard.css:509,517,520,591,592` `.col-ex/.ex-counts/.ex-more` | unused legacy rules in the frozen stylesheet | No (frozen) |

  No other table renders a "Filings" header. The Government Filings record list is titled "Forms Filed (Government Filings)" in `registry.py`.
- **Inventory** (`grep -rn "Calculated Values\|calc" app tests`): the label "Calculated Values" appears only in `registry.py:23` (NAV entry) and `calc.js:1,39`.
  `calc` is wired in `main.js` (import line 16, `COMPANY_VIEWS` line 124, render switch line 160). `GET /api/calc/{view}` (`routers/views.py`) and
  tests `test_isolation.py:87-97`, `test_workflows.py:464-471`, `test_meta_coverage.py:72-74` use the API/views and are unaffected.
  `calc-card` classes exist only in the frozen `dashboard.css`; no template/script uses `#calculated-values`.

## 2. Plan

| Step | Change | Files expected | Approach | Tests |
|---|---|---|---|---|
| 1 | Foundation | `main.js`, `state.js`, `sidebar.js` | Hash routing (`#/companies`, `#/directors`, `#/notifications`, `#/company/{id}/{view}[/{tab}]`) mapped onto `go()`; `bmp:company-changed` event; unknown view → first view of parent | UI-asset test; browser smoke |
| 2 | Change 3 | `dashboard.html`, `app.css`, `main.js` | Wrap FY + who-box in `div.app-topbar-right`; exact spec CSS in `app.css`; hide FY with no company | `test_ui_assets` order/ids |
| 3 | Change 2 | `companies.js`, `app.css` | Remove header + cell only in All Companies; scoped percentage widths | static test; companies API fields unchanged |
| 4 | Change 5 | `registry.py`, `main.js`, delete `calc.js` | Remove NAV entry/route/screen; keep `/api/calc/*` | meta coverage (no calc entry, 13 views) |
| 5 | Change 1 | `sidebar.js`, `main.js`, `dashboard.html`, `app.css`, `people.py`, new `notifications.py`, `alldirectors.js`, `notifications.js`, `main.py` | Two sidebar states; `GET /api/people/directors`, `GET /api/notifications`; bell badge | API tests incl. isolation loop |
| 6 | Change 9 | `people.py`, `directors.js`, `masterdata.js`, `app.css` | Columns exist (checked) → no migration; add fields to register payload and grids | register payload test |
| 7 | Change 10 | `people.py`, `util.js`, `directors.js`, `masterdata.js` | One predicate server-side, mirrored in `util.js`; optional `fy` + `include_inactive` | table-driven boundary tests (API + JS helper) |
| 8 | Change 6 | `registry.py`, new `tabs.js`, `directors.js`, `people.py` (flags) | One "Directors" link; tabbed panel; segments with counts | coverage test |
| 9 | Change 7 | `registry.py`, new `shareholders.js`, `masterdata.js` | One "Shareholders" link; cap table from `v_shareholding_percent` | percentage test |
| 10 | Change 4 | `masterdata.js`, `app.css` | Four tabs via `tabs.js`; lazy load; save-on-blur kept | tab labels / cards test |
| 11 | Change 8 | `registry.py`, new `foreign.js`, `main.js` | New view `#foreign-investments-tab` | coverage; read-only role |
| 12 | Verify | `tests/ui/`, docs | Full suite, node --check, traceability, browser smoke, run as 3 roles | — |

## 3. Assumptions & decisions

| # | Item | Assumption / decision | Reason | Needs client/BMP confirmation? |
|---|---|---|---|---|
| A1 | CSS location (D1) | All new/overriding CSS in `app.css`; `dashboard.css` never edited | Frozen theme, test-enforced | No |
| A2 | Git | `git init` + baseline commit because the folder was not a repo | Brief requires one commit per change | No |
| A3 | Test database | Throw-away seeded `bmp_ui_dev` via env vars; user's `bmp` left untouched | `bmp` has no seed data → baseline red for reasons outside the code | Team: re-seed or point `.env` at a seeded DB |
| A4 | Hash routes and view keys | The global "All Directors" screen is view key `all-directors` (hash `#/directors`); inside a company, `directors` is the company Directors panel (hash `#/company/{id}/directors`) | The same word means two screens in the brief | No |
| A5 | Global routes close the company | Opening `#/companies`, `#/directors` or `#/notifications` (including via the bell) clears the open company; the sidebar then shows the three global links | Sidebar state follows the route | No |
| A6 | Notifications scope (D2) | Read-only screen + bell badge; no e-mail | Brief D2 | Yes (scope) |
| A7 | KMP segment | KMP = latest designation is one of MD, CMD, CWMD, WTD, CEO, CFO, CS, Manager | No KMP flag in the data model | Yes |
| A8 | Directors card in Master Data | Stays in tab 1 (General Info & Registration) | It exists today but is not named in the brief's tab lists; "every card appears in exactly one tab" | Yes |
| A9 | Navigation groups | Shareholders link stays in group "Capital & Members"; Directors in "People & Roles"; the foreign tab in "Financial & Legal"; Auditors move to "Company" | Brief | No |
| A10 | Overview segment cards | Overview builds its cards from `NAV`; consolidation shortens some cards | Brief rule 4 / context note | Yes (client may expect the old counts) |
| A11 | Director active window (D4) | A stint counts for a FY when `start <= FY_end AND (end IS NULL OR end >= FY_start)`, FY = 1 Apr–31 Mar; one rule in `people.py`, mirrored in `util.js`, parity-tested | Brief D4 | No |
| A12 | Address / Phone (D7) | Shown only to users who can already read director records; no masking added; no migration (columns exist) | Personal data, but no new exposure | Yes |
| A13 | Notification categories | Overdue filings, overdue tasks, tasks due in 7 days, pending confirmations, rules needing action (latest evaluation per rule); archived companies excluded | Derived from existing data; the brief gives no list | Yes |
| A14 | Foreign tab "next" dates (D8) | Earliest stored date on a still-open record (ODI approved-not-filed, ECB maturity, DI filing due); no rules or templates added | Tracking only | No |

## 4. Change-by-change record

### Step 1 — Foundation: hash routing + `bmp:company-changed`   (status: Done)
- Every screen now has an address: `#/companies`, `#/company/{id}/{view}[/{tab}]` (the global `#/directors` and `#/notifications` arrive with Change 1).
  `main.js` gets `parseHash`/`hashFor`/`navigate`/`applyRoute`; the existing `go(view)` is unchanged and still draws the screen. Clicks (`[data-view]`),
  the Exit-company button and the company list now change the address, and a `hashchange` listener draws it, so Back/Forward and pasted links work.
- The address is kept in step with whatever is on screen (`history.replaceState`), the saved position (`localStorage`) now also remembers the tab.
- Unknown / removed view in an address or saved position → the first view (`overview`); a company the user cannot open → `#/companies`.
- `setCompany(id)` opens/closes a company and dispatches `bmp:company-changed`; `sidebar.js` listens and rebuilds itself.
- Files: `app/static/scripts/main.js` — modified (routing, event); `state.js` — modified (`tab`); `sidebar.js` — modified (event listener);
  `tests/ui/conftest.py`, `tests/ui/test_navigation.py` — added (opt-in browser tests, see section 6).
- Tests: 4 browser tests (address follows the screen and Back/Forward; pasted link; unknown view fallback; inaccessible company).
- Commands run / results:
  - `python -m pytest tests/api/test_ui_assets.py -q` → `24 passed`
  - `BMP_UI_TESTS=1 python -m pytest tests/ui -q` → `4 passed in 6.13s` (real Chrome via Playwright)
  - `python -m pytest` → `307 passed` (the browser tests are not collected by default)
- Acceptance: address follows screen ✔ · Back/Forward ✔ · pasted link ✔ · unknown view falls back ✔ (evidence: the 4 tests above).
- Note: the Overview page's title is the company name (not the word "Overview"); the tests wait for that.

### Change 3 — Top-bar realignment (FY dropdown and user identity to the far right)   (status: Done)
- The FY selector (with its label, wrapped in `#fyWrap`) and the signed-in box (`.who-box`: `#whoName`, `#whoSub`) moved out of the sidebar's company box
  into a new `div.app-topbar-right` inside `nav.app-topbar`. Order in the group: attention badge, Refresh, Print, FY, Data menu, signed-in user
  (the notification bell is added in Change 1 and goes before FY). The spec CSS values are used exactly
  (`.app-topbar{display:flex;justify-content:space-between;align-items:center}`, `.app-topbar-right{display:flex;align-items:center;margin-left:auto;gap:1.2rem}`),
  in `app.css` (decision D1), plus a rule that wraps the group under the title below 900 px and light-background colours for the user box.
- With no company open `#fyWrap` is hidden (`main.js render()`); the user box stays visible.
- Files: `app/templates/dashboard.html` — modified (moved markup, all ids kept); `app/static/stylesheets/app.css` — modified (additions only);
  `app/static/scripts/main.js` — modified (hide FY without a company); `tests/api/test_ui_assets.py` — 2 tests added; `tests/ui/test_topbar.py` — added.
- Tests: static — FY/user inside the right-hand group, FY before user, absent from the sidebar, and every id from rule 6 still present (2 new tests);
  browser — at 1920 / 1280 / 1024 px the user box is at the far right (< 40 px from the edge), FY ends before the user starts, no neighbour overlaps, no sideways scroll;
  FY hidden until a company opens; FY change, Change-password dialog and Sign out still work.
- Commands run / results: `python -m pytest tests/api/test_ui_assets.py -q` → `26 passed`; `BMP_UI_TESTS=1 python -m pytest tests/ui -q` → `9 passed` (4 consecutive runs, all green).
- Harness note: an early run was flaky — not the app: the page clears the sign-in form once after its first (401) session check, so a test that fills the form too early loses
  the password. `tests/ui/conftest.py` now waits for the form to settle.
- Acceptance: FY + user box together at far right ✔ (browser test, three widths) · no overlap/clipping at 1024 px ✔ · ids unchanged ✔ ·
  sign-out / change password / FY change work ✔. A screenshot was also inspected by eye at 1280 px.

### Change 2 — Remove the "Filings" column from the All Companies table (this table only)   (status: Done — the column existed)
- Evidence that the column existed: `grep` (section 1) found `<th>Filings</th>` at `companies.js:29` with its body cell at line 21 (the overdue-filings pill). Both removed.
- The table got the class `all-companies-table`; `app.css` gives it `width:100%; table-layout:fixed` and percentage widths for the 7 remaining columns
  (31 / 17 / 11 / 9 / 14 / 10 / 8 %), selector scoped to that class so no other table is affected.
- **Left alone (as required):** `GET /api/companies` (still returns `overdue_filings` etc.), the Overview "Filings recorded" / "Overdue filings" tiles and attention list,
  the "Forms Filed (Government Filings)" record list, the sidebar overdue-filings chip, every other table, and the CSV/Excel/JSON exports.
- Files: `app/static/scripts/companies.js` — modified; `app/static/stylesheets/app.css` — modified (scoped additions);
  `tests/api/test_ui_assets.py` — 1 test added; `tests/ui/test_all_companies.py` — added.
- Tests: static — the exact header list, one cell per header, no "overdue" cell, the Overview tile text, the Forms Filed label and the companies API fields unchanged;
  browser — no "Filings" header at 1280 and 1920 px, the table fills its card, no sideways scroll; the Overview tile and the Forms Filed page still work.
- Commands run / results: `python -m pytest` → `310 passed` (307 + 3 new); `BMP_UI_TESTS=1 python -m pytest tests/ui -q` → `12 passed`.
- Acceptance: no "Filings" header/cells in All Companies ✔ · fills width, no horizontal scroll at 1280 and 1920 ✔ · every other "Filings" occurrence unchanged ✔
  (compare with the section 1 inventory: only `overview.js:29`, the tooltip text and frozen CSS remain, all untouched).

### Change 5 — Remove "Calculated Values"   (status: Done)
- Removed the `{"view": "calc"}` entry from `NAV` (`registry.py`); removed `calc` from the `main.js` import, `COMPANY_VIEWS` and the render switch; **deleted `calc.js`**.
  Whole-code-base search (section 1): the label existed only in `registry.py` and `calc.js`; there was no `#calculated-values` / tab button / `.calc-card` use outside the frozen stylesheet.
- **Kept:** `GET /api/calc/{view}` and the 13 views. A saved position, bookmark or hash `.../calc` now falls back to the Overview (Step 1 `viewKnown`).
- Files: `app/registry.py` — modified; `app/static/scripts/main.js` — modified; `app/static/scripts/calc.js` — deleted;
  `tests/api/test_meta_coverage.py` — 1 test added; `tests/api/test_ui_assets.py` — 1 test added; `tests/ui/test_navigation.py` — `calc` added to the fallback cases + 1 test.
- **About the test the brief asked me to update:** `test_meta_coverage.py` contained **no** expectation of a sidebar entry for this screen (it only asserts the 13 views via `/meta`),
  so nothing had to be loosened. I *added* a test that asserts the entry is gone from `NAV` and from `/api/meta`'s nav, that the 13 views are still exposed and that every
  `/api/calc/<view>` still answers. No existing assertion was changed. The auto-generated per-file JavaScript syntax test for `calc.js` disappears with the file (suite count −1).
- Commands run / results: `python -m pytest` → `311 passed` (310 − 1 deleted per-file test + 2 new); `BMP_UI_TESTS=1 python -m pytest tests/ui -q` → `13 passed`;
  `node --check` on every module → no failures.
- Acceptance: "Calculated Values" text appears nowhere in the UI ✔ (static test over template, scripts, registry, app.css + browser check of sidebar/overview) ·
  `/api/calc/*` still returns the 13 views ✔ · old link lands on the first view without error ✔ (browser test).

### Change 1 — Conditional sidebar (global vs company state) + All Directors + Notifications   (status: Done)
- **Sidebar:** `buildSidebar()` now has two states. No company open → class `sidebar-global-only` on `#sidebar`, and exactly three links in `.side-scroll`
  (`#sideGlobal`): All Companies, All Directors, Notifications; `#sideAcc` is emptied (no accordion entry, no chip), the standalone `#navCompanies` link and the company box are hidden
  (it is the first of the three links instead). Company open → full accordion as before; `#navCompanies` is the "All companies" back link; the class is removed. `app.css` carries the
  safety-net rules for `.side-companies-group`, `.accordion`, `.entity-box` (and `#navCompanies`) under `.sidebar-global-only`. The user box lives in the top bar (Change 3), so identity stays visible.
- **Routes:** global views `companies`, `all-directors` (`#/directors`) and `notifications` (`#/notifications`) close any open company (assumption A5). The bell uses `data-view="notifications"`.
- **`GET /api/people/directors`** (`routers/people.py`): one row per person + `roles` (company, designation, dates, current flag) for the companies the user may read; optional `q` (name, DIN, company; `%`/`_` literal)
  and `limit`. Who is listed uses the existing `Scope.row_scope("director", …)` — staff see every person, a client only people linked to their company; roles are always limited to readable companies.
- **`GET /api/notifications`** (new `routers/notifications.py`, registered in `main.py`): per readable company — overdue MCA filings (`core.v_filings_overdue`), overdue tasks, tasks due within 7 days, pending confirmations, rules whose
  latest evaluation is "action required" — plus `items` and `total`. Same sources/conditions as `overview()` (copied query logic; `overview()` itself was not touched). Assumption A11: for rules I use the *latest evaluation per rule*
  (any financial year) because the seed only evaluates FY 2024-25 and "current FY" would always show zero.
- **UI:** `alldirectors.js` (search box → server `q`, role chips open that company's Directors, person opens the person record, CSV export); `notifications.js` (cards per company, items open the company/view through the hash route; `refreshBadge()` fills the bell, called on start-up and Refresh).
- Files: `app/routers/people.py` — modified (+endpoint); `app/routers/notifications.py` — added; `app/main.py` — modified (router registered); `app/static/scripts/{alldirectors,notifications}.js` — added;
  `sidebar.js`, `main.js` — modified; `app/templates/dashboard.html` — modified (`#sideGlobal`, bell `#btnNotifications` / `#notifCount`); `app/static/stylesheets/app.css` — additions;
  `tests/api/test_ui_changes.py` — added (17 tests); `tests/ui/test_sidebar.py` — added (6 tests).
- Tests: API — 401 without sign-in; admin sees all people and Joshi's roles in two companies; search by name, DIN and company (compared with direct database queries); literal `%`/`_`; **isolation loop for client / manager / admin**
  (roles never outside readable companies; person list equals the existing `/entities/director` list; client sees Nexatech-only roles; manager's companies are {2,3,4}); notifications — companies listed = readable set, every count equals an independent
  database query, counts agree with `/companies/{id}/overview`, a pending confirmation appears and disappears again. Browser — exactly three links with no company; swap on open/close; Back/Forward and pasted `#/directors`;
  search and roles; a client sees only Nexatech; the bell total equals the API total and equals the number of items listed; an item opens the right company screen.
- Commands run / results: `python -m pytest` → `330 passed`; `BMP_UI_TESTS=1 python -m pytest tests/ui -q` → `19 passed`.
- Test-suite note: other tests in the same session create people named `full_name_N`, so the new tests compare with live database queries instead of fixed counts (an early version assumed the pristine 12 people and failed in the full run — fixed in the test).
- Acceptance: three links only ✔ · opening/closing swaps the sidebar ✔ · back/forward + pasted `#/directors` ✔ · client sees only own company's people ✔ · notification counts match the data ✔ (all above).

### Change 9 — Director table: Address and Phone Number   (status: Done — no database change)
- **Field check (mapping):** `director.address` → `core.director.address` (text, nullable); `director.phoneNumber` → `core.director.phone` (text, nullable). Both are in `docs/DATA_DICTIONARY.md`
  and in the live schema (confirmed by query: both columns exist, 12/12 seeded directors have both). **No migration was needed**; migrations 001–011 and the seeds are untouched.
- `directors-register` payload gets one more key, `address` (`phone` was already there) — additive. `directors.js` register grid gets "Address" (class `cell-wrap`) and "Phone Number" (`tel:` link, text exactly as stored)
  columns; the Master Data "Directors & KMP" card table gets the same two columns (plain text, because those rows already navigate on click). `app.css`: `.reg-table td.cell-wrap, .md-card td.cell-wrap{max-width:320px;overflow-wrap:anywhere}`.
- The generic record editor already offers both fields on the person record (metadata-driven) — verified, not rebuilt.
- Files: `app/routers/people.py` — modified (+`d.address`); `app/static/scripts/directors.js`, `masterdata.js` — modified; `app/static/stylesheets/app.css` — modified;
  `tests/api/test_ui_changes.py` — 2 tests added; `tests/ui/test_directors_columns.py` — added; `tests/ui/test_navigation.py` — `go_to` helper added.
- Tests: API — register payload carries both keys with data; create → read → edit → History round trip with a 200-character address (stored exactly; values appear in History as from → to; the editor marks both fields writable).
  Browser — both headers in the register and in Master Data; a 200-character address (written through the API and restored afterwards) wraps to ≤ 340 px (320 px text + padding) in both places, the page and the table container never scroll sideways.
- Commands run / results: `python -m pytest` → `332 passed`; `BMP_UI_TESTS=1 python -m pytest tests/ui -q` → `21 passed`.
- Acceptance: columns shown ✔ · 200-char address wraps inside 320 px, no sideways scroll ✔ · values round-trip through the editor and appear in History ✔.
- D7 note: address and phone are shown only to users who can already see the director record (same endpoint, same scope). They were **not** added to any new export or AI path.
  (Observation: the existing company JSON/Excel export already contains every director column, including address and phone — unchanged, see section 8.)

### Change 10 — Financial-year-specific director filtering   (status: Done)
- **One rule, two implementations kept in step.** Server (`routers/people.py`): `fy_window("2024-25") -> (2024-04-01, 2025-03-31)` and
  `active_in_window(start, end, window_start, window_end)` = `start <= window_end AND (end IS NULL OR end >= window_start)` (decision D4: a director who resigned part-way through the year is shown).
  Browser (`util.js`): `fyWindow`, `activeInFy`, `ceasedInFy`, `directorShown` (+ `showHistorical`, `fmtDateDMY`). The convention is April–March, matching `current_financial_year()`.
- **API:** `GET /api/companies/{id}/directors-register` gets optional `fy` and `include_inactive`. With `fy`, each row gets `active_in_fy` and `ceased_in_fy`; with `include_inactive=false` rows not active in that year are dropped.
  Without `fy` the response is byte-for-byte the old one (no new keys, `include_ceased` default still `true`; `include_inactive` alone does nothing). A malformed `fy` → `422` with a field message. Company access rules unchanged.
- **UI:** Directors register and the Master Data directors card fetch with the selected year, hide rows not active in it by default (with "All years": rows not serving today), and offer the switch
  **"Show Historical/Ceased Directors"** (off by default, kept in `sessionStorage`, shared by both screens, applied without reload). Ended stints use the existing ceased styling (`tr.ceased` / `tr.md-ceased`; the Master Data table now carries the
  frozen CSS's own `md-dir-table` class so that style applies); stints that ended inside the selected year show a "Ceased on dd-mm-yyyy" badge; empty states "No directors were active in 2024-25" / "No current directors." / "No directors recorded."
- Files: `app/routers/people.py`, `app/static/scripts/util.js`, `directors.js`, `masterdata.js` — modified; `tests/api/test_ui_director_fy.py`, `tests/ui/test_fy_filter.py`, `tests/ui/helpers.py` — added (shared test helpers; earlier UI tests now import them).
- Tests: **table-driven API tests** at every boundary (appointed on the last day / the day after the year; ceased on the first day / the day before / on the last day / mid-year / after; no end date; entirely inside; previous and next year of the same stint) each checked with and without
  `include_inactive`; the demo director who resigned in 2021 and was re-appointed in 2023 across FY 2020-21, 2021-22, 2022-23, 2023-24; default behaviour unchanged; malformed years; access rules; and a **parity test** that runs `util.js` under Node over ~2,400 date/year combinations
  (boundary days ± 1, with/without end, valid and invalid years) and compares each answer with the Python rule. Browser tests: default hide / switch reveals without reload / remembered after reload / same switch in Master Data; a throw-away company (archived afterwards) shows that changing the year changes the list, the badge, and both empty states.
- Commands run / results: `python -m pytest` → `354 passed`; `BMP_UI_TESTS=1 python -m pytest tests/ui -q` → `23 passed` (two consecutive runs).
- Test-ordering note: `test_isolation.py` asserts exactly 12 directors (including archived) and runs alphabetically before the `test_ui_*` files, so the new data-creating API tests live in `test_ui_*` files (run afterwards) and archive what they create. `test_isolation.py` itself was not touched.
- Acceptance: changing the FY changes the list ✔ · all five boundary cases + re-appointment ✔ (API tables, demo data, browser) · toggle reveals rows without a reload ✔.

### Change 6 — Director navigation consolidation   (status: Done)
- **Sidebar:** People & Roles now holds one link, **Directors**. Removed from `NAV`: Directors & KMP Register, Directors (people), Board stints, Designation history, Independent-director terms, Declarations, DIR-3 KYC,
  Residency, Other directorships, and Committees / Committee members (Governance). **Auditors moved to the Company group** (they are not directors). The generic `entity:<key>` pages still open any of these record types by address.
- **`tabs.js` (new, reusable):** accessible tablist (`role=tablist/tab/tabpanel`, `aria-selected`, roving `tabindex`, ← → Home End), classes `.rec-tabs/.rec-tab/.tab-pane` (existing tab styles reused), each pane drawn on first open,
  remembers the tab in `state.tab` and the address (`#/company/{id}/directors/{tab}`); an unknown tab opens the first; Back/Forward switch tabs without redrawing the screen (`main.js` asks `activeTabs()` to show the tab; a click adds a history entry, opening a screen only rewrites the address).
- **`directors.js` is now the panel:** tabs **Register** (default: segment controls, the Change 9/10 columns and switch, add-director dialog unchanged), **DIN & KYC** (people of this board, DIR-3 KYC, residency), **Appointments** (board stints, designation history,
  independent-director terms), **Resignations** (every stint with an end date, from the register data), **Board Committees** (committees, members), **Declarations & other directorships**. Each list is the generic `mountList`, so search, sort, CSV, archive and the record editor work.
- **Segment controls** (client side): All / Active in FY / Ceased / Independent / KMP / On a committee, each with a count computed over the rows currently in scope; the rows shown for a segment equal its count (tested for every segment, with and without the history switch).
  The register payload gained two additive keys for this: `designation_code` and `on_committee` (current committee membership). KMP = designation MD, CMD, CWMD, WTD, CEO, CFO, CS or Manager (assumption A7).
- Files: `app/registry.py` (NAV) — modified; `app/routers/people.py` — modified (+2 payload keys); `app/static/scripts/tabs.js` — added; `directors.js` — rewritten as the panel; `main.js` — modified (tab events, address normalisation, `activeTabs`);
  `app/static/stylesheets/app.css` — additions (`.tab-host`, `.seg-bar`, `.seg-btn`); `tests/api/test_ui_directors_panel.py`, `tests/ui/test_directors_panel.py` — added.
- **Existing tests changed (narrowly) and why:**
  - `tests/api/test_meta_coverage.py` — `DEDICATED` gained `director` and `committee`. They no longer have a sidebar entry (the client asked for one link); the new `test_ui_directors_panel.py` proves the panel lists all ten former record types by reading the panel's source.
  - `tests/api/test_workflows.py::test_overview_counts_match_the_database` — the Overview page builds its "segment cards" from `NAV` (as the brief warned). The People & Roles group now holds no record types, so its card is no longer produced; the expected set of card ids dropped `"people"`. Nothing else in that test changed.
- Commands run / results: `python -m pytest` → `358 passed`; `BMP_UI_TESTS=1 python -m pytest tests/ui -q` → `30 passed` (twice).
- Found while testing: an address with an unknown view (`.../calc`) stayed in the address bar when it fell back to the Overview; fixed in `applyRoute` (`replaceState` to the screen actually opened) — the Step-1 browser test caught it.
- Acceptance: one "Directors" link, no duplicate children ✔ · every formerly separate record type reachable and editable inside the panel ✔ (test + the Board-stint editor opened with a Save button) · "Add director/KMP" still creates person + stint + designation ✔ (browser test; archived afterwards) · segment counts equal rows shown ✔.

### Change 7 — Shareholder navigation consolidation   (status: Done)
- **Sidebar:** Capital & Members now lists one link, **Shareholders** (new `shareholders.js`), plus — **until Change 8 moves it** — Foreign Investment (FC-GPR / FC-TRS), so that no record type is unreachable at this commit.
  Removed from `NAV`: Share classes, Share capital summary, Capital events, Shareholders (people & entities), Shareholdings, Allotments, Share transfers.
- **Panel tabs:** **Cap table** (current holdings grouped by share class with "N shares in issue", shares, and the **database-calculated percentage**; below it the editable *Holding records* list), **Allotments**, **Transfers**, **Shareholders** (people/entities).
  A "Capital structure" link at the top jumps to `#/company/{id}/masterdata/capital`. Share classes, share capital summary and **capital events** are shown in Master Data: the first two were already cards there; **I added a "Capital events" card** to the current stacked
  Master Data page so the record type stays reachable at this commit (Change 4 then groups these cards into tab 2).
- **No percentage is computed in the browser:** the cap table reads `/api/calc/v_shareholding_percent` (the 13 views and the endpoint stay); share-class names come from `/options/share_class`. A static test forbids `* 100`, division by total, `toFixed`, `Math.round` in `shareholders.js`.
- Files: `app/registry.py` — modified; `app/static/scripts/shareholders.js` — added; `main.js` — modified (import, `COMPANY_VIEWS`, render); `masterdata.js` — modified (+ Capital events card);
  `tests/api/test_meta_coverage.py` — `DEDICATED` gained `shareholder`, `share_transfer`, `share_class`, `capital_snapshot`, `capital_event` (they no longer have a sidebar entry; `test_ui_shareholders.py` proves the panel / Master Data list them);
  `tests/api/test_ui_shareholders.py`, `tests/ui/test_shareholders_panel.py` — added.
- Tests: API — sidebar entries; reachability by source; no browser-side percentage maths; **the endpoint equals a direct query of `core.v_shareholding_percent`**, each percentage re-derived independently, shares add up to the class total and percentages to 100 (±0.01) per class; scoping (client/manager get 404 for other companies).
  Browser — one link and no old entries; four tabs; **each cap-table percentage equals the API/database value exactly**; Add buttons for allotments/transfers open the editor and existing rows open for editing; a read-only client sees the panel with **no Add buttons**; the Capital-structure link lands on Master Data with Share classes / Share capital / Capital events; tab address + Back.
- Commands run / results: `python -m pytest` → `364 passed`; `BMP_UI_TESTS=1 python -m pytest tests/ui -q` → `36 passed`.
- Acceptance: one "Shareholders" link ✔ · allotment and transfer records can be added/edited from inside the panel ✔ · cap-table percentages match the core view ✔ · all former entries reachable ✔ (foreign investment moves in Change 8).

### Change 4 — Master Data tab modularisation   (status: Done)
- `masterdata.js` now mounts **four horizontal tabs** with the exact labels (via `tabs.js`; one pane visible at a time; each pane is drawn — and its data fetched — the first time it is opened; address `#/company/{id}/masterdata/{general|capital|charges|registers}`):
  1. **General Info & Registration** — Company profile (every field, **save-on-blur and the "✓ saved" tick unchanged**), Directors & KMP (assumption A8: it exists today but the brief does not name it, so it stays here), Business activities, Holding/subsidiary/associate companies, Statutory auditors, Registrar & Transfer Agent.
  2. **Capital Structure & Financials** — Share classes, Share capital (summary), Capital events, Financials by year, Shareholders and their holdings (with the link to the Shareholders view).
  3. **Charges & Borrowings** — Loans and deposits, an ECB summary (count + link to the foreign-investment tab, which arrives in Change 8), and the charge panel with the explicit empty state *"No charge register in the approved data model"* (decision D3 — no table invented).
  4. **Statutory Registers** — read-only registers composed from existing data: directors & KMP, members (the database's calculated percentages), loans to directors (Sec 185), loans & investments (Sec 186), related-party contracts (Sec 188); plus clear *"No source table"* placeholders for charges, debenture holders and sweat-equity shares. Each composed register has its own **Export CSV** (client side).
- Every card that existed before appears in exactly one tab (11 titles, tested). No `dashboard.css` change; the existing `.md-layout` / `.md-card` / `.rec-tabs` styles are reused as-is, so `app.css` needed no further additions.
- Files: `app/static/scripts/masterdata.js` — rewritten around tabs (profile/lists code moved, not changed); `tests/ui/test_master_data_tabs.py` — added.
- Tests (browser): exact labels and one pane at a time; each former card exactly once; lazy loading (no register requests before the tab is opened, pane empty until then); **save-on-blur still PATCHes `company`** (website edited, saved tick shown, value checked through the API, then restored); tab in the address / refresh / Back / unknown tab → first tab;
  the charge empty state and the link; registers: titles, no Add buttons or editable rows, placeholders, CSV download content (`Rajan Patel`, `56.6667`); a read-only client sees disabled profile fields.
- Commands run / results: `python -m pytest` → `364 passed`; `BMP_UI_TESTS=1 python -m pytest tests/ui -q` → `44 passed`.
- Acceptance: four tabs, exact labels ✔ · every previous card in exactly one tab ✔ · profile still saves on leaving a field ✔ · tab survives refresh and Back ✔.
- Known interim: the ECB summary link points at the foreign-investment tab, which is created in Change 8 (the next commit).


### Change 8 — ODI / ECB / DI / Foreign Investments tab   (status: Done)
- New company-sidebar entry, **exact label `ODI / ECB / DI / Foreign Investments`** (group Financial & Legal), opening the new `foreign.js` view (root `#foreign-investments-tab`, address `#/company/{id}/foreign`).
- The view holds: a **summary strip** (per section: record count, total amount, next date — ODI "approved, not yet filed", ECB maturity, DI filing due) and four `mountList` grids — **ODI**, **ODI step-down subsidiaries**, **ECB**, **DI / foreign investment received (FC-GPR and FC-TRS)**.
  Add buttons, editing and archive come from `mountList`, so a read-only client sees the grids **without Add buttons**.
- **Tracking only (D8):** no rules, activity templates, or due-date logic were added; the "next" dates are the earliest date already stored on a still-open record, read from the existing columns (`board_approval_date`/`filing_date`, `maturity_date`, `filing_due_date`).
- **One home per record:** `odi`, `odi_step_down_subsidiary`, `ecb` (Financial & Legal) and `foreign_investment` (Capital & Members, interim) were removed from `NAV`. The record types, endpoints and tables are unchanged. As a consequence the Overview no longer shows a "capital" segment card (its only item was `foreign_investment`); `test_workflows` expectation updated accordingly (`capital` dropped, like `people` in Change 6).
- Files: `app/registry.py` — modified; `app/static/scripts/foreign.js` — added; `main.js` — modified (import, `COMPANY_VIEWS`, render switch); `tests/api/test_meta_coverage.py` (`DEDICATED` + 3), `tests/api/test_workflows.py` — modified;
  `tests/api/test_ui_foreign.py`, `tests/ui/test_foreign_tab.py` — added; `tests/ui/test_fy_filter.py` — one assertion made wait-for-count (it raced the list render once in a full run; passed on rerun, behaviour unchanged).
- Tests: API — exact label present once, old entries gone, record types still in `ENTITIES`, view mounts all four keys and is registered, each type still readable via the API, no rules/templates code. Browser — sidebar entry and old names gone; summary strip + four grids; admin sees 4 Add buttons, client sees none.
- Commands run / results: `BMP_UI_TESTS=1 python -m pytest -q` → `416 passed` (includes 47 browser tests; `tests/ui -q` alone → `47 passed`).
- Acceptance: exact label ✔ · ODI, ECB and DI grids ✔ · summary strip ✔ · read-only client has no Add ✔ · old sidebar entries removed, ECB link in Master Data now resolves ✔.

## 5. Database / API changes

**Migrations: none.** `core.director.address` and `core.director.phone` (Change 9) already exist in migrations 001–011, so no additive migration was written. Migrations 001–011 and seeds 01–05 are untouched (`git diff 9a530f7 --name-only` lists no migration, seed or SQL file).

| Endpoint | Change | Compatible? |
|---|---|---|
| `GET /api/people/directors` | **New.** All directors across the companies the user may read (`q`, `limit`), with each person's roles. Uses the same row-scope builder as the generic engine, so a manager / client only sees their own companies. | Additive |
| `GET /api/notifications` | **New.** Per readable company: overdue filings, overdue tasks, tasks due within 7 days, pending confirmations, rules needing action; plus `items` and `total`. Read-only. | Additive |
| `GET /api/companies/{id}/directors-register` | New **optional** params `fy` (e.g. `2024-25`; malformed → 422 with a field message) and `include_inactive` (default `true` = today's behaviour). New **additive** keys per row: `address`, `designation_code`, `on_committee`, and — only when `fy` is given — `active_in_fy`, `ceased_in_fy`. | Additive; no key removed or renamed |
| `GET /api/calc/{view}` | Unchanged (the 13 views stay; only the Calculated Values screen was removed). | — |
| `GET /api/entities/{odi, odi_step_down_subsidiary, ecb, foreign_investment}` | Unchanged; their sidebar entries moved into one view. | — |

The FY rule (decision D4) — a stint counts for a financial year when `start <= FY_end AND (end IS NULL OR end >= FY_start)` with FY 1-Apr to 31-Mar — is implemented once in `people.py` and mirrored in `util.js`; a Node-based parity test runs the same table through both.

## 6. Final verification

Run on the branch head, against the seeded throw-away database `bmp_ui_dev` (see section 1), 7 Oct 2026:

```
python -m pytest                              ->  369 passed, 1 warning in 19.05s     (baseline before any change: 307 passed)
python -m pytest tests/api                    ->  350 passed
python -m pytest tests --ignore=tests/api     ->  19 passed
BMP_UI_TESTS=1 python -m pytest               ->  416 passed in 78.87s                (the 369 above + 47 browser tests)
BMP_UI_TESTS=1 python -m pytest tests/ui -q   ->  47 passed in 60.87s
python scripts/check_traceability.py          ->  SUCCESS: All 292 requirement rows across 26 data sheets are mapped in FIELD_TRACEABILITY.md (100.0% coverage).
sha256sum app/static/stylesheets/dashboard.css -> 420fec8ec2d96970c5237ac322a8b0c6cd9a26cbc3a82bbf6ede8a9c0ea90220  (identical to the baseline; `git diff 9a530f7 -- dashboard.css` is empty)
for f in app/static/scripts/*.js; do node --check "$f"; done   ->  no errors
```

Application run (`python scripts/run_server.py`, real server, HTTP walk as the three roles):

```
GET /api/health -> {"status": "ok", "database": true, "version": "1.0.0"}
admin   (5 companies): directors 200, register 200, notifications 200, odi/ecb/foreign 200, calc 200, overview 200, bad fy -> 422
manager (3 companies): same statuses
client  (1 company)  : same read statuses; POST /api/entities/ecb -> 403 (read-only)
GET /  -> 200   /static/scripts/foreign.js -> 200   /static/scripts/calc.js -> 404 (removed)
```

Browser tests (Playwright, system Chrome, opt-in with `BMP_UI_TESTS=1`) walked all ten changes as admin and, where it matters, as the read-only client: top bar order, All Companies headers, both sidebar states, Directors panel (tabs, keyboard arrows / Home / End, segments, FY toggle), Shareholders panel, four Master Data tabs, the foreign-investment tab, Back / refresh / pasted-link behaviour.
**Not run:** Newman on `docs/postman` (not installed here); no manual visual review at a phone width beyond the top-bar wrap rule; the stock `.env` baseline (empty `bmp` database) is red for reasons outside this work (section 1).

One browser test (`test_fy_filter`) raced the list render once in a full run (failed once, then passed on repeated runs); its assertion now waits for the row count. No behaviour changed.

## 7. Where things moved (release note for BMP staff)

| You used to… | Now… |
|---|---|
| See FY selector and user name in the left panel | They are in the **top bar**, on the right (FY next to the bell, user last). With no company open the FY selector is hidden. |
| See a **Filings** column on All Companies | The column is gone (the "Overdue filings" tile is still on the Overview and in Notifications). The filings themselves are under Financial & Legal → Forms Filed (Government Filings). |
| Open **Calculated Values** | Removed from the menu. The same figures are in Overview, the Shareholders cap table and the Master Data registers. (The data views stay in the database / API.) |
| See company menus when no company was open | Only **All Companies · All Directors · Notifications** show; the company menus appear once you open a company. |
| Open Directors, Appointments, Resignations, DIN & KYC, Declarations, Committees from the sidebar | One **Directors** link → tabs *Register · DIN & KYC · Appointments · Resignations · Board Committees · Declarations & other directorships*. Committees live in the Board Committees tab. |
| Open Share classes, Share capital summary, Capital events, Shareholdings, Allotments, Transfers, Shareholders | One **Shareholders** link → tabs *Cap table · Allotments · Transfers · Shareholders*. Share classes, capital summary and capital events are in **Master Data → Capital Structure & Financials**. |
| Scroll one long Master Data page | Four tabs: *General Info & Registration · Capital Structure & Financials · Charges & Borrowings · Statutory Registers*. |
| Open ODI, ODI step-down subsidiaries, ECB, Foreign Investment (FC-GPR / FC-TRS) separately | One **ODI / ECB / DI / Foreign Investments** entry (Financial & Legal) with a summary strip and four lists. |
| Look for the directors register without old directors | The register now shows **Address and Phone**, and hides directors who had left before the selected financial year; a "Show Historical / Ceased Directors" switch brings them back. |
| Look for directors across all companies | **All Directors** (left menu, no company open): search by name / DIN / PAN, with the companies and roles of each person, CSV export. |
| Look for alerts | **Notifications** (bell in the top bar, with a count) — on screen only, no e-mail. |

Overview cards: the *People & Roles* and *Capital & Members* cards disappear from the Overview because their record types are now reached through the new panels (the Overview builds cards from the menu; assumption A10).

## 8. Observations (not changed)

- The local `bmp` database has the schema but no seed data, so the stock-`.env` test run is red (17 database tests). Re-seed it or point `.env` at a seeded database.
- `dashboard.css` carries unused legacy rules (`.col-ex`, `.ex-counts`, `.ex-more`, `.calc-card`). The stylesheet is frozen, so they stay.
- The project's own `venv/` has no packages installed.
- The brief mentions `state.company` / `state.year`; the code uses `state.companyId` / `state.fy`. The code was followed.
- No charge register, debenture-holder or sweat-equity table exists in the approved data model; Master Data shows explicit "not in the approved data model / No source table" panels instead of inventing tables (D3).
- `Directors & KMP` appears in Master Data (General tab) as before; the brief did not name it (A8).
- `tests/ui` is opt-in (needs Playwright and a Chrome); `python -m pytest` without `BMP_UI_TESTS=1` neither imports nor needs it.

## 9. Open items for the team

1. **Seed the local `bmp` database** (or confirm which database the tests should use) — section 1.
2. **KMP definition (A7):** the segment uses MD, CMD, CWMD, WTD, CEO, CFO, CS, Manager because no KMP flag exists. Confirm the list.
3. **Overview cards (A10):** two cards (People & Roles, Capital & Members) no longer appear; confirm the client is happy, or ask for the cards to be built from the new panels.
4. **Notifications scope (A6 / A13):** on-screen only; confirm the five categories and the 7-day "due soon" window; e-mail / push is out of scope.
5. **Charge register (D3):** needs a data-model decision from BMP before any "Register of charges" can be shown.
6. **Address / phone (D7)** are personal data. They are visible to anyone who can already read director records; confirm no further masking is wanted.
7. **Newman** collection run and a manual visual pass on real phones were not done here.
8. Nothing was pushed, merged or deployed; the work is on branch `ui-changes-client-review` for review.
