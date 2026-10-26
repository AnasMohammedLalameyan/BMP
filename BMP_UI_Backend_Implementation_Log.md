# Implementation Log — Front End and FastAPI Back End

**Date:** 1 October 2026 · **Role:** senior software engineer (Claude) · **Scope:** the prompt in `UI and Backend prompt.txt`
**Rule applied throughout:** the approved Phase 1 database is retained *as is*; change the project only where necessary.

---

## 1. Outcome in one paragraph
A FastAPI back end and the approved dashboard UI were added on top of the unchanged Phase 1 database. The application builds from an empty PostgreSQL server, every one of the **65 tables / 897 columns / 518 writable fields** is reachable from the UI and was proven to store exactly what is sent, and **307 tests pass** (19 original + 288 new) — also on a brand-new Python environment installed only from `requirements.txt`. In a real browser all 66 sidebar pages loaded with no JavaScript errors. Testing and the build also surfaced **five weaknesses in the approved database** (listed in §5); none were changed, and the API compensates for each of them.

## 2. Inputs reviewed
| Input | Used for |
|---|---|
| `Latest_Implementation_with_approved_Database/` | The database and tooling to build on (unchanged) |
| `Old_implementation_with_approved_ui/` | **UI only**: `dashboard.html` shell, `dashboard.css`, Bootstrap vendor files, and the JavaScript view patterns. Its Flask back end, SQLite database, exchange/AI services and tests were **not** used or run. |
| `BMP_Phase1_Database_Guide.md`, `DATA_DICTIONARY.md`, `ERD.md` | How the database works |
| `BMP_Project_Requirements_v1_0.docx`, `BMP_Technical_Overview_v1.1.docx` | Requirements (FR-1…15) and the technical plan |
| `UI and Backend prompt.txt` | The tasks and notes |

## 3. What was done (in order)
| # | Action | Result |
|---|---|---|
| 1 | Read the prompt and located both folders; read the old UI shell, stylesheet, entry point, sidebar, master-data, companies, overview, meetings-style views, forms, registers and log modules to learn its structure. | The old app is an audit-checklist tool (BSE/NSE feeds, AI); its look and layout were kept, its content was re-mapped to the new data (guide §2). |
| 2 | Chose **not to run the old application**: it calls exchange feeds and a paid AI API at start-up. Its `dist/.env` contains an API-key entry (`OPENROUTER_API_KEY`); I listed the entry names with values masked, so I never saw, copied or used the value. | See §9: recommend rotating that key if the file was ever shared. |
| 3 | Inspected the live database catalogue (columns, foreign keys, check rules, lookup bindings, functions, views) and probed how isolation really behaves. | Findings §5. |
| 4 | Designed a **metadata-driven** back end so no field list can fall out of date: the API reads the schema and publishes it; the UI draws forms from it. | `app/schema_meta.py`, `registry.py`, `routers/meta.py`. |
| 5 | Built the back end: configuration, pools, error mapping, record engine, access rules, authentication, routers (auth, meta, entities, companies, people, meetings, views/rules, activities, documents, audit). | `app/` |
| 6 | Smoke-tested in-process, then built the front end: copied `dashboard.css` + Bootstrap verbatim, adapted the HTML shell, wrote the JavaScript modules (generic list + record editor, master data, directors register, meetings, activities, rules, calculated values, documents, activity log, overview, sign-in). | `app/static/`, `app/templates/` |
| 7 | Visual checks in Chrome (sign-in, companies, overview, master data, register, meetings, rules, activities/task board, record editor with tabs, create + validation, calculated values, activity log, mobile width) and a **sweep of all 66 sidebar pages** watching for errors. | No JS errors; all pages rendered. |
| 8 | Wrote the test suites (§7) and fixed what they found (§6). | 288 new tests. |
| 9 | Added `scripts/manage_users.py`, `scripts/run_server.py`, `README.md`, updated `requirements.txt` / `.env.example`, added `.gitignore`. | |
| 10 | Rebuilt the demo database from scratch (`setup_db.py --reset --seed`) to remove the test records created while checking the screens; ran the full suite again, including from a fresh virtual environment. | 307 passed, twice. |
| 11 | Wrote `BMP_UI_Backend_Implementation_Guide.md` (explanation, set-up, run, demo, production recommendations) and this log. | |

## 4. Decisions taken
| # | Decision | Reason |
|---|---|---|
| 1 | **Generic, schema-driven API and forms** rather than 65 hand-written screens. | Guarantees every field is available, stays correct as the schema evolves, and is provable by test. Hand-built screens exist only where a workflow needs one (register, meetings, activities, rules, overview). |
| 2 | **Authentication outside the database** (salted hashes in `instance/users.json`) tied to `core.app_user`. | The schema has no password column and must not change; the Phase 1 guide says authentication belongs to this layer. |
| 3 | **Two database logins**: `bmp_app` for everything; the owner login only to read the audit log and to onboard a company. | Row-level security stops `bmp_app` inserting a company nobody can yet access, and `audit.log` is closed to it by design. Documented as item B1 for a proper database-side fix. |
| 4 | **Aadhaar and portal-secret storage are off by default**, switchable by `.env` with an encryption key; values are never returned. | The client's workbook says "One thing NOT to build: portal passwords"; the overview says Aadhaar is not stored; the owner asked that every field be storable — so it *can* store, but only by an explicit decision. Both states are tested. |
| 5 | **Application-layer isolation** for tables and views the database does not scope, and a **same-company rule** for references. | Found by testing (§5, §6). Required by FR-10. |
| 6 | **A step needing confirmation cannot be completed until confirmed**, by a different person (an administrator may confirm their own). Switchable: `ENFORCE_TASK_CONFIRMATION`. | FR-13 asks for named-person confirmation to be built into the system; the schema had only the table. |
| 7 | **Rules and activities use the database as the authority**; the API only adds order-of-steps and confirmation rules around `ops.instantiate_activity`. | Keeps the approved logic where it was approved. |
| 8 | Default **financial year** = the newest year that has records (not "the year we are in"). | The seeded data is FY 2024-25 / 2025-26; defaulting to the empty current year would open every screen blank. |
| 9 | **Technical-overview clashes → the implementation wins** (as the prompt directs): Board Meeting not AGM; 39 not 37 rules; local file storage not MinIO; etc. | Guide §14. |
| 10 | **No deletion** anywhere; "Archive/Restore" instead. | Phase 1 principle; the database forbids deletes. |

## 5. Findings in the approved database (reported, **not changed**)
| # | Finding | How found | What the API does about it |
|---|---|---|---|
| F1 | The 13 calculated **views return other companies' rows** to the application login (views run with their owner's rights, bypassing row-level security). | Queried the views as the client user: 17 director rows across 5 companies. | Filters the views itself (tested). |
| F2 | **Shared and child tables have no row-level security** (directors, shareholders, attendance, designations, evidence links…). | Client user could read all 12 directors and other companies' attendance. | Scopes them through their parents; clients see only linked people (tested over every table). |
| F3 | The application login (`bmp_app`) **cannot add a company** (row-level security refuses a company nobody has access to yet) and **cannot read `audit.log`** (closed by design). | Direct attempts. | Uses the owner login for exactly those two actions, read-only for the audit log. |
| F4 | `activity.get_template_json` **duplicates** bindings/evidence when a step has several dependencies (unaggregated joins). | Compared function output to the tables. | Builds template detail from the tables; raw function still available. |
| F5 | `capital_event.reason_id` validates only against the *increase* reasons list. | Lookup trigger definition. | Dropdown offers what the database will accept; decrease reasons cannot be used. |
| Also | `step_dependency` has no archive columns; `role_permission` is empty (roles carry no permissions); no PAN uniqueness; `evidence_link.entity_type` is free text (guidelines wanted it validated). | Catalogue. | API validates `entity_type`; access uses company access level + role name. |

## 6. Defects found and fixed during this build
| # | Defect | Found by | Fix |
|---|---|---|---|
| D1 | A record could point at **another company's record** (e.g. a Greenfield director attending a BrightMed meeting) as long as the user could see both. | `test_workflows` (attendance) | Reference check now also requires the same company (`crud._check_refs`). |
| D2 | `SCOPE` not imported in `crud.py`, which broke every create. | The full suite (44 failures) | One-line import. |
| D3 | Field help text leaked database wording ("References lookup_list code …"). | Looking at the screen | Filtered in `meta.clean_help`. |
| D4 | Yes/no fields that can never be empty were drop-downs with a blank choice. | Looking at the screen | Rendered as checkboxes. |
| D5 | The first smoke test and the UI checks left test rows in the **demo** database. | Review | Demo database rebuilt from scratch; the real tests use a separate throw-away database. |
| D6 | Several of my own tests assumed seed counts that earlier tests change (rules = 39, bindings = 20, agenda items = 0). | Failures | Assertions compare with the database's own count. |
| D7 | The History tab for a newly created record listed every empty or false field. | Looking at the screen | Shows only the values that were actually set. |

## 7. Verification evidence
| Check | Result |
|---|---|
| `python -m pytest` (project environment) | **307 passed** |
| Same, in a brand-new virtual environment installed only from `requirements.txt` | **307 passed in 21 s** |
| Round trip: every writable field of every writable table created, read back, compared, edited, archived, restored | 67 tests, **all pass**; 518 writable fields exercised |
| Metadata coverage: 65 tables, 123 FKs, 23 dropdown bindings, 22 choice lists, 19 Standard Lists (102 values), 13 views, every table reachable from the UI | 9 tests, all pass |
| Isolation across **every table** for the read-only client and the manager | 142 tests, all pass |
| Browser sweep of all 66 sidebar pages as an administrator | 0 JavaScript errors, 0 error placeholders (one regex false positive on a hidden error box) |
| Mobile width (375 px) | No horizontal overflow; sidebar collapses to the menu |
| `db/` unchanged | Newest file in `db/` dated 30 Sept 2026 (before this work) |
| Old theme carried over | `dashboard.css` is byte-identical to the old file (asserted by a test) |

Test counts by file: auth 11 · metadata coverage 9 · isolation 142 · all-fields round trip 67 · workflows 35 · UI assets 24 · original database tests 19.

## 8. What was NOT done (explicitly)
* **No changes to the database**: no migration, seed, table, view, function, role or grant (the recommendations in guide §13-B are proposals).
* **Old features without a home in the new data model were not rebuilt**: statutory registers checklist, MR-3 report, audit note, other filings, events, data sources, BSE/NSE checklist sections. **Import (JSON)** was not rebuilt. Refresh now only reloads.
* **No AI, e-mail sending, notifications, MCP tools or document parsing** (out of scope today).
* **No HTTPS termination, backups, service installation, monitoring or Docker image** — operations tasks, listed in guide §13.
* **No single sign-on, two-factor sign-in, server-side session revocation, virus scanning of uploads, object storage.**
* **Not tested**: browsers other than Chrome; screen readers/keyboard-only use; load/volume; PostgreSQL versions other than 18.3; macOS/Linux; failover or restore of backups.
* The **Board Meeting steps and the 39 rules remain unverified legal content** (draft) — needs a BMP professional.
* I did **not** modify `.env` (it works as is in development; `APP_SECRET_KEY` is recommended).

## 9. Notes for the project owner
1. **Old implementation:** `Old_implementation_with_approved_ui/dist/.env` contains an API-key entry (and the `dist` folder holds logs and databases). I never saw the value; if that folder has ever been shared, **rotate the key** and keep the folder out of the new repository.
2. **Demo accounts** share whatever password you give `init-demo`; replace them before real use. `seed@system.internal` is inactive by design.
3. The new application depends on three things outside the database: `instance/users.json` (sign-in), `storage/` (uploaded files) and `.env` (settings). **Back up all three** with the database.
4. The `bmp_owner` login is used inside the app for two narrow actions; guide §13-B1 describes the database change that would remove that.

## 10. Effects on this computer
* Demo database `bmp` was **reset and re-seeded** to its pristine seed state (it held test rows from my UI checks).
* A throw-away database `bmp_api_test` is created and **dropped** by each test run.
* PostgreSQL roles and the pgvector extension from the earlier session are unchanged.
* Packages were installed only in scratch virtual environments (outside the project); the project's own `venv/` was not touched.
* The development server I used was stopped; `instance/` and `storage/` were **not** created in the project folder.

## 11. Files
**Created:** `app/` (all application code, UI and template) · `tests/api/` (7 files) · `scripts/manage_users.py` · `scripts/run_server.py` · `README.md` · `.gitignore` · `BMP_UI_Backend_Implementation_Guide.md` · this log.
**Changed:** `requirements.txt` (added fastapi, uvicorn, psycopg-pool, jinja2, python-multipart, itsdangerous, httpx) · `.env.example` (web-application settings).
**Unchanged:** everything under `db/`, `scripts/setup_db.py`, the existing tests, `docs/`, `.env`, and the two Phase 1 documents.

## 12. Open questions for the project owner
1. Keep the **portal-secret and Aadhaar columns** at all? (Recommendation: remove from the database or leave permanently off.)
2. Approve the **database hardenings** in guide §13-B (they need a deliberate, versioned migration).
3. Where will this be **hosted**, and who runs backups and monitoring?
4. Should **old audit-checklist features** (registers, MR-3, audit note) return as new tables in a later phase?
5. Which **roles and permissions** should exist (the schema's roles have no permissions yet)?
