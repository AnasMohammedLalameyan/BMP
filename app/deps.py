"""FastAPI dependencies shared by the routers: the signed-in user and the database session."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import Depends, Request

from .access import UserCtx, load_user
from .errors import ApiError, forbidden
from .security import csrf_ok

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def current_user(request: Request) -> UserCtx:
    uid = request.session.get("uid")
    if not uid:
        raise ApiError(401, "unauthenticated", "Please sign in")
    if request.method not in SAFE_METHODS and not csrf_ok(
            request.session.get("csrf"), request.headers.get("x-csrf-token")):
        raise ApiError(403, "csrf", "Your session token is missing or out of date. Reload the page.")
    with request.app.state.db.tx(None, readonly=True) as conn:
        ctx = load_user(conn, int(uid))
    if ctx is None:
        request.session.clear()
        raise ApiError(401, "unauthenticated", "Your account is not active")
    return ctx


def admin_user(ctx: UserCtx = Depends(current_user)) -> UserCtx:
    if not ctx.is_admin:
        raise forbidden("Administrator access is required")
    return ctx


@contextmanager
def session(request: Request, ctx: UserCtx, *, readonly: bool = False):
    """A database transaction on behalf of the user (sets app.current_user_id)."""
    with request.app.state.db.tx(ctx.id, readonly=readonly) as conn:
        yield conn


@contextmanager
def privileged_session(request: Request, ctx: UserCtx, *, readonly: bool = False):
    """A transaction on the privileged (owner) connection - used only for the audit log and
    for onboarding a new company, both of which the application login cannot do by design."""
    db = request.app.state.db_privileged
    if db is None:
        raise ApiError(501, "not_configured", "This action needs DATABASE_URL_PRIVILEGED to be configured")
    with db.tx(ctx.id, readonly=readonly) as conn:
        yield conn


def writable_company(ctx: UserCtx, company_id: int) -> None:
    if company_id not in ctx.writable:
        if company_id in ctx.access:
            raise forbidden("You have read-only access to this company")
        raise ApiError(404, "not_found", "Company not found")


def readable_company(ctx: UserCtx, company_id: int) -> None:
    if company_id not in ctx.access:
        raise ApiError(404, "not_found", "Company not found")
