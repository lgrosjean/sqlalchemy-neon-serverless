"""Async SQLAlchemy dialect for Neon's serverless HTTP endpoint.

Registers as ``postgresql+neonserverless://`` and works with
``create_async_engine``. Uses the async DBAPI adapter in
:mod:`sqlalchemy_neon_serverless.adbapi`.

Usage::

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("postgresql+neonserverless://user:pass@host/db")
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.pool import StaticPool

from sqlalchemy_neon_serverless.dialect import NeonServerlessDialect


class NeonServerlessAsyncDialect(NeonServerlessDialect):
    """Async variant of the Neon serverless dialect."""

    is_async = True
    supports_statement_cache = True

    @classmethod
    def import_dbapi(cls):
        from sqlalchemy_neon_serverless import adbapi

        return adbapi

    @classmethod
    def get_pool_class(cls, url):
        return StaticPool
