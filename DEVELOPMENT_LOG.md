# Development Log: Minutes & Meetings Dashboard

## Status board
- Current phase: 7: complete
- Last updated: 2026-10-26
- Overall: complete (see Final summary and Deferred)
- Blocked on: nothing

## Decisions (from the user and by default)
| # | Question / decision | Answer / choice | Date | Source (user / default) |
|---|---|---|---|---|
| D1 | Repo root for this work | `C:\Users\91953\Documents\bmp_deploy` (the enclosing git repo is the user's home dir; nothing here is tracked yet) | 2026-10-26 | default |
| D2 | Test runner | `venv\Scripts\python.exe -m pytest` (existing suite, needs local Postgres which is running) | 2026-10-26 | default |
| Q1 | Where do the NO-HOME fields live? | (a) Additive migration of nullable columns. SQL drafted at `db/proposed/012_minutes_meetings_fields.sql`; **not run, not in db/migrations/** until the user approves the draft | 2026-10-26 | user |
| Q2 | Minutes status | Stored in the same migration as `meeting.minutes_status` (CHECK of the 5 values); `meeting.status` untouched | 2026-10-26 | user (via Q1) |
| Q3 | Committee row missing | Add is disabled with a message; no auto-create | 2026-10-26 | user |
| Q4 | Circulation mode | Dropped. Modes: Physical, Video conferencing, OAVM | 2026-10-26 | user |
| Q5 | Keep activities.js, activity-form.js, /activities/*, /confirmations/* | Yes, keep; remove only act-* views, activities-main.js, activities_dashboard.html, /activity-board/*, and their tests. Duplicated dev seed data left untouched | 2026-10-26 | user |
| D3 | OAVM / Video conferencing mode mapping | Physical->PHYSICAL, Video conferencing->VC, OAVM->VC (lossy: read-back shows "Video conferencing" for both). Not asked; user can say if they want an `OAVM` lookup row | 2026-10-26 | default |
| D4 | Total/Present typed values | Stored in `attendance_present`/`attendance_total` (in the draft migration) so "remain editable" holds | 2026-10-26 | default |

## Schema gaps
| UI field | Needed storage | Resolution (migration approved / JSON / dropped / pending) | Notes |
|---|---|---|---|
| Date of notice | nullable date on meeting | migration approved and applied (012, 013) | `meeting.due_date` is the AGM statutory due date, a different thing |
| Time end / start | `meeting.start_time`, `meeting.end_time` exist | **no gap** | legacy text "11:00 AM to 12:00 PM" is derived |
| Chairman (free text) | text | migration approved and applied (012, 013) | `chairperson_directorship_id` only holds a director; free text of a non-director has no home |
| Invitees present (names) | text | migration approved and applied (012, 013) | `meeting_attendance` rows of type `invitee` have no name column |
| Leave of absence | text | migration approved and applied (012, 013) | |
| Minutes status | text/enum | pending (needs Q2) | `meeting.status` is planned/held/cancelled, not overloaded |
| Draft circulated / signed circulated dates | 2 dates | migration approved and applied (012, 013) | needed for the `draft` compliance check |
| Attendance sheet, Signed documents | text | migration approved and applied (012, 013) | |
| Date of entry, Date of signing, Place of signing | 2 dates + text | migration approved and applied (012, 013) | needed for the `minutes` compliance check |
| Total (board size) | int | derived | roster size / attendance rows; no column |
| Meeting-level comments | `meeting.remarks` | **no gap** (use `remarks`) | |
| Agenda: Reg 30 flag, Forms filed, Documents to check, BMP comments | per agenda item | migration approved and applied (012, 013) | `meeting_agenda_item` has only `item_no`, `text`. `government_filing` is company/FY scoped with no meeting or agenda link, so it cannot hold per-item forms |

## Field-mapping table
| UI field | Stored in | Type | Status | Notes |
|---|---|---|---|---|
| meeting_date | core.meeting.meeting_date | date | exists | FY derived from it; `meeting.financial_year` is NOT NULL so the service must set it from the date |
| register / meeting type | core.meeting.meeting_type_id (+ committee_id) | fk | exists | board->BOARD, agm->AGM, egm->EGM, committees->COMMITTEE + `committee_id` by name |
| mode | core.meeting.venue_mode_id | fk | exists (lossy) | **repo values are PHYSICAL / VC / MIX, not HYBRID.** "Video conferencing" and "OAVM" both map to VC, so the two cannot be told apart on read-back |
| meeting_time | core.meeting.start_time, end_time | time | derived | formatted "hh:mm AM to hh:mm PM" |
| notice_date | none | date | NO HOME | |
| chairman | core.meeting.chairperson_directorship_id | fk | partial | only when the name matches a roster director |
| directors_present | core.meeting_attendance (attendee_type='director', attended) | bool rows | derived | names from director.full_name |
| attendance[] | core.meeting_attendance.directorship_id, attended, mode | rows | exists | no unique constraint on (meeting_id, directorship_id): the service must prevent double rows (existing PUT attendance does an upsert-by-lookup) |
| attendance_present | count of attended rows | int | derived | |
| attendance_total | roster size on the date | int | derived | typed override has no home |
| invitees_present | none (names) | text | NO HOME | |
| leave_of_absence | none | text | NO HOME | |
| minutes_status | none | enum | NO HOME | |
| draft_circulated, signed_circulated | none | date | NO HOME | |
| attendance_sheet | none | text | NO HOME | |
| entry_date, signing_date, signing_place | none | date/text | NO HOME | |
| signed_documents | none | text | NO HOME | |
| agenda.text | core.meeting_agenda_item.text | text | exists | `item_no` int; no unique constraint on (meeting_id, item_no) |
| agenda.reg30 / forms / docs / comments | none | | NO HOME | |
| comments (meeting level) | core.meeting.remarks | text | exists | |
| updated_at (optimistic lock) | core.meeting.updated_at | timestamptz | exists | check how other flows send it (see below) |

## Discovery findings (2026-10-26)
**Stack.** FastAPI, psycopg3 with raw SQL (dict_row), `psycopg_pool`. Routers in `app/routers/*.py`, registered in a tuple in `app/main.py` with prefix `/api`. A new `minutes_api.py` goes there. Jinja templates in `app/templates`, static in `app/static`. CSP is `script-src 'self'`.

**Auth / access.** `deps.current_user` -> `UserCtx` (`.access {company_id: level}`, `.readable`, `.writable`, `.is_admin`). Helpers `readable_company(ctx, id)` (404 if no access) and `writable_company(ctx, id)` (403 if read-only, 404 if none). CSRF checked for non-GET inside `current_user`. Transaction helper `deps.session(request, ctx, readonly=)` which calls `Database.tx(user_id)` and sets `app.current_user_id` with `set_config(..., true)`. Error type `errors.ApiError(status, code, message, fields)` -> envelope `{error:{code,message,fields}}`. Success helper `responses.ok`.

**Entity registry.** `meeting`, `meeting_agenda_item`, `meeting_attendance`, `committee`, `committee_member`, `document`, `evidence_link`, `government_filing` are all registered entities (`app/registry.py`). Generic `/entities/{key}` CRUD and `POST /entities/{key}/{pk}/archive` exist and the engine (`app.state.engine`: `get/create/update/set_archived`) is what the existing `PUT /meetings/{id}/attendance` uses. So archive can reuse `/entities/meeting/{id}/archive`.

**Existing meeting routes (`app/routers/meetings.py`).** They do NOT match the names in the spec:
- `GET /api/companies/{id}/meetings-book?fy=` -> `{meetings:[{...meeting columns, meeting_type, meeting_type_code, venue_mode, committee, chairperson, agenda:[{id,meeting_id,item_no,text}], attendance:[{id,attendee_type,directorship_id,shareholder_id,attended,mode,name}]}]}`
- `GET /api/meetings/{id}/detail` -> `{meeting:{..., roster:[{directorship_id, full_name, designation}], documents:[...]}}`
- `PUT /api/meetings/{id}/attendance` body `{rows:[{directorship_id, attended, mode}]}` -> `{saved, attended}` (upsert, never deletes).
There is no `GET /meetings`. These are used by the existing Database Dashboard `meetings.js` and stay untouched.

**Years.** `GET /api/companies/{id}/years` -> `{years:["2025-26", ...] (desc), current:"2025-26"}`. Years come from any table that has records, plus "current" is offered even if empty.

**Files.** Excel is returned with `starlette.responses.Response(bytes, media_type=xlsx, headers={"Content-Disposition": 'attachment; filename="..."'})` (see `companies.export_xlsx`). `openpyxl` already in requirements. **PyMuPDF is not in requirements.txt and not installed in the venv** (`import fitz` fails). Must add `PyMuPDF` to requirements and install it (needs the user's OK to install a package? it is a normal dependency named by the spec; will log the command when run).

**Frontend.** `api.js` matches the spec (`post(path, body, params)`, `put(path, body)`, `upload(path, form)`, `download(path, params, fallback)`, `ApiError`). `util.js` already has `fyWindow`, `wireDropzone`, `fmtDate`, `fmtTime`, `esc`, `toast`. `state.js` has `canWriteCompany`, `company`. CSS: all the `.meet-*`, `.ss-*`, `.dir-*`, `.ag-*`, `.file-drop` classes already exist in `dashboard.css`; `.topbar-fy` in `app.css`. Launcher card is in `app/templates/dashboard.html` (`#goActivities` -> `/activities-dashboard`). Route in `main.py`: `/activities-dashboard`.

**Database (read-only inspection).**
- `MEETING_TYPE` values: BOARD, COMMITTEE, AGM, EGM, CLASS_MEETING, NCLT, REQUISITIONED, POSTAL_BALLOT. `MEETING_VENUE_MODE`: PHYSICAL, VC, MIX.
- Committees are rows in `core.committee` by company and name; the generic type is COMMITTEE. Seeded: only "Audit Committee" for BrightMed (company 2).
- **Seed data is duplicated in the live DB** (seed apparently ran twice): meetings 1-4 and 6-9 are identical copies; committee ids 1 and 2 are both "Audit Committee" for company 2. Register->committee resolution must tolerate duplicate names (choose lowest id, log it). I did not touch the data.
- Seeded meetings: BrightMed (2): 3 board + 1 AGM, all FY **2024-25**, duplicated; Nexatech (1): 1 board 2025-04-15 (FY 2025-26, planned), duplicated. So Phase 1 acceptance data is FY 2024-25 for BrightMed, not 2025-26.
- No unique constraint on `(meeting_id, directorship_id)` or `(meeting_id, item_no)`; the service must enforce them.
- `audit.log` exists (541 rows) and is written by triggers.

**Baseline tests.** `venv\Scripts\python.exe -m pytest -q --ignore=tests/ui` -> **385 passed, 1 skipped** (69 s) before any change.

### Removal scope, corrected by grep (differs from spec section 4)
| Item | Finding | Decision |
|---|---|---|
| `act-overview/catalogue/running/tasks/run/start.js`, `act-util.js`, `activities-main.js`, `activities_dashboard.html` | Only imported by each other / `activities-main.js` and the `/activities-dashboard` route. `tests/api/test_ui_assets.py:57` whitelists `activities-main.js`. `act-util.js` is imported only by `act-*` files | remove (update the asset test) |
| `activities.js`, `activity-form.js` | **`main.js:19` imports `activities.js`** (Database Dashboard "Activities" company view, sidebar chip, line 262); `activities.js` imports `activity-form.js` | **keep** (spec: delete only if nothing else uses them) |
| `/activity-board/*` routes + `tests/test_activity_board.py` | Only used by the removed dashboard | remove (test file also removes its `/activities/instances` check at the end, which is a separate concern; will keep that one assertion by moving it) |
| `/activities/*`, `/confirmations/*` routes | Used by `activities.js` (kept) and by `tests/api/test_workflows.py`, `test_ui_changes.py`, `test_isolation.py`, `tests/test_activity_board.py` | **keep** |
| `app.css` blocks `.task-*`, `.bind-*`, `.att-*` | `grep` needed in `activities.js` before removal (it is kept and may use `.task-*`) | decide in Phase 6 after grep |

## Work log (newest first)
### 2026-10-26 Frontend built, old Activities dashboard removed, suite green
- **Phase:** 2, 3, 4, 5, 6, 7
- **Action:** Built the Minutes & Meetings UI; removed the Activities dashboard pieces agreed in Q5; ran browser checks on a throwaway database; ran the full suite.
- **Files created:** `app/templates/minutes_dashboard.html`; `app/static/scripts/minutes-main.js`, `min-api.js`, `min-register.js`, `min-form.js`, `min-compliance.js`, `min-upload.js`. **Modified:** `app/main.py` (route `/minutes-dashboard`, removed `/activities-dashboard` and the `activity_board` router), `app/templates/dashboard.html` (launcher card now "Minutes & Meetings" with the requested text), `tests/api/test_ui_assets.py` (whitelist `minutes-main.js` instead of `activities-main.js`), `tests/api/test_minutes_api.py` (archives what it creates). **Deleted:** `act-overview/catalogue/running/tasks/run/start/util.js`, `activities-main.js`, `activities_dashboard.html`, `app/routers/activity_board.py`, `tests/test_activity_board.py`.
- **Commands:** `grep -rn "activity-board|act-util|act-(overview|catalogue|running|tasks|run|start)|activities-main|activities_dashboard|activities-dashboard|startActivityModal|activity_board|window.__state"` over `app tests scripts` -> no matches. `pytest -q --ignore=tests/ui` -> **406 passed, 1 skipped** (baseline was 385 + 1 skipped; +21 new tests).
- **Browser check** (throwaway DB `bmp_ui_check` built from migrations + seed, server on 127.0.0.1:8765, test accounts from the test suite; DB dropped and server stopped afterwards): admin: 8 sidebar entries, counts chips (board 3, AGM 1), FY switch re-renders, compliance chips, Add -> roster loads for the date -> "+ All present" ticks 4 and sets Present/Total 4/4 -> adding an agenda row keeps typed text -> Save -> card appears and count goes to 4; Edit -> panel prefilled -> status Signed saved; Archive -> card gone, count 3; upload of a generated .docx filled date, time, signing date/place, 3 agenda items, ticked 2 matched directors, listed "Outside Person" as to verify, and left an unrelated typed comment alone; NRC register shows the "no committee constituted" warning with Add disabled. Read-only client: sees only Nexatech, no Add/Edit/Archive buttons, Download Excel present. The only console error was a 401 from my own logout call.
- **Result:** All eight registers work end to end.
- **Next:** Final summary below.

### 2026-10-26 Backend complete: parser, compliance, Excel, service, router
- **Phase:** 1, 3, 4, 5 (backend halves)
- **Action:** Added PyMuPDF to `requirements.txt` and installed it (version resolved by pip is PyMuPDF 2.x; module imported as `pymupdf`, falling back to `fitz`). Built the pure modules and the API.
- **Files:** created `app/minutes_extract.py` (parser), `app/minutes_compliance.py` (SS-1/SS-2 checks + the 8 register definitions), `app/minutes_excel.py`, `app/minutes_service.py` (all field-to-column mapping: `MEETING_COLUMNS`, `MODE_TO_CODE`, `_legacy`), `app/routers/minutes_api.py`, `tests/test_minutes_extract.py`, `tests/test_minutes_pure.py`, `tests/api/test_minutes_api.py`. Modified `app/main.py` (router registered; `/minutes/parse` exempted from the 2 MB body cap, the route enforces its own 10 MB cap), `requirements.txt`.
- **Commands:** `pytest tests/test_minutes_extract.py tests/test_minutes_pure.py -q` -> 19 passed. `pytest tests/api/test_minutes_api.py -q` -> 12 passed (72 s).
- **Result:** Endpoints under `/api/minutes`: `registers`, `counts`, `roster`, `export.xlsx`, `parse`, `{register}` GET/POST, `{register}/{id}` PUT. Writes go through the entity engine (access checks, stale-save 409, audit trigger with actor); agenda is updated by id and removed rows are archived; attendance is one row per director; FY comes from the meeting date; committee registers resolve the committee by name pattern (lowest id when a company has duplicates) and return 409 `no_committee` when absent; lookup ids are resolved by code, not hard-coded. Archive uses the existing `POST /entities/meeting/{id}/archive`.
- **Notes / deviations:** (1) a bug I introduced while editing (a stray backspace character in a regex) was found by a failing test and removed. (2) Committee names are matched by keyword (`audit`, `nominat|remunerat`, ...) rather than exact name because companies word them differently. (3) A PUT takes `company_id` from the query string or the body.
- **Next:** Frontend (shell, routing, register view, form, upload), then removal of the Activities dashboard.

### 2026-10-26 Migration 013 applied; suite green again
- **Phase:** 0
- **Action:** User replied "ok" to the 013 proposal; applied `db/migrations/013_minutes_status_check_form.sql` via `run_migrations()`.
- **Commands:** `[run ] 013 ... OK`; `pytest -q --ignore=tests/ui` -> 385 passed, 1 skipped.
- **Result:** Schema work complete (012 + 013, additive only). Phase 0 accepted.
- **Next:** Phase 1 backend read path; parser and compliance engine as pure modules.

### 2026-10-26 Migration 012 applied; one existing test fails
- **Phase:** 0
- **Action:** User approved the draft. Moved it to `db/migrations/012_minutes_meetings_fields.sql` and applied it through `scripts/setup_db.py` `run_migrations()` (only pending migration ran).
- **Commands:** `run_migrations()` -> `[run ] 012_minutes_meetings_fields.sql ... OK`; then `pytest -q --ignore=tests/ui` -> **1 failed, 384 passed, 1 skipped**.
- **Result:** Failure is `tests/api/test_roundtrip_all_fields.py::test_every_field_round_trips[meeting]`: it sends `choices[0]` for `minutes_status`, but my CHECK is written `IS NULL OR ... IN (...)`, which the metadata reader does not turn into dropdown choices, so the test sends an invalid string. Cause is my constraint wording, not the app.
- **Proposed fix (NOT applied, needs user OK because it is a second schema change):** `013_minutes_status_check_form.sql` drops and re-adds `meeting_minutes_status_check` as plain `CHECK (minutes_status IN (...))`, same values. The user approved only 012's draft, so an auto-mode guard blocked me from running 013. Waiting.
- **Next:** Await decision on 013; meanwhile build parser, compliance, Excel.

### 2026-10-26 Answers received; migration drafted (not applied)
- **Phase:** 0
- **Action:** Logged Q1-Q5 answers. Drafted an additive migration with 14 nullable columns on `core.meeting` and 4 on `core.meeting_agenda_item`. Put it in `db/proposed/` on purpose: `scripts/setup_db.py` applies every `db/migrations/*.sql`, so it must not sit there before approval.
- **Files:** created `db/proposed/012_minutes_meetings_fields.sql`
- **Commands:** none against the DB.
- **Result:** Nothing in the database changed. Note: adding columns will affect `tests/api/test_meta_coverage.py` / `test_roundtrip_all_fields.py` style tests and `docs/DATA_DICTIONARY.md`; I will run them after approval and update docs only.
- **Next:** Ask the user to approve the SQL. Meanwhile build `minutes_extract.py` + tests (pure), the compliance engine, and the Excel builder.

### 2026-10-26 Discovery complete; questions prepared
- **Phase:** 0
- **Action:** Read backend core (`main`, `deps`, `access`, `db`, `errors`, `responses`, `registry`), routers `meetings`, `views`, `companies`, `activity_board`; migrations 006-008; seeds; frontend `api/state/util/meetings/activities-main`, shell HTML, CSS. Queried the dev DB read-only (SELECTs). Ran the baseline test suite.
- **Files:** modified `DEVELOPMENT_LOG.md` only. A throwaway script `peek.py` lived in the OS temp dir (read-only SELECTs, no secrets printed).
- **Commands:** `venv\Scripts\python.exe -m pytest -q -x --ignore=tests/ui` -> 385 passed, 1 skipped. `python -c "import fitz"` -> ModuleNotFoundError.
- **Result:** Checklist 3.3 complete except "files to delete with grep" which is above and corrects the spec (keep `activities.js`, `activity-form.js`, `/activities/*`, `/confirmations/*`).
- **Next:** Ask the Section 5 questions in one message. Unblocked work meanwhile: Phase 1 read path, parser, compliance engine, Excel builder.

### 2026-10-26 Log created
- **Phase:** 0
- **Action:** Created this log as the first action.
- **Files:** created `DEVELOPMENT_LOG.md`
- **Commands:** none
- **Result:** Log exists.
- **Next:** Discovery.

## Open questions asked of the user (2026-10-26) - ANSWERED, see Decisions
1. Schema gaps: approve an additive migration (nullable columns), store in `document.extracted_data` on the minutes document, or drop? (recommendation below)
2. Minutes status storage.
3. Missing committee rows: auto-create (admin, confirm) or disable Add.
4. Circulation mode: drop or give a tab.
5. (new) Mode mapping: OAVM and Video conferencing both map to VC. Accept the loss, or add `OAVM` to the lookup list (data row, not schema)?
6. (new) Remove-scope correction: keep `activities.js`, `activity-form.js`, `/activities/*`, `/confirmations/*` because the Database Dashboard uses them. OK?

## Verification record
| Check | Command / method | Result | Date |
|---|---|---|---|
| Full suite after all changes | `venv\Scripts\python.exe -m pytest -q --ignore=tests/ui` | 406 passed, 1 skipped | 2026-10-26 |
| Parser unit tests | `pytest tests/test_minutes_extract.py` | 10 passed | 2026-10-26 |
| Compliance + Excel unit tests | `pytest tests/test_minutes_pure.py` | 9 passed | 2026-10-26 |
| API/security/audit/FY boundary/Excel/parse | `pytest tests/api/test_minutes_api.py` | 12 passed | 2026-10-26 |
| JS syntax | `node --check` on each new module (copied to .mjs) | ok | 2026-10-26 |
| Browser walkthrough | throwaway DB + local server, see Work log | passed | 2026-10-26 |
| Baseline test suite | `venv\Scripts\python.exe -m pytest -q -x --ignore=tests/ui` | 385 passed, 1 skipped | 2026-10-26 |
| PyMuPDF present | `venv\Scripts\python.exe -c "import fitz"` | ModuleNotFoundError | 2026-10-26 |

## Removed code (with grep evidence)
| File / route | Evidence nothing else used it | Date |
|---|---|---|
| `act-overview.js`, `act-catalogue.js`, `act-running.js`, `act-tasks.js`, `act-run.js`, `act-start.js` | Imported only by each other and by `activities-main.js` (grep over `app/`) | 2026-10-26 |
| `act-util.js` | Imported only by the `act-*` files above | 2026-10-26 |
| `activities-main.js`, `templates/activities_dashboard.html`, route `/activities-dashboard` | Only the launcher card linked to it (now points to `/minutes-dashboard`); `test_ui_assets` whitelist updated | 2026-10-26 |
| `/api/activity-board/*` (`routers/activity_board.py`) and `tests/test_activity_board.py` | Called only by the removed `act-*` views and that test file | 2026-10-26 |
| **Kept on purpose:** `activities.js`, `activity-form.js`, `/activities/*`, `/confirmations/*` | `main.js:19` imports `activities.js` (Database Dashboard Activities view); routes used by it and by `test_workflows`, `test_ui_changes`, `test_isolation` | 2026-10-26 |
| **Kept on purpose:** `app.css` `.task-*`, `.bind-*`, `.att-*` blocks | still used by `activities.js` (task cards, bind chips) and `notifications.js` / `overview.js` (`.att-*`) | 2026-10-26 |

## Deferred / known limitations
- Attaching the uploaded minutes file to the saved meeting (document + evidence_link) is **deferred**. `POST /documents/upload` and the Database Dashboard's "Attach document" already do it for a saved meeting; wiring it into this flow was optional in the brief and is not done. The parse endpoint stores nothing.
- OAVM and Video conferencing both save as VC (D3); read-back shows "Video conferencing". `MIX` meetings entered elsewhere show as "Mix of both".
- Dev DB `bmp` still has the duplicated seed rows noticed in discovery (meetings and the Audit Committee twice). Not touched. Duplicate Audit Committee rows are tolerated (lowest id used; both count for the register).
- `tests/ui` (Playwright, `BMP_UI_TESTS=1`) was not run; it needs Playwright and Chrome and none of it references the removed dashboard. `docs/` (guide, Postman collection) still mention `/activity-board`; not edited.
- `docs/DATA_DICTIONARY.md` / `docs/FIELD_TRACEABILITY.md` not updated for the 18 new columns (traceability test passes).
- Quorum uses ticked directors, else typed Present; "Total" for a meeting with no typed total is the number of attendance rows.
- Default financial year is the current one (2026-27 today), so seeded meetings (FY 2024-25) appear after choosing that year.
- Compliance: `board_register` is a hard date check on `directorship` start/end of ticked directors.

## Final summary
**Built:** a Minutes & Meetings dashboard at `/minutes-dashboard` (launcher card updated): eight registers (Board, Audit, NRC, SRC, CSR, RMC, AGM, EGM) each with list cards, add / edit / archive, roster-based attendance, upload-to-autofill from Word/PDF, Secretarial Standards chips, and Excel download. Backend `/api/minutes/*` (`minutes_api.py`, `minutes_service.py`, `minutes_compliance.py`, `minutes_excel.py`, `minutes_extract.py`). Migrations `012` and `013` (additive nullable columns, approved) hold the fields that had no home.
**Removed:** the old Activities dashboard page, its views, `/activity-board/*`, and the test for it. The activity/ops schemas, `/activities/*`, `/confirmations/*`, `activities.js` were kept (still used by the Database Dashboard).
**Run:** `venv\Scripts\python.exe scripts/run_server.py`, sign in, open the launcher and choose Minutes & Meetings. After pulling this change run `python scripts/setup_db.py` to apply 012 and 013, and `pip install -r requirements.txt` for PyMuPDF.
**Test:** `venv\Scripts\python.exe -m pytest -q --ignore=tests/ui` (406 passed, 1 skipped).
