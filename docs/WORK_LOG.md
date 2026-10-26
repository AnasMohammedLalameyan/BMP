# Work log: BMP Compliance Platform

## Status board (keep this block current; edit in place)
| Milestone | Status (not started / in progress / done / blocked) | Last updated | Notes |
|---|---|---|---|
| A0 Recon | done | 2026-10-20 | Reconnaissance complete. All VERIFY items resolved. |
| A1 Board API, launcher, shell | in progress | 2026-10-20 | Building Activity Board API, launcher markup/CSS/JS, activities shell |
| A2 Read-only board | not started | | |
| A3 Run an activity | not started | | |
| A4 Task data capture | not started | | |
| A5 Tests, docs, hand-over | not started | | |
| Part B (AI) | done, waiting for review (adapted to the meetings registers) | 2026-10-26 | see B0 entry |
| R Rename Minutes & Meetings -> Activities Dashboard | done | 2026-10-26 | |
| B0 Recon (repo vs this prompt) | done | 2026-10-26 | finding: the standalone task-engine screens named in the prompt no longer exist |
| B1 Foundation (deps, settings, LLM client, status, UI switch) | done | 2026-10-26 | |
| B2 Read a document -> suggest meeting fields (adapted) | done | 2026-10-26 | |
| B3 Describe a meeting -> prefill Add meeting (adapted) | done | 2026-10-26 | |
| B4 Draft and send a meeting notice (adapted) | done | 2026-10-26 | sandbox mail only |
| B5 Ask a question with citations | done | 2026-10-26 | |
| B6 Tests, docs, hand-over | done, waiting for review | 2026-10-26 | |

## Open items (VERIFY list, questions, blockers). Move to Resolved when closed
- ~~QUESTION (blocks B2-B5 UI):~~ ANSWERED 2026-10-26 - mount the AI in the meetings registers of this dashboard (option 1). Original text: see the B0 entry: where should the AI elements mount, given that the dashboard now named "Activities Dashboard" is the meetings-registers dashboard and has no task cards, start dialog or notice steps?

## Resolved items
- [x] VERIFY: form.js, companies.js, registry.py, the router that serves dashboard.html, and core.company(id, name, is_archived) - Confirmed. dashboard.html is served in app/main.py at `@app.get("/", include_in_schema=False)` returning `templates.TemplateResponse(request, "dashboard.html", {"version": VERSION})`. core.company exists with id, name, is_archived, cin, pan, etc.
- [x] VERIFY: Exact router prefix and router inclusion for activities.router - In app/main.py, routers are included in a loop with `prefix="/api"`.
- [x] VERIFY: board_meeting_recipe.txt query results from dev db - Executed query and output saved to `docs/notes/board_meeting_recipe.txt`.
- [x] VERIFY: ops.instantiate_activity definition and row_filter/task_record_link behavior - Read `ops.instantiate_activity` in `db/migrations/009_activity_and_ops.sql`. It creates `activity_instance` and `task_instance` records with calculated due dates based on anchor params. `task_record_link` rows are created during workflow operations. Currently no non-null `row_filter` values exist in `step_data_binding`.
- [x] VERIFY: real signatures of fieldHTML, collect, hydrateFk, showErrors, clearErrors in form.js - Confirmed: `fieldHTML(entityKey, col, row, opts = {})`, `collect(root, original)`, `hydrateFk(root, companyId)`, `showErrors(root, fields)`, `clearErrors(root)`.

## Decisions and deviations from the prompt
- None so far.

## Entries (newest at the bottom)
### 2026-10-20 12:46  Milestone A0, step 4.0 (Initialization and Reconnaissance Start)
- Did: Verified baseline test suite with `.\venv\Scripts\python.exe -m pytest` (368 passed, 1 skipped). Initialized `docs/WORK_LOG.md`.
- Files: docs/WORK_LOG.md (new)
- Commands and results: `.\venv\Scripts\python.exe -m pytest` -> 368 passed, 1 skipped.
- Not done / problems: None.
- Next step: Milestone A0 step 1 & 2: inspect router files, JavaScript modules, database schema and queries.

### 2026-10-20 12:51  Milestone A0 completion
- Did: Reviewed app/main.py, app/registry.py, app/routers/activities.py, app/access.py, app/deps.py, app/static/scripts/(form.js, companies.js, main.js, state.js, api.js, util.js, entity.js, documents.js), tests/conftest.py, tests/api/conftest.py. Executed recipe query and wrote output to docs/notes/board_meeting_recipe.txt. Read `ops.instantiate_activity` and checked row_filter/task_record_link patterns.
- Files: docs/notes/board_meeting_recipe.txt (new), docs/WORK_LOG.md (updated)
- Commands and results: Executed SQL query for BOARD_MEETING recipe (saved 40 rows to docs/notes/board_meeting_recipe.txt).
- Not done / problems: None.
- Next step: Begin Milestone A1: Create `app/routers/activity_board.py`, register router and `/activities-dashboard` route in `app/main.py`, update `dashboard.html`, append styles to `app.css`, update `main.js`, create `activities_dashboard.html`, `activities-main.js`, and stub views (`act-overview.js`, `act-catalogue.js`, `act-running.js`, `act-tasks.js`, `act-run.js`, `act-start.js`, `act-util.js`).

### 2026-10-26 11:55  Step R (rename), done
- Did: Renamed the second dashboard from "Minutes & Meetings" to "Activities Dashboard". Searched the repo first (case-insensitive, all spellings). Renamed identifiers to the Part A target names: template `minutes_dashboard.html` -> `activities_dashboard.html`; route `/minutes-dashboard` -> `/activities-dashboard` (no redirect, old route now 404); `minutes-main.js` -> `activities-main.js`; `min-api/register/form/compliance/upload.js` -> `act-api/register/form/compliance/upload.js` (imports updated); launcher card id `goMinutes` -> `goActivities`, title "Activities Dashboard"; page `<title>`, top-bar brand, sidebar brand, crumb and heading; docstrings of the new modules; `tests/api/test_ui_assets.py` whitelist. The launcher card's description text was left as is (it describes the content, not the name).
- Files: app/templates/activities_dashboard.html (renamed+edited), app/static/scripts/activities-main.js and act-api.js, act-register.js, act-form.js, act-compliance.js, act-upload.js (renamed+edited), app/main.py, app/templates/dashboard.html, app/routers/minutes_api.py (docstring), app/minutes_service.py (docstring), tests/api/test_ui_assets.py, tests/api/test_minutes_api.py (docstring), DEVELOPMENT_LOG.md (history unchanged).
- Left on purpose (genuinely about meetings, Database Dashboard): `app/registry.py:38` NAV label, `app/routers/meetings.py`, `app/static/scripts/meetings.js` (title and docstring), `tests/api/test_meta_coverage.py:5`, `BMP_UI_Backend_Implementation_Guide.md` lines 69, 85, 283.
- Ambiguous, left for the client to decide: (a) backend names `app/minutes_*.py` and the API prefix `/api/minutes/*`, which are about the minutes registers rather than the dashboard's name; (b) the empty-sheet title in the Excel export (`app/minutes_excel.py:89`, "... Minutes & Meetings ..."); (c) a comment in `dashboard.css:103` (that file must not be edited); (d) the upload dialog title "Upload minutes to auto-fill".
- Commands and results: grep before and after (only the items above remain); `pytest -q --ignore=tests/ui` -> 406 passed, 1 skipped; TestClient: `/activities-dashboard` 200 with the new name, `/minutes-dashboard` 404, launcher card shows "Activities Dashboard" linking to `/activities-dashboard`. UI tests (`BMP_UI_TESTS=1`) not run: Playwright is not installed here.
- Not done / problems: none for the rename itself.
- Next step: B0.

### 2026-10-26 12:05  Milestone B0 (recon, no code changes)
- Findings (repo vs prompt):
  - Settings: `app/config.py` `Settings.load()` reads `os.environ`, `.env` loaded by `python-dotenv` (`config.py:18`); `.env` is git-ignored; `requirements.txt` uses `>=` ranges; Python 3.12.10; no existing AI code or packages anywhere (grep for groq/langchain/openai/chroma/faiss/typesense/sentence-transformers: nothing outside docs about pgvector).
  - Documents: files stored under `STORAGE_DIR` (`storage/<company>/<sha2>/<sha>_<name>`), `POST /api/documents/upload`, `GET /api/documents/{id}/download`; listing through the generic `/entities/document`. `evidence_link` ties a document to an entity or `task_instance_id`.
  - Task engine: `routers/activities.py` has `/activities/instances`, `/activities/tasks/{id}/fields`, `/activities/tasks/{id}/data`, `/confirmations/*`; `app/task_records.py` exists. Step types in the data: check, data_entry, manual, approval, document, notification. Only template: `BOARD_MEETING`, whose step 4 "Send Notice to Directors" is the one `notification` step. `step_template.ai_assisted` boolean already exists.
  - Emails: columns exist on `director`, `shareholder`, `auditor`, `company`, `company_rta`, view `v_current_directors`.
  - Isolation: `Scope.row_scope` masters branch still returns TRUE for any staff user (`app/access.py`), so AI code must filter by company explicitly (as the prompt says). Reported, not changed.
  - **The prompt expects files that do not exist any more:** `act-overview/catalogue/running/tasks/run/start/util.js`, `activity-form.js`-driven start dialog inside the dashboard, `routers/activity_board.py`. In the earlier task ("Part A" brief for this repo, section 4) the old Activities dashboard (templates, steps, tasks, instances, confirmations) was deliberately REMOVED and replaced by the meetings-registers dashboard, which is the one just renamed. The dashboard now called "Activities Dashboard" therefore has **no task cards, no start dialog and no notice-type step**. The task-engine screens still exist only inside the Database Dashboard (`activities.js`, `activity-form.js`, imported by `main.js`), which this prompt says not to touch.
- Consequence: B1 (settings, deps, LLM client, `/api/ai/status`) is independent of this and can proceed. B2 (suggest on a task card), B3 (start dialog), B4 (notice-step card) and the Ask panel on "the running activity screen" have nowhere to mount without either rebuilding the task-engine screens inside this dashboard (a large reversal of the Part A removal) or mounting them in the Database Dashboard's Activities view (an approved screen the prompt forbids editing).
- Files: none changed.
- Not done / problems: stopped before B1 to ask one question (see reply).
- Next step: after the answer, B1.

### 2026-10-26 12:15  Decision for Part B (adaptation)
- Did: User chose "AI for the meetings registers". Mapping of the prompt's four capabilities onto this dashboard (smallest adaptation): (1) **Suggest from document** = in the Add/Edit meeting panel, read an uploaded or already-stored company document and suggest the meeting fields (date, time, chairman, agenda, forms, etc.), reviewed field by field, saved only by the existing Save; (2) **Describe it instead** = a sentence box in the Add meeting panel -> `{register, date, mode, notice date, time, chairman, agenda...}` pre-filled for review; (3) **Draft notice** = on a saved meeting card, a notice to the directors on the roster for that meeting, reviewed and sent only on approval (sandbox mail); (4) **Ask** = a panel on each register, answers from the company's documents and the statute library with citations. "Instance" in the prompt's endpoints becomes the meeting id; the company comes from the meeting (server-side). Endpoints become `/api/ai/meetings/{mid}/...` and `/api/ai/intake`, `/api/ai/{register}/ask`. Nothing in the Database Dashboard or the task engine is touched.
- Files: docs/WORK_LOG.md
- Next step: B1 (dependencies, settings, status).

### 2026-10-26 13:10  Milestones B1-B5 code written (not yet run), B6 docs started
- Did: wrote the whole AI feature, adapted to the meetings registers (see the Decision entry). New: `app/ai/` (settings, masking, llm, schemas, reader, suggest, intake, notice, index, qa, graph, prompts/*.txt), `app/routers/ai.py` (`/api/ai/status|documents|suggest|intake|meetings/{id}/{register}/notice/draft|send|{register}/ask`), `app/static/scripts/act-ai.js`, tests `tests/ai/test_ai_unit.py`, `tests/ai/helpers.py`, `tests/api/test_ai_api.py`. Edited (all small): `app/main.py` (register router; `ai` field in `/api/health`), `act-register.js`, `act-form.js`, `activities-main.js` (mount lines and one status call), `app.css` (appended `.ai-*`), `requirements.txt`, `.env` (placeholders only, `AI_ENABLED=false`), `.env.example` (created: it did not exist; AI keys only), `.gitignore` (`data/ai_index/`), README, implementation guide, Postman collection (new "AI assistant" folder; the JSON file was re-serialised, so the diff is wide but content is unchanged).
- Deviations: (1) AI settings live in `app/ai/settings.py` (`AiSettings`), not in `app/config.py`: `Settings` is a frozen dataclass built field-by-field in tests, so adding required fields would change every existing test; (2) tests: unit and safety tests in `tests/ai/`, API tests in `tests/api/test_ai_api.py` so they share the existing session fixtures; (3) notice endpoints take the register in the path, `/meetings/{id}/{register}/notice/...`; (4) company for suggest/intake/ask is named by the browser but checked server-side against the person's access (write for suggest/intake, read for ask); for notices it is read from the meeting; (5) no amount normaliser: meeting records have no amount fields; (6) forms and documents for suggested agenda items come from the existing rules, not the model; (7) the router node (fast model) is only used for the free-text "Describe it instead" box, other endpoints pass their intent directly; (8) approver may be the same person who typed (decision 5 not yet asked; default allowed).
- Not done / problems: dependency install (torch via sentence-transformers) is slow; two overlapping pip runs were started by mistake and a request to stop one was refused by the permission guard, so both were left to finish. Nothing has been run yet.
- Next step: when installs finish, verify the environment (`pip check`), run the new tests and the full suite, then pin versions into `requirements.txt`, then a browser walkthrough with the fake model.

### 2026-10-26 14:05  B1-B6 verified; hand-over
- Did: the install collided once (two overlapping pip runs; the first failed with a file-in-use error) and the second finished with exit 0; `pip check` reports no broken requirements. Added the missing packages to `requirements.txt` (`>=` style, versions as installed: langchain 1.4, langchain-core 1.7, langchain-community 0.4, langchain-groq 1.1, langchain-openai 1.7, langgraph 1.2, pypdf 6.21, sentence-transformers 6.2, faiss-cpu 1.15, chromadb 1.5, typesense 2.1; `pymupdf`/`python-dotenv` were already listed). Fixed three things found by tests: a pydantic field named `register` shadowed an attribute (renamed `register_key`); a model that failed to be created was not mapped to the friendly 503; two of my tests left meetings in the shared test database (now archived at teardown) and one compared the question text instead of the retrieved passages.
- Commands and results: `pytest tests/ai` -> 26 passed; `pytest -q --ignore=tests/ui` -> **444 passed, 1 skipped** (406 before Part B; +38 new). Browser walkthrough on a throwaway database (dropped afterwards) with a scripted fake model: Ask box present; Describe it instead filled date, time, mode and agenda; Suggest from document showed three suggestions with tier and applied only the ticked ones; Draft notice showed the test-mode banner, the four directors from the database with emails, an editable covering text, and Approve and send stayed disabled until the box was ticked, then locked after one click; with no test mail server running every recipient showed "Could not be sent" and the log recorded approver and counts only; Ask declined because the fake model's quote was not in the document (the citation check working). The live Groq tests were not written or run: no key, and AI_ENABLED stays false.
- Rules check: AI off = nothing renders and nothing errors (test); no write path in `app/ai/` or `routers/ai.py` (static test); no row counts change on suggest, intake, draft or ask (test); company isolation for suggest, intake, notice and ask (tests); no migration, table, role or `dashboard.css` change; Database Dashboard untouched.
- Known limitations / open: (1) "Now" in Suggest compares with the SAVED meeting only; for an unsaved new meeting it shows a dash and flags no conflict; (2) first Ask builds the index (about 20 s here, with the fake embedder; the real model will also download on first use); (3) Typesense, the statute library source, whether the same person may approve their own send (default: allowed) and real-data approval are all still open (decisions 3, 4, 5, 7); (4) no OCR: scanned documents are reported unreadable; (5) the Playwright UI tests were not run (Playwright not installed); (6) `docs/postman` JSON was re-serialised so its diff is wide; (7) `/api/health` reports `ai` from the app's settings.
- Next step: wait for review.

### 2026-10-26 15:10  Fix: "AI is unavailable" on Draft notice with the real Groq key
- Did: reproduced the failure with one live call (error type and message only, key never printed): Groq returned 400 `tool_use_failed` because LangChain's default structured output forces a tool call and `openai/gpt-oss-120b` answered in prose. `app/ai/llm.py` now asks for JSON-schema output first, then JSON mode, then function calling, moving on only when the provider refuses the request. Live checks then passed for the notice cover, the router, extraction and Ask. Found and fixed two more things only a real model shows: the 20b model returns an empty plan for the intake sentence, so intake now uses the larger model (`AI_MODEL_EXTRACT`); and the covering paragraph invented "[date] [time]" blanks, so the prompt is stricter and `notice.draft_cover` replaces any cover containing square brackets with plain standard wording.
- Files: app/ai/llm.py, app/ai/intake.py, app/ai/notice.py, app/ai/prompts/notice_cover_v1.txt, tests/api/test_ai_api.py (the "off by default" test now forces AI off itself, because the local .env now has AI on).
- Commands and results: live calls via `invoke_structured` -> notice OK, route OK, extract OK, intake OK (120b), ask OK; `pytest -q --ignore=tests/ui` -> 444 passed, 1 skipped.
- Not done: the end-to-end browser flow against real Groq has not been re-run by me; the running server must be restarted to load the fix.
