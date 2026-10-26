"""Notifications: what needs a person's attention, company by company (read only, no e-mail).

The numbers use the same sources as the Overview page (`core.v_filings_overdue`, `ops.task_instance`, rule evaluations), so the
two always agree. Only companies the signed-in user may open are included."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..access import UserCtx
from ..deps import current_user, session
from ..responses import ok

router = APIRouter(tags=["notifications"])

DUE_SOON_DAYS = 7
KINDS = ("overdue_filings", "overdue_tasks", "due_soon_tasks", "pending_confirmations", "rules_action_required")

TASKS_SQL = """
SELECT i.company_id, k.id AS task_id, s.title, t.name AS activity, k.due_date,
       (k.due_date < current_date) AS overdue
FROM ops.task_instance k
JOIN ops.activity_instance i ON i.id = k.instance_id
JOIN activity.step_template s ON s.id = k.step_id
JOIN activity.activity_template t ON t.id = i.template_id
WHERE i.company_id = ANY(%(ids)s::bigint[]) AND NOT k.is_archived AND NOT i.is_archived
  AND k.status NOT IN ('completed', 'skipped') AND k.due_date IS NOT NULL
  AND k.due_date <= current_date + %(soon)s
ORDER BY k.due_date, k.id
"""

CONFIRMATIONS_SQL = """
SELECT i.company_id, c.id AS confirmation_id, s.title, ru.name AS requested_by_name, c.created_at
FROM ops.confirmation c
JOIN ops.task_instance k ON k.id = c.subject_id
JOIN ops.activity_instance i ON i.id = k.instance_id
JOIN activity.step_template s ON s.id = k.step_id
LEFT JOIN core.app_user ru ON ru.id = c.requested_by
WHERE c.subject_type = 'task_instance' AND c.status = 'pending' AND NOT c.is_archived
  AND i.company_id = ANY(%(ids)s::bigint[]) AND NOT k.is_archived AND NOT i.is_archived
ORDER BY c.created_at, c.id
"""

# a rule needs action when the latest recorded evaluation of it for that company says so
RULES_SQL = """
SELECT c.id AS company_id, r.code, r.name, e.financial_year
FROM core.company c
CROSS JOIN core.rule_definition r
JOIN LATERAL (SELECT x.status, x.financial_year FROM core.rule_evaluation x
              WHERE x.rule_id = r.id AND x.company_id = c.id AND NOT x.is_archived
              ORDER BY x.evaluated_on DESC, x.id DESC LIMIT 1) e ON TRUE
WHERE c.id = ANY(%(ids)s::bigint[]) AND NOT c.is_archived AND r.is_active AND NOT r.is_archived AND e.status = 'action_required'
ORDER BY r.name
"""


@router.get("/notifications")
def notifications(request: Request, ctx: UserCtx = Depends(current_user)):
    """Per company: overdue MCA filings, overdue tasks, tasks due within 7 days, confirmations waiting for a person,
    and rules whose latest evaluation says action is required. `total` is the number shown on the bell."""
    ids = ctx.readable
    params = {"ids": ids, "soon": DUE_SOON_DAYS}
    with session(request, ctx, readonly=True) as conn:
        companies = conn.execute("SELECT id, name FROM core.company WHERE id = ANY(%(ids)s::bigint[]) AND NOT is_archived ORDER BY name",
                                 params).fetchall()
        filings = conn.execute("SELECT company_id, form_name, financial_year, due_date, days_overdue FROM core.v_filings_overdue "
                               "WHERE company_id = ANY(%(ids)s::bigint[]) ORDER BY due_date", params).fetchall()
        tasks = conn.execute(TASKS_SQL, params).fetchall()
        confirmations = conn.execute(CONFIRMATIONS_SQL, params).fetchall()
        rules = conn.execute(RULES_SQL, params).fetchall()

    out = {c["id"]: {"company_id": c["id"], "company_name": c["name"], "counts": {k: 0 for k in KINDS}, "items": []} for c in companies}

    def add(company_id, kind, level, title, detail, view):
        entry = out.get(company_id)
        if entry is None:
            return
        entry["counts"][kind] += 1
        entry["items"].append({"kind": kind, "level": level, "title": title, "detail": detail, "view": view})

    for f in filings:
        add(f["company_id"], "overdue_filings", "no", f"{f['form_name']} overdue", f"Due {f['due_date']} - {f['days_overdue']} days overdue",
            "entity:government_filing")
    for k in tasks:
        if k["overdue"]:
            add(k["company_id"], "overdue_tasks", "no", f"Task overdue: {k['title']}", f"{k['activity']} - due {k['due_date']}", "activities")
        else:
            add(k["company_id"], "due_soon_tasks", "part", f"Task due soon: {k['title']}", f"{k['activity']} - due {k['due_date']}", "activities")
    for c in confirmations:
        who = f" (asked by {c['requested_by_name']})" if c["requested_by_name"] else ""
        add(c["company_id"], "pending_confirmations", "prog", f"Confirmation waiting: {c['title']}", f"A named person must confirm{who}", "activities")
    for r in rules:
        add(r["company_id"], "rules_action_required", "no", f"Rule needs action: {r['name']}", f"{r['code']} - evaluated for {r['financial_year']}", "rules")

    rows = list(out.values())
    for entry in rows:
        entry["total"] = sum(entry["counts"].values())
    return ok({"total": sum(e["total"] for e in rows), "companies": rows})
