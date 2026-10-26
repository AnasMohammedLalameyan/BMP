# BMP Compliance Platform — Phase 1 Database Guide

**Audience:** anyone — technical or not — who needs to understand, set up, run or demonstrate the Phase 1 prototype.
**Prepared:** 30 September 2026 · **Verified against:** PostgreSQL 18.3, pgvector 0.8.6, Python 3.12 on Windows 11.

> **How to read this guide.** Part A explains *what was built* in plain English. Part B explains the *requirements* and what Phase 1 does and does not cover. Part C is a *step-by-step manual* to set up, run and demonstrate it. Words in **bold** are explained the first time they appear, and there is a glossary at the end.
> Diagrams are written in *Mermaid*. They display automatically in VS Code (with a Mermaid preview extension), GitHub, and most Markdown viewers. If yours shows raw text, use the ASCII overview in section 2.

---

## 0. Status at a glance

| Question | Answer |
|---|---|
| Does the project work end to end? | **Yes.** From an empty PostgreSQL server it builds the database (11 migrations), loads demo data (5 seed files), passes **19 / 19 automated tests**, and runs the **12-item demonstration** without errors. Verified on a clean rebuild. |
| Were there problems? | **Yes — 6 defects and 3 environment problems were found and fixed** (details in `TEST_AND_FIX_LOG.md`). The most important: the vector-search extension was silently skipped; passwords were hard-coded in a setup script; and running the seed a second time duplicated data in ~20 tables. |
| Was the required demo data complete? | It was not. A follow-up added the missing rows (`db/seed/05_required_seed_completion.sql`): a >₹50 crore public company, two years of capital for every company, a share transfer, and independent-director terms. |
| Is anything still imperfect? | **Yes — see section 9.4.** The most important: users restricted to one company can still read shared "people" tables (directors, shareholders) and a few child tables of other companies. This matches the written guidelines but not the *spirit* of the client's isolation requirement, so it should be decided before Phase 2. Also see 9.3: one stored-secret column contradicts the client's instruction. |
| What is in Phase 1? | The database only: structure, rules, history protection, audit trail, company isolation, demo data (5 companies + 1 activity). No AI, no web screens, no API — by design. |

---

# PART A — The database explained

## 1. The big picture (plain English)

BMP is a company-secretarial firm. Its staff keep records for client companies: who the directors are, who owns shares, when meetings were held, which government forms were filed. Today much of this is typed by hand into spreadsheets.

The long-term goal is an **AI-assisted dashboard** that removes manual data entry. The client decided to build in this order:

1. **Phase 1 (this project): a trustworthy "system of record"** — a database that stores everything correctly, remembers history, and can't lose data.
2. Phase 2: an AI assistant that reads documents and sets up work (e.g. "set up the board meeting for Company X") — but only with a person's confirmation.
3. Phase 3: roll out to all clients, connect the existing dashboard.

Think of Phase 1 as building **a perfectly organised filing room with a security guard and a CCTV log** *before* hiring the assistant who will use it:

| Real-life idea | What the database does |
|---|---|
| Filing cabinets, one drawer per topic | **Tables** (55 for business data), grouped into four **schemas** (sections of the room) |
| A label that ties a folder to another folder | **Keys** — a director's appointment points to the company and to the person |
| Nothing is ever shredded | Deleting is blocked everywhere; records are **archived** instead |
| A sign-in sheet for every change | The **audit log** records who changed what, when, from which value to which value |
| Calculators, not handwriting | Ages, percentages, attendance are **calculated by views**, never typed |
| A guard who only lets you into your own client's room | **Row-level security** (RLS) |
| Rule book that can be edited | Compliance rules are **stored as data**, not buried in code |
| A recipe card for each task | The **Activity Database** — the step-by-step recipe for a task, e.g. a Board Meeting |

## 2. Architecture: one database, four sections

The client spoke of "two databases" (a *User Database* and an *Activity Database*). The design keeps them **inside one physical PostgreSQL database named `bmp`**, split into **schemas** (think: folders inside the database). This lets records in one section point safely at records in another, and lets changes succeed or fail together.

```mermaid
flowchart TB
  subgraph BMP["PostgreSQL database: bmp"]
    direction TB
    subgraph CORE["schema  core  —  the USER DATABASE  (55 tables + 13 views)"]
      C1["Company · People · Directors<br/>Shareholders · Capital · Meetings<br/>Filings · Loans · Documents<br/>Rules · Standard lists · Users"]
    end
    subgraph ACT["schema  activity  —  the ACTIVITY DATABASE  (6 tables)"]
      A1["Activity templates · Steps<br/>Step order · Data bindings<br/>Evidence requirements · Field registry"]
    end
    subgraph OPS["schema  ops  —  live work  (4 tables)"]
      O1["Activity instances · Task status<br/>Records touched by each task<br/>Confirmations"]
    end
    subgraph AUD["schema  audit  —  the change log  (1 table + helper functions)"]
      U1["audit.log  (append-only)"]
    end
  end
  ACT -- "step bindings name fields in" --> CORE
  OPS -- "an instance is for one company in" --> CORE
  OPS -- "an instance follows a template in" --> ACT
  CORE -. "every change is recorded in" .-> AUD
  ACT -. "every change is recorded in" .-> AUD
  OPS -. "every change is recorded in" .-> AUD
```

ASCII version of the same picture:

```
+---------------------------- database "bmp" -----------------------------+
|  core      = USER DATABASE  (companies, people, capital, meetings ...)   |
|  activity  = ACTIVITY DATABASE (templates, steps, field bindings)        |
|  ops       = live instances of activities + task status + confirmations  |
|  audit     = audit.log (who changed what) + safety-guard functions       |
+--------------------------------------------------------------------------+
   activity --describes work on--> core       ops --records work done on--> core
```

**Extensions** (add-ons switched on inside PostgreSQL):

| Extension | Why it is needed |
|---|---|
| `vector` (pgvector) | Lets the database store "embeddings" (numbers that represent meaning) so the future AI can search documents by meaning. Structure only in Phase 1 — the table stays empty. |
| `btree_gist` | Enables the "no overlapping dates" protection (see 5.1). |
| `pgcrypto` | Provides encryption for sensitive fields (Aadhaar, portal secrets). |

**Two database logins (roles)** — a safety feature:

| Role | Used for | Limits |
|---|---|---|
| `bmp_owner` | Building the database (migrations) and loading seed data. Owns all objects. | Not a superuser. |
| `bmp_app` | What the future application will use. | Can read, add and change rows. **Cannot delete or truncate.** Subject to company-isolation rules (RLS). |

## 3. Keys and constraints explained for non-technical readers

A **key** is how the database identifies records and connects them.

| Term | Plain-English meaning | Example in this project |
|---|---|---|
| **Primary key (PK)** | The unique "ID number" of one row. No two rows share it; it never changes. | Every table has `id` — a whole number the database hands out automatically (`bigint GENERATED ALWAYS AS IDENTITY`). Cannot be typed in by hand. |
| **Foreign key (FK)** | A column that *points at* a row in another table. The database refuses a pointer to something that does not exist. | `directorship.company_id` → `company.id`; `directorship.director_id` → `director.id`. |
| **Unique key (UK)** | A "business identifier" that must not repeat. | `company.cin` (the 21-character Company ID), `director.din` (8-digit Director ID), `app_user.email`. |
| **Composite unique key** | Uniqueness of a *combination*. | `company_financials (company_id, financial_year)` → one financial record per company per year. |
| **Check constraint** | A rule a value must satisfy. | Financial year must look like `2024-25`; a meeting must be `planned`, `held` or `cancelled`. (46 in total.) |
| **Exclusion constraint** | "No two rows may overlap in time." | Two appointments of the same person on the same company board can't overlap (see 5.1). (3 in total.) |
| **`ON DELETE RESTRICT`** | If something points at this row, the database refuses to delete it. | Used on **all 123 foreign keys**. No `CASCADE` (automatic mass delete) exists anywhere — a test proves it. |

### Conventions used everywhere
- Table names are **singular** and lower-case (`company`, not `Companies`), always written with the section name: `core.company`.
- Every business table has the same housekeeping columns: `created_at`, `updated_at` (kept up to date automatically), and `is_archived`, `archived_at`, `archived_by` (the "soft delete").
- Money is `numeric(18,2)` (exact, never floating-point); percentages `numeric(9,4)`; financial years are text like `2024-25`.
- **Dropdown values ("Standard Lists")** are not free text. They live in `core.lookup_list` / `core.lookup_value`, and other tables store the *ID* of the chosen value. A safety trigger checks that the value belongs to the right list (e.g. you can't put a "Meeting Type" into a "Designation" field). **19 lists / 102 values** were loaded from the client's spreadsheet; 23 columns are protected this way.

## 4. The data model, domain by domain

The complete, auto-generated diagrams for all 66 tables are in **`docs/ERD.md`**, and every column with its explanation is in **`docs/DATA_DICTIONARY.md`**. Below are the important parts in simplified form (crow's-foot notation: `||--o{` = "one … to many").

### 4.1 Company

```mermaid
erDiagram
  company ||--o{ company_rta : "registrar & transfer agent"
  company ||--o{ company_business_activity : "what it does"
  company ||--o{ company_relationship : "holding / subsidiary / associate"
  company ||--o{ company_financials : "one row per financial year"
  company {
    bigint id PK
    text cin UK "21-char Company ID"
    text name
    text pan
    date date_of_incorporation
    bigint category_id FK "Private / Public"
    bigint subcategory_id FK "Small, Subsidiary..."
    boolean is_listed
  }
  company_financials {
    bigint company_id FK
    text financial_year "2024-25"
    numeric turnover
    numeric net_worth
    int total_security_holders
  }
```

`company` is the anchor of the whole model: **almost everything hangs off `company.id`**. Facts that change every year (turnover, net worth, number of holders…) live in `company_financials`, one row per company per year — never as flat columns — so history is never overwritten.

### 4.2 People and roles — how history is kept (the "director" example)

A **person** is stored once (`director`, keyed by DIN — "Don't Ask Twice"). Each time that person serves on a company's board, that is a separate row in `directorship` (a **stint**). Job titles within a stint are separate rows in `directorship_role`.

```mermaid
erDiagram
  director ||--o{ directorship : "serves as"
  company  ||--o{ directorship : "has on its board"
  directorship ||--o{ directorship_role : "designation history"
  directorship ||--o{ independent_director_term : "term 1 / term 2"
  directorship ||--o{ director_declaration : "declarations on file"
  director ||--o{ director_residency : "per financial year"
  director ||--o{ director_kyc : "per financial year"
  director ||--o{ director_other_directorship : "seats elsewhere"
  director {
    bigint id PK
    text din UK "8 digits"
    text full_name
    date date_of_birth "age is NOT stored"
    bytea aadhaar_encrypted "encrypted, optional"
  }
  directorship {
    bigint id PK
    bigint company_id FK
    bigint director_id FK
    date start_date "appointment"
    date end_date "NULL = still serving"
    text cessation_reason
    boolean is_independent
  }
  directorship_role {
    bigint directorship_id FK
    bigint designation_id FK
    date start_date
    date end_date
  }
```

**Worked example from the seed data — Prashant Joshi (DIN 12340012):**

| Company | From | To | Meaning |
|---|---|---|---|
| BrightMed Pharma Limited | 2016-06-01 | 2021-05-31 | First stint — ended, reason "Resignation" |
| Nexatech Solutions Private Limited | 2021-04-01 | *(open)* | Serving on a different company at the same time — allowed |
| BrightMed Pharma Limited | 2023-07-01 | *(open)* | **Reappointed** after a gap — a *new row*, so the old stint stays visible |

Also: Arjun Kapoor is a *Director* at Nexatech (2015-03-12 → 2018-12-31) and a *Managing Director* from 2019-01-01 — a designation change kept as history in `directorship_role`.

### 4.3 Capital and members

```mermaid
erDiagram
  company ||--o{ share_class : "classes of shares"
  share_class ||--o{ capital_snapshot : "authorised / issued / paid-up per year"
  company ||--o{ capital_event : "split, consolidation, increase, decrease"
  shareholder ||--o{ shareholding : "holds"
  share_class ||--o{ shareholding : "of class"
  company ||--o{ shareholding : "in company"
  shareholder ||--o{ allotment : "receives"
  shareholder ||--o{ share_transfer : "transferor / transferee"
  allotment ||--o{ foreign_investment : "FC-GPR (issue)"
  share_transfer ||--o{ foreign_investment : "FC-TRS (transfer)"
  shareholding {
    bigint shareholder_id FK
    bigint share_class_id FK
    bigint number_of_shares
    date valid_from
    date valid_to "NULL = current holding"
  }
```

**How shareholding changes are tracked:** a change in holding never overwrites — it *closes* the old row (`valid_to`) and opens a new one. Example: Arjun Kapoor (HUF) held 400,000 shares until 2025-01-15 and 450,000 from 2025-01-16. The current position is "the row with `valid_to` empty". An exclusion constraint stops two overlapping rows for the same holder/class/folio.

### 4.4 Governance — meetings, committees, attendance

```mermaid
erDiagram
  company ||--o{ meeting : "holds"
  committee ||--o{ meeting : "committee meetings"
  meeting ||--o{ meeting_agenda_item : "agenda"
  meeting ||--o{ meeting_attendance : "who attended"
  directorship ||--o{ meeting_attendance : "as director"
  shareholder ||--o{ meeting_attendance : "as member"
  company ||--o{ committee : "has"
  committee ||--o{ committee_member : "members"
  directorship ||--o{ committee_member : "is member"
  company ||--o{ circular_resolution : "passes"
  circular_resolution ||--o{ circular_resolution_response : "each director's reply"
  company ||--o{ postal_ballot : "runs"
```

One `meeting` table covers Board, Committee, AGM and EGM meetings; the *type* comes from the Standard Lists. `meeting_attendance` has a check rule: an attendee of type *director* must point to a directorship, a *member* to a shareholder (verified by test).

### 4.5 Financial, legal and filings

`government_filing` (MCA forms with due date, filing date, SRN), `loan_deposit`, `remuneration` (with a **generated `total`** column), `penalty_action`, `yearly_disclosure`, `s185_loan`, `s186_transaction`, `s188_related_party_txn`, `odi` (+ `odi_step_down_subsidiary`), `ecb`, and `portal_access` (portal name + username; the optional secret is encrypted — see 5.7). All point at `company` (and, where relevant, at `directorship` or `meeting`).

### 4.6 Documents and evidence (requirement FR-3)

```mermaid
erDiagram
  document_type ||--o{ document : "kind of file"
  company ||--o{ document : "belongs to"
  document ||--o{ evidence_link : "supports"
  task_instance ||--o{ evidence_link : "evidence for a task"
  document ||--o{ document_chunk : "text pieces + vector"
  evidence_link {
    bigint document_id FK
    text entity_type "e.g. meeting, directorship"
    bigint entity_id "which record"
    bigint task_instance_id FK "optional task"
  }
  document_chunk {
    bigint document_id FK
    int chunk_no
    text content
    vector embedding "1536 placeholder size"
  }
```

`document` stores file details (name, storage path, type, SHA-256 fingerprint, version, extracted data). `evidence_link` is the **durable link** from a document to *any* record (a meeting, a director…) or to a task. `document_chunk` (with an HNSW search index) is ready for Phase-2 AI search and is empty now. **The vector size 1536 is a placeholder** — it must be confirmed against the embedding model chosen in Phase 2.

### 4.7 Users, roles and access

`app_user` (email, name, role, active flag — **no passwords**; login belongs to Phase 2), `role`, `permission`, `role_permission`, and `user_company_access` (which user may see which company, at level read/write/admin). Seeded users:

| User | Role | Company access |
|---|---|---|
| admin@bmpco.in | admin | all 5 companies (admin) |
| manager@bmpco.in | manager | companies 2, 3, 4 (write) |
| client@nexatech.co.in | client | company 1 only (read) |
| seed@system.internal | — | none (used only to load seed data) |

### 4.8 Reference data and the rules engine

- `lookup_list` / `lookup_value` — the 19 dropdown lists (company category, designation, meeting type, share class, filing status…).
- `document_type` — 17 kinds of documents (Board Notice, Board Agenda, Draft/Signed Minutes, Form MGT-7, Form ADT-1…).
- `rule_definition` — the client's **39 "When Something Becomes Required" rules** (e.g. CSR spending, Audit Committee, Woman Director), each with legal reference, who is responsible and how often.
- `rule_evaluation` — the result of applying a rule to a company for a year (applies? met / pending / action required / not applicable). Six example rows are hand-entered; **the automatic rule engine is Phase 2+**.

### 4.9 Activity database and operations (requirement FR-6)

```mermaid
erDiagram
  activity_template ||--o{ step_template : "has ordered steps"
  step_template ||--o{ step_dependency : "must follow"
  step_template ||--o{ step_data_binding : "reads / writes fields"
  entity_field_registry ||--o{ step_data_binding : "field is registered"
  step_template ||--o{ step_evidence_requirement : "needs documents"
  document_type ||--o{ step_evidence_requirement : "of type"
  activity_template ||--o{ activity_instance : "used by"
  company ||--o{ activity_instance : "work for one company"
  activity_instance ||--o{ task_instance : "one task per step"
  step_template ||--o{ task_instance : "task follows step"
  task_instance ||--o{ task_record_link : "records touched"
  task_instance ||--o{ evidence_link : "evidence attached"
  app_user ||--o{ confirmation : "requested / confirmed by"
```

| Table | In plain words |
|---|---|
| `activity_template` | The *recipe*: e.g. `BOARD_MEETING` version 1, status *draft*, never reviewed yet. |
| `step_template` | One step of the recipe: order, type (data entry, document, notification, approval, check, filing, manual), who is responsible, deadline rule ("7 days before the meeting date"), whether AI may assist, whether a person must confirm. |
| `step_dependency` | "Step 4 can only start after step 3" — forms a chain; a trigger rejects cross-recipe links, cycles and a step depending on itself. |
| `entity_field_registry` | A catalogue of **769 fields** of the User Database, built automatically from the database itself. A step can only refer to a registered field. |
| `step_data_binding` | "Step 1 *writes* `meeting.meeting_date`; step 3 *reads* `company.name`." A trigger forbids *writing* to calculated fields. |
| `step_evidence_requirement` | "Step 3 needs a Board Meeting Notice and Agenda." |
| `activity_instance` | A live run of a recipe for one company (pins the template version). |
| `task_instance` | One task per step, with status (not started / in progress / completed / overdue / skipped) and a **due date computed from the meeting date**. |
| `task_record_link` | Exactly which records a task read or wrote — the "association back to the User Database". |
| `confirmation` | Structure for "no change or email without a named person's confirmation" (FR-13). Table only; enforcement is Phase 2. |

**The sample activity — Board Meeting** (durations are sensible defaults from Companies Act s.173 / Secretarial Standard SS-1 and **must be verified by a BMP professional**):

| # | Step | Type | Deadline | Reads / writes |
|---|---|---|---|---|
| 1 | CONFIRM_DATE_VENUE | data entry | — | writes meeting date, start time, venue, venue mode |
| 2 | PREPARE_AGENDA | document | — | reads meeting number; writes agenda items |
| 3 | DRAFT_NOTICE | document | 7 days before meeting | reads company name, directorships, meeting date; evidence: Notice + Agenda |
| 4 | SEND_NOTICE | notification | 7 days before | reads director e-mail; **AI-assisted; needs confirmation** |
| 5 | CONDUCT_MEETING | manual | on meeting date | writes meeting status |
| 6 | RECORD_ATTENDANCE | data entry | on meeting date | writes attendance |
| 7 | DRAFT_MINUTES | document | 15 days after | reads agenda, attendance; evidence: Draft Minutes |
| 8 | SIGN_MINUTES | approval | 30 days after | evidence: Signed Minutes; needs confirmation |
| 9 | UPDATE_REGISTERS_AND_FILINGS | check | — | writes government filing if applicable |

Steps run as a chain 1→2→…→9. The function `activity.get_template_json('BOARD_MEETING')` returns the whole recipe as one JSON document (the shape a future AI tool will fetch), and `ops.instantiate_activity(...)` creates a run with all task due dates worked out — plain SQL, no AI.

**The seeded run:** a Board Meeting for *Nexatech Solutions Private Limited* dated 15 April 2025 — steps 1–4 completed (with linked records and a dummy evidence document), step 5 in progress, steps 6–9 not started. Due dates: notice 8 Apr, minutes drafted 30 Apr, signed 15 May.

## 5. Built-in protections (how the database defends itself)

### 5.1 History is preserved — "no overlapping dates"
`directorship`, `directorship_role` and `shareholding` each have an **exclusion constraint** using date ranges. The same person can't be on the same board twice *at the same time*, but can return *after a gap*. (Tests: overlap rejected; gap re-appointment accepted.)

### 5.2 Data is never destroyed
- **Triggers on every table** raise an error on `DELETE` and on `TRUNCATE`.
- `bmp_app` isn't even granted those privileges.
- "Removing" means setting `is_archived = true` (plus who and when). The row stays.
- `audit.log` is itself append-only: updates and deletes on it are blocked.
- The only way to wipe data is to drop and recreate the whole *development* database (`setup_db.py --reset`, clearly marked dev-only).

### 5.3 Every change is attributable — the audit trail
Before any write, the application must announce who it is: `SET app.current_user_id = <user id>`. If it doesn't, **the write is rejected** ("app.current_user_id must be set…"). Every insert/update then writes a row to `audit.log`: table, record, operation, **actor**, time, and the **old and new values as JSON**. The seed run alone produced 398 audit rows. `bmp_app` cannot read `audit.log` directly.

### 5.4 Calculated values are never stored
Age, shareholding %, top-10 flag, attendance %, independent-director years served, filing overdue days are produced by **views** (saved queries), so they can't go stale or be typed wrongly. The one stored-but-generated value, `remuneration.total`, is a *generated column* — the database computes it and refuses manual writes.

| View | What it calculates |
|---|---|
| `v_current_directors` | Who is serving *now*, with current designation |
| `v_director_history` | Every stint, with duration in months and whether current |
| `v_director_age` | Age in years from date of birth |
| `v_shareholding_percent` | % held per holder, by company and share class (current holdings only) |
| `v_top10_shareholders` | Holders ranked within company and class |
| `v_company_shareholder_counts` | Number of current shareholders |
| `v_director_attendance_summary` | Board meetings entitled vs attended, %, attended last AGM |
| `v_committee_attendance_percent` | Committee attendance % |
| `v_independent_director_years` | Total years served as independent director |
| `v_s186_running_total` | Running total of s.186 loans/investments |
| `v_filings_overdue` | Filings past due and not filed, with days overdue |
| `v_rule_resident_director`, `v_rule_woman_director` | Two *examples* of rules computed from data instead of hard-coded |

### 5.5 Company isolation (Row-Level Security)
On the **32 tables that carry a `company_id`** (and on `company` itself) the database only shows rows for companies listed in the user's `user_company_access` entries. In the demo, the *client* user sees 1 company and the *admin* sees 5. It applies to the `bmp_app` login — the owner login bypasses it (needed for building and seeding). **Important limitation:** see 9.4.

### 5.6 Rules stored as data
Compliance rules are rows in `rule_definition`, not `if company == "X"` code, so they can be reviewed and changed without touching software. The seeded rules carry the legal section and responsible person from the client's sheet; review status is a Phase-2/3 item.

### 5.7 Secrets
- No passwords are stored anywhere in the data model (`app_user` has no password column).
- Aadhaar (`director.aadhaar_encrypted`) and portal secrets (`portal_access.secret_encrypted`) are optional encrypted columns; the encryption key would be supplied at run time, never stored. The seed data contains none.
- Database login passwords live in `.env` only (not in code). *Note: the shipped `.env` holds development-only passwords; replace them and keep the file out of version control.*

## 6. What the demo data contains

| Company | Type | Highlights |
|---|---|---|
| **Nexatech Solutions Private Limited** (id 1) | Small private company | Directors Arjun Kapoor (Director → Managing Director), Sunita Rao (independent), Prashant Joshi; shareholding change in Jan 2025; the seeded Board Meeting activity; 12 holders |
| **BrightMed Pharma Limited** (id 2) | Public company, ₹1.5 crore paid-up | The **resign-and-reappoint** director; woman independent director (Nalini Sharma, with first and second independent-director terms → 8.74 years served); a non-resident (Polish) director; Audit Committee; 3 board meetings + 1 AGM with attendance and agendas; auditor; related-party transaction; overdue filing; **a share transfer** (Rajan Patel → General Public - A, 50,000 shares on 22 Aug 2024, approved at BM-2) that changed the holdings from 900,000/600,000 to 850,000/650,000 (56.67% / 43.33%) |
| **Greenfield Industries Limited** (id 3) | **Large public company, ₹60 crore paid-up** | 4 directors incl. a woman independent director; net worth ₹105 crore; 920 holders; equity share class and two years of capital snapshots |
| **Skyward Technologies Limited** (id 4) | Listed public company | **16,500 security holders**; ₹45 crore paid-up; SRC-committee rule example |
| **Indovance Fintech Private Limited** (id 5) | Subsidiary of a foreign company | **Foreign shareholder** Alpine Capital GmbH; FC-GPR foreign-investment record |

Totals loaded: 5 companies · 12 directors · 18 board stints (9 designation records, 2 independent-director terms) · 5 shareholders / 9 holding rows (3 closed, 6 current) · 2 allotments · 1 share transfer · 1 foreign-investment (FC-GPR) record · 20 capital snapshots (2 financial years × opening/closing × 5 companies) · 5 meetings (4 held, 1 planned) with 12 attendance rows and 15 agenda items · 1 circular resolution · 4 government filings (2 overdue per the view) · 6 rule evaluations · 1 activity template (9 steps, 20 field bindings, 4 evidence requirements) · 1 activity instance (9 tasks). All names, CINs, DINs and PANs are **fictional**. See 9.4 #3 for what is still *not* seeded.

## 7. Automated tests — what they prove (19)

| Test file | Proves |
|---|---|
| `test_no_delete_and_audit.py` (5) | Deletes and truncates are blocked on every business table; audit log can't be edited; writes without a user are rejected; audit rows capture old and new values |
| `test_overlap_constraints.py` (4) | Overlapping stints, overlapping designations, overlapping holdings are rejected; re-appointment after a gap works |
| `test_rls_isolation.py` (2) | Client sees one company in *every* company-scoped table; admin sees all |
| `test_lookups_and_constraints.py` (3) | A value from the wrong dropdown list is rejected; **no foreign key uses CASCADE/SET NULL/SET DEFAULT**; financial-year format enforced |
| `test_activity_ops.py` (4) | Instantiating an activity creates the right tasks and due dates; writing to a calculated field is rejected; dependency cycles rejected; the JSON template has the expected shape |
| `test_traceability.py` (1) | All 292 spreadsheet fields are mapped in `docs/FIELD_TRACEABILITY.md` |

Additional checks run manually during this review (not yet in the test suite): meeting-attendance type/FK check, foreign-investment "exactly one reference" check, cross-template and self-dependency rejection, generated-column write rejection, and seed re-run safety (row counts of all tables compared before and after a second `--seed`).

---

# PART B — Requirements: what is and is not met

## 8. Sources and how conflicts were treated
`guidelines.md` (the master prompt) states that it wins over the draft requirement documents when they disagree. The client spreadsheet is the source of truth for fields. Traceability: **all 292 field rows across the 26 data sheets are mapped** to a column, view, rule or lookup (`docs/FIELD_TRACEABILITY.md`; `scripts/check_traceability.py` passes).

## 9. Coverage

### 9.1 Functional requirements (BMP_Project_Requirements_v1_0)

Legend: ✅ met in Phase 1 · 🟡 partly / structure only · ⏭ later phase by design · ❌ gap

| Req. | Summary | Status | How Phase 1 addresses it |
|---|---|---|---|
| Principle | System of record first, AI second | ✅ | Whole of Phase 1 |
| FR-1 | Obligations defined as statutory processes | 🟡 | 39 rules with law references (`rule_definition`) + `activity_template.obligation_ref`. Only one process (Board Meeting) modelled, and it is *draft* pending professional review |
| FR-2 | Tasks are concrete steps against entities; design data model from tasks | ✅ | `step_template` + `step_data_binding` (20 bindings) declare exactly which fields each step reads/writes |
| FR-3 | Evidence stored with a durable link to task/entity/person | ✅ | `document`, `document_type` (17), `evidence_link` (to any record *and* to a task), SHA-256 + version. One dummy document seeded |
| FR-4 | API / data-access layer | ⏭ | Explicitly excluded from Phase 1 by the guidelines (no FastAPI). Database-side groundwork exists: `get_template_json`, `instantiate_activity`, roles, RLS |
| FR-5 | User Database from the client's field list | ✅ | 55 `core` tables cover all 26 data sheets; 292/292 rows traced |
| FR-6 | Activity Database: tasks/steps with association back to User Database records | ✅ | Field-level (`step_data_binding`) and record-level (`task_record_link`) associations |
| FR-7 | AI parses uploaded file into fields, person checks | ⏭ | Prepared: `document.extracted_data` (JSON), `ai_assisted` flag on steps |
| FR-8 | AI carries out a task from a short prompt | ⏭ | Prepared: machine-readable template JSON, input schema, `instantiate_activity` |
| FR-9 | Send resulting communications automatically | ⏭ | Prepared: SEND_NOTICE step flagged AI-assisted + needs confirmation. No email code |
| FR-10 | Each company isolated | 🟡 | Database-level RLS on 32 company-scoped tables + `company` (tested). **Gap:** shared master/child tables — see 9.4. AI-context isolation is Phase 2 |
| FR-11 | AI context/history preserved between sessions | ⏭ | Not started (audit log and ops tables give the base) |
| FR-12 | Limit data exposed to AI provider | ⏭ | Prepared: no plaintext secrets; sensitive fields encrypted. Provider controls are Phase 2 |
| FR-13 | No change/communication without named person's confirmation, built into the system | 🟡 | `ops.confirmation` table and `requires_confirmation` flags exist; **enforcement is not built** (Phase 2) |
| FR-14 | Retain supplied dashboard, connect later | ⏭ | Not in Phase 1 |
| FR-15 | Web-based, portable, multi-organisation later | ⏭ | Database is portable (plain PostgreSQL, numbered SQL files); company-level isolation is a prerequisite for multi-organisation use |
| Data §5 | Seed 5 companies + 1 activity, fully populated and related | ✅ / 🟡 | 5 companies and 1 activity in place. Not every company is equally "fully" populated (see 9.4) |

### 9.2 Technical Overview — Phase 1 deliverables

| Deliverable in the Technical Overview | Status | Note |
|---|---|---|
| Complete database structure (all categories in §3.2) | ✅ | All 12 categories present |
| Audit trail from day one | ✅ | Old/new values, actor, append-only |
| Standard lists ("19 lists") | ✅ | 19 lists, 102 values |
| Rules loaded ("37 rules") | ✅ | **39** rules loaded — the client spreadsheet contains 39; the overview's "37" is out of date |
| "All calculated fields working" | ✅ | 13 views. Notice periods are step deadlines in `ops.task_instance` rather than a view |
| 5 clients fully loaded (directors, shareholders, KMPs, auditors, committees, capital) | 🟡 | Sample-level depth only: 1 auditor and 1 committee in total; capital for all 5 companies over 2 years; shareholder rows exist for 3 companies (the two large public companies are represented by their `total_security_holders` count) (see 9.4 #3) |
| **AGM** fully set up with tasks and evidence | ❌ (by design) | The guidelines replaced the AGM pilot with a **Board Meeting** as the single sample activity. An AGM *meeting record* with attendance exists for BrightMed |
| Rules "evaluated per company" | 🟡 | Rule data present; only 6 hand-entered evaluations; engine logic out of scope |
| Admin interface (password-protected web screen) | ❌ (out of scope) | Excluded by guidelines; pgAdmin can be used to browse for the demo |
| Data-access layer / API | ⏭ | See FR-4 |
| Daily backups | ❌ | Not implemented (operational task, not code) |

### 9.3 Where the documents disagree — the decision implemented for each

**Precedence rule used (stated in `guidelines.md` §1):** the requirement documents are *drafts, not signed off*; where they conflict with `guidelines.md`, the guidelines win and the conflict is logged. The client's xlsx is the primary source for *which fields exist*. Everything below follows that rule, and "Implemented" describes what is actually in the database today.

| # | Topic | What the sources say | **Decision implemented** | Assessment / recommendation |
|---|---|---|---|---|
| 1 | **Sample activity** | Technical Overview: the pilot is the **AGM** (11 evidence document types). `guidelines.md` §7.3: seed **one** activity, the **Board Meeting** (9 steps). | **Board Meeting.** Template `BOARD_MEETING` v1 (draft) with 9 steps, 20 field bindings, 4 evidence requirements. AGM exists only as a *meeting type* (BrightMed has one held AGM with attendance); there is **no AGM activity template** and only the 2 AGM document types (notice, minutes) are seeded. | Consistent with the guidelines. Confirm with BMP whether the AGM should be the Phase 2 pilot; the structure supports adding it as a second template without schema changes. |
| 2 | **Number of rules** | Overview says **37** rules; the xlsx sheet "When Something Becomes Required" numbers **1–39**; guidelines say "about 39". | **39** rules loaded from the xlsx (`core.rule_definition`). | The overview figure is out of date; 39 is right. |
| 3 | **Portal passwords** | Xlsx Read Me: *"One thing NOT to build — do not store portal or website passwords"*; xlsx Portal Access row 5: *"Never store this in the dashboard"*. Overview: *"There is no password field."* Guidelines §5.6: keep an optional **encrypted** `secret_encrypted` column ("or not at all", §2.10). | `core.portal_access` stores portal name, username, holder, notes **plus** an optional `secret_encrypted` column. It is **empty** (0 rows have a value) and no seed row uses it. `app_user` has no password column. | **This is the one decision I would reverse.** The column contradicts the client's explicit instruction in two documents. Recommend dropping `secret_encrypted` (a one-line migration). Not changed because it needs your say-so. |
| 4 | **Aadhaar numbers** | Overview: *"Aadhaar numbers are not stored."* Xlsx Directors row 5: Aadhaar is *Optional — sensitive; check whether it should be stored at all, or only referenced*. Guidelines §5.3: encrypted `bytea` **or last 4 digits only**. | `core.director.aadhaar_encrypted` (encrypted, optional, nullable). **0 rows** contain a value. | Acceptable as a safe placeholder, but it still stores personal data if someone fills it. Recommend removing it or replacing it with "last 4 digits" once BMP decides. |
| 5 | **Docker** | Overview glossary defines Docker as the packaging method; guidelines §2: **no Docker**. | No Docker anywhere. Plain local PostgreSQL + Python scripts. | Fine for Phase 1. Revisit at hosting review (Phase 3). |
| 6 | **ODI and ECB** | Overview: *"ODI compliances and ECB: out of scope, as agreed."* Guidelines §5.6 and the xlsx: implement every field of the ODI and ECB sheets. | Tables `odi`, `odi_step_down_subsidiary` and `ecb` **are built** (fields traced 100%) but hold **no data**. | Harmless and avoids a later migration. Confirm the client is happy with tables existing early. |
| 7 | **What Phase 1 delivers** | Overview Phase 1: password-protected **admin interface**, a **data-access layer**, **daily backups**. Requirements FR-4 wants an API. Guidelines §1/§14: *no front-end, no FastAPI*; database and demo only. | **None of the three is built.** Database-side groundwork exists (functions `get_template_json`, `instantiate_activity`; roles; RLS). Browsing is done with pgAdmin/psql. | Big scope difference — make sure the client knows Phase 1 as built is *database-only*. Backups are an operations task still to be scheduled. |
| 8 | **User accounts** | Overview: individual accounts are **Phase 2**. Guidelines §5.8: build `app_user`, `role`, `permission`, `user_company_access` now (no passwords). | The tables exist and are seeded with 4 users (admin, manager, client, seed). Nobody can log in; login is a later-phase job. `role_permission` is empty. | Structure now, behaviour later. Decide the real permissions (Overview item 8) before Phase 3. |
| 9 | **Rule review tracking** | Overview §3.4: each rule records **when last reviewed and by whom**; every rule is **"pending review"** until a professional signs it off. Guidelines §5.1 defines `rule_definition` with **no review columns** (only `is_active`). | Followed the guidelines: **no review status is stored** for rules. (The Board Meeting *template* does have `reviewed_by` / `reviewed_on`, left empty.) | **Gap against the Overview.** Recommend adding `reviewed_by`, `reviewed_on`, `review_status` to `rule_definition` before anyone relies on the rules. |
| 10 | **Filing status** | Overview: filing status is **calculated from the dates**. Guidelines §5.6: `government_filing.status_id` is a **stored** lookup (Filed on time / Filed late / Not yet filed…). | Both: the stored status column exists, and `v_filings_overdue` *calculates* overdue days from the dates. | Stored status can disagree with the dates. Consider deriving it fully in a view in Phase 2. |
| 11 | **Matching people/companies (DIN/PAN/CIN)** | Overview: people matched on **DIN or PAN**, companies on **CIN**; similar names prompt "same entity?". | **DIN** and **CIN** are unique keys (duplicates rejected). **PAN is not unique** (director or shareholder). Similar-name prompting is application behaviour → Phase 2. | Consider a partial unique index on PAN where present. |
| 12 | **Audit trail "cannot be altered by anyone, including administrators"** | Overview §3.5. | Updates/deletes on `audit.log` are blocked by triggers for everyone, and the application role has no read access. A PostgreSQL *superuser* could still disable triggers. | Adequate for Phase 1; protect superuser access and consider write-once storage later. The AI-action and notification entries the Overview mentions belong to Phase 2. |
| 13 | **Document storage** | Overview: files stored in a separate document store (MinIO). | Only file *metadata* is stored (`document.storage_path`, hash, version, type). No file store. | Phase 2/3. |
| 14 | **Hosting** | Requirements: local vs cloud undecided, keep it portable. Guidelines: **local PostgreSQL 16+**, no SSH, no SQLite fallback. | Local PostgreSQL, plain numbered SQL, configuration via `.env`. | Portable as required. |

**In short:** the guidelines were followed wherever they conflict; the only implemented choices I disagree with are #3 (stored-secret column against the client's wording) and, to a lesser extent, #9 (no rule-review tracking).

### 9.4 Known limitations and recommendations
| # | Limitation | Why it matters | Recommendation |
|---|---|---|---|
| 1 | **Shared tables are not company-isolated.** A client-level user (1 company) can still read *all* 12 directors' names, PANs, e-mails and birth dates, all shareholders, and `meeting_attendance`, `directorship_role`, `committee_member` rows of *other* companies. These tables have no `company_id`, and the guidelines only require RLS where one exists. | FR-10 says one company's data must never be exposed while working on another's. | Before Phase 2, add RLS policies on those child tables (join through their parent) and decide how the shared "person" master should be restricted. |
| 2 | RLS is `ENABLE`d but not `FORCE`d | Guidelines ask for FORCE. Not needed while the app connects as `bmp_app`, but the owner role can read everything. | Never let the application connect as `bmp_owner`. |
| 3 | **Seed data still thin outside the §8 checklist.** (The §8 items — >₹50 crore company, two years of capital, share transfer, independent-director terms — were added in `05_required_seed_completion.sql`.) Still empty: `role_permission`, `director_declaration`, `director_kyc`, `company_rta`, `company_relationship`, `company_business_activity`, `capital_event`, `yearly_disclosure`, `portal_access`, `odi`, `ecb`; no FC-TRS example; only one auditor and one committee; BrightMed/Greenfield CINs start with `L` (listed) but are flagged unlisted; Prashant Joshi's Nexatech stint has no designation row | Structure is complete and tested; these tables just have nothing to show | Add rows if a particular table must be demonstrated |
| 4 | `foreign_investment` requires exactly one of allotment/transfer but does not check it matches the type (FC-GPR ↔ allotment, FC-TRS ↔ transfer) | Data-quality gap | Add a check tying type to reference |
| 5 | Board Meeting template is *draft*, durations unverified | Legal substance | Professional review; then set `reviewed_by/on` and status `active` |
| 6 | Vector size 1536 is a placeholder | Wrong size breaks embedding loads | Confirm with the Phase-2 embedding model |
| 7 | `IMPLEMENTATION_LOG.md` and `README.md` (asked for in the guidelines) do not exist; `progress_summary.md` is out of date | Documentation debt | This guide plus `TEST_AND_FIX_LOG.md` replace them; consider adding a short README |

---

# PART C — Set up, run and demonstrate

## 10. Before you start: what you need

| Requirement | Version tested | Notes |
|---|---|---|
| Windows 10/11 (macOS/Linux also work — see notes) | Windows 11 | |
| **PostgreSQL** 16 or newer | 18.3 | With its "postgres" administrator password to hand |
| **pgvector** matching your PostgreSQL version | 0.8.6 for PG 18 | Not included with PostgreSQL — see step 2 |
| **Python** 3.10+ | 3.12 | Tick "Add Python to PATH" when installing |
| Free disk / RAM | ~50 MB / minimal | Database is ~15 MB |

No Docker, no internet connection at run time, no cloud account.

## 11. Set-up, step by step (Windows / PowerShell)

### Step 1 — Install PostgreSQL
1. Download the installer from <https://www.postgresql.org/download/windows/> and run it.
2. Accept defaults (port **5432**). When asked, **set a password for the `postgres` user and write it down.**
3. Confirm the service is running: open PowerShell and run
   ```powershell
   Get-Service | Where-Object { $_.Name -match 'postgres' }
   ```
   Status should be `Running`.

### Step 2 — Install pgvector (the one tricky step)
pgvector does not ship with PostgreSQL and the official project provides **no Windows installer**. Choose one:

- **Option A — build it (recommended for production/security).** Install "Visual Studio Build Tools" with *C++ support*, open *x64 Native Tools Command Prompt* **as Administrator**, then:
  ```bat
  set "PGROOT=C:\Program Files\PostgreSQL\18"
  cd %TEMP%
  git clone --branch v0.8.6 https://github.com/pgvector/pgvector.git
  cd pgvector
  nmake /F Makefile.win
  nmake /F Makefile.win install
  ```
  (Change `18` to your PostgreSQL version.)
- **Option B — use a pre-built package (what was done for this review).** A community build exists at `github.com/andreiramani/pgvector_pgsql_windows` (release `0.8.6_18`, file `vector.v0.8.6-pg18.zip`, ~170 KB). It is **third-party** — review it against your IT policy first. Copy `lib\vector.dll` to `C:\Program Files\PostgreSQL\18\lib\` and the contents of `share\extension\` to `C:\Program Files\PostgreSQL\18\share\extension\` (needs Administrator rights).

Check it worked (replace the password prompt as needed):
```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -c "SELECT name, default_version FROM pg_available_extensions WHERE name='vector';"
```
You must see one row containing `vector`. If not, stop here — the project will refuse to build without it (by design; earlier it silently skipped it, which was fixed).

### Step 3 — Open the project folder
```powershell
cd "C:\Users\<you>\Desktop\BMP\BMP Phase 1 v 2"
```

### Step 4 — Create a fresh Python environment
The `venv` folder that came with the project was created on another computer and **does not work here**. Delete it and create your own:
```powershell
Remove-Item -Recurse -Force .\venv
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If PowerShell refuses to run the activate script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.
Your prompt should now start with `(venv)`.

### Step 5 — Configure `.env`
`.env` (in the project folder) tells the scripts how to log in. Copy `.env.example` to `.env` if it's missing, then make it look like this — **replace the three passwords with your own choices**:
```ini
# Login the migrations use (will be created automatically):
DATABASE_URL=postgresql+psycopg://bmp_owner:CHOOSE_A_PASSWORD@localhost:5432/bmp
# Login the application uses (will be created automatically):
DATABASE_URL_APP=postgresql+psycopg://bmp_app:CHOOSE_ANOTHER@localhost:5432/bmp
# Your PostgreSQL administrator login (only needed by the set-up script):
DATABASE_URL_ADMIN=postgresql+psycopg://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/postgres
```
Rules: no spaces around `=`; if a password contains `@ : / # %` write it URL-encoded (e.g. `@` → `%40`). Remove `DATABASE_URL_ADMIN` after set-up if you don't want the admin password lying in a file.

### Step 6 — Build the database and load demo data
```powershell
python scripts/setup_db.py --seed
```
What happens: it (1) creates the two logins and the empty `bmp` database, (2) switches on the three extensions, (3) runs the 11 numbered SQL files in `db/migrations/`, recording each in `schema_migrations`, (4) loads the 5 seed files, recording each in `schema_seeds`. **Expected output (abridged):**
```
  Creating role 'bmp_owner'...   Creating role 'bmp_app'...   Creating database 'bmp'...
  Extensions vector, btree_gist, pgcrypto present.
  [run ] 001_extensions_schemas_roles.sql ... OK
  ... (to) 011_triggers_rls_grants.sql ... OK
Migrations: 11 applied.
  [seed] 01_lookups_rules_doctypes.sql ... OK   ... 05_required_seed_completion.sql ... OK
Done.
```
It is safe to run again: applied migrations **and applied seed files are skipped** (`[skip] … already seeded`), so nothing is duplicated. (Verified: after a second `--seed` the row count of every table is identical.) To reload the demo data from scratch, use the reset command below.

To start again from nothing (**development only — it deletes the whole database**):
```powershell
python scripts/setup_db.py --reset --seed
```

## 12. Verify: run the tests
```powershell
python -m pytest -v
```
Expected last line: **`19 passed`** (takes a few seconds). Any red `FAILED` line means something is wrong — see Troubleshooting.

## 13. Run the demonstration
```powershell
python scripts/run_demo.py
```
It prints twelve numbered sections; the last line is `DEMO COMPLETE — All 12 items demonstrated successfully.` (The script now stops with an error if any item fails.) To save the output: `python scripts/run_demo.py > demo_output.txt`.

**Alternative for a live SQL walk-through:** open `demo/demo_queries.sql` in pgAdmin's Query Tool (or `psql -U bmp_owner -d bmp -f demo/demo_queries.sql`). Four statements are **meant** to fail (overlap, delete, truncate, write-without-user) — that is the point of the demo. Run the "Isolation" section as `bmp_app`.

### Browsing visually with pgAdmin 4 (installed with PostgreSQL)
1. Open pgAdmin → *Add New Server*: Host `localhost`, Port `5432`, Database `bmp`, Username `bmp_owner`, Password = the one from `.env`.
2. Expand *Databases → bmp → Schemas → core → Tables* to see all tables. Right-click a table → *View/Edit Data → All Rows*.
3. Right-click database `bmp` → *ERD For Database* to see an interactive relationship diagram.

## 14. Demonstration script (what to say and show)

Suggested 20-minute flow. Command: `python scripts/run_demo.py` (each item below is a numbered section of the output).

| # | Show | Say (in plain words) |
|---|---|---|
| 1 | **Structure** | "One database, four sections: 55 business tables, 6 activity tables, 4 operations tables, 1 audit table — with the three add-ons switched on, including the AI-search one." |
| 2 | **Director history** | "Prashant Joshi resigned from BrightMed in 2021 and came back in 2023. Both periods are kept. 'Current directors' shows only who's serving now; 'history' shows everything." |
| 3 | **Overlap protection** | "If someone tries to record the same person twice on the same board for overlapping dates, the database refuses." |
| 4 | **No deletion** | "Deleting or emptying a table is impossible. To remove something we mark it archived — the record and its history stay." |
| 5 | **Audit trail** | "A write with no user is rejected. With a user, every change is logged with old value, new value and who did it. Nobody can edit this log." |
| 6 | **Calculated values** | "Shareholding percentages, age and attendance are calculated live from the data. Nobody types them, so they can't be wrong or stale." |
| 7 | **Rules as data** | "The 39 compliance rules from your spreadsheet are rows in a table with the legal section — changeable without software changes. Two sample rules are computed straight from the data." |
| 8 | **Activity definition** | "Here is the recipe for a Board Meeting: nine steps, in order, with deadlines and exactly which data each step reads or writes. This is what the AI will follow in Phase 2." |
| 9 | **Activity instance** | "A live board meeting for Nexatech: four steps done, one in progress, four to go — each with due dates, the records it touched, and its evidence document." |
| 10 | **Isolation** | "Logged in as a client of Nexatech you see one company; as an administrator you see all five." *(Be candid about limitation 9.4-#1 if asked about people tables.)* |
| 11 | **Vector readiness** | "The table for AI document search exists and works: we stored and searched a test vector, then rolled it back." |
| 12 | **Coverage** | "Every one of the 292 fields in your spreadsheet is mapped to a place in the database — 100%." |

**Good extra moment:** in pgAdmin, open `core.directorship` and `core.v_current_directors` side by side for Prashant Joshi.

## 15. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `password authentication failed for user "postgres"` | Wrong password in `DATABASE_URL_ADMIN` (the shipped `.env` had an example value) | Put your real postgres password in `.env` |
| `could not create extension 'vector'` / `extension "vector" is not available` | pgvector not installed for this PostgreSQL version | Step 2; make sure the version folder (e.g. `18`) matches |
| `permission denied to create extension "vector"` on migration 001 | Set-up script wasn't given the admin URL | Ensure `DATABASE_URL_ADMIN` is set; re-run `setup_db.py` |
| `No Python at "C:\Users\91953\..."` when using `venv\Scripts\python.exe` | The shipped `venv` belongs to another PC | Step 4 |
| `ModuleNotFoundError: psycopg` / `openpyxl` / `dotenv` | Environment not active or packages missing | `.\venv\Scripts\Activate.ps1` then `pip install -r requirements.txt` |
| `connection refused` / `could not connect to server` | PostgreSQL service stopped, or a different port | Start the service; check the port in `.env` |
| Tests fail with `relation ... does not exist` | Database not built or seeded | `python scripts/setup_db.py --seed` |
| A seed file fails with `app.current_user_id must be set` | A seed file was run by hand without the actor line | Always seed through `setup_db.py --seed` |
| Unexpected data after experiments | Demo edits persisted | `python scripts/setup_db.py --reset --seed` (dev only) |

## 16. Map of the project folder

| Path | What it is |
|---|---|
| `guidelines.md` | The master specification the prototype was built from |
| `BMP_Master Checklist_Dashboard Requirements.xlsx` | Client's field list (source of truth for data) |
| `BMP_Project_Requirements_v1_0.docx`, `BMP_Technical_Overview_v1.1.docx` | Requirements and technical plan |
| `db/migrations/001…011_*.sql` | The database structure, in the order it is built |
| `db/seed/01…05_*.sql` | The demo data (05 = the required rows added in the follow-up: large public company, 2-year capital, share transfer, independent-director terms) |
| `scripts/setup_db.py` | Creates logins/database/extensions, runs migrations and seeds |
| `scripts/run_demo.py`, `demo/demo_queries.sql` | The demonstration (Python and pure SQL versions) |
| `scripts/check_traceability.py`, `scripts/generate_traceability.py` | Spreadsheet-coverage check and generator |
| `tests/` | The 19 automated tests |
| `docs/FIELD_TRACEABILITY.md` | Spreadsheet field → database column map (292 rows) |
| `docs/ERD.md`, `docs/DATA_DICTIONARY.md` | Full diagrams and column dictionary *(added during this review, generated from the live database)* |
| `TEST_AND_FIX_LOG.md` | What was tested, found, fixed — and what was not |
| `.env`, `.env.example` | Login settings (keep `.env` private) |

macOS/Linux notes: install PostgreSQL and pgvector with your package manager (e.g. `brew install postgresql pgvector`), use `python3 -m venv venv && source venv/bin/activate`; all other commands are identical.

---

## Glossary

| Term | Meaning |
|---|---|
| **Schema** | A named section inside a database (like a folder) |
| **Table / row / column** | A spreadsheet-like grid / one record / one field |
| **View** | A saved query that behaves like a read-only table; used for calculated values |
| **Migration** | A numbered SQL file that changes the database structure; applied in order |
| **Seed data** | Demo data loaded so there is something to show |
| **Trigger** | An automatic check/action the database runs when a row is added, changed or deleted |
| **RLS (Row-Level Security)** | Database rule that hides rows a user isn't entitled to |
| **CIN / DIN / PAN** | Company ID / Director ID / tax ID numbers used as unique business keys |
| **KMP** | Key Managerial Personnel (CEO, CFO, Company Secretary…) |
| **Soft delete / archive** | Marking a record inactive instead of removing it |
| **Audit log** | Permanent record of every change |
| **pgvector / embedding** | Add-on and data type used to search documents by meaning |
| **HNSW index** | A fast-search structure for vectors |
| **ERD** | Entity-relationship diagram — a map of tables and how they connect |
| **FR-n** | Functional requirement number *n* in the requirements document |
