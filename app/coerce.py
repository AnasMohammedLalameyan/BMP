"""Turns what the browser sends (JSON strings and numbers) into typed database values.

Validation here is only about *form*: is this a date, a number of the right size, one of
the allowed choices. Whether a combination is *allowed* (no overlapping stints, lookup
belongs to the right list, one reference only ...) stays with the database.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation

from psycopg.types.json import Jsonb

from .schema_meta import Column

IST = timezone(timedelta(hours=5, minutes=30))
_FY = re.compile(r"^\d{4}-\d{2}$")
_TRUE = {"true", "t", "yes", "y", "on", "1"}
_FALSE = {"false", "f", "no", "n", "off", "0"}


class FieldError(ValueError):
    def __init__(self, column: str, message: str):
        super().__init__(message)
        self.column = column
        self.message = message


def is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def coerce(col: Column, value):
    """Return the Python value for `col`, or None for blank. Raises FieldError."""
    if is_blank(value):
        return None
    k = col.kind
    try:
        if k == "int":
            if isinstance(value, bool):
                raise ValueError
            if isinstance(value, float):
                if value != int(value):
                    raise ValueError
                return int(value)
            return int(str(value).strip())
        if k == "decimal":
            if isinstance(value, bool):
                raise ValueError
            d = Decimal(str(value).strip().replace(",", ""))
            if not d.is_finite():
                raise ValueError
            if col.precision is not None:
                if abs(d) >= Decimal(10) ** (col.precision - (col.scale or 0)):
                    raise FieldError(col.name, "Number is too large for this field")
                if col.scale is not None and d.as_tuple().exponent < -col.scale:
                    d = round(d, col.scale)
            return d
        if k == "bool":
            if isinstance(value, bool):
                return value
            s = str(value).strip().lower()
            if s in _TRUE:
                return True
            if s in _FALSE:
                return False
            raise ValueError
        if k == "date":
            return date.fromisoformat(str(value).strip()[:10])
        if k == "time":
            return time.fromisoformat(str(value).strip())
        if k == "datetime":
            dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=IST)
        if k == "json":
            parsed = json.loads(value) if isinstance(value, str) else value
            return Jsonb(parsed)
        if k == "vector":
            arr = json.loads(value) if isinstance(value, str) else value
            if not isinstance(arr, list) or not all(isinstance(x, (int, float)) for x in arr):
                raise ValueError
            if col.dims and len(arr) != col.dims:
                raise FieldError(col.name, f"A vector of exactly {col.dims} numbers is required")
            return "[" + ",".join(repr(float(x)) for x in arr) + "]"
        if k == "bytea":
            return str(value)
        text = str(value).strip()
        if col.choices is not None and text not in [str(c) for c in col.choices]:
            raise FieldError(col.name, "Must be one of: " + ", ".join(str(c) for c in col.choices))
        if col.fmt == "financial_year" and not _FY.match(text):
            raise FieldError(col.name, "Financial year must look like 2024-25")
        return text
    except FieldError:
        raise
    except (ValueError, TypeError, InvalidOperation, json.JSONDecodeError):
        raise FieldError(col.name, _HINT.get(k, "Invalid value"))


_HINT = {
    "int": "Enter a whole number", "decimal": "Enter a number", "bool": "Enter yes or no",
    "date": "Enter a date as YYYY-MM-DD", "time": "Enter a time as HH:MM",
    "datetime": "Enter a date and time", "json": "Enter valid JSON",
    "vector": "Enter a JSON array of numbers",
}
