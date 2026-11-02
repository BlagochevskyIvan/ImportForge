"""Integration checks require a dedicated database and apply real Alembic migrations."""

import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def alembic_command(database_url: str, *arguments: str) -> subprocess.CompletedProcess:
    environment = {**os.environ, "DATABASE_URL": database_url, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="session")
def database_url() -> str:
    value = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test_user:test_password@localhost:5433/test_importforge",
    )
    url = make_url(value)
    if url.drivername != "postgresql+asyncpg" or not (url.database or "").startswith("test_"):
        pytest.fail("TEST_DATABASE_URL must use asyncpg and a database named test_...")
    if os.getenv("DATABASE_URL"):
        application_url = make_url(os.environ["DATABASE_URL"])
        if (url.host, url.port or 5432, url.database) == (
            application_url.host,
            application_url.port or 5432,
            application_url.database,
        ):
            pytest.fail("The test and application databases must be different")
    result = alembic_command(value, "upgrade", "head")
    if result.returncode:
        pytest.fail(
            "Test migration failed. Start 'make test-db-up'.\n" + result.stderr + result.stdout
        )
    return value


@asynccontextmanager
async def isolated_sessions(database_url: str):
    """Real SQL and SAVEPOINT commits; the outer rollback removes only this test's changes."""
    engine = create_async_engine(database_url, hide_parameters=True)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            sessions = async_sessionmaker(
                connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )
            try:
                yield sessions
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@asynccontextmanager
async def temporary_database(database_url: str):
    """Create and drop only a uniquely named database on the dedicated test server."""
    url = make_url(database_url)
    name = f"test_importforge_{uuid4().hex}"
    administration = await asyncpg.connect(url.set(drivername="postgresql").render_as_string(False))
    created = False
    try:
        await administration.execute(f'CREATE DATABASE "{name}"')
        created = True
        yield url.set(database=name).render_as_string(False)
    finally:
        if created:
            await administration.execute(f'DROP DATABASE "{name}"')
        await administration.close()
