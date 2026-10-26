"""Company isolation and access levels, proven across every table.

client  : read-only on Nexatech (company 1)
manager : write on BrightMed, Greenfield, Skyward (2, 3, 4); no access to 1 or 5
admin   : admin on all five
"""
import pytest

from app.registry import ENTITIES, SCOPE

ALL = sorted(ENTITIES)


def rows(sess, key, **params):
    return sess.get(f"/entities/{key}", params={"size": 5000, "archived": "true", **params})


@pytest.fixture(scope="module")
def company_scoped(admin):
    """Tables that carry a company_id column."""
    ent = admin.ok(admin.get("/meta"))["entities"]
    return {k for k, e in ent.items() if any(c["name"] == "company_id" for c in e["columns"])}


@pytest.mark.parametrize("key", ALL)
def test_client_never_sees_another_company_in_any_table(client, admin, company_scoped, key):
    r = rows(client, key)
    if r.status_code == 404:                       # administration tables are hidden entirely
        assert SCOPE.get(key, {}).get("type") == "admin"
        return
    assert r.status_code == 200, r.text
    got = r.json()["rows"]
    if key == "company":
        assert {x["id"] for x in got} <= {1}
    elif key in company_scoped:
        assert {x["company_id"] for x in got} <= {1}, key
    # never more than the administrator can see
    allrows = {x["_pk"] for x in rows(admin, key).json()["rows"]}
    assert {x["_pk"] for x in got} <= allrows


@pytest.mark.parametrize("key", ALL)
def test_manager_only_sees_own_companies_in_any_table(manager, company_scoped, key):
    r = rows(manager, key)
    if r.status_code == 404:
        return
    got = r.json()["rows"]
    if key == "company":
        assert {x["id"] for x in got} <= {2, 3, 4}
    elif key in company_scoped:
        assert {x["company_id"] for x in got} <= {2, 3, 4}, key


def test_shared_people_tables_are_narrowed_for_read_only_users(client, admin, owner):
    expect = {r["director_id"] for r in owner.execute("SELECT director_id FROM core.directorship WHERE company_id = 1")}
    assert {r["id"] for r in rows(client, "director").json()["rows"]} == expect
    assert len(rows(admin, "director").json()["rows"]) == 12
    holders = {r["shareholder_id"] for r in owner.execute(
        "SELECT shareholder_id FROM core.shareholding WHERE company_id = 1 UNION SELECT shareholder_id FROM core.allotment "
        "WHERE company_id = 1 UNION SELECT transferor_id FROM core.share_transfer WHERE company_id = 1 "
        "UNION SELECT transferee_id FROM core.share_transfer WHERE company_id = 1")}
    assert {r["id"] for r in rows(client, "shareholder").json()["rows"]} == holders


def test_child_tables_follow_their_parents_company(client, manager, owner):
    # attendance exists only for BrightMed (company 2)
    assert rows(client, "meeting_attendance").json()["total"] == 0
    assert rows(manager, "meeting_attendance").json()["total"] == 12
    own_agenda = owner.execute("SELECT count(*) AS n FROM core.meeting_agenda_item a JOIN core.meeting m ON m.id = a.meeting_id "
                               "WHERE m.company_id = 1").fetchone()["n"]
    assert rows(client, "meeting_agenda_item").json()["total"] == own_agenda
    all_agenda = owner.execute("SELECT count(*) AS n FROM core.meeting_agenda_item").fetchone()["n"]
    assert own_agenda < all_agenda                      # the client really is seeing a subset
    expected = owner.execute("SELECT count(*) AS n FROM core.directorship_role r JOIN core.directorship d "
                             "ON d.id = r.directorship_id WHERE d.company_id = 1").fetchone()["n"]
    assert rows(client, "directorship_role").json()["total"] == expected
    assert rows(client, "committee_member").json()["total"] == 0


def test_administration_tables_are_admin_only(client, manager, admin):
    for key in ("app_user", "user_company_access"):
        assert client.get(f"/entities/{key}").status_code == 404
        assert manager.get(f"/entities/{key}").status_code == 404
        assert admin.get(f"/entities/{key}").status_code == 200


def test_calculated_views_are_scoped_even_though_the_database_views_are_not(client, manager, admin, owner):
    for view in ("v_current_directors", "v_shareholding_percent", "v_filings_overdue", "v_director_history", "v_top10_shareholders"):
        got = client.ok(client.get(f"/calc/{view}"))["rows"]
        assert {r["company_id"] for r in got} <= {1}, view
    # director age has no company_id: it must still be narrowed to people linked to the user's companies
    ages = client.ok(client.get("/calc/v_director_age"))["rows"]
    linked = {r["director_id"] for r in owner.execute("SELECT director_id FROM core.directorship WHERE company_id = 1")}
    assert {r["director_id"] for r in ages} == linked
    assert len(admin.ok(admin.get("/calc/v_director_age"))["rows"]) == 12
    assert client.get("/calc/v_current_directors", params={"company_id": 2}).status_code == 404
    assert manager.get("/calc/v_current_directors", params={"company_id": 1}).status_code == 404


def test_company_pages_are_closed_to_people_without_access(client, manager):
    for path in ("/companies/2/overview", "/companies/2/years", "/companies/2/directors-register", "/companies/2/meetings-book",
                 "/companies/2/rules", "/companies/2/activities", "/companies/2/export.xlsx", "/companies/2/export.json"):
        assert client.get(path).status_code == 404, path
    assert manager.get("/companies/1/overview").status_code == 404
    assert [c["id"] for c in client.ok(client.get("/companies"))["companies"]] == [1]
    assert [c["id"] for c in manager.ok(manager.get("/companies"))["companies"]] == [2, 3, 4]


def test_a_read_only_user_cannot_write_anything(client):
    r = client.post("/entities/company_rta", {"company_id": 1, "name": "Nope", "valid_from": "2024-04-01"})
    assert r.status_code == 403
    first = client.ok(client.get("/entities/director", params={"company_id": 1}))["rows"][0]
    assert client.patch(f"/entities/director/{first['_pk']}", {"phone": "1", "updated_at": first["updated_at"]}).status_code == 403
    mt = client.ok(client.get("/entities/meeting", params={"company_id": 1}))["rows"][0]
    assert client.patch(f"/entities/meeting/{mt['_pk']}", {"remarks": "x", "updated_at": mt["updated_at"]}).status_code == 403
    assert client.post(f"/entities/meeting/{mt['_pk']}/archive").status_code == 403
    assert client.post("/activities/instances", {"template_code": "BOARD_MEETING", "company_id": 1, "params": {}}).status_code == 403
    assert client.put(f"/meetings/{mt['_pk']}/attendance", {"rows": []}).status_code == 403


def test_a_user_cannot_write_to_a_company_they_have_no_access_to(manager):
    assert manager.post("/entities/company_rta", {"company_id": 1, "name": "No", "valid_from": "2024-04-01"}).status_code == 403
    assert manager.post("/entities/company_rta", {"company_id": 5, "name": "No", "valid_from": "2024-04-01"}).status_code == 403


def test_a_user_cannot_touch_another_companys_record_by_id(manager, admin):
    other = admin.ok(admin.get("/entities/meeting", params={"company_id": 1}))["rows"][0]
    assert manager.get(f"/entities/meeting/{other['_pk']}").status_code == 404
    assert manager.patch(f"/entities/meeting/{other['_pk']}", {"remarks": "hijack", "updated_at": other["updated_at"]}).status_code == 404
    assert manager.post(f"/entities/meeting/{other['_pk']}/archive").status_code == 404
    assert manager.get(f"/meetings/{other['_pk']}/detail").status_code == 404
    assert manager.get(f"/entities/meeting/{other['_pk']}/history").status_code == 404


def test_cross_company_references_are_refused(manager, admin):
    """The database's foreign-key check ignores row-level security, so the API must not let a record point at
    another company's row."""
    foreign_stint = admin.ok(admin.get("/entities/directorship", params={"company_id": 1}))["rows"][0]["id"]
    mtype = admin.ok(admin.get("/meta"))["lookups"]["MEETING_TYPE"][0]["id"]
    r = manager.post("/entities/meeting", {
        "company_id": 2, "meeting_type_id": mtype, "financial_year": "2024-25", "meeting_date": "2024-12-01",
        "chairperson_directorship_id": foreign_stint})
    assert r.status_code == 422, r.text
    assert "chairperson_directorship_id" in r.json()["error"]["fields"]


def test_options_are_scoped(client):
    assert client.ok(client.get("/options/meeting", params={"company_id": 1}))["options"]
    assert client.ok(client.get("/options/meeting", params={"company_id": 2}))["options"] == []
    assert client.get("/options/app_user").status_code == 404


def test_audit_log_is_narrowed_to_the_users_companies(client, manager, admin):
    c = client.ok(client.get("/audit", params={"limit": 500}))["entries"]
    assert c and all(e["table"] != "app_user" for e in c)
    assert client.get("/audit", params={"company_id": 2}).status_code == 404
    full = admin.ok(admin.get("/audit", params={"limit": 500}))["entries"]
    assert len(full) > len(c)
    m = manager.ok(manager.get("/audit", params={"limit": 500}))["entries"]
    assert not any(e["table"] == "company" and e["record_id"] == 1 for e in m)


def test_a_client_cannot_see_the_documents_of_another_company(client, owner):
    other = owner.execute("SELECT id FROM core.document WHERE company_id <> 1 LIMIT 1").fetchone()
    if other:
        assert client.get(f"/documents/{other['id']}/download").status_code == 404
