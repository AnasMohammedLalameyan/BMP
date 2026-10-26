"""Connection pools and the per-request transaction.

Every request runs inside one transaction in which `app.current_user_id` is set with
`set_config(..., is_local := true)`. That single setting drives three things in the
database: the audit trigger (who made the change), the row-level-security policies
(which companies the user may see) and the rule that rejects writes with no actor.
Because it is transaction-local it cannot leak to the next request that reuses the
pooled connection.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class Database:
    def __init__(self, dsn: str, *, name: str, min_size: int = 1, max_size: int = 10):
        self.name = name
        self.pool = ConnectionPool(
            dsn, min_size=min_size, max_size=max_size, open=False, name=name, timeout=10,
            kwargs={"row_factory": dict_row},
        )

    def open(self) -> None:
        self.pool.open(wait=True, timeout=20)

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def tx(self, user_id: int | None = None, *, readonly: bool = False) -> Iterator[psycopg.Connection]:
        """A transaction as `user_id`. Commits on success, rolls back on any exception."""
        with self.pool.connection() as conn:
            with conn.transaction():
                if readonly:
                    conn.execute("SET TRANSACTION READ ONLY")
                conn.execute("SELECT set_config('app.current_user_id', %s, true)",
                             (str(user_id) if user_id else "",))
                yield conn

    def ping(self) -> bool:
        try:
            with self.pool.connection(timeout=3) as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False
