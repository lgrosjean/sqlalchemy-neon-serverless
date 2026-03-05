# sqlalchemy-neon-serverless

A [SQLAlchemy](https://www.sqlalchemy.org/) dialect for [Neon](https://neon.tech/)'s serverless HTTP endpoint. Sends all SQL over HTTPS — no TCP connection, no `psycopg2`, no `asyncpg`.

This is useful when:

- You're behind a **corporate proxy** that blocks PostgreSQL TCP connections (port 5432)
- You're running in a **serverless environment** (Lambda, Cloud Functions, Edge) where persistent connections aren't practical
- You want to use **SQLModel** or **SQLAlchemy ORM** with Neon without installing native PostgreSQL drivers

## How it works

```
SQLAlchemy Engine (postgresql+neonserverless://)
  └── NeonServerlessDialect (extends PGDialect)
      └── DBAPI 2.0 Module (PEP 249)
          └── httpx POST → https://{host}/sql
```

Each SQL statement is sent as an HTTP POST to Neon's `/sql` endpoint. Every request auto-commits. The DBAPI module handles parameter conversion from SQLAlchemy's `%s` format to Neon's `$1, $2, ...` positional format.

Supports both **sync** (`create_engine`) and **async** (`create_async_engine`) usage.

## Installation

```bash
pip install sqlalchemy-neon-serverless

# Or with uv
uv add sqlalchemy-neon-serverless

# With SQLModel support
pip install sqlalchemy-neon-serverless[sqlmodel]
```

## Usage

### SQLAlchemy Core

```python
from sqlalchemy import create_engine, text

engine = create_engine("postgresql+neonserverless://user:pass@ep-cool-123.neon.tech/mydb")

with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": 1})
    print(result.fetchone())
```

### SQLAlchemy ORM

```python
from sqlalchemy import create_engine, Column, String
from sqlalchemy.orm import DeclarativeBase, Session

engine = create_engine("postgresql+neonserverless://user:pass@ep-cool-123.neon.tech/mydb")

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String)

with Session(engine) as session:
    users = session.query(User).all()
```

### SQLModel

```python
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("postgresql+neonserverless://user:pass@ep-cool-123.neon.tech/mydb")

class User(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str

with Session(engine) as session:
    users = session.exec(select(User)).all()
```

### Async (SQLAlchemy / FastAPI)

The dialect supports SQLAlchemy's async engine via `create_async_engine`. Under the hood, it uses `httpx.AsyncClient` with SQLAlchemy's greenlet bridge — no blocking I/O on the event loop.

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import select

engine = create_async_engine("postgresql+neonserverless://user:pass@ep-cool-123.neon.tech/mydb")

async with AsyncSession(engine) as session:
    result = await session.execute(select(User))
    users = result.scalars().all()
```

With FastAPI:

```python
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import select

app = FastAPI()
engine = create_async_engine("postgresql+neonserverless://user:pass@ep-cool-123.neon.tech/mydb")

@app.get("/users")
async def get_users():
    async with AsyncSession(engine) as session:
        result = await session.execute(select(User))
        return result.scalars().all()
```

> **Note**: Async requires `greenlet` (`pip install greenlet`).

### Connection URL format

```
postgresql+neonserverless://user:password@endpoint-host.neon.tech/dbname
```

The same URL works for both `create_engine` and `create_async_engine`. The dialect automatically:
- Strips the `-pooler` suffix from the hostname (Neon HTTP API requires the non-pooler host)
- Constructs the `Neon-Connection-String` header
- Sends queries to `https://{host}/sql`
- Selects the async DBAPI when used with `create_async_engine`

### Environment variables

| Variable | Description |
|----------|-------------|
| `SSL_CERT_FILE` | Path to CA bundle for TLS verification. Set to `""` to disable verification (corporate proxy). |

## Architecture

| Component | Module | Description |
|-----------|--------|-------------|
| Sync DBAPI | `sqlalchemy_neon_serverless.dbapi` | PEP 249 adapter using `httpx.Client` |
| Async DBAPI | `sqlalchemy_neon_serverless.adbapi` | PEP 249 adapter using `httpx.AsyncClient` + `await_only()` |
| Sync Dialect | `sqlalchemy_neon_serverless.dialect` | `NeonServerlessDialect` extending `PGDialect` |
| Async Dialect | `sqlalchemy_neon_serverless.async_dialect` | `NeonServerlessAsyncDialect` with `is_async = True` |

## Limitations

- **No transactions**: Each HTTP request auto-commits. `session.rollback()` is a no-op.
- **No server-side cursors**: All results are fetched in a single HTTP response.
- **No streaming**: Large result sets are fully loaded into memory.
- **No LISTEN/NOTIFY**: WebSocket-based features are not supported.

## Inspired by

- [sqlalchemy-aurora-data-api](https://github.com/cloud-utils/sqlalchemy-aurora-data-api) — SQLAlchemy dialect for AWS Aurora Data API (same pattern: SQL over HTTP)
- [@neondatabase/serverless](https://github.com/neondatabase/serverless) — Official Neon TypeScript serverless driver

## License

MIT
