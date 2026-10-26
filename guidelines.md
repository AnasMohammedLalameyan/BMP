# TASK: Implement the BMP Compliance Platform Activities Dashboard (Part A), then the AI Assistant (Part B, only when instructed)

You are a coding agent working inside the BMP Compliance Platform repository (FastAPI backend, PostgreSQL, vanilla-JS ES-module front end with Bootstrap). Phase 1 (database) and the Database Dashboard (UI plus backend) are finished. Your job is to **add** a second dashboard, the **Activities Dashboard**, and a **launcher** screen shown after login.

**This file has two parts.** **Part A** (sections 0 to 14) is the work to do now. **Part B** (AI integration, at the end of the file) is the plan for the work that follows. It is included so you understand where the project is heading, but you must **not start, scaffold or stub any of Part B** until I explicitly tell you that Part A is accepted and to begin Part B.

## 0. Scope and hard boundaries

**In scope now (Part A):** launcher, Activity Board API, Activities Dashboard pages, start-an-activity dialog, run-an-activity screen, per-task data capture, tests, docs.

**Out of scope until I say so:** everything AI (Groq, LLM calls, `app/ai/`, proposals, embeddings, OCR, `ai_*` tables, assistant panels, `AI_*` settings, AI buttons or AI migrations). That work is Part B and starts only on my explicit instruction after Part A is accepted.

**Rules that always apply:**

1. **Extend, do not rewrite.** The Database Dashboard keeps working exactly as before. Never edit `dashboard.css`. New styles are appended to `app.css`.
2. **No database schema change** in this task. No migrations (except optional step 10.6b, only if I ask).
3. **One write path.** Every change to company data goes through the existing engine (`engine.create/update`) so validation, optimistic locking (`updated_at`) and the audit trail apply. Never `UPDATE core.*` directly.
4. **The Activities Dashboard must never display the database.** No registers, tables, columns, `table.column` text, record IDs, record editor, exports, notifications bell. See the checklist in section 9.
5. **Company scoping.** Every new query passes `ctx.readable` explicitly (PostgreSQL row-level security applies as well). Never add an endpoint returning raw rows of `core.*` tables.
6. **Do not invent.** Items marked **VERIFY** depend on files or facts you must read in the repo first. If reality differs from this prompt, follow the repo, make the smallest adaptation, and note it in your report.
7. Work milestone by milestone (A1 to A5). After each, run the existing test suite plus the new tests, fix failures, and give a short report before continuing. Do not batch everything into one change.
8. Match existing code style, naming, error handling and response helpers (`ok(...)`, `session(...)`, `current_user`).
9. Keep the system working for every existing user flow; run the existing UI tests after touching `main.js` or `dashboard.html`.
10. **Keep the working log** described in section 0.1 up to date throughout. Work is not considered done until it is in the log.

### 0.1 Working log (mandatory)

Create `docs/WORK_LOG.md` at the very start of A0 (before any other change) and keep it updated for the whole project, including Part B later. It is the shared memory between sessions and the record I will review.

**Rules**

1. **Create it first, update it continuously.** Add an entry when you start a step, after each meaningful change (a file created or edited, a command run, a test result), and when you finish. Do not wait until the end of a milestone.
2. **Append only.** Never delete or rewrite earlier entries. If something was wrong, add a new entry that corrects it and refers to the old one.
3. **Resume from it.** At the start of every new session, read `docs/WORK_LOG.md` first, then continue from its Next step. If the log and the repo disagree, trust the repo and record the discrepancy.
4. **Be specific and honest.** Record what was done, what was not done, what failed, and what you assumed. Do not mark something done that was not run or tested.
5. **Commit it** together with the code changes it describes (or save it with them if you are not committing).
6. **No secrets or real data** in the log (no keys, passwords, personal data).

**Structure of the file**

```markdown
# Work log: BMP Compliance Platform

## Status board (keep this block current; edit in place)
| Milestone | Status (not started / in progress / done / blocked) | Last updated | Notes |
|---|---|---|---|
| A0 Recon | | | |
| A1 Board API, launcher, shell | | | |
| A2 Read-only board | | | |
| A3 Run an activity | | | |
| A4 Task data capture | | | |
| A5 Tests, docs, hand-over | | | |
| Part B (AI) | not started: waits for my instruction | | |

## Open items (VERIFY list, questions, blockers). Move to Resolved when closed
- [ ] ...

## Decisions and deviations from the prompt
- YYYY-MM-DD: what changed, why

## Entries (newest at the bottom)
### YYYY-MM-DD HH:MM  Milestone A1, step 5.4 (main.js launcher edits)
- Did: ...
- Files: path/one.py (new), path/two.js (edited)
- Commands and results: `pytest tests/...` -> 41 passed, 0 failed
- Not done / problems: ...
- Next step: ...
```

The status board and Open items block are the only parts you edit in place; everything under Entries is append-only.

## 1. Client requirements (what the result must do)

| # | Requirement | Meaning |
|---|---|---|
| 1 | Phase 1 is done | Extend; do not rewrite |
| 2-4 | Second dashboard; choose one after login; current UI is the Database Dashboard | New Activities Dashboard plus launcher with two cards |
| 5 | Looks like the Database Dashboard | Same shell (top bar, navy sidebar, cards, pills, task cards). Reuse `dashboard.css` and `app.css` |
| 6 | Works on the database but does not display it | Read/write behind the scenes through the engine; never show internals |
| 7-9 | Lists all activities to be performed; only Board Meeting for now | Catalogue from `activity.activity_template` plus cross-company running list and task list. Adding an activity later is a data change, not a code change |

Assumptions (do not ask; implement as stated): one login/session shared by both dashboards; this is a UX separation, not a security boundary; the existing Activities & Tasks page inside the Database Dashboard stays; users who can edit a company may start activities for it (existing rule); completing a task is never blocked by missing details (warn only); the launcher is always shown after login.

## 2. Architecture

```
Sign in --> Launcher (after login)
              |                              |
   Database Dashboard                Activities Dashboard
   dashboard.html (as is)            activities_dashboard.html (new)
   main.js + register modules        activities-main.js + act-*.js
              \                              /
               v                            v
        FastAPI /api/...  existing routers | activities.py (reused + task data)
                          activity_board.py (new)
                          |
        PostgreSQL (core / activity / ops)
```

Two page shells, not one SPA with a switch: the Activities page never loads the register screens, it only borrows shared dialogs (`openModal`/`closeModal` from `entity.js`, `openUploadModal` from `documents.js`) and shared helpers (`api.js`, `state.js`, `util.js`).

Facts already confirmed from the files reviewed (`api.js`, `main.js`, `state.js`, `util.js`, `entity.js`, `documents.js`, `access.py`, `deps.py`, `activities.py`):

- `GET /auth/me` returns `{user, csrf}`; `state.user.access` maps company id (string) to `read`/`write`/`admin`. There is no `state.me`.
- `UserCtx` already has `.readable` and `.writable` (lists of company ids).
- `main.js` routes by hash and treats any unknown hash as go-to-saved-position, so `#/launcher` must be intercepted in `applyRoute`.
- `api.get(path, params)` returns the parsed body; `api.js` fires `bmp:unauthenticated` on any 401.
- Table names (from `activities.py`): `ops.activity_instance`, `ops.task_instance`, `activity.activity_template`, `activity.step_template`, `ops.task_record_link`, `activity.step_data_binding`, `activity.entity_field_registry`.
- Not yet seen, so **VERIFY** by reading them: `form.js`, `companies.js`, `registry.py`, the router that serves `dashboard.html`, and that `core.company(id, name, is_archived)` exists.

## 3. Files to create or change

| File | Status | Purpose |
|---|---|---|
| `app/routers/activity_board.py` | new | Cross-company summary, catalogue, running list, upcoming tasks |
| `app/routers/activities.py` | edit | Add task data endpoints `/fields` and `/data` |
| `app/task_records.py` | new | Shared helpers `_target_record`, `_entity_name`, `_label` (imported by `activities.py`) |
| page router (VERIFY) | edit | Serve `/activities-dashboard` |
| `app/main.py` (or router registration site) | edit | Register the new router |
| `app/templates/dashboard.html` | edit | Launcher view plus Switch dashboard menu item |
| `app/templates/activities_dashboard.html` | new | Activities shell |
| `app/static/scripts/main.js` | edit | Show launcher after login |
| `app/static/scripts/activities-main.js` | new | Entry point and router |
| `app/static/scripts/act-overview.js`, `act-catalogue.js`, `act-running.js`, `act-tasks.js`, `act-run.js`, `act-start.js`, `act-util.js` | new | Views and helpers |
| `app/static/scripts/activity-form.js` | new (extracted) | Start form shared with `activities.js` |
| `app/static/scripts/activities.js` | edit | Use the extracted form; behaviour unchanged |
| `app/static/stylesheets/app.css` | append | `.launcher-*` and `.act-*` rules |
| `tests/test_activity_board.py`, `tests/ui/test_launcher.py`, UI login helper | new/edit | Coverage |
| `README.md`, guides, `docs/postman/*` | edit | Documentation |

Confirm the real folder names (`app/static/scripts/`, `app/static/stylesheets/`) with a directory listing before creating files.

## 4. Milestone A0: reconnaissance (no code changes)

0. Create `docs/WORK_LOG.md` as described in section 0.1 and add the first entry.
1. List the repo tree. Read `form.js`, `companies.js`, `registry.py`, the router serving `dashboard.html`, `activities.py`, `activities.js`, `main.js`, `state.js`, `api.js`, `util.js`, `entity.js`, `documents.js`, `access.py`, `deps.py`, and one existing API test plus `tests/conftest.py`.
2. Find where `activities.router` is included (`include_router(activities`) and where `dashboard.html` is rendered (`grep -rn "dashboard.html" app/`).
3. Run this query against the dev database and **save the output into `docs/notes/board_meeting_recipe.txt`** (adjust the template code if it is not `BOARD_MEETING`):

```sql
SELECT s.seq, s.title, s.step_type, s.requires_confirmation, s.responsible_role,
       b.mode, f.table_name, f.column_name, f.is_calculated
FROM activity.step_template s
JOIN activity.activity_template t ON t.id = s.template_id AND t.code = 'BOARD_MEETING'
LEFT JOIN activity.step_data_binding b ON b.step_id = s.id AND NOT b.is_archived
LEFT JOIN activity.entity_field_registry f ON f.id = b.field_id
WHERE NOT s.is_archived
ORDER BY s.seq, b.id;
```

4. Read the SQL of `ops.instantiate_activity`: how `row_filter` is expressed and how `task_record_link` rows are written.
5. Report (and write the same into the log): confirmed paths, every VERIFY item resolved or still open, the recipe output, and any difference from this prompt. Then continue.

## 5. Milestone A1: Activity Board API, launcher, empty Activities shell

### 5.1 Backend: `app/routers/activity_board.py`

Read-only. Starting an activity, moving a task, evidence and confirmations keep using the endpoints in `activities.py`.

```python
"""Activities dashboard: the cross-company view of every activity to be performed.

Read-only. Everything here is limited to the companies the signed-in user may read.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from ..access import UserCtx
from ..deps import current_user, session
from ..responses import ok

router = APIRouter(prefix="/activity-board", tags=["activity-board"])

OPEN = "k.status NOT IN ('completed', 'skipped')"


@router.get("/summary")
def summary(request: Request, ctx: UserCtx = Depends(current_user)):
    with session(request, ctx, readonly=True) as conn:
        ids = ctx.readable
        inst = conn.execute(
            """SELECT count(*) FILTER (WHERE status = 'active') AS active,
                      count(*) FILTER (WHERE status = 'completed') AS completed,
                      count(*) FILTER (WHERE status = 'cancelled') AS cancelled
               FROM ops.activity_instance
               WHERE NOT is_archived AND company_id = ANY(%s::bigint[])""",
            (ids,)).fetchone()
        tasks = conn.execute(
            f"""SELECT count(*) FILTER (WHERE {OPEN}) AS open_tasks,
                       count(*) FILTER (WHERE {OPEN} AND k.due_date < current_date) AS overdue_tasks,
                       count(*) FILTER (WHERE {OPEN} AND k.due_date BETWEEN current_date
                                        AND current_date + 7) AS due_this_week
                FROM ops.task_instance k JOIN ops.activity_instance i ON i.id = k.instance_id
                WHERE NOT k.is_archived AND NOT i.is_archived AND i.status <> 'cancelled'
                  AND i.company_id = ANY(%s::bigint[])""", (ids,)).fetchone()
        return ok({**inst, **tasks})


@router.get("/catalogue")
def catalogue(request: Request, ctx: UserCtx = Depends(current_user)):
    """Every activity type, latest version of each, with how many are running for this user."""
    with session(request, ctx, readonly=True) as conn:
        ids = ctx.readable
        rows = conn.execute(
            """SELECT DISTINCT ON (t.code)
                      t.id, t.code, t.version, t.name, t.status, t.obligation_ref,
                      t.description, t.input_schema,
                      (SELECT count(*) FROM activity.step_template s
                        WHERE s.template_id = t.id AND NOT s.is_archived) AS steps,
                      (SELECT count(*) FROM ops.activity_instance i
                        WHERE i.template_id IN (SELECT id FROM activity.activity_template x
                                                WHERE x.code = t.code)
                          AND NOT i.is_archived AND i.status = 'active'
                          AND i.company_id = ANY(%s::bigint[])) AS running
               FROM activity.activity_template t
               WHERE NOT t.is_archived AND t.status <> 'retired'
               ORDER BY t.code, t.version DESC""", (ids,)).fetchall()
        rows.sort(key=lambda r: r["name"])
        return ok({"activities": rows})


@router.get("/instances")
def instances(request: Request, status: str | None = None, template_code: str | None = None,
              company_id: int | None = None, ctx: UserCtx = Depends(current_user)):
    """Running and finished activities across the user's companies. Overdue first, then next due."""
    with session(request, ctx, readonly=True) as conn:
        ids = ctx.readable
        rows = conn.execute(
            f"""SELECT i.id, i.status, i.params, i.created_at, i.company_id,
                       c.name AS company_name, t.code AS template_code,
                       t.name AS template_name, t.version,
                       count(k.id) AS tasks,
                       count(k.id) FILTER (WHERE k.status IN ('completed', 'skipped')) AS done,
                       count(k.id) FILTER (WHERE {OPEN} AND k.due_date < current_date) AS overdue,
                       min(k.due_date) FILTER (WHERE {OPEN}) AS next_due
                FROM ops.activity_instance i
                JOIN activity.activity_template t ON t.id = i.template_id
                JOIN core.company c ON c.id = i.company_id
                LEFT JOIN ops.task_instance k ON k.instance_id = i.id AND NOT k.is_archived
                WHERE NOT i.is_archived AND i.company_id = ANY(%s::bigint[])
                  AND (%s::text IS NULL OR i.status = %s)
                  AND (%s::text IS NULL OR t.code = %s)
                  AND (%s::bigint IS NULL OR i.company_id = %s)
                GROUP BY i.id, c.name, t.code, t.name, t.version
                ORDER BY overdue DESC, next_due NULLS LAST, i.created_at DESC""",
            (ids, status, status, template_code, template_code, company_id, company_id)).fetchall()
        return ok({"instances": rows})


@router.get("/tasks")
def upcoming_tasks(request: Request, days: int = Query(30, ge=1, le=365),
                   ctx: UserCtx = Depends(current_user)):
    """Open tasks across all companies that are overdue or due within `days`, soonest first."""
    with session(request, ctx, readonly=True) as conn:
        ids = ctx.readable
        rows = conn.execute(
            f"""SELECT k.id, k.status, k.due_date, k.instance_id, i.company_id,
                       c.name AS company_name,
                       t.name AS activity_name, s.seq, s.title, s.responsible_role,
                       (k.due_date < current_date) AS is_overdue
                FROM ops.task_instance k
                JOIN ops.activity_instance i ON i.id = k.instance_id
                                            AND i.status = 'active' AND NOT i.is_archived
                JOIN activity.activity_template t ON t.id = i.template_id
                JOIN activity.step_template s ON s.id = k.step_id
                JOIN core.company c ON c.id = i.company_id
                WHERE NOT k.is_archived AND {OPEN} AND i.company_id = ANY(%s::bigint[])
                  AND k.due_date IS NOT NULL AND k.due_date <= current_date + %s
                ORDER BY k.due_date, k.id""", (ids, days)).fetchall()
        return ok({"tasks": rows})
```

Adapt cursor/row access (dict rows, `fetchone`) to the repo's conventions. One instance detail screen reuses `GET /activities/instances/{id}` unchanged.

Register the router next to `activities.router` with the same prefix:

```python
from .routers import activity_board
app.include_router(activity_board.router, prefix="/api")  # VERIFY: same prefix as activities
```

Serve the page next to the existing `dashboard.html` route, copying exactly what it passes:

```python
@router.get("/activities-dashboard", include_in_schema=False)
def activities_dashboard(request: Request):
    return templates.TemplateResponse(request, "activities_dashboard.html", {"version": VERSION})  # VERIFY
```

Use `/activities-dashboard` (not `/activities`) so it cannot clash with `/activities/...` API paths. No server-side auth on the page itself, like the existing page; the script checks the session.

### 5.2 Launcher markup in `dashboard.html`

Add **between** `#loginView` and `#appShell`:

```html
<!-- ===== Launcher: shown after sign-in ===== -->
<div id="launcherView" class="launcher-wrap d-none">
  <div class="launcher-top">
    <div class="d-flex align-items-center gap-2">
      <div class="brand-seal login-seal">BMP</div>
      <div><div class="brand-name fs-5 text-white">BMP &amp; Co. LLP</div>
           <div class="brand-sub" style="color:var(--sb-silver)">Compliance Platform</div></div>
    </div>
    <div class="text-end">
      <div class="who-name" id="launcherWho">---</div>
      <button class="btn btn-sm btn-outline-light mt-1" id="launcherSignOut" type="button">Sign out</button>
    </div>
  </div>
  <div class="launcher-body">
    <h1 class="launcher-title">Where would you like to work?</h1>
    <div class="launcher-grid">
      <a class="launcher-card tbl-card" id="goDatabase" role="button" tabindex="0">
        <span class="grp-ic launcher-ic"><svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></svg></span>
        <div class="launcher-card-title">Database Dashboard</div>
        <div class="launcher-card-text">Company records, directors, shareholders, meetings, filings and the compliance checklists.</div>
        <span class="launcher-go">Open &rarr;</span>
      </a>
      <a class="launcher-card tbl-card" id="goActivities" href="/activities-dashboard">
        <span class="grp-ic launcher-ic"><svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 11l3 3 8-8"/><path d="M20 12v7a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h9"/></svg></span>
        <div class="launcher-card-title">Activities Dashboard</div>
        <div class="launcher-card-text">Every compliance activity to be performed, step by step, with due dates, evidence and confirmations.</div>
        <span class="launcher-go">Open &rarr;</span>
      </a>
    </div>
  </div>
</div>
```

Also add to the **Data** dropdown, above Change my password:

```html
<li><a class="dropdown-item" id="btnSwitchDash" href="#/launcher">Switch dashboard</a></li>
<li><hr class="dropdown-divider"></li>
```

Do not add inline `<script>` (the CSP blocks it).

### 5.3 Launcher styles: append to `app.css`

```css
/* ===== Launcher (after sign-in) ===== */
.launcher-wrap{min-height:100vh;background:linear-gradient(160deg,#0f2747 0%,#16345c 38%,var(--bg) 38%)}
.launcher-top{display:flex;justify-content:space-between;align-items:center;padding:1rem 1.6rem}
.launcher-body{max-width:900px;margin:0 auto;padding:1.5rem 1rem 3rem}
.launcher-title{color:#fff;font-size:1.5rem;font-weight:700;margin-bottom:1.4rem}
.launcher-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.1rem}
.launcher-card{display:block;padding:1.4rem 1.4rem 1.2rem;color:inherit;text-decoration:none;cursor:pointer;
  box-shadow:var(--shadow);transition:transform .08s,box-shadow .12s}
.launcher-card:hover{transform:translateY(-2px);box-shadow:0 10px 26px rgba(15,23,42,.14);color:inherit}
.launcher-card:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.launcher-ic{width:52px;height:52px;border-radius:12px;background:#eef4fc;color:var(--brand-2);
  display:flex;align-items:center;justify-content:center;margin-bottom:.8rem}
.launcher-card-title{font-weight:800;color:var(--brand);font-size:1.1rem}
.launcher-card-text{color:var(--muted);font-size:.86rem;margin:.3rem 0 .9rem;min-height:3.2em}
.launcher-go{color:var(--brand-2);font-weight:600;font-size:.84rem}
```

### 5.4 Launcher behaviour in `main.js` (six edits)

1. `showLogin` and `showApp` also hide the launcher; add `showLauncher` and `enterDatabase`:

```js
function showLogin(message) {
  $("#appShell").classList.add("d-none");
  $("#launcherView").classList.add("d-none");   // new
  $("#loginView").classList.remove("d-none");
  $("#loginError").textContent = message || "";
  $("#loginPassword").value = "";
  setTimeout(() => $("#loginEmail").focus(), 50);
}
function showApp() {
  $("#loginView").classList.add("d-none");
  $("#launcherView").classList.add("d-none");   // new
  $("#appShell").classList.remove("d-none");
}
function showLauncher() {                        // new
  $("#loginView").classList.add("d-none");
  $("#appShell").classList.add("d-none");
  $("#launcherWho").textContent = state.user.name;
  $("#launcherView").classList.remove("d-none");
  if (location.hash !== "#/launcher") history.replaceState(null, "", "#/launcher");
}
async function enterDatabase() {                // new: what used to happen straight after login
  history.replaceState(null, "", location.pathname + location.search);  // clear "#/launcher"
  showApp();
  buildSidebar();
  await applyRoute(true);                       // saved position, or the Companies page
}
```

2. `startApp`: replace its last three lines (`showApp(); buildSidebar(); await applyRoute(restore);`) so it ends:

```js
$("#whoName").textContent = state.user.name;
$("#whoSub").textContent = `${state.user.role || "user"} · ${state.user.email}`;
const h = location.hash;
if (!h || h === "#/" || h === "#/launcher") { showLauncher(); return; }   // new
showApp();                       // a bookmark such as #/company/3/meetings still opens directly
buildSidebar();
await applyRoute(restore);
```

3. In the login submit handler, before `await startApp(true);` add `history.replaceState(null, "", "#/launcher");` (so a leftover hash cannot skip the launcher).
4. In `applyRoute`, right after `if (!state.user) return;` add: `if (location.hash === "#/launcher") { showLauncher(); return; }`
5. In `wire()`:

```js
$("#goDatabase").addEventListener("click", enterDatabase);
$("#goDatabase").addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); enterDatabase(); } });
$("#launcherSignOut").addEventListener("click", signOut);
```

6. Update the shared UI-test login helper (`tests/ui`) to click `#goDatabase` after login, so existing tests that expect the Companies page still pass.

### 5.5 Activities shell: `app/templates/activities_dashboard.html`

Copy `dashboard.html` (before any other additions), then change only:

- `<title>`: `BMP &amp; Co. LLP, Activities Dashboard`; every `brand-sub`: Activities Dashboard.
- **Delete** `#loginView`, `#launcherView`, the whole `.entity-box` (`<aside class="entity-box">`), `#sideAcc`, `#btnNotifications`, `#fyWrap`, `#btnExportExcel`, `#btnExport`. Keep `#btnPrint`. Keep `#btnRefresh` (remove `disabled`).
- Dropdown: keep Sign out; add a Switch dashboard link to `/#/launcher`. Omit Change my password (its dialog lives in `main.js`, not exported).
- Replace the sidebar body with fixed links (add SVG icons the way `sidebar.js` does):

```html
<div class="side-scroll">
  <div id="sideGlobal">
    <a class="side-top" data-view="overview" role="button">Overview</a>
    <a class="side-top" data-view="catalogue" role="button">All activities <span class="cnt" id="cntCatalogue" style="display:none"></span></a>
    <a class="side-top" data-view="running" role="button">Running activities <span class="cnt" id="cntRunning" style="display:none"></span></a>
    <a class="side-top" data-view="tasks" role="button">Tasks due <span class="cnt cnt-warn" id="cntTasks" style="display:none"></span></a>
  </div>
  <div class="side-cap">Switch</div>
  <a class="side-top" href="/#/launcher">All dashboards</a>
</div>
```

- Scripts at the bottom:

```html
<script src="{{ url_for('static', path='vendor/bootstrap.bundle.min.js') }}"></script>
<script type="module" src="{{ url_for('static', path='scripts/activities-main.js') }}?v={{ version }}"></script>
```

`#appShell` starts with `d-none`; `activities-main.js` reveals it.

### 5.6 Entry point: `activities-main.js`

```js
import * as api from "./api.js";
import { state } from "./state.js";
import { $, $$, toast } from "./util.js";
import * as overview from "./act-overview.js";
import * as catalogue from "./act-catalogue.js";
import * as running from "./act-running.js";
import * as tasks from "./act-tasks.js";
import * as run from "./act-run.js";

const VIEWS = { overview, catalogue, running, tasks, run };

async function boot() {
  try {                                   // same calls as main.js startApp()
    const res = await api.me();
    state.user = res.user;
    state.csrf = res.csrf;
  } catch (e) { location.href = "/"; return; }   // not signed in: "/" shows the sign-in form
  try {
    state.meta = await api.getMeta();     // the upload dialog and field renderer read it
    state.companies = (await api.getCompanies()).companies;
  } catch (e) { toast(e.message); }
  $("#whoName").textContent = state.user.name;
  $("#whoSub").textContent = `${state.user.role || "user"} · ${state.user.email}`;
  $("#btnSignOut").addEventListener("click", async () => {
    try { await api.logout(); } catch (e) { /* already gone */ }
    location.href = "/";
  });
  window.addEventListener("bmp:unauthenticated", () => { location.href = "/"; });
  $("#btnRefresh").addEventListener("click", () => route());
  $("#sidebar").addEventListener("click", (e) => {
    const a = e.target.closest("[data-view]");
    if (a) { e.preventDefault(); location.hash = `#/${a.dataset.view}`; }
  });
  window.addEventListener("hashchange", route);
  $("#appShell").classList.remove("d-none");
  route();
}

export async function route() {
  const [name = "overview", arg] = location.hash.replace(/^#\//, "").split("/");
  const known = !!VIEWS[name];
  $$(".side-top[data-view]").forEach((a) =>
    a.classList.toggle("active", a.dataset.view === (known ? name : "overview")));
  $("#view").innerHTML = "";
  window.scrollTo(0, 0);
  await (known ? VIEWS[name] : overview).render(arg);
  refreshCounts();
}

async function refreshCounts() {
  try {
    const s = await api.get("/activity-board/summary");
    const set = (id, n) => { const el = $(id); el.textContent = n; el.style.display = n ? "" : "none"; };
    set("#cntRunning", s.active);
    set("#cntTasks", s.overdue_tasks);
  } catch (e) { /* counts are decoration */ }
}

boot();
```

Check the real names in `api.js` (`me`, `getMeta`, `getCompanies`, `logout`, `get`) and adapt.

### 5.7 Overview: `act-overview.js` (A1 can ship a minimal version; A2 completes it)

Shows four tiles (Running activities, Open tasks, Overdue tasks in red `b-no`, Due in 7 days amber `b-part`), a **Needs attention** list (first ten rows of `/activity-board/tasks?days=7` as `.att-item`, click goes to `#/run/{instance_id}`), and an **Activities** card per catalogue row with a **Start** button.

```js
import * as api from "./api.js";
import { $, esc, fmtDate } from "./util.js";
import { startActivityModal } from "./act-start.js";

export async function render() {
  $("#crumb").textContent = "";
  $("#pageTitle").textContent = "Activities Dashboard";
  $("#pageSub").textContent = "Everything that has to be done, across all your companies.";
  $("#view").innerHTML = `<div class="tbl-card p-4 text-muted">Loading...</div>`;
  try {
    const [s, cat, due] = await Promise.all([
      api.get("/activity-board/summary"), api.get("/activity-board/catalogue"),
      api.get("/activity-board/tasks", { days: 7 })]);
    draw(s, cat.activities, due.tasks);
  } catch (e) { $("#view").innerHTML = `<div class="tbl-card p-4 text-danger">${esc(e.message)}</div>`; }
}

const tile = (k, v, cls) =>
  `<div class="col-6 col-lg-3"><div class="stat ${cls}"><div class="k">${k}</div><div class="v">${v}</div></div></div>`;

function draw(s, activities, due) {
  $("#view").innerHTML = `
    <div class="row g-3 mb-4">
      ${tile("Running activities", s.active, "b-prog")}${tile("Open tasks", s.open_tasks, "b-all")}
      ${tile("Overdue tasks", s.overdue_tasks, s.overdue_tasks ? "b-no" : "b-ok")}${tile("Due in 7 days", s.due_this_week, "b-part")}
    </div>
    <h2 class="h6 fw-bold text-brand mb-2">Needs attention</h2>
    <div class="tbl-card mb-4">${due.length ? due.slice(0, 10).map((t) => `
      <div class="att-item" data-run="${t.instance_id}">
        <span class="att-dot ${t.is_overdue ? "att-no" : "att-part"}"></span>
        <div><div class="fw-semibold">${esc(t.title)} <span class="text-muted fw-normal">· ${esc(t.activity_name)}</span></div>
        <div class="co-sub">${esc(t.company_name)} · due ${esc(fmtDate(t.due_date))}${t.is_overdue ? " · overdue" : ""}</div></div></div>`).join("")
      : `<div class="p-4 text-muted">Nothing is overdue or due in the next 7 days.</div>`}</div>
    <h2 class="h6 fw-bold text-brand mb-2">Activities</h2>
    <div class="row g-3">${activities.map((a) => `
      <div class="col-lg-6"><div class="tbl-card p-3 h-100">
        <div class="fw-bold text-brand">${esc(a.name)}</div>
        <div class="co-sub">${esc(a.obligation_ref || "")}</div>
        <div class="mt-2"><span class="pill pill-na">${a.steps} steps</span> <span class="pill pill-prog">${a.running} running</span></div>
        <button class="btn btn-brand btn-sm mt-3" data-start="${esc(a.code)}" type="button">Start</button></div></div>`).join("")}</div>`;
  $("#view").onclick = (e) => {
    const r = e.target.closest("[data-run]"); if (r) { location.hash = `#/run/${r.dataset.run}`; return; }
    const st = e.target.closest("[data-start]");
    if (st) startActivityModal(activities.find((a) => a.code === st.dataset.start));
  };
}
```

For A1, create `act-catalogue.js`, `act-running.js`, `act-tasks.js`, `act-run.js`, `act-start.js` as minimal modules exporting `render()` (and `startActivityModal` for `act-start.js`) so the shell loads; fill them in A2/A3.

### 5.8 A1 acceptance

- Sign in shows two cards. *Database Dashboard* opens Companies and behaves exactly as before; the browser Back button and the Switch dashboard menu item return to the launcher.
- A bookmark such as `#/company/3/meetings` still opens directly after login.
- *Activities Dashboard* opens `/activities-dashboard` inside the same visual shell; sidebar links change the hash; Sign out and All dashboards work; signed out, the page bounces to `/`.
- Existing backend and UI tests pass. Add `tests/test_activity_board.py` cases for the four GET endpoints (see section 9).

## 6. Milestone A2: read-only board (catalogue, running list, tasks list)

- **`act-catalogue.js`**: one `.tbl-card` per row of `/activity-board/catalogue`: name, obligation reference, status pill, steps, running count, **Start** and **View steps**. View steps reuses the table from `toggleTemplate` in `activities.js` (same `/activities/templates/{id}`) but replaces the Reads / writes column with a friendly **Records it updates** list (see rule 2 in section 9). Keep the draft warning (the Board Meeting definition is still draft):

```js
${a.status === "draft" ? `<div class="rec-note mt-2">Draft: step durations are defaults from the Companies Act (s.173) and SS-1 and have not yet been verified by a BMP professional.</div>` : ""}
```

- **`act-running.js`**: a `.list-bar` filter bar with three selects: Company (from `state.companies`), Activity (from the catalogue), Status (active/completed/cancelled). Each filter re-calls `/activity-board/instances` with params. Each row is a card like `drawList` in `activities.js` plus the company name, a progress bar and an overdue pill; click goes to `#/run/{id}`.
- **`act-tasks.js`**: a `.chk-table` from `/activity-board/tasks?days=90`: Due, Company, Activity, Step, Responsible, status. Row click goes to `#/run/{instance_id}`.
- Complete `act-overview.js` as in 5.7.

Every row comes from `activity_template`, so adding the next activity (AGM, EGM, and so on) must need no front-end change. Do not hard-code Board Meeting anywhere.

A2 acceptance: all four views render real data for the admin (five companies) and only Nexatech data for `client@nexatech.co.in`.

## 7. Milestone A3: run an activity (no database internals)

### 7.1 Extract the start form (extract, do not copy)

In `activities.js`, `startForm()` builds the form from `input_schema` and collects the values. Move that into `activity-form.js` and make `activities.js` call it. **Behaviour of the Database Dashboard page must not change; run the existing tests after.**

```js
// activity-form.js
import { esc, words } from "./util.js";

export function renderStartFields(host, tpl) {   // body of the old startForm() up to innerHTML
  /* the existing `field()` generator and `host.innerHTML = ...` go here,
     minus the Start button handler */
}

export function collectParams(host) {            // the loop that builds `params` from [data-p]
  const params = {};
  host.querySelectorAll("[data-p]").forEach((el) => {
    const v = el.value.trim(); if (!v) return;
    params[el.dataset.p] = el.dataset.list ? v.split("\n").map((x) => x.trim()).filter(Boolean) : v;
  });
  return params;
}

export function showFieldErrors(host, err) {      // the has-error handling from the catch block
  Object.entries(err.fields || {}).forEach(([k, m]) => {
    const f = host.querySelector(`.rec-field[data-field="${CSS.escape(k)}"]`);
    if (f) { f.classList.add("has-error"); f.querySelector(".err").textContent = m; }
  });
}
```

### 7.2 Permission helper: `act-util.js`

`canWriteCompany()` reads `state.companyId`, which is always null on this dashboard, so it would hide every button. Use:

```js
import { state } from "./state.js";

/** Same rule as canWriteCompany() in state.js, for any company (the server remains the authority). */
export const canWriteFor = (companyId) => {
  const level = state.user.access[String(companyId)];
  return level === "write" || level === "admin";
};
export const writableCompanies = () => state.companies.filter((c) => canWriteFor(c.id));
```

### 7.3 `act-start.js`

Open the form in a modal using `openModal`/`closeModal` from `entity.js` (needs `#modalHost`, already in the shell) with: a **Company** select from `writableCompanies()`; the generated fields from `renderStartFields`; a **Start activity** button that calls `POST /activities/instances` with `{template_code, company_id, params}`, shows field errors via `showFieldErrors`, turns a 403 into a toast (the server is the real gate: `start_activity` calls `writable_company`), and on success goes to `#/run/{id}`. Export `startActivityModal(activity)`.

### 7.4 `act-run.js`

Start from `draw()` and `taskCard()` in `activities.js` and apply these differences:

| Item | Database Dashboard `activities.js` | `act-run.js` |
|---|---|---|
| Back link | back to list | back to `#/running` |
| Company name | implied (open company) | shown in the header: `state.companies.find((c) => c.id === inst.company_id).name` |
| `canWriteCompany()` | uses `state.companyId` | `canWriteFor(inst.company_id)` |
| Uses these records chips | shown | **removed** (replaced by the task form in A4) |
| Records this task involved / Link a record | shown, opens `openRecord` | **removed** |
| Evidence, confirmation, notes, status buttons | yes | **kept as they are** (same endpoints, `openUploadModal` is allowed) |

No server change is needed. Do not render `k.links`, record IDs, or call `openRecord`, `mountList`, `renderEntityPage`.

A3 acceptance: from the catalogue or overview, start a Board Meeting for a writable company; land on its task board; complete the first task; evidence upload and confirmation work; a read-only user gets no Start button and a forced request returns 403.

## 8. Milestone A4: task data capture (writes records through the engine, never shows them)

Today a task changes only its status. Each task with write bindings gets a small form that writes the records through the same engine (validation, `updated_at` locking, audit trail).

**First** read `docs/notes/board_meeting_recipe.txt` (from A0) and classify each Board Meeting step: **Capture** (has write bindings, needs a form), **Document** (evidence only, uses existing Attach evidence), **Decision** (confirmation, uses existing buttons). If linking is more complex than described below (for example unusual `row_filter`), stop and report before building.

### 8.1 Shared helpers: `app/task_records.py`

Implement `_target_record(conn, request, task, binding)`, `_entity_name(table_name)` and `_label(column_name)` here (not inside `activities.py`), and import them in `activities.py`. A later AI task will reuse them, so they must not depend on request-handler internals.

`_target_record` rules (depends on how `ops.instantiate_activity` links records; in `_instance_detail`, `ops.task_record_link` rows carry `entity_type` and `entity_id`):

1. Look for a `task_record_link` row for **this task or any task in the same instance** whose `entity_type` matches the binding's table (`core.meeting` gives `meeting`). That is the record to read and update.
2. If the binding has a `row_filter`, apply it only when you must choose among several rows (for example the chairperson's attendance row). Read the SQL that `instantiate_activity` writes to see how `row_filter` is expressed before implementing.
3. If no link exists, return `None`; the form shows the field empty with a note. Only if the step is a create step: use `engine.create` then insert the link.

`_entity_name`: map registry table names (`core.meeting`) to engine entity keys (`meeting`) using `app/registry.py` (ENTITIES) and `request.app.state.catalog` (**VERIFY**). `_label`: turn `meeting_date` into `Meeting date`.

### 8.2 Endpoints in `activities.py`

Imports such as `Body`, `conflict`, `bad_request`, `writable_company` come from the existing module; **VERIFY** and keep the router prefix consistent.

```python
@router.get("/activities/tasks/{task_id}/fields")
def task_fields(task_id: int, request: Request, ctx: UserCtx = Depends(current_user)):
    engine = request.app.state.engine
    with session(request, ctx, readonly=True) as conn:
        task = engine.get(conn, "task_instance", ctx, str(task_id))      # scope-checked
        binds = conn.execute(
            """SELECT b.id AS binding_id, b.alias, f.table_name, f.column_name
               FROM activity.step_data_binding b
               JOIN activity.entity_field_registry f ON f.id = b.field_id
               WHERE b.step_id = %s AND b.mode = 'write' AND NOT b.is_archived
                 AND NOT f.is_calculated
               ORDER BY b.id""", (task["step_id"],)).fetchall()
        fields = []
        for b in binds:
            rec = _target_record(conn, request, task, b)
            fields.append({"binding_id": b["binding_id"],
                           "label": b["alias"] or _label(b["column_name"]),
                           "entity": _entity_name(b["table_name"]),
                           "column": b["column_name"],
                           "value": rec.get(b["column_name"]) if rec else None,
                           "version": rec.get("updated_at") if rec else None})
        return ok({"fields": fields})


@router.post("/activities/tasks/{task_id}/data")
def task_data(task_id: int, request: Request, payload: dict = Body(...),
              ctx: UserCtx = Depends(current_user)):
    engine = request.app.state.engine
    values = payload.get("values") or {}
    with session(request, ctx) as conn:
        task = engine.get(conn, "task_instance", ctx, str(task_id))
        inst = engine.get(conn, "activity_instance", ctx, str(task["instance_id"]))
        writable_company(ctx, inst["company_id"])
        if inst["status"] == "cancelled":
            raise conflict("This activity was cancelled; reopen it first.")
        allowed = {str(r["binding_id"]): r for r in conn.execute(
            """SELECT b.id AS binding_id, f.table_name, f.column_name
               FROM activity.step_data_binding b
               JOIN activity.entity_field_registry f ON f.id = b.field_id
               WHERE b.step_id = %s AND b.mode = 'write' AND NOT b.is_archived
                 AND NOT f.is_calculated""", (task["step_id"],))}
        unknown = [k for k in values if k not in allowed]
        if unknown:    # whitelist: a client can only write what the step declares
            raise bad_request("Some fields do not belong to this step.",
                              {k: "Not allowed" for k in unknown})
        by_record: dict = {}
        for k, v in values.items():
            b = allowed[k]
            rec = _target_record(conn, request, task, b)
            if rec is None:
                raise conflict("The record this step updates does not exist yet.")
            by_record.setdefault((_entity_name(b["table_name"]), rec["id"], rec["updated_at"]), {})[b["column_name"]] = v
        for (entity, rec_id, version), body in by_record.items():
            engine.update(conn, entity, ctx, str(rec_id), {**body, "updated_at": version})   # validates + audits
        # Record that this task wrote them: insert into ops.task_record_link if the pair is not
        # already there. VERIFY the columns from the entity catalogue.
        return ok({"saved": len(values)})
```

Calculated fields (`is_calculated`) are never offered or accepted. Mark complete stays allowed without data.

### 8.3 Front end (in `act-run.js` `taskCard()`)

Add a **Details to record** section for steps with write bindings:

1. Load `/activities/tasks/{id}/fields` only when the card is expanded.
2. Render each field with `fieldHTML(entity, colMeta(entity, column), {[column]: value}, { readonly: false })` from `form.js`/`state.js` inside `.rec-grid`/`.rec-field` markup (label, control, `.err`), so date pickers, dropdowns and validation match the Database Dashboard. The browser has `state.meta.entities[entity].columns`. **VERIFY** the real signatures of `fieldHTML`, `collect`, `hydrateFk`, `showErrors`, `clearErrors` in `form.js`.
3. Wrap each binding in its own `<div data-binding="{binding_id}">` and call `collect` per wrapper (two bindings can share a column name on different records). Call `hydrateFk(root, inst.company_id)` when a form has dropdowns.
4. **Save details** posts `{values: {"<binding_id>": value}}` to `/data`, shows the server's `fields` errors under each field (same pattern as the start form), and toasts on success. A stale `updated_at` surfaces the normal conflict message.
5. If a task is completed while its details are not recorded, show a warning like the existing missing-evidence warning ("Details not recorded: Venue, Meeting time"). Do not block completion.
6. Attendance (a roster of directors with ticks) is a list, not a field: build one dedicated panel reusing the idea of `meetings.js::attendanceDialog`, calling the existing `PUT /meetings/{id}/attendance`.

Labels must never show `table.column`. Do not hard-code step numbers; identify steps by `step_type` and bindings (the Board Meeting template is still draft).

A4 acceptance: on a Board Meeting, fix date, time and venue through the task form; a row appears in the audit trail with the user as actor; a wrong `updated_at` gives the usual conflict; the Activities page text never contains table or column names or record IDs.

## 9. Rules checklist (review every milestone against this)

1. The Activities Dashboard never imports the register screens (masterdata, directors, shareholders, foreign, meetings, rules, trail, alldirectors, notifications, companies, overview of the Database Dashboard). Allowed imports: `api`, `state`, `util`, `activity-form`, `act-*`, and shared dialogs `openModal`/`closeModal` (`entity.js`) and `openUploadModal` (`documents.js`). Never call `openRecord`, `mountList` or `renderEntityPage`.
2. No `table.column` text anywhere. Bind-chip outputs like `meeting.meeting_date` become plain labels: use `b.alias` if present, otherwise the column name in words with a capital first letter (Meeting date).
3. No record IDs (`#42`, `meeting 5`). Do not render `k.links`.
4. No JSON/Excel export of company data, no notifications bell, no Open record buttons.
5. No endpoint returning raw table rows is added.
6. Data a task needs is shown only inside that task.

## 10. Milestone A5: tests, docs, hand-over

### 10.1 Backend tests: `tests/test_activity_board.py` (copy fixtures from an existing API test)

| Test | Expectation |
|---|---|
| admin summary | counts across all five companies |
| `client@nexatech.co.in` instances | only Nexatech rows; other companies never appear |
| catalogue | one row, Board Meeting, steps > 0, latest version only |
| instances filters | `status`, `template_code`, `company_id` each narrow the list |
| overdue ordering | an instance with an overdue task sorts before one without |
| unauthenticated | all four endpoints return 401 |
| start as read-only user | `POST /activities/instances` returns 403 (existing rule, regression) |
| `/fields` | returns only write bindings; no `is_calculated` field |
| `/data` with a binding from another step | 400, nothing written |
| `/data` valid | value saved; an audit-trail row exists; wrong `updated_at` gives the usual conflict |
| cancelled activity | `/data` returns 409 |

### 10.2 UI tests (Playwright, `tests/ui/test_launcher.py`, `BMP_UI_TESTS=1`)

1. Login shows the two cards; *Database Dashboard* opens Companies.
2. *Activities Dashboard* opens; tiles render; the sidebar has four links.
3. Start a Board Meeting from the catalogue for a company; land on its task board; complete the first task.
4. On the Activities Dashboard, page text contains none of: `core.`, `.column`, `Master Data`, `Directors register`, `Export data` (automated guard for requirement 6).
5. *Switch dashboard* returns to the launcher from both dashboards.

### 10.3 Manual QA (as admin, manager, client users)

Client user sees the launcher, Activities shows only Nexatech, no Start button on companies they cannot edit (the server rejects it if forced); narrow window collapses the sidebar into the offcanvas menu and stacks launcher cards; Back/Forward and refresh on `#/run/{id}` reopen the same activity; printing an activity page hides `.no-print` buttons.

### 10.4 Documentation

- `README.md`: add the Activities Dashboard to the table and quick start (URL `/activities-dashboard`).
- `BMP_UI_Backend_Implementation_Guide.md`: add a short Two dashboards section (launcher, how to open each).
- `BMP_UI_Backend_Implementation_Log.md`: record what was built, tested and not done.
- `docs/postman/`: new folder **Activity board** with the four GET requests and the two task-data requests, with assertions on status and shape.
- Technical guide: add the new files to the structure section.
- A one-page How to add the next activity: create the template, its steps, dependencies, bindings and evidence rules in the Activity Database (as was done for Board Meeting); it appears in the catalogue automatically.

## 11. Optional step (do NOT do unless I ask): restrict by user

Add `dashboards text[] NOT NULL DEFAULT '{database,activities}'` to `core.app_user` via a migration, return it from `/auth/me`, hide launcher cards the user lacks, and enforce server-side only if real access control is requested.

## 12. Keep these in mind for Part B (do not build now)

- Keep `_target_record` and friends in `app/task_records.py` so Part B can reuse them.
- Keep front-end files in `app/static/scripts/` and avoid inline scripts (CSP).
- Do not add anything that assumes AI is present; the system must run fully without it.
- Part B is specified at the end of this file. Do not begin it until I say so.

## 13. How to report

After each milestone, first make sure `docs/WORK_LOG.md` is current, then reply with: files changed, commands run and test results, any VERIFY item you resolved (and how), any deviation from this prompt with the reason, and anything left open. Ask a question only if the repo contradicts this prompt in a way that blocks you; otherwise make the smallest reasonable choice and say what you chose. Stop after A5, mark Part A as done in the log status board, and wait. Do not start Part B until I explicitly instruct you to.

## 14. Risks to watch

1. Task-to-record linking (section 8.1) is the least known part and can change A4's effort; check the A0 recipe output first and report early.
2. Files not yet seen (`form.js`, `registry.py`, page router): adapt, do not guess.
3. Existing UI tests assume login lands on Companies: fixed by the helper change in 5.4 step 6.
4. The Board Meeting definition is draft: keep the draft notice visible.
5. Some duplication between `activities.js` and `act-run.js` is acceptable now; the start form is the only shared extraction required.

---

# PART B: AI Assistant integration (DO NOT START until I explicitly instruct you)

> **Gate.** Part B begins only after (1) Part A milestones A0 to A5 are done and recorded as done in `docs/WORK_LOG.md`, and (2) I have written to you that Part A is accepted and Part B may start. Until then, treat everything below as read-only planning context. Do not create `app/ai/`, AI settings, AI tables, AI endpoints or AI UI.
>
> **When it starts:** first re-read `docs/WORK_LOG.md`, re-read the repo state, set the Part B row of the status board to in progress, and run milestone B0a (recon) before any code. The working-log rules in section 0.1 apply unchanged. Every Part B milestone gets log entries and a report.

## B1. What Part B delivers

A Groq-powered layer that **proposes and never acts**: the AI reads documents, plans activities, drafts notices and answers questions, and every database change or email still needs a named person's approval. About 15 existing files get small changes, about 30 new files are added, and one migration adds the AI tables. Then the AI is wired into the Activities Dashboard built in Part A.

| Capability | Requirement | What it does |
|---|---|---|
| 1. Read documents | FR-7 | Extracts fields from an uploaded document, each with source quote and page |
| 2. Set up work from a prompt | FR-8 | Turns a sentence such as set up the AGM into a deterministic plan |
| 3. Draft and send notifications | FR-9 | Drafts notices and cover emails; sends only after approval |
| 4. Answer questions with citations | n/a | Answers from the company's documents and the shared statute library |

Cross-cutting: FR-3 evidence links, FR-10 company isolation, FR-11 per-company history, FR-12 evidence of every model call, FR-13 named-person approval.

**Non-negotiables**

1. The AI has **no write path** to company data. Approval runs through `Engine.create/update` under the approver's own session.
2. The whole system must run with `AI_ENABLED=false`: every AI element is hidden and nothing errors.
3. Development runs on **dummy data only**. Real client data stays blocked until BMP answers four decisions (see B12).
4. Everything AI-specific lives under `app/ai/` so it can be switched off, tested and audited as one unit.
5. Never hold a database transaction open during an LLM call (the pool has about 10 connections).
6. The Part A rules still hold: the Activities Dashboard never displays the database, one write path, company scoping.

## B2. Groq: facts that shape the design

**VERIFY** every model name and limit below against Groq's current documentation before building; they were read when the plan was written and preview models can be withdrawn. Keep model IDs in `.env`.

| Groq fact | Design consequence |
|---|---|
| Free limits for `openai/gpt-oss-120b`: 30 requests/min, 1,000 requests/day, 8,000 tokens/min, 200,000 tokens/day | Chunk documents to about 3,000 tokens per call. Add a rate limiter that reads `retry-after`. Record and replay LLM responses in tests, or one evaluation run uses up a day's quota. |
| Strict `json_schema` output works only on `gpt-oss-20b/120b`, `qwen3.8-27b` and `muse-spark-open`. It cannot be combined with tool use or streaming | Two call types. Extraction and intent calls use strict schemas with no tools. Chat and Q&A calls use tools, and their arguments are validated by your own code (Pydantic). |
| No embeddings endpoint | Embed locally (for example `fastembed` with `bge-small-en-v1.5`, 384 dimensions). This also keeps chunk text off the provider. |
| Only multimodal model listed is `qwen/qwen3.8-27b` (preview) | Do scans with local OCR (RapidOCR or Tesseract). Treat Groq vision as an optional fallback. |
| No retention by default, but inputs and outputs may be logged up to 30 days. Zero Data Retention is opt-in under Data Controls. Data is stored in the US | Free tier for dummy data only. Before any real data, enable ZDR and get BMP's approval for processing outside India. A startup guard in `config.py` enforces this. |

The `openai` Python SDK works against Groq's OpenAI-compatible endpoint, so switching provider later is a base URL, key and model change. All calls go through `providers/base.py`.

## B3. Architecture: the AI proposes, a person applies

Use a fixed router plus four deterministic workflows, not a free-roaming agent. The LLM does only what code cannot: read messy text, parse a sentence, draft prose.

1. **Request.** A signed-in user acts inside one company. The AI session is bound to that company (FR-10).
2. **Route.** One strict-schema call classifies the request: extract a document, set up an activity, draft a notice, or answer a question.
3. **Read.** The workflow fetches only what it needs through a tool gateway: company-scoped, field-allowlisted, identifiers masked before anything leaves the server.
4. **Propose.** Saved as an `ai_proposal` row (operations, sources, confidence). Nothing in `core` or `ops` changes.
5. **Review.** A person sees current value, proposed value, confidence and source quote side by side, and edits or rejects.
6. **Apply.** Approval runs through the normal engine under the approver's session, in one transaction. Emails go to an outbox and send only after approval.
7. **Record.** Proposal, decision, effects and the call manifest are stored; the audit trigger records the approver as actor.

**FR-13 enforced in the system, not in a prompt**

- `UserCtx` gets a `via_ai` flag; `can_write_entity` returns False when it is set. AI tools get only read functions and `create_proposal`.
- A separate `bmp_ai` database role with SELECT plus INSERT on the new `ai_*` tables only (recommended).
- Database constraints: an applied proposal needs `decided_by`; a notification cannot reach `queued` without `approved_by`; the sender re-checks that the body hash equals the approved hash.
- Code under `app/ai/` never uses `privileged_session`; a test fails the build if it does.
- Extraction calls have no tools, so an instruction hidden in an uploaded file has nothing to trigger.

| Capability | Sent to Groq | Never sent |
|---|---|---|
| 1. Read documents | Document text with PAN, DIN, phone, email and Aadhaar replaced by placeholders | The identifiers themselves; other companies' data |
| 2. Set up an activity | The instruction, company names, activity codes | People, financials |
| 3. Draft notices | Company name, meeting date, venue, agenda, a recipient placeholder | Recipient names and emails (merged in by code) |
| 4. Answer questions | The question and top retrieved chunks, masked the same way | Anything outside those chunks |

Keep the tool registry in the shape of an MCP tool list (name, schema, permission, scope).

## B4. Existing files to change

| File | Change |
|---|---|
| `app/config.py` | Add `AI_ENABLED`, `AI_PROVIDER`, `GROQ_API_KEY`, `AI_BASE_URL`, per-task model IDs (`AI_MODEL_EXTRACT`, `_CHAT`, `_FAST`, `_VISION`), timeouts, rate-limit figures, SMTP settings, embedding model, `AI_DATA_MODE=dummy` or `real`. In real mode refuse to start unless `AI_ZDR_CONFIRMED=true` and `AI_OUTSIDE_INDIA_APPROVED=true`. `AI_ENABLED=false` must keep working. |
| `app/main.py` | Register `routers/ai.py`. In lifespan build the provider, tool gateway, rate limiter and `bmp_ai` pool. Report AI status in `/api/health`. |
| `app/access.py` **(fix)** | In `Scope.row_scope` the masters branch returns TRUE for any staff user, so an AI session narrowed to Company A would still see every director and shareholder. Add `UserCtx.via_ai` and `UserCtx.bound_company`; make the masters branch use the company link check when either is set. Add `narrow_to_company(ctx, cid)`. `can_write_entity` returns False when `via_ai`. After this change re-run the Part A activity-board tests: a normal user's counts must not change. |
| `app/crud.py` **(fix)** | `PAGE_MAX = 5000` is far too large for a model's context; the AI gateway caps at 20 to 50 rows. Add a short `statement_timeout` for AI reads. No other change. |
| `app/registry.py` | Add the AI tables to ENTITIES (all `write="none"`) and SCOPE (direct by `company_id`). Add an AI Assistant group to NAV. Add an `AI_POLICY` block: entities the AI may read, fields that may be sent, a never-send list (pan, date_of_birth, phone, personal addresses, every bytea column), pending BMP's decision. Rename the step section Automation (later phases). |
| `app/deps.py` | Add `ai_session(request, ctx, company_id)` (AI enabled, company readable, narrowed context, per-user rate limit) and a confirmer dependency (write access to the proposal's company). |
| `app/db.py` | Optional `bmp_ai` pool. Document: read, close, call the model, then open a new transaction to save. |
| `app/errors.py` | Add `ai_unavailable` (503), `ai_rate_limited` (429), `ai_policy` (403), and a provider-exception mapper. |
| `app/coerce.py` | **No change.** Put Indian-format normalisation (12th Sept 2026, 12/09/2026, Rs. 5,00,000, lakh and crore) in new `ai/normalize.py` that runs before coerce. |
| `app/schema_meta.py`, `app/responses.py` | No change. |
| `scripts/setup_db.py` | Create the `bmp_ai` role from `DATABASE_URL_AI`. Add `pg_trgm` to `ensure_extensions` if name matching in SQL is used. |
| `scripts/manage_users.py` | Add approver demo accounts if the seed adds them; `list` shows who can approve AI actions. |
| `scripts/run_demo.py` **(fix)** | Item 9 hard-codes a 1536-dimension vector; if the embedding size changes, read it from the catalog. |
| `README.md`, `.env.example`, `requirements.txt` | Document new settings. Add `openai`, `pydantic`, `fastembed`, `pdfplumber`, `python-docx`, `pymupdf`, `rapidocr-onnxruntime` (or Tesseract), `rapidfuzz`, `aiosmtpd`, `reportlab`. |

No `X-Frame-Options` change: do not embed PDFs; show the extracted page text with the quote highlighted.

## B5. New files

```
app/ai/
  providers/        base.py  openai_compat.py (Groq)  fake.py (tests)  ratelimit.py
  gateway.py        tool registry: the only data path for the AI
  policy.py         allowlists, never-send list, masking of PAN/DIN/phone/email/Aadhaar
  schemas.py        Pydantic models for every model output
  router.py         intent classification (strict schema, no tools)
  extraction.py     Capability 1 pipeline
  ingest/           text_extract.py  ocr.py  chunker.py  embed.py
  normalize.py      Indian dates, amounts, names
  resolve.py        DIN/PAN/CIN matching, lookup-label matching, same-entity check
                    (reuses app/task_records.py from Part A)
  planner.py        Capability 2: deterministic plan from the activity template
  notify.py         Capability 3: recipients, templates, drafting
  rag.py            Capability 4: hybrid retrieval, answer, citation check
  memory.py         conversations, rolling summary, company memory
  proposals.py      proposal states, approve/reject, apply through Engine
  prompts/          versioned prompt files (one per task)
app/routers/ai.py   all AI endpoints
app/static/scripts/ ai-panel.js  ai-review.js  ai-notify.js   (shared by both dashboards; no inline scripts)
scripts/            run_worker.py  make_dummy_docs.py  seed_ai_demo.py  ai_eval.py  run_demo_phase2.py
db/migrations/NN_phase2_ai.sql
tests/ai/           unit, database, isolation, safety, live (skipped by default)
tests/ai/golden/    dummy documents, prompts, questions, expected answers
tests/ai/cassettes/ recorded LLM responses for replay
docs/AI_EVAL_REPORT.md   generated
```

Background queue: a Postgres table `ops.ai_job` claimed with `FOR UPDATE SKIP LOCKED` plus a worker script. No Redis or Celery.

## B6. Database changes (one migration)

Put the tables in the `ops` schema so catalog, scoping and audit machinery pick them up. Copy the existing Phase 1 pattern for row-level security, audit trigger, no-delete trigger and grants from an existing migration (read one first).

| Table | Purpose |
|---|---|
| `ops.ai_conversation`, `ops.ai_message` | Per-company chat history (FR-11) with a rolling summary |
| `ops.ai_company_memory` | Short facts established earlier for a company, each tied to its source message |
| `ops.ai_proposal` | Kind, company, payload (operations, sources, confidence), payload hash, status (proposed, approved, rejected, applied, failed, stale), proposed_by, decided_by, decided_at, model, prompt version. CHECK: applied or approved needs `decided_by` |
| `ops.ai_proposal_effect` | Which records each applied proposal created or changed |
| `ops.ai_call_log` | One row per model call: purpose, model, manifest of fields and chunk IDs sent, token counts, latency, status. Stores no document text (evidence for FR-12) |
| `ops.notification`, `ops.notification_recipient` | Email outbox: draft, approved, queued, sent, failed, cancelled; `approved_by`, `body_sha256`, `sent_body_sha256`. A trigger blocks `queued` without an approver |
| `ops.ai_job` | Background queue |
| `core.document_page` | Extracted text per page and method (digital or OCR) |
| `core.document_chunk` (alter) | Add `page_no`, `section_ref`, a generated `tsvector`. Change `embedding` from `vector(1536)` to the local model size (384), set NULL on migrate, rebuild the index. Fallback: keep 1536 and zero-pad (cosine distance unchanged). Which one is a decision, see B12 |
| `core.library_document`, `core.library_chunk` | Companies Act and Secretarial Standards, global scope. Skip if `core.document.company_id` is already nullable |

Also: if the `confirmation` table restricts `subject_type`, add `ai_proposal`; store a named-person confirmation row per AI proposal there.

## B7. The four capabilities

**Capability 1: read an uploaded document (FR-7).**

1. Upload uses the existing documents router; a new Extract details action creates an `ai_job`.
2. Text: `pdfplumber` (digital PDF), `python-docx` (Word), PyMuPDF plus local OCR (scans). Save each page to `core.document_page`.
3. Optionally screen with Groq `llama-prompt-guard-2-86m` for injection (preview model).
4. Mask PAN, DIN, phone, email and Aadhaar. Aadhaar is dropped for good: never stored, never proposed.
5. Classify against `core.document_type`; build the extraction schema from the catalog and `step_data_binding`.
6. Extract with a strict schema; each field returns value, `source_quote` and page. Long documents go in page-sized pieces merged by code.
7. Verify in code: the quote appears verbatim in the page text; the value passes normalize then coerce; dropdown labels match a standard list value; two passes agree. Confidence is a tier (high, check, unverified) from these checks, never the model's own number.
8. Resolve: match people on DIN or PAN and companies on CIN; similar names become a same-entity question. Plain code, never the model.
9. Compare with current values; a disagreement shows both with a choice; nothing is overwritten silently.
10. Propose with the `updated_at` each operation was based on, so a record changed since gives 409 at approval.
11. Apply on approval and create `evidence_link` rows tying the document to every record it produced (FR-3).

**Capability 2: set up work from a prompt (FR-8).** One strict-schema call turns a sentence into `{company, activity_code, params, missing[]}`. If something required is missing, ask; never guess. `planner.py` then builds the plan with no model: it reads `activity.get_template_json(code)`, computes due dates from anchors, offsets and directions, and links steps to records named in `step_data_binding`. Statutory dates (AGM within six months of year end, 21 clear days' notice) are calculated in code and tested. Instance creation reuses the existing `ops.instantiate_activity` (behind `POST /activities/instances`); the planner only supplies parameters. Replace it only if recon shows it cannot take what the planner needs.

**Capability 3: draft and send notifications (FR-9).** Recipients come from the database, never the model: current directors (`v_current_directors`), shareholders, auditors, as the notice type requires. Statutory notice text is a Jinja2 template filled from records; the model writes only the cover email with a recipient placeholder. The review screen shows the draft, the full recipient list with emails, and attachments. Approval stores `approved_by` and `body_sha256`. The worker re-checks the hash, sends through SMTP one row per recipient, retrying failures without double-sending. Until BMP picks a mail system, run in sandbox mode: every message goes to a local test mail server.

**Capability 4: answer questions with citations.** Hybrid retrieval (PostgreSQL full-text plus local-vector similarity, merged by reciprocal rank fusion), always filtered to the session's company plus the shared library. Library text is chunked by section so a citation can read Companies Act, s. 96(1). The model answers only from supplied chunks and cites chunk IDs; code checks every cited ID was retrieved and every quote is a substring of its chunk. Thin evidence means the answer says so. Statute answers carry a standing note to check the current text.

**Cross-cutting:** per-model rate limiter (token estimate before each call, wait on `retry-after`, backoff with jitter, fallback model only if its output schema is the same, log which model answered); all calls through `providers/base.py`, with a test that runs the golden set on a second provider by configuration; memory = last N messages plus rolling summary plus company memory, per company.

## B8. API endpoints (all under `/api/ai`, existing session and CSRF checks, bound to one company)

| Endpoint | Purpose |
|---|---|
| `POST /companies/{cid}/documents/{id}/extract` | Queue extraction; returns a job ID (202) |
| `GET /jobs/{id}` | Job status |
| `POST /companies/{cid}/chat` | Instruction or question; returns a reply and any proposals. `GET` returns history |
| `GET /proposals`, `GET /proposals/{id}` | Review list and detail |
| `GET /proposals/awaiting` | Summary-only list across the user's writable companies (kind in words, company name, proposer, time, link target). Never returns operation payloads |
| `POST /proposals/{id}/approve` | Body: field edits, conflict choices, payload hash. Applies as the signed-in user |
| `POST /proposals/{id}/reject` | Records decision and reason |
| `GET /notifications/{id}`, `POST .../approve`, `POST .../cancel` | Review and approve the outbox message |
| `GET /calls` (admin) | Model-call manifest log |
| `GET /status` | AI enabled, provider, model names. No secrets |

## B9. UI: shared modules and integration into the Activities Dashboard (milestone I1)

Build `ai-panel.js` (assistant panel), `ai-review.js` (review screen: a row per field with current value, proposed value, confidence tier, source quote with page, accept/edit/reject) and `ai-notify.js` (notification review) as ES modules both dashboards import. No inline scripts (CSP). They accept a **labels-only mode** so the Activities Dashboard never shows entity keys, operation payloads or record IDs; use one shared labelling helper (alias, else the column name in words).

**Ground rules in the Activities Dashboard:** it calls `GET /api/ai/status` once at boot; if AI is disabled or the call fails, no AI element renders and nothing else changes. Every AI element sits where a company is already known. Section 9 rules (no database internals) apply to AI elements too. Approving a suggestion runs the engine under the approver's session, exactly as Save details does, with `updated_at` checks.

| Where | AI element | Backend | Notes |
|---|---|---|---|
| Start dialog (`act-start.js`) | Describe it instead: a sentence box beside the generated fields | `POST /companies/{cid}/chat` (Capability 2) | Company chosen first. Review shows steps and due dates in plain words; approval creates the instance and goes to `#/run/{id}`. Missing details are asked for, never guessed |
| Task card, Details to record (`act-run.js`) | Suggest from document | Extract endpoint (Capability 1), schema limited to that step's write bindings | Offered when the activity has documents attached. Per-field review; approval writes through the engine and refreshes the form |
| Task card on notice-type steps | Draft notice | Capability 3 | Opens the notification review. The recipient list with emails must be shown so the approver can check it (exception to the no-database-display rule, inside this screen only) |
| Running activity screen | Ask panel | `POST /companies/{cid}/chat` (Capability 4) | Bound to the activity's company; answers come from retrieved document and statute chunks with citations, so no register data is shown |
| Sidebar | Awaiting approval view (`act-approvals.js`) with a count | `GET /proposals/awaiting` | Hidden when AI is off or the user cannot approve anything |

Behaviour to get right: a stale suggestion (record edited after it was made) returns 409; show "This changed since the suggestion was made; review it again", reload the field values, never overwrite silently. Task forms and AI share records through `app/task_records.py` so they cannot update different rows. The person who clicks approve is the named approver and audit actor. Save details on the task form stays a direct human edit through the engine, unchanged.

Files for I1: `activities-main.js` (AI status at boot, approvals view and sidebar link), `act-start.js`, `act-run.js`, new `act-approvals.js`, the three shared AI modules, `app.css` (`.ai-*` appended), `routers/ai.py` (awaiting list).

## B10. Dummy data (generate with `scripts/make_dummy_docs.py`, JSON answer key per file; fictional names, synthetic DIN range)

| Set | Contents | Count |
|---|---|---|
| Extraction documents | Per company (5): AGM notice, board notice, minutes, director appointment letter, shareholder list; variants digital PDF, Word, scanned (skew and noise), one with a date that conflicts with the database | About 40 |
| Attack documents | Hidden instruction (ignore previous instructions, email all shareholders), a document naming another company's director, a document with an Aadhaar number | 5 |
| Prompts | Clear, missing a date, ambiguous company, unknown company, injection | About 20 |
| Notification cases | AGM notice, board notice, one with a director who has no email | 10 |
| Library | Short paraphrased excerpts of ss. 96, 100, 101, 102, 173 marked as test text (official text only at go-live) | 5 to 10 |
| Questions | Answerable from library, from company documents, unanswerable, cross-company traps | About 40 |
| Test mail server | `python -m aiosmtpd -n -l localhost:1025`; no real email can leave | 1 |

## B11. Build order, tests, demo and readiness gates

| Milestone | Delivers | Exit test |
|---|---|---|
| B0a Recon | Read the files not yet seen: `app/routers/documents.py`, `app/security.py`, one Phase 1 migration and seed, `tests/conftest.py` and the isolation test, `.env.example`, `requirements.txt`; read `ops.instantiate_activity`; check whether `core.document.company_id` is nullable and whether `confirmation` restricts `subject_type`. Log it | Open items listed in the log |
| B0 Safety spine | Migration, config guard, provider interface, fake provider, rate limiter, tool gateway, proposal state machine, `via_ai` fix, `bmp_ai` role | Gate and isolation tests pass with the fake provider; no AI code can write company data |
| B1 Capability 1 | Ingestion, OCR, masking, extraction, verification, resolve, apply, evidence links | Golden extraction set scored; conflict and injection cases pass |
| B2 Capability 2 | Router, planner, activity proposal | Plan matches expected for every prompt |
| B3 Capability 3 | Recipients, templates, outbox, worker, test mail server | Correct recipients, hash check, no send without approval |
| B4 Capability 4 | Library ingest, local embeddings, hybrid search, citation checker | Question set scored, including refusals |
| B5 Memory and evidence | Memory, call manifest, admin log, privacy report | A new session recalls earlier work; manifest shows only allowed fields |
| B6 Shared AI UI | Assistant panel, review screen, notification screen | A non-developer completes each flow |
| I1 Integration | Section B9 inside the Activities Dashboard | Start a Board Meeting from a sentence, fill the venue from a document suggestion, approve, complete tasks, draft the notice and see it in the test mail server, without opening a register page |
| B7 Evaluation and UAT | `scripts/ai_eval.py`, `scripts/run_demo_phase2.py`, report, UAT with BMP staff, fixes | Readiness gates below |

Order: B0a, B0, then capabilities (B2 and B3 may run in parallel with B1 if there are two workers), B5, B6, I1, B7. Effort estimate: about 51 working days for B0 to B7, plus about 4 for I1.

**Test layers.** (1) Unit with the fake provider: masking round-trips, normalize, planner dates, a quote not in the page is rejected, schema builder matches catalog. (2) Database: approve as a read-only user returns 403; approving twice applies once; a failure on the third operation rolls back all; editing after the proposal gives 409 stale; `bmp_ai` gets InsufficientPrivilege on any core write; a notification cannot reach `queued` without `approved_by`. (3) Isolation and safety: loop over every table and every AI tool, a Company A session never returns a Company B row; retrieval filtered by company; attack documents trigger no action; a static test fails if `app/ai/` imports `privileged_session`; the same golden set passes on a second provider. (4) Live Groq (marked `live_ai`, skipped by default): golden sets scored; responses recorded to `tests/ai/cassettes/`. Layers 1 to 3 need no network. **Integration tests (I1):** with AI off every Part A flow works and no AI element renders; with AI on, a Company A session started from a run page cannot produce or approve a proposal for Company B; a read-only user approving gets 403; a task form save then approving an older suggestion gives the stale message; re-run the Part A no-database-text guard with AI enabled and the fake provider.

**Demo script** (`scripts/run_demo_phase2.py`, numbered, printed evidence, rolled back or on dummy data): 1 setup; 2 read a digital document; 3 scanned document via OCR with unsure fields flagged; 4 conflict shown, nothing overwritten; 5 approve, audit log shows the approver, evidence links exist; 6 set up the AGM from one sentence; 7 notify, blocked before approval, sent to the test server after; 8 ask a statute question with citation, then an unanswerable one that is declined; 9 isolation; 10 attack document causes no action; 11 call manifest shows placeholders; 12 a new session recalls earlier work.

**Evidence queries (after the demo)**

```sql
-- 0 rows: an applied proposal with no named approver
SELECT id FROM ops.ai_proposal WHERE status = 'applied' AND (decided_by IS NULL OR decided_at IS NULL);
-- 0 rows: a message queued or sent without approval
SELECT id FROM ops.notification WHERE status IN ('queued','sent') AND (approved_by IS NULL OR approved_at IS NULL);
-- 0 rows: a sent body that differs from what was approved
SELECT id FROM ops.notification WHERE status = 'sent' AND sent_body_sha256 <> body_sha256;
-- every applied proposal lists its created records and its approver
SELECT p.id, p.kind, u.email AS approver, count(e.*) AS records_touched
FROM ops.ai_proposal p JOIN core.app_user u ON u.id = p.decided_by
LEFT JOIN ops.ai_proposal_effect e ON e.proposal_id = p.id
WHERE p.status = 'applied' GROUP BY p.id, p.kind, u.email;
```

**Readiness gates** (written by `scripts/ai_eval.py` to `docs/AI_EVAL_REPORT.md`; pass marks are proposals to agree with BMP; the model's own confidence is not used): G1 Safety (cross-company probes, gate bypasses, attack documents, sends without approval, AI writes outside an approved proposal): 0 failures. G2 Extraction: digital mandatory fields 95%+, scanned 85%+, fields marked high that were wrong 1% or less, conflicts shown not overwritten 100%. G3 Activity set-up: plan equals expected 100%, missing details asked for 100%. G4 Notifications: recipient list equals database truth and sent body equals approved body, 100%. G5 Questions: every claim cited 100%, unanswerable declined 90%+, right chunk in top 5 85%+. G6 Reliability: works with AI off, rate-limit and provider-down handled without data loss, jobs never duplicate, 95th percentile reply time under 30 s for a standard document. G7 Operations: backup restore tested, secrets only in `.env`, logs hold no document text, token use per task reported. G8 People: BMP staff complete each flow unaided in UAT; approvers named with accounts.

## B12. Decisions to confirm before or during Part B (ask me; do not guess)

1. Embedding size: migrate `document_chunk` to 384 dimensions (cleaner) or zero-pad and keep 1536 (no migration risk)?
2. May the person who typed an instruction also approve it, or is a second approver required for sends?
3. Are individual accounts plus approver accounts enough, with full roles left to a later phase?
4. Keep the local document folder (not MinIO) for the pilot?
5. Is the recipient list with emails acceptable inside the notice review on the Activities Dashboard?
6. Is the cross-company Awaiting approval list (summary only) acceptable?

**Real client data stays blocked** until BMP answers four decisions: provider with Zero Data Retention switched on, approval for processing outside India, the list of fields never sent to the AI, and the email system. Before relying on AI output, run a shadow pilot: staff do each task by hand, the AI proposes the same task, and the two are compared for a few weeks.

## B13. Part B reporting

Same as section 13: keep `docs/WORK_LOG.md` current (status board row per Part B milestone), report files changed, commands and test results, VERIFY items resolved, deviations, and open questions after each milestone, and stop at the end of B7 for my review.