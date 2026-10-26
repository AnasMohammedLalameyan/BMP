"""Sign in, sign out, who am I, change password, and (admin) set another user's password."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..access import UserCtx
from ..deps import admin_user, current_user, session
from ..errors import ApiError, bad_request, not_found
from ..responses import ok
from ..security import MIN_PASSWORD_LENGTH, csrf_ok, new_csrf_token, verify_password

router = APIRouter(tags=["auth"])


class Login(BaseModel):
    email: str
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class PasswordSet(BaseModel):
    new_password: str


def _client_key(request: Request, email: str) -> str:
    host = request.client.host if request.client else "?"
    return f"{host}|{email.strip().lower()}"


@router.post("/auth/login")
def login(body: Login, request: Request):
    email = body.email.strip().lower()
    throttle = request.app.state.throttle
    key = _client_key(request, email)
    if throttle.blocked(key):
        raise ApiError(429, "too_many_attempts", "Too many failed sign-in attempts. Try again in a few minutes.")
    stored = request.app.state.users.hash_for(email)
    password_ok = verify_password(body.password, stored)
    user_id = None
    if password_ok:
        with request.app.state.db.tx(None, readonly=True) as conn:
            row = conn.execute(
                "SELECT id FROM core.app_user WHERE lower(email) = %s AND is_active AND NOT is_archived", (email,)
            ).fetchone()
        user_id = row["id"] if row else None
    if not (password_ok and user_id):
        throttle.fail(key)
        raise ApiError(401, "bad_credentials", "Email or password is incorrect")
    throttle.clear(key)
    request.session.clear()                      # new session on sign-in (no fixation)
    request.session["uid"] = user_id
    request.session["csrf"] = new_csrf_token()
    with request.app.state.db.tx(None, readonly=True) as conn:
        from ..access import load_user
        ctx = load_user(conn, user_id)
    return ok({"user": ctx.public(), "csrf": request.session["csrf"]})


@router.post("/auth/logout")
def logout(request: Request):
    if request.session.get("uid") and not csrf_ok(request.session.get("csrf"), request.headers.get("x-csrf-token")):
        raise ApiError(403, "csrf", "Your session token is missing or out of date. Reload the page.")
    request.session.clear()
    return ok({"ok": True})


@router.get("/auth/me")
def me(request: Request, ctx: UserCtx = Depends(current_user)):
    if not request.session.get("csrf"):
        request.session["csrf"] = new_csrf_token()
    return ok({"user": ctx.public(), "csrf": request.session["csrf"]})


@router.post("/auth/password")
def change_password(body: PasswordChange, request: Request, ctx: UserCtx = Depends(current_user)):
    users = request.app.state.users
    if not verify_password(body.current_password, users.hash_for(ctx.email)):
        raise ApiError(403, "bad_credentials", "Your current password is incorrect")
    try:
        users.set_password(ctx.email, body.new_password)
    except ValueError as e:
        raise bad_request(str(e), {"new_password": str(e)})
    return ok({"ok": True})


@router.post("/admin/users/{user_id}/password")
def admin_set_password(user_id: int, body: PasswordSet, request: Request, ctx: UserCtx = Depends(admin_user)):
    with session(request, ctx, readonly=True) as conn:
        row = conn.execute("SELECT email FROM core.app_user WHERE id = %s", (user_id,)).fetchone()
    if row is None:
        raise not_found("User")
    try:
        request.app.state.users.set_password(row["email"], body.new_password)
    except ValueError as e:
        raise bad_request(str(e), {"new_password": f"At least {MIN_PASSWORD_LENGTH} characters"})
    return ok({"ok": True, "email": row["email"]})
