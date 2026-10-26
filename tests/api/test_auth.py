"""Sign-in, sessions, CSRF, throttling, password changes."""
from tests.api.conftest import PASSWORDS, Session


def test_health_is_public(anon):
    r = anon.http.get("/api/health")
    assert r.status_code == 200 and r.json()["database"] is True


def test_api_requires_sign_in(anon):
    for path in ("/auth/me", "/meta", "/companies", "/entities/meeting", "/audit"):
        r = anon.get(path)
        assert r.status_code == 401, path
        assert r.json()["error"]["code"] == "unauthenticated"


def test_bad_password_and_unknown_user_look_the_same(app):
    a = Session(app).http.post("/api/auth/login", json={"email": "admin@bmpco.in", "password": "nope"})
    b = Session(app).http.post("/api/auth/login", json={"email": "ghost@nowhere.in", "password": "nope"})
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["message"] == b.json()["error"]["message"]


def test_login_returns_identity_and_csrf(admin):
    me = admin.ok(admin.get("/auth/me"))
    assert me["user"]["email"] == "admin@bmpco.in" and me["user"]["is_admin"] is True
    assert me["csrf"]


def test_changes_need_the_csrf_token(app):
    s = Session(app, "admin@bmpco.in", PASSWORDS["admin@bmpco.in"])
    del s.http.headers["X-CSRF-Token"]
    r = s.post("/entities/company_rta", {"company_id": 1, "name": "x", "valid_from": "2024-04-01"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf"
    s.http.headers["X-CSRF-Token"] = "wrong"
    assert s.post("/entities/company_rta", {"company_id": 1, "name": "x", "valid_from": "2024-04-01"}).status_code == 403


def test_sign_out_ends_the_session(app):
    s = Session(app, "manager@bmpco.in", PASSWORDS["manager@bmpco.in"])
    assert s.get("/auth/me").status_code == 200
    assert s.post("/auth/logout").status_code == 200
    assert s.get("/auth/me").status_code == 401


def test_repeated_failures_lock_out_then_recover(app, workdir):
    from tests.api.conftest import make_settings  # noqa: F401  (documented dependency)
    s = Session(app)
    for _ in range(5):
        assert s.http.post("/api/auth/login", json={"email": "manager@bmpco.in", "password": "bad"}).status_code == 401
    r = s.http.post("/api/auth/login", json={"email": "manager@bmpco.in", "password": PASSWORDS["manager@bmpco.in"]})
    assert r.status_code == 429                        # even the right password is refused while locked out
    app.state.throttle.clear(f"testclient|manager@bmpco.in")
    assert s.http.post("/api/auth/login", json={"email": "manager@bmpco.in", "password": PASSWORDS["manager@bmpco.in"]}).status_code == 200


def test_inactive_user_cannot_sign_in(app, owner, settings):
    from app.security import UsersStore
    UsersStore(settings.users_file).set_password("seed@system.internal", "Seed#Pass1234")
    owner.execute("SET app.current_user_id = '1'")
    r = Session(app).http.post("/api/auth/login", json={"email": "seed@system.internal", "password": "Seed#Pass1234"})
    # the seed user is active in the seed data; make it inactive and confirm the door closes
    owner.execute("UPDATE core.app_user SET is_active = false WHERE email = 'seed@system.internal'")
    r2 = Session(app).http.post("/api/auth/login", json={"email": "seed@system.internal", "password": "Seed#Pass1234"})
    owner.execute("UPDATE core.app_user SET is_active = true WHERE email = 'seed@system.internal'")
    assert r2.status_code == 401


def test_user_without_a_password_cannot_sign_in(app):
    r = Session(app).http.post("/api/auth/login", json={"email": "seed@system.internal", "password": ""})
    assert r.status_code == 401


def test_change_password(app, settings):
    from app.security import UsersStore
    UsersStore(settings.users_file).set_password("manager@bmpco.in", "Manager#Pass123")
    s = Session(app, "manager@bmpco.in", "Manager#Pass123")
    assert s.post("/auth/password", {"current_password": "wrong", "new_password": "NewPassw0rd!"}).status_code == 403
    assert s.post("/auth/password", {"current_password": "Manager#Pass123", "new_password": "short"}).status_code == 422
    assert s.post("/auth/password", {"current_password": "Manager#Pass123", "new_password": "NewPassw0rd!"}).status_code == 200
    assert Session(app).http.post("/api/auth/login", json={"email": "manager@bmpco.in", "password": "Manager#Pass123"}).status_code == 401
    assert Session(app).http.post("/api/auth/login", json={"email": "manager@bmpco.in", "password": "NewPassw0rd!"}).status_code == 200
    UsersStore(settings.users_file).set_password("manager@bmpco.in", "Manager#Pass123")     # restore for later tests


def test_only_an_admin_can_set_another_users_password(admin, manager, owner):
    uid = owner.execute("SELECT id FROM core.app_user WHERE email = 'client@nexatech.co.in'").fetchone()["id"]
    assert manager.post(f"/admin/users/{uid}/password", {"new_password": "Whatever#123"}).status_code == 403
    assert admin.post(f"/admin/users/{uid}/password", {"new_password": "Client#Pass123"}).status_code == 200
