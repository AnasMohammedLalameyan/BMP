# BMP Compliance Platform — UI Change Set: Implementation Prompt


---

## 0. Your role

You are a **senior software engineer** joining the BMP Compliance Platform project. Phase 1 (the approved PostgreSQL
database) is complete. The FastAPI back end and the approved dashboard front end are built and hosted. After a design
review, the client (BMP & Co. LLP) asked for **10 UI changes**. Your job is to implement exactly those 10 changes,
prove nothing else broke, and keep a written log of everything you did.

You work **inside the existing repository**. You are not redesigning anything.

## 1. Non-negotiable rules

Read these twice. They override anything else in this file if there is a conflict.

1. **Minimal change.** Touch only what is needed for the 10 changes. No refactors, renames, reformatting, dependency
   upgrades, "clean-ups", or style fixes in code you did not need to change. If you are tempted to improve something
   unrelated, write it in the log under *"Observations (not changed)"* instead.
2. **`app/static/stylesheets/dashboard.css` must stay byte-identical.** A test (`tests/api/test_ui_assets.py`) enforces
   it. The client documents say "in dashboard.css", but the approved engineering plan (decision D1) puts **all new and
   overriding rules in `app/static/stylesheets/app.css`**, using the exact property values from the spec. Do that. Record
   the decision in the log. Never edit `dashboard.css`.
3. **The approved database is not edited.** Migrations `db/migrations/001`–`011` and seeds `01`–`05` are never modified.
   A database change is allowed only as a *new, additive, numbered migration* and only for Change 9, and only if the
   field check (section 5, Change 9) proves the columns are missing. Flag it clearly in the log as *"needs BMP approval"*.
4. **No API contract breaks.** Existing endpoints keep their paths, inputs, outputs, status codes and defaults.
   New query parameters must be optional and default to today's behaviour. New endpoints are allowed only where this
   file says so (Changes 1 and 10, plus optionally 6).
5. **No access removed.** No change may make any table or record type unreachable from the UI. Where a sidebar entry is
   removed, the record type must be reachable somewhere else (inside a consolidated view, a Master Data tab, or the
   foreign-investment tab).
6. **Keep every existing HTML element `id`.** `main.js` binds by id and `test_ui_assets.py` checks that every id used
   in JavaScript resolves in the template. You may *move* elements; do not rename or drop ids
   (`fySelect`, `whoName`, `whoSub`, `entityName`, `entityMeta`, `btnRefresh`, `btnPrint`, `btnExport`,
   `btnExportExcel`, `btnChangePassword`, `btnSignOut`, `btnExitCompany`, `navCompanies`, `sideAcc`, `view`,
   `pageTitle`, `pageSub`, `crumb`, `search`, `searchWrap`, `overallBadge`, `modalHost`, `toast`, `toastMsg`, …).
7. **Security stays intact.** Do not weaken CSRF, session handling, company isolation, row-level security, or the
   read-only behaviour of the *client* access level. Escape all database text with `esc()` (a test looks for unescaped
   output). No inline scripts and no CDN/external resources (the Content-Security-Policy forbids them; the UI must work
   fully offline).
8. **No build step, no new front-end framework.** The front end is plain ES modules under `app/static/scripts/`. Keep it
   that way. Do not add npm dependencies to the application. (Dev-only test tooling is covered in section 7.)
9. **Do not guess silently.** When the requirement is ambiguous, apply the default in section 4, and log it as an
   *Assumption*. When something in the repository contradicts this brief, trust the repository, adapt, and log it.
10. **Never claim something works unless you ran it.** Every "done" in the log must be backed by a command you ran and its
    result.

## 2. Context you must absorb first (read, don't skim)

Read these in the repository before writing any code. File names below come from the project's Technical Guide;
**verify they exist and match** before relying on them.

| Read | Why |
|---|---|
| `README.md`, `BMP_UI_Backend_Implementation_Guide.md`, `BMP_UI_Backend_Implementation_Log.md` | How the project is built, what was already decided |
| `docs/DATA_DICTIONARY.md` | Real column names (needed for Change 9) |
| `app/templates/dashboard.html` | The single HTML page: sign-in, top bar, sidebar, content, modal host |
| `app/static/stylesheets/app.css`, and *skim* `dashboard.css` (read-only) | Existing tokens (`--brand`, `--line`, `--ok`…), `.rec-tabs`, `.rec-tab`, `.md-card`, `.reg-table`, `.cell-wrap` |
| `app/static/scripts/main.js`, `state.js`, `sidebar.js`, `entity.js`, `form.js`, `util.js`, `api.js` | Routing (`go(view)`), shared state, sidebar builder, generic list/record editor |
| `masterdata.js`, `directors.js`, `calc.js`, `overview.js`, `companies.js` | The screens being changed |
| `app/registry.py` | `NAV`, `ENTITIES`, `SCOPE`, `VIEWS` — drives the sidebar **and** the Overview segment cards |
| `app/routers/companies.py`, `people.py`, `meetings.py`, `views.py`, `main.py` | Back-end patterns to copy (`session()`, `readable_company()`, `ok()`, router registration loop in `main.py`) |
| `tests/api/test_ui_assets.py`, `test_meta_coverage.py`, `test_isolation.py`, `test_workflows.py`, `conftest.py` | What the existing tests assert, so you update them deliberately and only where needed |

### Facts already established (confirm each in the repo)

- Front end = 1 Jinja template + `dashboard.css` (approved, frozen) + `app.css` (additions) + 17 ES modules. No build step.
- State lives in `state.js` (`state.company` is the "selected company", `state.year` is the financial year,
  `state.current` is the open view). Views switch with `go(view)`; there are **no URL routes today**.
- The sidebar is built by `sidebar.js` from the server's `NAV` (in `registry.py`). `NAV` items are either
  `{"view": ...}` (hand-built screens) or `{"entity": ...}` (generic table pages rendered by `entity.js`).
- `app/routers/companies.py → overview()` **iterates `NAV` to build the Overview "segment cards"** (it looks at items with an
  `entity` key). Editing `NAV` therefore changes the Overview payload. Keep that endpoint working and its tests green.
- Currently the FY selector (`#fySelect`) and the signed-in box (`.who-box`) are inside the sidebar's `.entity-box`.
  Hiding `.entity-box` in the "no company" state must not hide the user identity — Change 3 moves both to the top bar.
- Demo users: `admin@bmpco.in` (administrator, 5 companies), `manager@bmpco.in` (3 companies, can edit),
  `client@nexatech.co.in` (Nexatech only, **read-only**). All data is fictional.
- Baseline test suite: **307 tests** (19 database + 288 web). Expected: all pass in about 20 seconds.

## 3. Mandatory workflow

Work in this order. Do not skip ahead.

### Phase A — Orient and baseline (no code changes yet)

1. Confirm the environment: Python venv active, `.env` present, PostgreSQL reachable, `node --version` works
   (the UI tests call `node --check`). If something is missing, fix the *environment*, not the code, and log it.
2. Create the log file `docs/UI_CHANGES_LOG.md` (template in section 8). Write the "Environment" and "Baseline" sections.
3. Run the full baseline **before touching anything**:
   ```bash
   python -m pytest
   ```
   Record the exact result (expected `307 passed`). If the baseline is not green, **stop**, log the failures and their
   probable cause, and do not start changes on a red baseline.
4. Also record: `git status` (should be clean), current branch, and a checksum of `dashboard.css`
   (`sha256sum app/static/stylesheets/dashboard.css`). Create a working branch, e.g. `ui-changes-client-review`.
5. Take inventory with searches and write the results in the log:
   `grep -rn "Filings\|col-ex\|ex-counts\|ex-more" app/static app/templates`,
   `grep -rn "Calculated Values\|calc" app tests`,
   and list every place that currently renders a "Filings" header, noting which one is the **All Companies** table
   (the only one Change 2 touches; the rest must be left as they are).

### Phase B — Plan

Write a short plan in the log: for each change, the files you expect to touch, the approach, and the tests you will add or
update. Keep the plan consistent with the build order in section 5.

### Phase C — Implement, one change at a time

For **each** change, in the order in section 5:

1. Make the smallest edit that satisfies the change.
2. Add or update the tests for it (section 7).
3. Run the fast checks (`python -m pytest tests/api/test_ui_assets.py -q` plus the tests for the area you touched).
4. Commit with a message like `UI change 3: topbar realignment`. One change = one commit, so any change can be reverted
   on its own.
5. Append a log entry (what, why, files, commands run, results, assumptions) **before** starting the next change.

### Phase D — Full verification

Run the full end-to-end verification in section 7. Do not finish until it is green.

### Phase E — Hand-over

Finalise the log, write the release note and the UAT checklist (section 9), and give a short final summary.

## 4. Assumptions to use when a decision is open

The approved Plan of Action lists open decisions. Do **not** stop to ask. Use these defaults, implement so they are easy to
change later, and list every one in the log under *Assumptions*.

| ID | Open question | Default to implement |
|---|---|---|
| D1 | CSS location | New rules in `app.css`; `dashboard.css` untouched (see rule 2). |
| D2 | Notifications scope | Read-only screen + topbar count badge. **No e-mail.** |
| D3 | Charge register / Statutory Registers have no tables in the approved model | Show an explicit, honest empty state ("No charge register in the approved data model"). Do not invent tables. Registers composed from **existing** data are read-only views. |
| D4 | Meaning of "active in the FY" | A director whose board stint overlaps the FY window is shown. Overlap rule: `start <= FY_end AND (end IS NULL OR end >= FY_start)`. Someone who resigned part-way through the FY **is** shown, with a "Ceased on dd-mm-yyyy" badge. Ceased before the FY started, or appointed after it ended, are hidden by default. |
| D7 | Personal data | Address and phone are personal data: show them to users who can already see the director; do not add them to any AI or export path; for the read-only *client* level, do not add them to exports. |
| D8 | Foreign-investment scope | Tracking view only. No new rules, due-date logic or activity templates. |

## 5. The 10 changes — build in this order

Order matters: Changes 1, 4, 6, 7, 8 all touch navigation; Changes 6, 9, 10 all touch the Directors screen.

### Step 1 — Foundation (enabler, no visible change)

- Add **hash routing** that maps onto the existing `go()`: `#/companies`, `#/directors`, `#/notifications`,
  `#/company/{id}/{view}` (and `#/company/{id}/masterdata/{tab}` later). Keep "restore last position". Browser back/forward
  and a pasted link must work. An unknown or removed view in a saved position or hash must fall back to the **first
  available view** of the parent (this also serves Change 5).
- Emit a `bmp:company-changed` event when a company is opened or closed (alongside the existing `bmp:unauthenticated`
  pattern). `sidebar.js` listens to it and calls `buildSidebar()`.
- Keep this small. Put routing in `main.js` or a tiny new module; do not restructure `main.js`.

### Step 2 — Change 3: Top-bar realignment (FY dropdown and user identity to the far right)

- In `dashboard.html`, wrap the FY `<select id="fySelect">` (with its label) and the `.who-box` (`#whoName`, `#whoSub`) in a new
  `div.app-topbar-right`, placed inside the `nav.app-topbar`. Right-group order: notification bell (added in Change 1),
  FY, Data menu, user. Keep the existing Refresh / Print / Data buttons working; they may sit in the same right group.
- In `app.css` (exact values from the spec):
  `.app-topbar{display:flex;justify-content:space-between;align-items:center}`
  `.app-topbar-right{display:flex;align-items:center;margin-left:auto;gap:1.2rem}`
  and a rule so that below about 900 px the right group wraps under the title instead of overflowing.
- When **no company is open**, hide or disable the FY selector (a financial year only means something for a company).
- All element ids unchanged; sign-out, change password, export and FY change must still work.
- **Acceptance:** FY selector and user box sit together at the far right at desktop widths; no overlap or clipping at
  1024 px.

### Step 3 — Change 2: Remove the "Filings" column from the All Companies table (this table only)

**Scope is deliberately narrow.** The client wants the "Filings" column removed **only** from the table on the
**All Companies** page, the table used to pick/select a company. It is **not** being removed from any other table, screen or
record list. Do not touch any other "Filings" label, column, tile or screen.

- The All Companies screen is rendered by `companies.js` (`renderCompanies`), fed by `GET /api/companies`
  (`list_companies` in `app/routers/companies.py`). Locate the "Filings" header cell and its matching body cell(s)
  (the old-dashboard markup was `<th class="col-ex">Filings</th>` / `td.col-ex` with `.inst`, `.ex-counts`, `.ex-more`; the
  rebuilt UI may render it differently, for example as a count of overdue filings).
- Remove **only** that header and its cells from the All Companies table, in `companies.js`. Then make the remaining columns
  fill the table width using percentage widths, scoped to this table with a specific selector in `app.css` (do not use a rule that
  would affect other tables).
- **Leave unchanged:** the `GET /api/companies` response (including `overdue_filings`; other code, such as tests or the
  Overview, may rely on it), the Overview page's filing tiles and attention list, the Government Filings / "Forms Filed"
  record list, every other table, and the CSV/Excel/JSON exports.
- If the All Companies table in the rebuilt UI **has no "Filings" column** (verify by reading `companies.js` and, if possible,
  the rendered page), the change is **not applicable**: do not invent work. Record "N/A — column does not exist in the rebuilt
  All Companies table" with the search commands and results as evidence, and list it for the client to confirm.
- **Acceptance:** the All Companies table has no "Filings" header or cells and its remaining columns fill the width with no
  horizontal scroll at 1280 px and 1920 px. Every other table that was showing a "Filings" header or column before still shows
  it exactly as before (compare against the Phase A inventory).

### Step 4 — Change 5: Remove "Calculated Values"

- Remove the `{"view": "calc"...}` entry from `NAV` in `registry.py`, remove `calc` from `COMPANY_VIEWS` and the render switch in
  `main.js`, delete `calc.js` and its import. Search the whole code base for the label "Calculated Values" and remove any
  tab button or container (`#calculated-values`, `.calc-card`) found.
- **Keep** `GET /api/calc/{view}` and the 13 database views. Only the screen goes.
- A saved position, bookmark or hash that points to the removed view must land on the first available view with no error.
- Update `tests/api/test_meta_coverage.py` so it no longer expects a sidebar entry for this screen but **still** expects the
  13 views to be exposed by the API. Write in the log why the test was changed.
- **Acceptance:** the text "Calculated Values" appears nowhere in the UI; `/api/calc/*` still returns the 13 views.

### Step 5 — Change 1: Conditional sidebar (global vs company state) + All Directors + Notifications

- **No company open:** `sidebar.js` renders exactly three links in `.side-scroll`: **All Companies**, **All Directors**,
  **Notifications**, and nothing else. Add class `.sidebar-global-only` to the sidebar container. No company-specific entry
  (accordion, entity box, meeting register, checklists) may exist in the DOM. Add CSS safety-net rules in `app.css` that hide
  `.side-companies-group`, `.accordion`, `.entity-box` under `.sidebar-global-only`. Because Change 3 already moved the user
  box to the top bar, the user identity stays visible.
- **Company open:** full sidebar as today, plus an "All companies" back link; remove `.sidebar-global-only`.
  Closing the company (existing "Exit company" button) restores the three-link sidebar.
- **All Directors screen (new, `alldirectors.js`):** one row per *person* with their roles across every company the signed-in user may access.
  Search by name, DIN, company. Reuse list/table helpers (`mountList` in `entity.js`, `esc`, `toCSV`) where possible.
- **New endpoint `GET /api/people/directors`** (extend `app/routers/people.py` or a new router; if new, register it in the
  router loop in `app/main.py`). Scope it like existing people tables: staff (admin/manager) see all people; a **client** sees only people linked to their own company. Use `session()` / the existing access helpers — do not hand-roll access control.
- **Notifications screen (new, `notifications.js`):** read-only. New endpoint `GET /api/notifications` aggregating, per
  accessible company: overdue tasks, tasks due within 7 days, confirmations awaiting a person, overdue MCA filings, rules
  needing action. **Reuse the queries already in `companies.py → overview()`** (`core.v_filings_overdue`, `ops.task_instance`,
  rule evaluation) instead of writing new logic. Show a count badge on a bell icon in the top bar (`.app-topbar-right`).
  Clicking an item opens the relevant company/view via the hash routes.
- **Acceptance:** with no company open the sidebar shows exactly three links; opening/closing a company swaps the sidebar; back/forward
  and a pasted `#/directors` link work; a read-only client user sees only their own company's people; notification counts match
  the underlying data.

### Step 6 — Change 9: Director table — Address and Phone Number

- **Field check first.** Open `docs/DATA_DICTIONARY.md` and the person/director table. Map the spec placeholders
  `director.address` / `director.phoneNumber` to the **real** column names. Record the mapping in the log.
- If the columns exist, only surface them. If they do **not** exist: add a new additive migration
  `db/migrations/012_person_contact.sql` (next free number — check first) adding nullable `address` (text) and `phone` (text,
  light format check) to the people table; update the fictional seed data only if that can be done by adding a *new* seed
  file, not by editing existing seeds. Run `python scripts/setup_db.py` to apply. Log it as **"database change — requires BMP
  approval"**. Never edit migrations 001–011.
- Add the two fields to the `directors-register` payload and add `Address` and `Phone Number` columns to the register grid in
  `directors.js` (`.reg-table` / `.md-dir-table`). The generic record editor will show the new fields automatically (it is
  metadata-driven) — verify, don't rebuild.
- Apply the existing `.cell-wrap` rule (`max-width:320px; overflow-wrap:anywhere`) to the address cell. Show phone as stored
  (no reformatting); a `tel:` link is fine.
- **Acceptance:** a 200-character address wraps inside 320 px and the page never scrolls sideways; values round-trip through
  the record editor and appear in History.

### Step 7 — Change 10: Financial-year-specific director filtering

- Define the predicate **once** (server side, in `people.py`, and mirrored in a small shared JS helper): a stint is active in
  the FY when `start <= FY_end AND (end IS NULL OR end >= FY_start)`. Derive the FY window from the selected `state.year`
  (format `2024-25`, April–March, matching `current_financial_year()` in `companies.py`); do not hard-code anything beyond
  that same convention.
- `GET /api/companies/{id}/directors-register`: add **optional** `fy` and `include_inactive` parameters. Without them the
  behaviour (including the existing `include_ceased` default of `true`) is **exactly** as today, so existing tests and the Postman collection keep passing.
- In every Director table under Master Data and in the Directors view: by default hide ceased/inactive rows
  (`tr.md-ceased` / `tr.ceased`); add a toggle **"Show Historical/Ceased Directors"** (default off, remembered for the session)
  that reveals them with the existing ceased styling, **without a page reload**. Show the "Ceased on dd-mm-yyyy" badge for
  directors who resigned during the selected FY. Empty state: "No directors were active in 2024-25".
- **Acceptance:** changing the FY changes the list. Boundary cases all pass: appointed on the last day of the FY; ceased on the
  first day; ceased the day before; no end date; resigned and re-appointed (the demo data has a director resigned in 2021 and
  re-appointed in 2023).

### Step 8 — Change 6: Director navigation consolidation

- One sidebar link: **Directors**. Remove the duplicate entries from `NAV` (People & Roles: Directors & KMP Register,
  Directors (people), Board stints, Designation history, Independent-director terms, Declarations, DIR-3 KYC, Residency, Other
  directorships; and Board committees / committee members under Governance). **Auditors stay under Company.**
- Build a small reusable tab component (`tabs.js`): accessible `tablist` (arrow keys, `aria-selected`), classes `.rec-tabs`,
  `.rec-tab`, `.tab-pane`; remembers the active tab in state and in the hash. Unknown tab name → first tab. **Reuse the existing
  `.rec-tabs`/`.rec-tab` styles** from `app.css`.
- The Directors panel (`directors.js`) has sections: **Register** (default; existing register + add-director dialog, unchanged
  behaviour, with the new columns and FY filter), **DIN & KYC**, **Appointments** (board stints, designation history,
  independent-director terms), **Resignations** (stints with an end date, with reason/date), **Board Committees**,
  **Declarations & other directorships**.
- Each section reuses `mountList` from `entity.js`, so search, sort, CSV, archive and the record editor keep working.
- Inline **segment controls** above the grid: All / Active in FY / Ceased / Independent / KMP / On a committee, with counts.
  Counts must equal the number of rows shown. Filtering is client-side.
- *Optional only if it measurably simplifies loading:* a `GET /api/companies/{id}/directors-overview` helper. Skip it if
  `mountList` per section is enough.
- **Acceptance:** one "Directors" link, no duplicate children; every formerly separate record type is reachable and editable
  inside the panel; "Add director/KMP" still creates person + board stint + designation in one step.

### Step 9 — Change 7: Shareholder navigation consolidation

- One sidebar link: **Shareholders** (new `shareholders.js`) with sections: **Cap table** (shareholders joined to shareholdings:
  shares, class, **calculated** percentage), **Allotments**, **Transfers**, **Shareholders** (people/entities).
- Share classes, share capital summary and capital events move to Master Data tab 2 (Change 4); add a "Capital structure" link at
  the top of the panel that jumps there. Foreign investment (FC-GPR / FC-TRS) moves to the foreign tab (Change 8).
- **Do not compute percentages in the browser.** Read the existing calculated value (`core.v_company_shareholder_counts` /
  shareholding-percentage view exposed by `/api/calc/*`, which stays available).
- Remove the other entries from `NAV`. All eight former entries (Share classes, Share capital summary, Capital events,
  Shareholders, Shareholdings, Allotments, Share transfers, Foreign investment) must remain reachable.
- **Acceptance:** one "Shareholders" link; allotment and transfer records can be added and edited from inside the panel; cap
  table percentages match the core calculated view.

### Step 10 — Change 4: Master Data tab modularisation

- Convert the stacked `.md-card` blocks in `masterdata.js` into horizontal sub-tabs using `tabs.js`, with these **exact labels**:
  1. **General Info & Registration** — company profile (identity, CIN, registration, registered office, contact), business
     activities, group companies, auditors, RTA.
  2. **Capital Structure & Financials** — share classes, share capital summary, capital events, financials by year, holders
     summary (link to the Shareholders view).
  3. **Charges & Borrowings** — loans and deposits, ECB summary (link to the foreign tab), and the charge panel with the explicit
     empty state from D3.
  4. **Statutory Registers** — read-only registers **composed from existing data** (register of directors/KMP, register of members,
     register of loans & investments, register of contracts with related parties), plus clear placeholders for registers
     with no source table. CSV export per register.
- Every card that exists today appears in **exactly one** tab. Only one pane is visible at a time. Load a tab's data on first
  open. Keep the profile's **save-on-blur** behaviour and the "saved" tick. The active tab survives a refresh and works with
  Back (`#/company/{id}/masterdata/{tab}`).
- Fallback: an unknown saved tab opens the first tab.
- Style additions (`.md-layout` as a tab-pane container, `.tab-pane`) go in `app.css`.

### Step 11 — Change 8: ODI / ECB / DI / Foreign Investments tab

- Add a company-navigation entry with the **exact label** `ODI / ECB / DI / Foreign Investments`, a new `foreign.js` view, root
  element `#foreign-investments-tab`.
- Sections (use `mountList`): **ODI** (with step-down subsidiaries), **ECB**, **DI / Foreign investment inbound**
  (FC-GPR and FC-TRS records), and a **Summary strip** (counts, total amounts, next due date per section).
- "Add" buttons open the same generic record editor. A read-only (client) user sees the grids **without** Add buttons.
- Remove the same record types from their old sidebar groups so each record has one home.
- Tracking view only (D8): no new rules, due-date logic or activity templates.

### Step 12 — Regression, accessibility, clean-up

- Walk the whole app once as admin, manager and client. Keyboard-test the tab component and both sidebar states.
- Check the Overview page still renders its segment cards correctly after the `NAV` changes.
- Confirm `dashboard.css` checksum is unchanged.

## 6. Cross-change coding standards

- Match the existing code style of each file (indentation, naming, ES module style, type hints in Python). Do not run
  formatters over whole files.
- Reuse before writing: `mountList`, `openRecord`, `form.js` field engine, `util.js` helpers, `session()`/`readable_company()`
  on the server.
- New files only where this brief names them: `tabs.js`, `alldirectors.js`, `notifications.js`, `shareholders.js`, `foreign.js`,
  optional `app/routers/notifications.py`, optional new tests, the log, and (only if Change 9 requires it) one migration.
- New front-end modules must be imported where needed so the "every import and element id resolves" test passes.
- Comments only where intent is not obvious. No dead code, no leftover `console.log`.

## 7. Testing and end-to-end verification (mandatory)

### 7.1 Tests you must write or update

| Change | Tests |
|---|---|
| 1 | API tests for `/api/people/directors` and `/api/notifications`, **including the isolation loop**: client sees only their company; manager only their three; admin all. UI-asset test: template contains the three global links' targets; ids still resolve. |
| 2 | Assertion (static or browser) that the All Companies table has no "Filings" header, and that `GET /api/companies` still returns its existing fields; if N/A, the log evidence. Do not assert anything about other tables. |
| 3 | Element-order/ids check in `test_ui_assets.py`; layout check (see 7.3). |
| 4 | Tab labels exact; each former card present once; save-on-blur still PATCHes `company`. |
| 5 | Updated `test_meta_coverage.py` (no sidebar entry for calc, **13 views still exposed**); deep link to the removed view falls back without error. |
| 6 | Coverage test updated to count tables reachable through the Directors panel; segment-count logic. |
| 7 | API test that cap-table percentages equal the core calculated view. |
| 8 | Coverage test; read-only role has no Add buttons. |
| 9 | Register payload contains address/phone; round-trip test picks up new columns automatically. |
| 10 | **Table-driven** API tests of the FY predicate with the boundary dates in Change 10; default behaviour without the new params unchanged. |

When you must change an existing test (navigation and coverage tests for Changes 5, 6, 7, 8), change **only the expectation
that the client changed**, and write the reason in the log. Never delete or weaken a test just to make it pass; never touch
`test_isolation.py` assertions except to add the new endpoints.

### 7.2 Run everything — the definition of "done"

Run these and record the **actual output** in the log:

```bash
# 1. Full suite (database + web). Must be green. Baseline was 307; the final number should be 307 + your new tests.
python -m pytest

# 2. Web tests only, then database tests only (to localise any failure)
python -m pytest tests/api
python -m pytest tests --ignore=tests/api

# 3. Requirement traceability (exit code must be 0)
python scripts/check_traceability.py

# 4. Frozen theme check
sha256sum app/static/stylesheets/dashboard.css     # must equal the Phase A checksum

# 5. JavaScript syntax of every module (also covered by test_ui_assets)
for f in app/static/scripts/*.js; do node --check "$f" || echo "FAIL $f"; done
```

If you added a migration: `python scripts/setup_db.py` must apply it cleanly on a fresh database
(`python scripts/setup_db.py --reset --seed`, development database only), and the whole suite must still pass afterwards.

### 7.3 Run the application end to end

1. Start the app: `python scripts/run_server.py` (default `http://127.0.0.1:8000`). Confirm `GET /api/health` returns
   `{"status":"ok","database":true,...}`.
2. Exercise the UI. Prefer an **automated browser smoke test** (Playwright) kept in its own folder (for example
   `tests/ui/`) that **does not run by default** and does not break `python -m pytest` on a machine without a browser; add a
   short `README` line on how to run it. If Playwright cannot be installed in the environment, say so in the log and instead
   verify through HTTP requests (curl or `httpx`: sign in, read `/`, call each new and changed endpoint, check HTML for the
   expected ids/labels) plus a precise **manual UAT checklist** (section 9). Do not pretend a browser test ran when it did not.
3. Whatever method is used, the checks to cover are: sidebar in both states; hash links and back button; top-bar layout at
   1280 / 1920 / 1024 px; Master Data four tabs and save-on-blur; no "Calculated Values" text; Directors panel segments, FY toggle
   and the new columns (200-character address test); Shareholders cap table; the foreign tab with and without Add buttons;
   export (Excel/JSON) still downloads; sign-in, sign-out and change-password still work; client user is read-only.
4. Optionally run the Postman collection with Newman (`docs/postman/…`) if Node/Newman is available. It is expected to still
   pass because API defaults are unchanged. Add requests for the new endpoints only if cheap.

### 7.4 If something fails

Fix the **cause in your change**, not the test. If a pre-existing test fails because the client's change legitimately altered the
behaviour, update that expectation narrowly and log it. If you cannot make the suite green, **do not** declare completion:
write the blocker, evidence and your best diagnosis in the log and stop.

## 8. The log file — `docs/UI_CHANGES_LOG.md`

Keep it current as you go (append after every change; do not write it all at the end). Use exactly this structure:

```markdown
# UI Changes — Implementation Log
Branch: <name> | Started: <date/time> | Author: <LLM/agent name>

## 1. Environment & baseline
- OS / Python / Node / PostgreSQL versions
- Baseline `python -m pytest` result: <exact line>
- dashboard.css sha256 (before): <hash>
- Inventory findings (search commands + results)

## 2. Plan
<per change: files expected, approach, tests>

## 3. Assumptions & decisions
| # | Item | Assumption / decision | Reason | Needs client/BMP confirmation? |

## 4. Change-by-change record
### Change N — <title>   (status: Done | N/A | Blocked | Partial)
- What was done (2–5 lines)
- Files changed (path — added/modified/deleted — one-line reason)
- Tests added/updated (and why any existing test was altered)
- Commands run and results (paste the key output lines)
- Acceptance criteria: each ✔ / ✘ with evidence
- Commit: <hash> <message>

## 5. Database / API changes
- New endpoints, new query params, migrations (flag "needs BMP approval"), contract impact: none / describe

## 6. Final verification
- Full `python -m pytest` result: <exact line>
- tests/api, database tests, traceability, node --check: results
- dashboard.css sha256 (after) — identical? yes/no
- Application run: server start, health check, UI/HTTP checks performed, with results
- Newman/Postman result (if run)

## 7. Where things moved (release note)
| Old location | New location |
(e.g., "Calculated Values → shareholding % in Shareholders; ages/tenure in Directors; attendance rate in Meetings; overdue days in Activities/Notifications")

## 8. Observations (not changed)
<problems noticed but deliberately left alone>

## 9. Open items for the team
```

Log writing rules: be factual and specific; include real command output; include failures and how you fixed them;
never write "should work" — write what you ran and saw.

## 9. Hand-over deliverables

Besides the code, leave in the repository:

1. `docs/UI_CHANGES_LOG.md` (complete).
2. A one-page **UAT checklist** (one line per change, with a pass/fail column) — in the log or as `docs/UI_UAT_CHECKLIST.md`.
3. New/updated tests, all green.
4. A **final chat summary** (max ~15 lines): changes done / N/A / partial, tests result (exact numbers), anything that needs BMP
   approval (especially a migration), and open questions.

Do **not** push to a remote, deploy, or merge to the main branch unless explicitly told to; stop at a clean, committed working
branch.

## 10. Stop-and-report conditions

Stop and report (in the log and in your final message) instead of improvising, if:

- the baseline test suite is red before you start;
- a change would require editing `dashboard.css`, an approved migration (001–011), or an approved seed;
- a change would break an existing API contract;
- the real repository structure differs so much from this brief that the described approach cannot be applied;
- any isolation/security test fails and you cannot fix it inside your own change.

## 11. Definition of done (checklist)

- [ ] Baseline recorded; branch created
- [ ] Changes 1–10 each marked Done / N/A (with evidence) in the log
- [ ] `dashboard.css` byte-identical (checksum matches)
- [ ] No migration 001–011 or existing seed edited; any new migration flagged "needs BMP approval"
- [ ] Existing API behaviour unchanged by default; Postman collection still valid
- [ ] `python -m pytest` fully green (baseline 307 + new tests); `check_traceability.py` exit 0; every JS module passes `node --check`
- [ ] App starts, `/api/health` ok, end-to-end checks performed as admin, manager and client
- [ ] Log complete, release note and UAT checklist written
- [ ] Nothing changed beyond what the 10 changes required