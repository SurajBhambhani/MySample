"""Database access helpers for the MCP server."""

from __future__ import annotations

from contextlib import contextmanager
import re
from typing import Any, Optional, Sequence

import psycopg2
from psycopg2.extras import RealDictCursor


class DatabaseError(RuntimeError):
    """Raised when the database cannot be initialised or accessed."""


class Database:
    """Thin repository-style wrapper around psycopg2 interactions."""

    def __init__(self, url: str) -> None:
        if not url:
            raise DatabaseError("DATABASE_URL must be configured for MCP server")
        self._url = self._normalise_url(url)

    @staticmethod
    def _normalise_url(url: str) -> str:
        """Translate SQLAlchemy-style URLs (e.g., postgresql+psycopg2://) to psycopg2 DSN."""

        match = re.match(r"^(?P<scheme>[a-zA-Z0-9+]+)://", url)
        if match:
            scheme = match.group("scheme")
            if "+" in scheme:
                primary = scheme.split("+", 1)[0]
                return url.replace(f"{scheme}://", f"{primary}://", 1)
        return url

    @contextmanager
    def connection(self):
        conn = psycopg2.connect(self._url, cursor_factory=RealDictCursor)
        try:
            yield conn
        finally:
            conn.close()

    def fetch_all(self, sql: str, params: Optional[Sequence[Any]] = None) -> list[dict[str, Any]]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                return cur.fetchall()

    def fetch_one(self, sql: str, params: Optional[Sequence[Any]] = None) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                return cur.fetchone()

    def execute(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
        *,
        returning: bool = False,
    ) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                result = cur.fetchone() if returning else None
                conn.commit()
                return result


def ensure_select_only(sql: str) -> None:
    if not sql.lstrip().lower().startswith("select"):
        raise DatabaseError("Only SELECT queries are allowed")
