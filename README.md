# ImportForge
Backend service for asynchronous CSV ingestion, validation, normalization.

The project is organized as a modular monolith with ports and adapters inside
each business module. See [Architecture](docs/architecture.md) for module
boundaries, dependency rules, and the target request flows.

## Local database setup

Run commands from the project root. PostgreSQL runs in Docker; Python runs locally.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install fastapi 'uvicorn[standard]' 'sqlalchemy[asyncio]>=2.0,<2.1' asyncpg python-dotenv
```

Configure the root `.env` file (local development values):

```dotenv
DB_USER=user
DB_PASS=password
DB_NAME=db
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}
```

```bash
docker compose up -d --wait postgres
python -m src.db.database
uvicorn src.main:app --reload
```

`python -m src.db.database` creates missing tables from the existing SQLAlchemy
models. It can be repeated, but does not alter existing tables or replace schema
migrations. Alembic is not part of this setup. The API checks database connectivity
on startup and closes its connection pool on shutdown.

Verify the running API with `curl http://127.0.0.1:8000/` (expected response:
`{"status":"ok"}`). Inspect the tables with:

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\\dt"'
```

Use `get_session` from `src.db.database` as a FastAPI dependency. Each request gets
its own session. Writes must explicitly commit with `await session.commit()` or
use `async with session.begin():`. Closing a session rolls back uncommitted work.
Do not share a session between concurrent tasks.

If Python is later run inside this Compose network, use `postgres` instead of
`localhost` in `DATABASE_URL`. PostgreSQL data persists in the `postgres_data`
volume; the initial database credentials apply when that volume is first created.
Stop PostgreSQL without removing its data using `docker compose stop postgres`.
