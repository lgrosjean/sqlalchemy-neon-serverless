"""Tests for the NeonServerless SQLAlchemy dialect."""

from __future__ import annotations

from sqlalchemy import make_url

from sqlalchemy_neon_serverless.dialect import NeonServerlessDialect


def test_driver_name():
    """Dialect reports correct driver name."""
    assert NeonServerlessDialect.driver == "neonserverless"


def test_dbapi_module():
    """dbapi() returns the DBAPI module."""
    module = NeonServerlessDialect.dbapi()
    assert module.apilevel == "2.0"
    assert module.paramstyle == "format"


def test_create_connect_args():
    """Parses URL into endpoint and connection_string kwargs."""
    dialect = NeonServerlessDialect()
    url = make_url("postgresql+neonserverless://user:pass@ep-cool-123.neon.tech/mydb")

    args, kwargs = dialect.create_connect_args(url)

    assert args == []
    assert kwargs["endpoint"] == "https://ep-cool-123.neon.tech/sql"
    assert "postgresql://user:pass@ep-cool-123.neon.tech" in kwargs["connection_string"]
    assert "mydb" in kwargs["connection_string"]


def test_create_connect_args_strips_pooler():
    """Strips -pooler suffix from host."""
    dialect = NeonServerlessDialect()
    url = make_url("postgresql+neonserverless://user:pass@ep-cool-123-pooler.neon.tech/mydb")

    _, kwargs = dialect.create_connect_args(url)

    assert kwargs["endpoint"] == "https://ep-cool-123.neon.tech/sql"
    assert "-pooler" not in kwargs["connection_string"]


def test_isolation_level():
    """Always returns AUTOCOMMIT."""
    dialect = NeonServerlessDialect()
    assert dialect.get_isolation_level(None) == "AUTOCOMMIT"


def test_server_version():
    """Returns default server version without querying."""
    dialect = NeonServerlessDialect()
    assert dialect._get_server_version_info(None) == (16, 0)
