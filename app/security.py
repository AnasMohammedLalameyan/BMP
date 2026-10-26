"""Passwords, the credentials file, login throttling and CSRF.

The Phase 1 schema deliberately has no password column ("authentication belongs to the
later FastAPI layer"), and the database must stay as it is. So credentials live in a
small JSON file next to the application (USERS_FILE, default instance/users.json,
never committed), holding only salted scrypt hashes keyed by e-mail. A person can sign
in only if they have a hash there AND an active row in core.app_user; the app_user row
is what gives them an identity, a role and company access in the database.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

_N, _R, _P, _DKLEN = 2 ** 14, 8, 1, 32
MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return "scrypt${}${}${}${}${}".format(_N, _R, _P, base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time check. A missing user still burns the same work so timing does not reveal them."""
    if not stored:
        hashlib.scrypt(b"x", salt=b"0" * 16, n=_N, r=_R, p=_P, dklen=_DKLEN)
        return False
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt),
                            n=int(n), r=int(r), p=int(p), dklen=len(base64.b64decode(expected)))
        return hmac.compare_digest(dk, base64.b64decode(expected))
    except Exception:
        return False


class UsersStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")).get("users", {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def hash_for(self, email: str) -> str | None:
        rec = self._read().get(email.strip().lower())
        return rec.get("hash") if rec else None

    def set_password(self, email: str, password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
        with self._lock:
            users = self._read()
            users[email.strip().lower()] = {"hash": hash_password(password), "updated": time.strftime("%Y-%m-%dT%H:%M:%S")}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"users": users}, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def emails(self) -> list[str]:
        return sorted(self._read())


class LoginThrottle:
    """Locks an (address, e-mail) pair out for a while after repeated failures."""

    def __init__(self, max_failures: int, window_seconds: int):
        self.max = max_failures
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        hits = [t for t in self._hits.get(key, []) if now - t < self.window]
        self._hits[key] = hits
        return hits

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.time())) >= self.max

    def fail(self, key: str) -> None:
        with self._lock:
            self._prune(key, time.time()).append(time.time())

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_ok(session_token: str | None, header_token: str | None) -> bool:
    return bool(session_token and header_token) and hmac.compare_digest(session_token, header_token)
