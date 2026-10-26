"""JSON responses that keep database values exact (numbers as strings, dates as ISO text)."""
from __future__ import annotations

import json
from datetime import date, datetime, time
from decimal import Decimal

from starlette.responses import Response


def _default(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Cannot serialise {type(value).__name__}")


class ApiResponse(Response):
    media_type = "application/json"

    def __init__(self, content, status_code: int = 200, headers: dict | None = None):
        body = json.dumps(content, default=_default, ensure_ascii=False, allow_nan=False).encode("utf-8")
        super().__init__(content=body, status_code=status_code, headers=headers, media_type=self.media_type)


def ok(data, status: int = 200) -> ApiResponse:
    return ApiResponse(data, status)
