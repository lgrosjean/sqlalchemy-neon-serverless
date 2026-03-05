"""Async-compatible PEP 249 adapter for Neon's serverless HTTP endpoint.

Uses ``httpx.AsyncClient`` with SQLAlchemy's ``await_only()`` bridge so
that the async engine can issue non-blocking HTTP calls through greenlet.

The cursor methods are **sync** but internally yield to the event loop
via ``await_only()``, which is how SQLAlchemy's async engine expects
DBAPI adapters to work (same pattern as asyncpg, aiomysql, etc.).

Usage::

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("postgresql+neonserverless://user:pass@host/db")
"""

from __future__ import annotations

import json
import math
import os
import re
import ssl
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy.util.concurrency import await_only

# ---------------------------------------------------------------------------
# Module-level attributes
# ---------------------------------------------------------------------------
apilevel = "2.0"
threadsafety = 1
paramstyle = "format"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class Error(Exception):
    pass


class DatabaseError(Error):
    pass


class OperationalError(DatabaseError):
    pass


class InterfaceError(Error):
    pass


class ProgrammingError(DatabaseError):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_FMT_RE = re.compile(r"%s")


def _format_to_dollar(sql: str, params: Sequence[Any] | None) -> tuple[str, list[Any]]:
    if not params:
        return sql, []

    idx = 0
    values: list[Any] = list(params)

    def _replacer(_match: re.Match) -> str:
        nonlocal idx
        idx += 1
        return f"${idx}"

    return _FMT_RE.sub(_replacer, sql), values


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


@staticmethod
def _normalize_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


# ---------------------------------------------------------------------------
# Cursor
# ---------------------------------------------------------------------------
class Cursor:
    """DBAPI cursor that uses httpx.AsyncClient via await_only()."""

    arraysize: int = 1

    def __init__(self, connection: Connection) -> None:
        self._connection = connection
        self._rows: list[dict[str, Any]] = []
        self._description: list[tuple[str, Any, None, None, None, None, None]] | None = None
        self._rowcount: int = -1
        self._pos: int = 0

    @property
    def description(self):
        return self._description

    @property
    def rowcount(self) -> int:
        return self._rowcount

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> None:
        sql, param_list = _format_to_dollar(sql, params)
        serialized = [_serialize(v) for v in param_list]

        # await_only() bridges the async call within the greenlet context
        response = await_only(
            self._connection._http_client.post(
                self._connection._endpoint,
                json={"query": sql, "params": serialized},
                headers={
                    "Neon-Connection-String": self._connection._connection_string,
                    "Content-Type": "application/json",
                },
            )
        )

        if not response.is_success:
            raise DatabaseError(f"Neon HTTP error {response.status_code}: {response.text}")

        self._parse_response(response.json())

    def executemany(self, sql: str, seq_of_params: Sequence[Sequence[Any]]) -> None:
        for params in seq_of_params:
            self.execute(sql, params)

    def fetchone(self) -> tuple[Any, ...] | None:
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return tuple(row.values())

    def fetchmany(self, size: int | None = None) -> list[tuple[Any, ...]]:
        sz = size or self.arraysize
        rows = self._rows[self._pos : self._pos + sz]
        self._pos += len(rows)
        return [tuple(r.values()) for r in rows]

    def fetchall(self) -> list[tuple[Any, ...]]:
        rows = self._rows[self._pos :]
        self._pos = len(self._rows)
        return [tuple(r.values()) for r in rows]

    def close(self) -> None:
        pass

    def setinputsizes(self, sizes: Any) -> None:
        pass

    def setoutputsize(self, size: Any, column: Any = None) -> None:
        pass

    def _parse_response(self, data: dict[str, Any]) -> None:
        fields = data.get("fields", [])
        rows = data.get("rows", [])

        if fields:
            self._description = [
                (f["name"], f.get("dataTypeID"), None, None, None, None, None) for f in fields
            ]
        else:
            self._description = None

        norm = _normalize_value
        if rows and isinstance(rows[0], dict):
            self._rows = [{k: norm(v) for k, v in row.items()} for row in rows]
        elif rows and isinstance(rows[0], list):
            col_names = [f["name"] for f in fields]
            self._rows = [dict(zip(col_names, [norm(v) for v in row])) for row in rows]
        else:
            self._rows = []

        self._rowcount = len(self._rows) if rows else data.get("rowCount", -1)
        self._pos = 0


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
class Connection:
    """DBAPI connection using httpx.AsyncClient."""

    def __init__(
        self,
        http_client: Any,
        endpoint: str,
        connection_string: str,
    ) -> None:
        self._http_client = http_client
        self._endpoint = endpoint
        self._connection_string = connection_string

    def cursor(self) -> Cursor:
        return Cursor(self)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        await_only(self._http_client.aclose())


# ---------------------------------------------------------------------------
# Module-level connect()
# ---------------------------------------------------------------------------
def connect(
    dsn: str | None = None,
    *,
    endpoint: str | None = None,
    connection_string: str | None = None,
    ssl_cert_file: str | None = None,
    **kwargs: Any,
) -> Connection:
    """Create a DBAPI connection backed by httpx.AsyncClient."""
    import httpx

    if not endpoint or not connection_string:
        msg = "Both 'endpoint' and 'connection_string' are required"
        raise InterfaceError(msg)

    verify: ssl.SSLContext | bool = True
    if ssl_cert_file:
        verify = ssl.create_default_context(cafile=ssl_cert_file)
    elif os.environ.get("SSL_CERT_FILE", None) == "":
        verify = False

    http_client = httpx.AsyncClient(timeout=30.0, verify=verify)

    return Connection(
        http_client=http_client,
        endpoint=endpoint,
        connection_string=connection_string,
    )
