"""SQLAlchemy dialect for Neon's serverless HTTP endpoint.

Usage::

    from sqlalchemy import create_engine

    engine = create_engine("postgresql+neonserverless://user:pass@host/db")

Or with SQLModel::

    from sqlmodel import Session, create_engine

    engine = create_engine("postgresql+neonserverless://user:pass@host/db")
    with Session(engine) as session:
        ...
"""

from sqlalchemy_neon_serverless.dbapi import (
    Connection,
    Cursor,
    DatabaseError,
    Error,
    InterfaceError,
    OperationalError,
    ProgrammingError,
    connect,
)
from sqlalchemy_neon_serverless.async_dialect import NeonServerlessAsyncDialect
from sqlalchemy_neon_serverless.dialect import NeonServerlessDialect

__all__ = [
    "Connection",
    "Cursor",
    "DatabaseError",
    "Error",
    "InterfaceError",
    "NeonServerlessAsyncDialect",
    "NeonServerlessDialect",
    "OperationalError",
    "ProgrammingError",
    "connect",
]

__version__ = "0.1.0"
