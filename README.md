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

### Connection URL format

```
postgresql+neonserverless://user:password@endpoint-host.neon.tech/dbname
```

The dialect automatically:
- Strips the `-pooler` suffix from the hostname (Neon HTTP API requires the non-pooler host)
- Constructs the `Neon-Connection-String` header
- Sends queries to `https://{host}/sql`

### Environment variables

| Variable | Description |
|----------|-------------|
| `SSL_CERT_FILE` | Path to CA bundle for TLS verification. Set to `""` to disable verification (corporate proxy). |

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
