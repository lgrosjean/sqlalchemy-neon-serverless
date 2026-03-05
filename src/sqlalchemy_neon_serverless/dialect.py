"""SQLAlchemy dialect for Neon's serverless HTTP endpoint.

Registers as ``postgresql+neonserverless://`` so that SQLModel/SQLAlchemy
can use Neon without a TCP connection. All SQL is sent over HTTP via the
:mod:`sqlalchemy_neon_serverless.dbapi` module.

Usage::

    from sqlalchemy import create_engine

    engine = create_engine("postgresql+neonserverless://user:pass@host/db")
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects import registry
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.pool import StaticPool

# Register the dialect so create_engine("postgresql+neonserverless://...") works
registry.register(
    "postgresql.neonserverless",
    "sqlalchemy_neon_serverless.dialect",
    "NeonServerlessDialect",
)

# Register async variant for create_async_engine("postgresql+neonserverless://...")
registry.register(
    "postgresql.neonserverless.async",
    "sqlalchemy_neon_serverless.async_dialect",
    "NeonServerlessAsyncDialect",
)


class NeonServerlessDialect(PGDialect):
    """PostgreSQL dialect that sends queries via Neon's HTTP /sql endpoint."""

    name = "postgresql"
    driver = "neonserverless"
    supports_statement_cache = True

    # Neon HTTP is stateless — disable server-side cursors and two-phase
    supports_server_side_cursors = False
    supports_sane_multi_rowcount = False

    @classmethod
    def import_dbapi(cls):
        from sqlalchemy_neon_serverless import dbapi

        return dbapi

    @classmethod
    def get_async_dialect_cls(cls, url):
        from sqlalchemy_neon_serverless.async_dialect import NeonServerlessAsyncDialect

        return NeonServerlessAsyncDialect

    @classmethod
    def get_pool_class(cls, url):
        # Single stateless connection — no pool needed
        return StaticPool

    def create_connect_args(self, url):
        """Convert a SQLAlchemy URL to DBAPI connect() kwargs.

        Expects: ``postgresql+neonserverless://user:pass@host/dbname``
        """
        host = url.host or ""
        # Strip -pooler suffix for the HTTP endpoint
        neon_host = host.replace("-pooler", "")
        endpoint = f"https://{neon_host}/sql"

        # Reconstruct the postgres:// connection string for the Neon header
        port = url.port or 5432
        user = url.username or ""
        password = url.password or ""
        database = url.database or ""

        connection_string = (
            f"postgresql://{user}:{password}@{neon_host}:{port}/{database}?sslmode=require"
        )

        return (
            [],
            {
                "endpoint": endpoint,
                "connection_string": connection_string,
            },
        )

    def do_ping(self, dbapi_connection: Any) -> bool:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SELECT 1")
            return True
        except Exception:
            return False

    def _get_server_version_info(self, connection: Any) -> tuple[int, ...]:
        # Return a reasonable default to avoid querying server version
        return (16, 0)

    def get_isolation_level(self, dbapi_connection: Any) -> str:
        return "AUTOCOMMIT"

    def set_isolation_level(self, dbapi_connection: Any, level: Any) -> None:
        # HTTP is always auto-commit
        pass
