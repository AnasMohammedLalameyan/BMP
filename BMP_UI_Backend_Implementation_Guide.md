# BMP Compliance Platform — Web Application: Implementation & Operation Guide

**What this covers:** the front end (the approved dashboard look, rebuilt on the new database) and the FastAPI back end that were added on top of the Phase 1 database — what they are, how they work, how to set them up, run them and demonstrate them, and what should change before they go into live use.
**Prepared:** 1 October 2026 · **Verified on:** Windows 11, PostgreSQL 18.3, pgvector 0.8.6, Python 3.12, Chrome.
**The Phase 1 database was not changed.** Every file in `db/` is exactly as approved (last modified 30 Sept 2026; this work added nothing to it).

> **Reading guide.** Part A explains the product. Part B explains how it is built and protected. **Part C is the step-by-step manual** (set up → run → demonstrate). Part D lists what I recommend changing before production use. Words in **bold** are defined the first time they appear.

---

## 0. Status at a glance

| Question | Answer |
|---|---|
| Does it work end to end? | **Yes.** From an empty PostgreSQL server: build the database, set passwords, start the server, sign in, and every screen opens and saves. **307 automated tests pass** (the 19 original database tests + 288 new web tests), including on a brand-new Python environment installed only from `requirements.txt`. |
| Is every field in the database usable from the UI? | **Yes — proven by test.** All **65 tables / 897 columns / 518 writable fields** are reachable from the sidebar (or from a record's "Related records"), and for every writable table a record is created with **every** writable field filled in, read back, compared field by field, edited, archived and restored. |
| Does it look like the old dashboard? | **Yes.** The same HTML shell, the same Bootstrap theme and the *byte-identical* `dashboard.css` (a test checks that), the same sidebar/accordion, entity box, tables, cards and badges. |
| Was the database retained as-is? | **Yes.** No migration, seed or table was touched. The application adapts to the database, never the other way round. |
| Is it "production-ready"? | **Ready for a supervised pilot / staging deployment, not yet for unattended live use.** Part D lists exactly what is still needed (HTTPS, backups, a few database-level hardenings that I was not allowed to make, and operational items). |

---

# PART A — The product

## 1. What was built

```mermaid
flowchart LR
  B["Browser<br/>the approved dashboard UI<br/>(HTML + CSS + JavaScript modules)"]
  subgraph APP["FastAPI application  (app/)"]
    A["Sign-in, sessions, CSRF,<br/>access rules"]
    M["Self-describing metadata<br/>(reads the live schema)"]
    C["Generic record engine<br/>list · create · edit · archive"]
    W["Workflows<br/>activities, meetings, register,<br/>documents, exports, audit"]
  end
  subgraph DB["PostgreSQL  (database bmp - unchanged)"]
    S["schemas core / activity / ops / audit<br/>row-level security · audit trigger · no-delete"]
  end
  F["Evidence files<br/>(storage folder)"]
  U["Credentials file<br/>(password hashes)"]
  B -- "JSON over HTTPS" --> A
  A --> M --> C --> S
  A --> W --> S
  W --> F
  A --> U
```

| Piece | What it is | Where |
|---|---|---|
| **Front end** | The approved dashboard, ported: same layout and theme, new screens for the new data. Plain JavaScript modules — no build step. | `app/static/`, `app/templates/dashboard.html` |
| **Back end** | A FastAPI application: sign-in, a self-describing API over every table, and the business workflows. | `app/*.py`, `app/routers/` |
| **Credentials file** | The database has no password column (by design), so sign-in passwords are kept as salted hashes in a small file next to the app. | `instance/users.json` (never committed) |
| **Evidence files** | Uploaded documents are stored on disk (fingerprinted); the database holds their details and links. | `storage/` |
| **Tests** | 288 new tests against a throw-away copy of the database. | `tests/api/` |

## 2. From the old dashboard to the new one

The old dashboard was built for a different job (a secretarial-audit checklist fed by BSE/NSE announcements and an AI service, on its own SQLite database). The new database is a system of record. The **look, layout and behaviour** were kept; each old screen was mapped to the nearest meaning in the new data.

| Old screen | New screen | Notes |
|---|---|---|
| All companies (list) | **All companies** | Same table style. Shows only companies the signed-in person may access. |
| Entity under audit box | **Company box** | Company name, CIN, category, financial-year selector, signed-in person. (The exchange selector is gone — there are no exchange feeds in this system.) |
| Dashboard Overview | **Dashboard Overview** | Same stat tiles, progress bar and segment cards, fed by the live database. Adds a "Needs attention" list. |
| Master Data | **Master Data** | Company profile saves as you leave each field (same behaviour), plus every standing record: directors, share capital, financials, RTA, activities, group companies, auditors, holders. |
| Applicability engine | **Applicability Rules** | The 39 client rules with evaluations per company and year. |
| Calculators | **Calculated Values** | The 13 database views (ages, percentages, attendance, overdue days …) shown live. |
| Transaction checklists | **Activities & Tasks** | The Board Meeting recipe, started per company, with a task board. |
| Minutes & Meetings | **Minutes & Meetings** | Same card layout: particulars, agenda, attendance. |
| Forms Filed | **Forms Filed** (Government Filings) | A generic table page with the overdue count on the sidebar chip. |
| Activity Log | **Activity Log** | Backed by the database's tamper-proof audit trail. |
| Data menu (Export Excel / JSON) | **Data menu** | Export Excel and JSON for the open company, plus password change and sign out. |
| Print, Refresh data | **Print, Refresh data** | Refresh now simply reloads from the database. |

**Not carried over — deliberately.** Statutory Registers checklist, MR-3 report, Audit Note, Other Filings, Events, Data Sources and the BSE/NSE checklist sections have **no tables in the approved database** and depend on exchange feeds and AI (out of scope today). Rather than invent data structures, I left them out. "Import JSON" was also not carried (see §14).

## 3. A tour of the screens

| Sidebar group | What is there |
|---|---|
| **Working Papers** | Dashboard Overview · Master Data · Calculated Values · Applicability Rules · Activities & Tasks · Activity Log |
| **Company** | Financials by year · Registrar & Transfer Agent · Business activities · Holding/subsidiary/associate |
| **People & Roles** | **Directors & KMP Register** (a company's whole board over time) · Directors (people) · Board stints · Designation history · Independent-director terms · Declarations · DIR-3 KYC · Residency · Other directorships · Auditors |
| **Capital & Members** | Share classes · Share capital summary · Capital events · Shareholders · Shareholdings · Allotments · Share transfers · Foreign investment (FC-GPR / FC-TRS) |
| **Governance** | **Minutes & Meetings** · Committees · Committee members · Circular resolutions (+ responses) · Postal ballots |
| **Financial & Legal** | Forms filed · Loans & deposits · Remuneration · Penalties · Yearly disclosures · Sec 185 / 186 / 188 · ODI (+ step-down subsidiaries) · ECB · Portal access |
| **Evidence** | **Documents & Evidence** (upload, drag and drop) · Evidence links · Document chunks |
| **Administration** *(administrators only)* | Standard lists and values · Document types · Rule definitions · Users · User company access · Roles · Permissions · Activity templates, steps, dependencies, bindings, evidence requirements · Field registry · Task record links · Confirmations |

**On every table page:** search · sortable columns · "Show archived" · **Export CSV** · **+ Add**. **Click any row** to open its **record editor**: all fields grouped into sections, dropdowns filled from the Standard Lists and from the related tables, plain-language validation messages, a **Related records** tab (child records you can add in place) and a **History** tab (every change: who, when, from → to). **Archive** hides a record but never deletes it; **Restore** brings it back.

## 4. How "every field is available" works

The API **reads the database's own catalogue** at start-up — each column's type, whether it is required, which table it points at, which Standard List a dropdown uses, which values a CHECK rule allows — and the screens draw themselves from that. So there is no hand-maintained field list to fall out of date: a field added to the database appears on the forms, and the round-trip test will exercise it.

| Database feature | What the user sees |
|---|---|
| NOT NULL, no default | Required field (red star; named in the error if missing) |
| Foreign key | Dropdown showing a readable label (e.g. "Prashant Joshi (12340012)"), limited to what the user may see |
| 23 lookup-validated columns | Dropdown of the right Standard List only |
| CHECK … = ANY(…) | Dropdown of the allowed values |
| `financial_year` pattern | Format hint (2024-25) |
| yes/no that can't be empty | Checkbox |
| date / time / date-time / number | The matching input (money in Indian digit grouping) |
| JSON (inputs, details, params) | Editable JSON box |
| `vector(1536)` | Shown as "N-dimension vector"; paste a JSON array to replace |
| Generated column (`remuneration.total`) | Read-only, computed by the database |
| System columns (`created_at`, `is_archived` …) | Shown under "Record information"; never typed |
| Encrypted columns (Aadhaar, portal secret) | See §5.5 |

**Proof.** `tests/api/test_roundtrip_all_fields.py` builds, from the live metadata, a record for every writable table with **every** writable field populated (tables with an either/or rule such as foreign investment get two variants), then checks each value comes back exactly (numbers, dates, times, JSON, vectors included). `test_meta_coverage.py` checks that all 65 tables, 123 foreign keys, 23 dropdown bindings, 22 enumerated checks, 19 Standard Lists (102 values) and 13 views are exposed, and that every table is reachable from the sidebar.

---

# PART B — How it is built and protected

## 5. Security and data integrity

### 5.1 Who can do what

| | Administrator | Manager | Client |
|---|---|---|---|
| Demo account | admin@bmpco.in | manager@bmpco.in | client@nexatech.co.in |
| Companies | all 5 (admin) | BrightMed, Greenfield, Skyward (write) | Nexatech (read-only) |
| See records | their companies | their companies | their company |
| Add / edit / archive | yes | yes, in their companies | **no** |
| Add a company, manage users, edit Standard Lists, rules, templates | **yes** | no | no |
| See Administration group | yes | no | no |

Access comes from `core.user_company_access` (a level of *read*, *write* or *admin* per company) and the person's role. It is checked on **every** request, so removing access takes effect immediately.

### 5.2 Company isolation — three layers
1. **The database** (Phase 1): row-level security on the 32 tables that carry a `company_id`, driven by the signed-in user's id which the API sets on every request.
2. **The API**, for everything the database does not cover — and this matters, because testing found gaps:
   * the **shared people tables** (directors, shareholders) and **child tables with no company_id** (attendance, designations, evidence links …) are scoped through their parents. Staff (anyone with write access) see all people ("don't ask twice"); a read-only client sees only people linked to their own company;
   * the database's **calculated views are not scoped** (they run with their owner's rights) — the API filters them itself;
   * a record may only **point at records of its own company** (a Greenfield director cannot be recorded at a BrightMed meeting) — the database's foreign-key check ignores row-level security, so this is enforced here.
3. **The tests**: 142 isolation tests loop over *every table* for the client and manager accounts, plus targeted tests for the people tables, views, audit log, documents, exports and cross-company references.

### 5.3 Sign-in and sessions
* Passwords are stored only as **salted scrypt hashes** in `instance/users.json`; nothing secret is in the database. A person can sign in only if they have **both** a password there **and** an active `core.app_user` row.
* A signed, `HttpOnly`, `SameSite=Lax` session cookie (8 hours); `Secure` and HSTS in production.
* **CSRF protection** on every change (a token the page must echo back).
* **Lock-out** after 5 failed attempts for 10 minutes (per address and e-mail). Unknown users and wrong passwords give the identical answer and take the same time.
* Security headers: CSP (no external scripts), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`.

### 5.4 Nothing is ever lost
* There is **no delete** anywhere in the API (`DELETE` returns 405). "Archive" sets a flag; "Restore" clears it. The database's own triggers also forbid deletes.
* Every insert and update is written to the audit trail with **who, when, old and new values** (the API sets the user on each request, otherwise the database refuses the write). The **Activity Log** and each record's **History** tab read it.
* **Edits are version-checked**: if someone else changed the record meanwhile you get a clear "reload and try again" instead of silently overwriting them.

### 5.5 Sensitive fields (Aadhaar, portal secrets)
The database has two encrypted columns. The client's own brief says portal passwords must **never** be stored in the dashboard (and the technical overview says Aadhaar is not stored), so:
* Both are **switched off by default** (`ALLOW_PORTAL_SECRET_STORAGE=false`, `ALLOW_AADHAAR_STORAGE=false`): the screens show "storage switched off by policy" and the API refuses writes.
* If BMP decides otherwise, set the flag(s) **and** `APP_ENCRYPTION_KEY` in `.env`. Values are then encrypted by the database (pgcrypto) using that key (kept outside the database), and are **never sent back** to the browser, the history or the exports. The tests prove both states.

### 5.6 Uploads
Type allow-list (PDF, Word, Excel, CSV, text, common images — no scripts, HTML or archives), size cap (25 MB), names sanitised (no path tricks), stored outside the web root, **SHA-256 fingerprint** recorded, repeat uploads of the same name become **versions**, the fingerprint is **re-checked on download** (a file altered on disk is refused), and files are always downloaded as attachments.

### 5.7 Two database connections — and why
Normal requests use the **`bmp_app`** login (cannot delete; subject to row-level security). Two things that login cannot do *by design* use the owner login, read-only or tightly scoped:
1. **Reading the audit log** (closed to `bmp_app` so it can't be tampered with);
2. **Adding a company** (row-level security refuses to let `bmp_app` insert a company nobody has access to yet; the same action also grants the creating administrator access).
See Part D for the cleaner long-term fix (a database change).

## 6. The workflows

| Workflow | Behaviour |
|---|---|
| **Start an activity** | The start form is generated from the template's `input_schema` (meeting date, time, venue, mode, agenda). Required fields and dates are checked, then the database function `ops.instantiate_activity` creates the instance and **one task per step with due dates worked out** (e.g. meeting 10 Dec → notice due 3 Dec, minutes drafted 25 Dec, signed 9 Jan). |
| **Move a task** | Not started → in progress → completed / skipped, and back. **A step cannot be completed before the steps it depends on.** A step flagged *requires confirmation* (send notice, sign minutes) **cannot be completed until a named person has confirmed it**: someone requests confirmation; a *different* person confirms or rejects (an administrator may confirm their own). Missing mandatory evidence produces a warning. Completing sets who/when. **Overdue is calculated** from the due date, never stored. When every task is done the activity completes; reopening a task reopens the activity. |
| **Evidence & record links** | Attach a file to a task (fingerprinted, linked) and link the records the task touched. |
| **Directors & KMP register** | One screen for a board over time. **Add director / KMP** is one step: pick an existing person or enter a new one (a known **DIN reuses the person**), then the board stint and designation are created together. Overlapping stints for the same person are refused. |
| **Meetings** | The meetings book (per year) with agenda and attendance; **Attendance by roster** lists the directors who were on the board on the day and saves one row per director (create or update, never duplicates). |
| **Rules** | Every rule with its latest evaluation for the chosen year; each saved evaluation is a **new dated record** (history kept); two rules are also computed from the board's records. |
| **Add a company** (admin) | Every company field; the creator is granted access in the same step. |
| **Exports** | Per list: CSV (Excel-safe, formulas neutralised). Per company: Excel workbook (one sheet per record type) and JSON. |

## 7. API reference (summary)
Interactive documentation is at **`/api/docs`** when `APP_ENV=development`.

| Area | Endpoints |
|---|---|
| Session | `POST /api/auth/login` · `POST /api/auth/logout` · `GET /api/auth/me` · `POST /api/auth/password` · `POST /api/admin/users/{id}/password` |
| Describing itself | `GET /api/meta` (entities, fields, dropdowns, navigation, views) · `GET /api/options/{entity}` |
| Any record type | `GET/POST /api/entities/{type}` · `GET/PATCH /api/entities/{type}/{id}` · `POST …/{id}/archive` · `POST …/{id}/restore` · `GET …/{id}/history` · `GET /api/entities/{type}/export.csv` |
| Companies | `GET/POST /api/companies` · `…/{id}/overview` · `…/years` · `…/directors-register` (GET/POST) · `…/meetings-book` · `…/rules` · `…/activities` · `…/export.xlsx` · `…/export.json` |
| Calculated values | `GET /api/calc/{view}` |
| Meetings | `GET /api/meetings/{id}/detail` · `PUT /api/meetings/{id}/attendance` |
| Activities | `GET /api/activities/templates` (+ `/{id}`, `/{code}/json`) · `POST /api/activities/instances` · `GET /api/activities/instances/{id}` · `POST /api/activities/tasks/{id}/status` · `POST …/tasks/{id}/confirmations` · `POST /api/confirmations/{id}/confirm|reject` |
| Documents | `POST /api/documents/upload` · `GET /api/documents/{id}/download` |
| Audit | `GET /api/audit` |
| Health | `GET /api/health` |

Errors always look like `{"error": {"code", "message", "fields"}}` — `fields` names the boxes to highlight.

---

# PART C — Set up, run and demonstrate (step by step)

> If you completed the Phase 1 set-up (PostgreSQL, pgvector, the `bmp` database, a working `.env`), you can **skip to Step 3**. Commands are for **Windows PowerShell**; macOS/Linux notes are at the end of Step 3.

## 8. Set-up

### Step 1 — Install the prerequisites (once)
| Needed | Version | Notes |
|---|---|---|
| PostgreSQL | 16 or newer (tested 18.3) | Remember the `postgres` password you set. |
| pgvector | matching your PostgreSQL | Not bundled with PostgreSQL; see `BMP_Phase1_Database_Guide.md` §11 Step 2 for the options on Windows. |
| Python | 3.10 or newer (tested 3.12) | Tick "Add Python to PATH". |
| A modern browser | Chrome, Edge, Firefox, Safari | Tested in Chrome. |

### Step 2 — Open the project folder
```powershell
cd "C:\Users\<you>\Desktop\BMP\Latest_Implementation_with_approved_Database"
```

### Step 3 — Create a Python environment and install the packages
The `venv` folder that arrived with the project may belong to another computer; make your own:
```powershell
Remove-Item -Recurse -Force .\venv        # only if it came from another machine
python -m venv venv
.\venv\Scripts\Activate.ps1               # your prompt now starts with (venv)
pip install -r requirements.txt
```
*If PowerShell refuses to run the activate script:* `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.
*macOS/Linux:* `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`; every other command is the same.

### Step 4 — Configure `.env`
Open `.env` (copy `.env.example` to `.env` if it does not exist) in a text editor — **type these lines into the file, not into the terminal**. At minimum:
```ini
DATABASE_URL=postgresql+psycopg://bmp_owner:YOUR_OWNER_PASSWORD@localhost:5432/bmp
DATABASE_URL_APP=postgresql+psycopg://bmp_app:YOUR_APP_PASSWORD@localhost:5432/bmp
DATABASE_URL_ADMIN=postgresql+psycopg://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/postgres
APP_ENV=development
APP_SECRET_KEY=PASTE_A_LONG_RANDOM_VALUE_HERE
```
Generate the secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. (If you leave it empty in development the app invents a temporary one, and everyone is signed out whenever the server restarts.) All other keys have sensible defaults — the full list is in §10.

### Step 5 — Build and fill the database (skip if `bmp` already exists)
```powershell
python scripts/setup_db.py --seed
```
Expected ending: `Migrations: 11 applied.` … five seed files `OK` … `Done.` Running it again is safe (applied files are skipped). To start from nothing — **development only, deletes the database**: `python scripts/setup_db.py --reset --seed`.

### Step 6 — Give the demo users passwords
The database stores no passwords, so set them in the credentials file:
```powershell
python scripts/manage_users.py init-demo        # asks once; applies to the three demo users
python scripts/manage_users.py list             # shows who exists and who has a password
```
Real people: add them under *Administration → Users* (name, e-mail, role, active), grant company access under *User company access*, then `python scripts/manage_users.py set-password their.email@firm.in` (or an administrator can use **Set password** inside the user's record).

### Step 7 — Run the tests (recommended)
```powershell
python -m pytest
```
**Expected: `307 passed`** in about 20 seconds. (The web tests build and delete a throw-away database called `bmp_api_test`, which needs `DATABASE_URL_ADMIN`; your demo data is never touched.)

### Step 8 — Start the application
```powershell
python scripts/run_server.py
```
Open **<http://127.0.0.1:8000>** and sign in. Stop the server with **Ctrl + C**. Options: `--port 8080`, `--host 0.0.0.0` (reachable by other computers on your network), `--reload` (development: restart on code changes).

### Step 9 — Day-to-day
* Start: Step 8. The browser remembers where you were (company, year, screen) after a refresh.
* Back up **both** the database and the `storage/` folder (§12).
* After pulling new code: `pip install -r requirements.txt`, `python scripts/setup_db.py` (applies any new migrations), restart.

## 9. A 25-minute demonstration

Sign in as **admin@bmpco.in**. (The seeded data is fictional.)

| # | Do this | Say / point out |
|---|---|---|
| 1 | **All companies** | "Five client companies; each person sees only the ones they have access to." |
| 2 | Open **BrightMed Pharma Limited** → **Dashboard Overview** | Tiles, the **Needs attention** list (an overdue MGT-7; a rule needing action), the rules bar, and the segment cards with record counts. "Everything here is calculated live." |
| 3 | **Master Data** | Every company field. Change the phone number and tab away → **✓ saved**. Scroll: share capital, financials, auditors, shareholders — each opens its full record on click. |
| 4 | **People & Roles → Directors & KMP Register** | **Prashant Joshi appears twice** — resigned 2021 (red), re-appointed 2023. "History is kept, never overwritten." |
| 5 | Click his current row | The **board stint** record: appointment dates, flags, dropdowns. **Related records** (designation history, terms, declarations, committees, remuneration). **History** tab: who created it and when. |
| 6 | **+ Add director / KMP** | Enter a new person with a 8-digit DIN, a start date, a designation. Add the same DIN to another company later → the person is **reused**. |
| 7 | **Governance → Minutes & Meetings** | BM-1…BM-3 and the AGM: particulars, agenda, attendance. **Attendance** → tick directors on the board that day → Save. |
| 8 | **Calculated Values** | Board attendance %, shareholding %, director ages. "Never typed — they cannot go stale." |
| 9 | **Applicability Rules** | Filter **Action required**. Open "How it is decided". **Record evaluation** → a new dated record. |
| 10 | Switch to **Nexatech** → **Activities & Tasks** | The seeded **Board Meeting**: steps 1–4 done, step 5 in progress, and "overdue" flags (the meeting date is in the past). Open it. |
| 11 | Try to complete step 7 | Refused: *"Finish the earlier step(s) first"*. Complete step 5, then 6. |
| 12 | **Start an activity** for BrightMed | Enter a meeting date → nine tasks appear with **due dates calculated** (notice 7 days before, minutes 15 and 30 days after). |
| 13 | Complete steps 1–3, then try step 4 | Refused: *needs a named person's confirmation*. **Request confirmation**; sign in as the manager and **Confirm** (you cannot confirm your own request unless administrator). |
| 14 | **Evidence → Documents & Evidence** | Drag a PDF in. It is fingerprinted and versioned (upload the same name again → version 2). **Download file** from its record. |
| 15 | Any table, e.g. **Capital & Members → Share Transfers** | Search, sort, **Export CSV**, open a record, **Archive** it, tick **Show archived**, **Restore** it. "Nothing is ever deleted." |
| 16 | **Activity Log** | Every change with person and time. Open any record's **History** for from → to values. |
| 17 | **Data → Export Excel** | One workbook, a sheet per record type, for this company only. |
| 18 | **Sign out**, sign in as **client@nexatech.co.in** | Only Nexatech; no "+ Add" buttons; no Administration group; directors/shareholders limited to Nexatech's own. "Row-level security plus the API's rules." |

## 10. Configuration reference (`.env`)

| Key | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | — | `bmp_owner`; migrations, and the web app's audit reader / company onboarding |
| `DATABASE_URL_APP` | — | `bmp_app`; all normal requests |
| `DATABASE_URL_ADMIN` | — | PostgreSQL administrator; only `setup_db.py` and the tests (remove after set-up if you prefer) |
| `DATABASE_URL_PRIVILEGED` | = `DATABASE_URL` | Optional separate login for the two privileged actions |
| `APP_ENV` | `development` | `production` requires `APP_SECRET_KEY` (≥ 32 chars), forces secure cookies and HSTS, hides `/api/docs` |
| `APP_SECRET_KEY` | (temporary) | Signs session cookies |
| `SESSION_MAX_AGE_SECONDS` | 28800 | Sign-in lifetime (8 h) |
| `COOKIE_SECURE` | false (true in production) | Send the cookie over HTTPS only |
| `STORAGE_DIR` | `storage` | Where uploaded files live |
| `MAX_UPLOAD_MB` | 25 | Upload size cap |
| `USERS_FILE` | `instance/users.json` | Credentials file |
| `ALLOW_PORTAL_SECRET_STORAGE` / `ALLOW_AADHAAR_STORAGE` | false | See §5.5 |
| `APP_ENCRYPTION_KEY` | — | Required when either flag above is true |
| `ENFORCE_TASK_CONFIRMATION` | true | Steps flagged "requires confirmation" need a confirmation |
| `DB_POOL_MIN` / `DB_POOL_MAX` | 1 / 10 | Connection pool size |
| `LOGIN_MAX_FAILURES` / `LOGIN_WINDOW_SECONDS` | 5 / 600 | Lock-out rule |

## 11. Testing — what the 307 tests prove

| File | Tests | Proves |
|---|---|---|
| `tests/` (original) | 19 | The Phase 1 database: no deletes, overlaps rejected, audit, row-level security, lookups, activity rules, traceability |
| `test_auth.py` | 11 | Sign-in, bad/unknown users, CSRF, lock-out, sign-out, inactive users, password change |
| `test_meta_coverage.py` | 9 | Every table/column/key/dropdown/view is exposed; every table has a screen |
| `test_isolation.py` | 142 | For every table: a client sees only their company; a manager only theirs; people/child tables, views, audit, documents, exports, cross-company references |
| `test_roundtrip_all_fields.py` | 67 | Every writable field of every writable table stores exactly; stale edits refused; archive/restore; validation messages; calculated columns can't be typed; audit trail |
| `test_workflows.py` | 35 | Activities (due dates, order, confirmation, roll-up), meetings, register, documents (hash, version, tamper, bad files), exports, paging/search, secrets policy, rules, overview, administration |
| `test_ui_assets.py` | 24 | Page and headers; no internet resources; the approved CSS is byte-identical; every JavaScript module parses and every import and element id resolves; no unescaped database text |

---

# PART D — Production readiness: what I recommend

## 12. Already in place
Authentication and sessions; CSRF; lock-out; layered company isolation; read-only users enforced; version-checked edits; no deletion; full audit trail; encrypted-field policy; safe uploads with integrity checks; input validation and friendly errors; request-size limit; structured request logging (method, path, status, time, user id — never data); health endpoint; security headers; secrets only in `.env`; configuration that refuses to start unsafely (production without a key, secrets enabled without an encryption key); tests with a throw-away database; a clean-install check.

## 13. Recommended before live use

**A. Must do before real client data goes in**

| # | Item | Why |
|---|---|---|
| 1 | **Serve over HTTPS** behind a reverse proxy (IIS/Nginx/Caddy) and set `APP_ENV=production`, a strong `APP_SECRET_KEY`, `COOKIE_SECURE=true`. | Credentials and data cross the network. The app refuses to start in production without the key. |
| 2 | **Backups**: daily `pg_dump` of `bmp` **plus** a copy of `storage/`, held on separate storage, with a **tested restore**. | Evidence files are outside the database; either alone is useless. (Technical Overview requires daily backups.) |
| 3 | **Run it as a service** (Windows service via NSSM / Task Scheduler, or systemd) with restart-on-failure and log files rotated. | `run_server.py` stops when the window closes. |
| 4 | **Give the application its own least-privilege database path** — see item B1. | Today two actions need the owner login inside the app. |
| 5 | **Decide the portal-password and Aadhaar columns** (recommend removing them from the database, or leaving them permanently off). | The client's brief forbids storing portal passwords; the columns still exist. Currently disabled by policy. |
| 6 | **Real user set-up**: create each person, grant per-company access, set passwords; remove or lock the demo accounts and `seed@system.internal`. | Demo accounts share a known password. |
| 7 | **Professional review** of the Board Meeting steps/durations and the 39 rules. | Draft legal content (also flagged in the Phase 1 guide). |

**B. Database changes I recommend (not made — you asked for the database to stay as is)**

| # | Change | Why it matters |
|---|---|---|
| B1 | A `SECURITY DEFINER` function for "onboard company" and a read-only audit view/function granted to `bmp_app`. | Removes the need for the owner login inside the web application. |
| B2 | Make the 13 views `security_invoker` (or add `company_id` filtering). | **Found by testing:** the views currently return other companies' rows to `bmp_app`; the API compensates, but a future tool querying the views directly would leak. |
| B3 | Row-level security (via parent joins) on the child tables with no `company_id`, and a policy for the shared people tables. | Same gap, same compensation in the API. |
| B4 | `FORCE ROW LEVEL SECURITY`, as the original guidelines asked. | Defence in depth. |
| B5 | Fix `activity.get_template_json`: it multiplies bindings/evidence when a step has several dependencies (it joins them without de-duplicating). | **Found while building the screens:** the API builds the template itself to avoid the duplicates. |
| B6 | `capital_event.reason_id` only accepts *increase* reasons (the decrease list can't be chosen). | The 5 "capital decrease" reasons in the client's lists are unusable. |
| B7 | A uniqueness rule on PAN (people and shareholders); a trigger validating `evidence_link.entity_type` against real tables (the guidelines asked for it; the API now does it). | Data quality. |
| B8 | Rule-review columns on `rule_definition` (reviewed by / on, "pending review"). | Promised in the Technical Overview; absent from the approved schema. |
| B9 | Permissions: `role_permission` is empty, so the roles carry no permissions today; access is by *company access level* + role name (admin). | Needed before the Phase 3 roles (Administrator / CS Professional / Viewer). |

**C. Operations and quality**

| # | Item |
|---|---|
| C1 | **Monitoring and alerts** on `/api/health`, disk space (`storage/`), database size, error log. Ship logs somewhere central. |
| C2 | **Server-side sessions** (so a single sign-in can be revoked) and **two-factor / single sign-on** for staff — today a session lasts until it expires or the user's access is changed. |
| C3 | **Multiple workers**: the lock-out counter is per process; with `--workers N` use the proxy's rate limiting or a shared store. |
| C4 | **Virus-scan uploads** and consider moving evidence to **object storage (MinIO)** as the Technical Overview plans. |
| C5 | **Browser and accessibility testing**: only Chrome was exercised; run a keyboard/screen-reader pass. |
| C6 | **Load and volume testing** with realistic data (hundreds of companies, tens of thousands of records); review indexes and add full-text search if needed. |
| C7 | **A user-management screen** that also sets passwords on creation (today: create the user in Administration, then set the password with the script or the "Set password" button). |
| C8 | **CI pipeline** (run the 307 tests on every change), **dependency pinning** and vulnerability scanning. |
| C9 | **Data-protection (DPDP Act) review**: retention policy, access reviews, the processor agreement for any future AI provider. |
| C10 | A **Docker image** — excluded by the Phase 1 guidelines; reconsider at the hosting review. |
| C11 | **Import** (the old UI's JSON import) and e-mail/notification sending — not built (the latter is Phase 2). |

## 14. Where the Technical Overview and the actual implementation differ (decision: the implementation wins)

| Topic | Overview says | Implemented |
|---|---|---|
| Sample activity | AGM pilot | **Board Meeting** (the approved database); AGM exists as a meeting type |
| Rules | 37 | **39** (the client's spreadsheet) |
| Individual accounts | Phase 2 | Built now (sign-in, per-company access); no SSO/MFA yet |
| Admin interface | Password-protected web screen | **Done** (this application) |
| Document storage | MinIO | Local folder (`storage/`), fingerprinted — swap later |
| Aadhaar / portal passwords | Not stored | Columns exist but **disabled by policy** (switchable) |
| Daily backups, server hosting | Phase 1 deliverable | **Not built** — an operations task (item A2) |
| Notices e-mailed, AI reading/drafting | Phase 2 | Not built (out of scope today) — the `ai_assisted` / `requires_confirmation` flags are shown and enforced where relevant |

## 15. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Terminal says *"The term 'DATABASE_URL=…' is not recognized"* | Those lines belong **inside the `.env` file**, not the terminal. |
| `password authentication failed for user "postgres"` | Wrong password in `DATABASE_URL_ADMIN`. |
| Sign-in says *Email or password is incorrect* | The person has no password yet (`python scripts/manage_users.py list`), or is inactive, or the e-mail differs from `core.app_user`. |
| *Too many failed sign-in attempts* | Wait 10 minutes (or restart the server). |
| Signed out every time the server restarts | `APP_SECRET_KEY` is empty; set it. |
| A page says *Open a company* | Pick a company from **All companies** first. |
| *"This record was changed by someone else"* | Close and reopen the record, then repeat your edit. |
| "+ Add" or edit boxes are missing | Your access to that company is read-only. |
| Upload refused | Allowed types only; 25 MB maximum. |
| `ModuleNotFoundError: fastapi` (or `psycopg_pool`…) | The environment is not active, or `pip install -r requirements.txt` was skipped. |
| Tests say *DATABASE_URL_ADMIN … must be set* | Add it to `.env`; the web tests need to create a throw-away database. |
| Port 8000 already in use | `python scripts/run_server.py --port 8080`. |

## 16. Known limitations
* Statutory registers, MR-3, audit note, exchange filings and events (old audit-checklist features) are not part of the new data model and were not rebuilt.
* The History/Activity Log filters narrow by company through the record's own `company_id` or its parent; a few child tables are matched through their parent, so very unusual cases may show on the parent only.
* Activity "start" currently covers the one seeded template; the screen will list further templates automatically when they are added under Administration.
* Two people editing the same record at once are protected (the second gets a conflict message); there is no live co-editing indicator.

## 17. Project map

| Path | Purpose |
|---|---|
| `app/main.py`, `config.py`, `db.py`, `errors.py`, `responses.py` | Application factory, settings, connection pools, error mapping |
| `app/schema_meta.py`, `registry.py` | Reads the live schema; labels, navigation, child tables and access scope per table |
| `app/crud.py`, `coerce.py`, `access.py` | The generic record engine, value conversion, who-can-see-what rules |
| `app/security.py`, `deps.py` | Passwords, lock-out, CSRF, the signed-in user |
| `app/routers/` | `auth`, `meta`, `entities`, `companies`, `people`, `meetings`, `views`, `activities`, `documents`, `audit` |
| `app/static/`, `app/templates/` | The UI: `dashboard.css` (unchanged), `app.css`, `scripts/*.js`, `dashboard.html` |
| `scripts/run_server.py`, `manage_users.py` | Start the server; manage sign-in passwords |
| `tests/api/` | The 288 web tests |
| `db/`, `scripts/setup_db.py`, `docs/` | The Phase 1 database and its documentation (unchanged by this work) |
| `BMP_UI_Backend_Implementation_Log.md` | What was done, found, fixed and left undone |

## AI in the Activities Dashboard

A small `app/ai/` package plus `app/routers/ai.py` (`/api/ai/*`) and `static/scripts/act-ai.js`. It is a fixed workflow
(route, one workflow, validate) built with LangGraph, not an autonomous agent: the model has no tools and never chooses what to
fetch. It reads and writes nothing in the database through its own code (a test enforces this); every save still goes through the
existing meeting endpoints under the signed-in person's session, with the existing validation, `updated_at` locking and audit
trail. Each endpoint is tied to one company, taken from the meeting on the server or checked against the person's access, and every
read filters by that company explicitly. See the README for settings and `docs/postman/` (folder "AI assistant") for the endpoints.
