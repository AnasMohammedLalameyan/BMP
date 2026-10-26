"""One error type for the API, and the translation of database errors into it.

The database is the authority on what is valid (constraints, triggers, row-level
security). The API does not re-implement those rules; it only turns the database's
refusal into a status code and a sentence a person can act on.
"""
from __future__ import annotations

import logging
import re

import psycopg
from psycopg import errors as pgerr

log = logging.getLogger("bmp.errors")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, fields: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields or {}

    def body(self) -> dict:
        out = {"error": {"code": self.code, "message": self.message}}
        if self.fields:
            out["error"]["fields"] = self.fields
        return out


def bad_request(message: str, fields: dict | None = None) -> ApiError:
    return ApiError(422, "validation", message, fields)


def not_found(what: str = "Record") -> ApiError:
    return ApiError(404, "not_found", f"{what} not found")


def forbidden(message: str = "You do not have permission to do that") -> ApiError:
    return ApiError(403, "forbidden", message)


def conflict(message: str, code: str = "conflict") -> ApiError:
    return ApiError(409, code, message)


# Friendly text for the named CHECK constraints in the schema. Anything not listed
# falls back to a generic sentence that still names the constraint.
_CHECK_TEXT = [
    (r"financial_year_check", "Financial year must look like 2024-25."),
    (r"company_cin_check", "CIN must be exactly 21 characters."),
    (r"director_din_check", "DIN must be exactly 8 digits."),
    (r"director_gender_check", "Gender must be M, F or Other."),
    (r"fi_one_reference", "Give exactly one of: allotment (FC-GPR) or share transfer (FC-TRS)."),
    (r"attendance_type_fk_check", "A director needs a directorship, a member needs a shareholder."),
    (r"number_of_shares_check", "Number of shares must be greater than zero."),
    (r"turnover_percent_check", "Turnover percentage must be between 0 and 100."),
    (r"term_no_check", "Term number must be 1 or 2."),
    (r"step_template_check|deadline", "Deadline anchor, offset and direction must be given together."),
]


def _friendly_check(constraint: str | None) -> str:
    for pattern, text in _CHECK_TEXT:
        if constraint and re.search(pattern, constraint):
            return text
    return f"A value is not allowed ({constraint})." if constraint else "A value is not allowed."


def map_db_error(exc: Exception) -> ApiError:
    """Translate a psycopg exception into an ApiError."""
    if isinstance(exc, ApiError):
        return exc
    diag = getattr(exc, "diag", None)
    constraint = getattr(diag, "constraint_name", None)
    column = getattr(diag, "column_name", None)
    detail = (getattr(diag, "message_detail", None) or "").strip()
    primary = (getattr(diag, "message_primary", None) or str(exc)).strip()

    if isinstance(exc, pgerr.UniqueViolation):
        return conflict(f"That record already exists. {detail}".strip(), "duplicate")
    if isinstance(exc, pgerr.ExclusionViolation):
        return conflict("This overlaps an existing period for the same record. " + detail, "overlap")
    if isinstance(exc, pgerr.ForeignKeyViolation):
        return bad_request("This refers to a record that does not exist, or that is still in use. " + detail)
    if isinstance(exc, pgerr.CheckViolation):
        return bad_request(_friendly_check(constraint))
    if isinstance(exc, pgerr.NotNullViolation):
        field = column or "a required field"
        return bad_request(f"{field} is required.", {column: "Required"} if column else None)
    if isinstance(exc, pgerr.RaiseException):
        # Messages raised by the schema's own triggers are written for people.
        return bad_request(primary)
    if isinstance(exc, pgerr.InsufficientPrivilege):
        return forbidden()
    if isinstance(exc, (pgerr.InvalidTextRepresentation, pgerr.InvalidDatetimeFormat,
                        pgerr.NumericValueOutOfRange, pgerr.StringDataRightTruncation,
                        pgerr.InvalidParameterValue, pgerr.DatetimeFieldOverflow,
                        pgerr.DataError)):
        return bad_request(f"A value has the wrong format: {primary}")
    if isinstance(exc, psycopg.OperationalError):
        log.error("database unavailable: %s", exc)
        return ApiError(503, "unavailable", "The database is not available right now.")
    log.exception("unexpected database error", exc_info=exc)
    return ApiError(500, "internal", "Something went wrong. The error has been logged.")
