"""The endpoints added or extended for the client's UI change set (people overview, notifications, director register filters)."""
import pytest


def readable(session):
    return {int(c) for c in session.ok(session.get("/auth/me"))["user"]["access"]}


# ======================= Change 1: GET /api/people/directors =======================

def test_people_directors_needs_a_sign_in(anon):
    assert anon.get("/people/directors").status_code == 401


def test_admin_sees_every_person_with_their_roles_across_companies(admin, owner):
    data = admin.ok(admin.get("/people/directors"))
    everyone = owner.execute("SELECT count(*) AS n FROM core.director WHERE NOT is_archived").fetchone()["n"]
    assert data["total"] == len(data["people"]) == everyone
    joshi = next(p for p in data["people"] if p["full_name"] == "Prashant Joshi")
    assert {r["company_id"] for r in joshi["roles"]} == {1, 2}                      # one person, roles in two companies
    assert len(joshi["roles"]) == 3                                                   # resigned, re-appointed, and the Nexatech stint
    assert {"directorship_id", "company_name", "start_date", "end_date", "designation", "is_current"} <= set(joshi["roles"][0])
    ordered = [r["full_name"] for r in owner.execute("SELECT full_name FROM core.director WHERE NOT is_archived ORDER BY full_name, id")]
    assert [p["full_name"] for p in data["people"]] == ordered                        # ordered by name, as the database sorts it


@pytest.mark.parametrize("query,expected", [("joshi", {"Prashant Joshi"}), ("12340012", None), ("brightmed", None), ("zzz-nobody", set())])
def test_people_directors_search_by_name_din_and_company(admin, owner, query, expected):
    found = admin.ok(admin.get("/people/directors", params={"q": query}))["people"]
    if query == "12340012":
        expected = {r["full_name"] for r in owner.execute("SELECT full_name FROM core.director WHERE din ILIKE %s", ("%12340012%",))}
    if query == "brightmed":
        expected = {r["full_name"] for r in owner.execute(
            """SELECT DISTINCT d.full_name FROM core.director d JOIN core.directorship s ON s.director_id = d.id
               JOIN core.company c ON c.id = s.company_id WHERE c.name ILIKE '%brightmed%' AND NOT s.is_archived""")}
    assert {p["full_name"] for p in found} == expected


def test_people_directors_percent_and_underscore_in_a_search_are_literal(admin):
    """`%` and `_` are ordinary characters in a search, not wildcards (other tests create names such as full_name_22)."""
    assert admin.ok(admin.get("/people/directors", params={"q": "%"}))["total"] == 0
    everyone = admin.ok(admin.get("/people/directors"))["total"]
    found = admin.ok(admin.get("/people/directors", params={"q": "_"}))["people"]
    assert len(found) < everyone                                                       # not "match everything"
    for p in found:
        assert "_" in " ".join([p["full_name"], p["din"] or "", *[r["company_name"] for r in p["roles"]]]), p["full_name"]


@pytest.mark.parametrize("who", ["client", "manager", "admin"])
def test_people_directors_roles_never_leave_the_users_companies(request, owner, who):
    """The isolation loop for the new endpoint: a client sees only their company's people, a manager and an admin see
    only roles in the companies they may open."""
    s = request.getfixturevalue(who)
    ok_companies = readable(s)
    people = s.ok(s.get("/people/directors"))["people"]
    for p in people:
        assert {r["company_id"] for r in p["roles"]} <= ok_companies, (who, p["full_name"])
    listed = {p["id"] for p in people}
    generic = {r["id"] for r in s.ok(s.get("/entities/director", params={"size": 5000}))["rows"]}
    assert listed == generic                                                          # same people as the existing people table
    if who == "client":
        everyone = owner.execute("SELECT count(*) AS n FROM core.director WHERE NOT is_archived").fetchone()["n"]
        assert ok_companies == {1} and all(p["roles"] for p in people) and 0 < len(people) < everyone
        assert "Prashant Joshi" in {p["full_name"] for p in people}
        assert all({r["company_id"] for r in p["roles"]} == {1} for p in people)     # Joshi's BrightMed roles are not shown
    if who == "manager":
        assert ok_companies == {2, 3, 4}


# ======================= Change 1: GET /api/notifications =======================

def test_notifications_need_a_sign_in(anon):
    assert anon.get("/notifications").status_code == 401


def owner_counts(owner, ids):
    tasks = {r["company_id"]: r for r in owner.execute(
        """SELECT i.company_id, count(*) FILTER (WHERE k.due_date < current_date) AS overdue,
                  count(*) FILTER (WHERE k.due_date >= current_date) AS soon
           FROM ops.task_instance k JOIN ops.activity_instance i ON i.id = k.instance_id
           WHERE i.company_id = ANY(%s) AND NOT k.is_archived AND NOT i.is_archived AND k.status NOT IN ('completed', 'skipped')
             AND k.due_date IS NOT NULL AND k.due_date <= current_date + 7 GROUP BY 1""", (ids,))}
    filings = {r["company_id"]: r["n"] for r in owner.execute(
        "SELECT company_id, count(*) AS n FROM core.v_filings_overdue WHERE company_id = ANY(%s) GROUP BY 1", (ids,))}
    conf = {r["company_id"]: r["n"] for r in owner.execute(
        """SELECT i.company_id, count(*) AS n FROM ops.confirmation c JOIN ops.task_instance k ON k.id = c.subject_id
           JOIN ops.activity_instance i ON i.id = k.instance_id
           WHERE c.subject_type = 'task_instance' AND c.status = 'pending' AND NOT c.is_archived AND i.company_id = ANY(%s)
             AND NOT k.is_archived AND NOT i.is_archived GROUP BY 1""", (ids,))}
    rules = {r["company_id"]: r["n"] for r in owner.execute(
        """SELECT c.id AS company_id, count(*) AS n FROM core.company c CROSS JOIN core.rule_definition r
           JOIN LATERAL (SELECT x.status FROM core.rule_evaluation x WHERE x.rule_id = r.id AND x.company_id = c.id AND NOT x.is_archived
                         ORDER BY x.evaluated_on DESC, x.id DESC LIMIT 1) e ON TRUE
           WHERE c.id = ANY(%s) AND r.is_active AND NOT r.is_archived AND e.status = 'action_required' GROUP BY 1""", (ids,))}
    return tasks, filings, conf, rules


@pytest.mark.parametrize("who", ["client", "manager", "admin"])
def test_notifications_cover_only_the_users_companies_and_match_the_data(request, owner, who):
    s = request.getfixturevalue(who)
    data = s.ok(s.get("/notifications"))
    archived = {r["id"] for r in owner.execute("SELECT id FROM core.company WHERE is_archived")}          # archived companies are not listed
    ids = sorted(readable(s) - archived)
    assert sorted(c["company_id"] for c in data["companies"]) == ids
    tasks, filings, conf, rules = owner_counts(owner, ids)
    for c in data["companies"]:
        cid, n = c["company_id"], c["counts"]
        assert set(n) == {"overdue_filings", "overdue_tasks", "due_soon_tasks", "pending_confirmations", "rules_action_required"}
        assert n["overdue_filings"] == filings.get(cid, 0)
        assert n["overdue_tasks"] == (tasks[cid]["overdue"] if cid in tasks else 0)
        assert n["due_soon_tasks"] == (tasks[cid]["soon"] if cid in tasks else 0)
        assert n["pending_confirmations"] == conf.get(cid, 0)
        assert n["rules_action_required"] == rules.get(cid, 0)
        assert c["total"] == sum(n.values()) == len(c["items"])
        assert all({"kind", "level", "title", "detail", "view"} <= set(i) for i in c["items"])
    assert data["total"] == sum(c["total"] for c in data["companies"])


def test_notification_counts_agree_with_the_overview_page(admin):
    for c in admin.ok(admin.get("/notifications"))["companies"]:
        tiles = admin.ok(admin.get(f"/companies/{c['company_id']}/overview"))["tiles"]
        assert c["counts"]["overdue_filings"] == tiles["overdue_filings"]
        assert c["counts"]["overdue_tasks"] == tiles["overdue_tasks"]


def test_the_seeded_demo_data_produces_notifications_for_brightmed_and_nexatech(admin):
    byco = {c["company_id"]: c for c in admin.ok(admin.get("/notifications"))["companies"]}
    assert byco[2]["counts"]["overdue_filings"] >= 1 and byco[2]["counts"]["rules_action_required"] >= 1       # MGT-7 and the woman-director rule
    assert byco[1]["counts"]["overdue_tasks"] >= 1                                                           # the seeded Board Meeting is past its dates
    assert any(i["view"] == "entity:government_filing" for i in byco[2]["items"])


def test_a_pending_confirmation_shows_up_for_the_company_and_leaves_when_decided(admin):
    """Uses the seeded Nexatech Board Meeting (company 1); the request is rejected again at the end, so the data is as it was."""
    inst = admin.ok(admin.get("/companies/1/activities"))["instances"][0]
    tasks = admin.ok(admin.get(f"/activities/instances/{inst['id']}"))["tasks"]
    task = next(t for t in tasks if t["step"]["requires_confirmation"] and t["status"] != "completed" and not t["confirmations"])

    def waiting():
        return next(c for c in admin.ok(admin.get("/notifications"))["companies"] if c["company_id"] == 1)

    before = waiting()["counts"]["pending_confirmations"]
    conf = admin.ok(admin.post(f"/activities/tasks/{task['id']}/confirmations", {}), status=201)["confirmation"]
    after = waiting()
    assert after["counts"]["pending_confirmations"] == before + 1
    assert any(i["kind"] == "pending_confirmations" and task["step"]["title"] in i["title"] for i in after["items"])
    admin.ok(admin.post(f"/confirmations/{conf['id']}/reject"))
    assert waiting()["counts"]["pending_confirmations"] == before


# ======================= Change 9: Address and Phone Number =======================
# Field check: the spec's director.address / director.phoneNumber are core.director.address and core.director.phone (both text, nullable,
# already in the approved database), so no migration was needed.

def test_the_directors_register_payload_carries_address_and_phone(admin):
    rows = admin.ok(admin.get("/companies/2/directors-register"))["rows"]
    assert rows and all("address" in r and "phone" in r for r in rows)
    assert any(r["address"] for r in rows) and any(r["phone"] for r in rows)


def test_address_and_phone_round_trip_through_the_record_editor_and_appear_in_history(admin, uniq):
    long_address = ("Plot 12, Sector 18, " * 12)[:200].strip()          # text values are stored trimmed
    created = admin.ok(admin.post("/entities/director", {"full_name": "Address Test Person", "din": f"61{uniq():06d}",
                                                         "address": long_address, "phone": "+91 98765 43210"}), status=201)["row"]
    pk = created["_pk"]
    got = admin.ok(admin.get(f"/entities/director/{pk}"))["row"]
    assert got["address"] == long_address and got["phone"] == "+91 98765 43210"                  # stored exactly, no reformatting
    cols = {c["name"]: c for c in admin.ok(admin.get("/meta"))["entities"]["director"]["columns"]}
    assert cols["address"]["writable"] and cols["phone"]["writable"]                          # the editor offers both fields
    patched = admin.ok(admin.patch(f"/entities/director/{pk}", {"address": "New address, Pune 411001", "phone": "020-2600 1234",
                                                                  "updated_at": got["updated_at"]}))["row"]
    assert patched["address"] == "New address, Pune 411001" and patched["phone"] == "020-2600 1234"
    history = admin.ok(admin.get(f"/entities/director/{pk}/history"))["entries"]
    changed = [e["changes"] for e in history if e["operation"] == "UPDATE"]
    assert any(c.get("address", {}).get("to") == "New address, Pune 411001" and c.get("phone", {}).get("from") == "+91 98765 43210"
               for c in changed)
    admin.ok(admin.post(f"/entities/director/{pk}/archive"))                                  # nothing is deleted; tidy up by archiving
