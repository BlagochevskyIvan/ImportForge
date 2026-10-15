import asyncio

import asyncpg
import pytest
from sqlalchemy.engine import make_url

from tests.conftest import alembic_command, temporary_database

pytestmark = pytest.mark.integration


def assert_migration_ok(url, *arguments):
    result = alembic_command(url, *arguments)
    assert result.returncode == 0, result.stdout + result.stderr


async def connect(url):
    return await asyncpg.connect(make_url(url).set(drivername="postgresql").render_as_string(False))


def test_clean_install_schema_check_and_empty_roundtrip(database_url):
    async def scenario():
        async with temporary_database(database_url) as url:
            assert_migration_ok(url, "upgrade", "head")
            assert_migration_ok(url, "check")
            connection = await connect(url)
            try:
                tables = await connection.fetch(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
                assert {row["tablename"] for row in tables} == {
                    "users",
                    "suppliers",
                    "import_configs",
                    "alembic_version",
                }
            finally:
                await connection.close()
            assert_migration_ok(url, "downgrade", "base")
            assert_migration_ok(url, "upgrade", "head")
            assert_migration_ok(url, "check")

    asyncio.run(scenario())


def test_existing_user_survives_type_conversion(database_url):
    async def scenario():
        async with temporary_database(database_url) as url:
            assert_migration_ok(url, "upgrade", "b54de5027f26")
            connection = await connect(url)
            try:
                user_id = await connection.fetchval(
                    "INSERT INTO users (username, email, password_hash, is_active, created_at) "
                    "VALUES ('legacy', 'LEGACY@EXAMPLE.COM', 'existing-hash', 1, '1700000000') "
                    "RETURNING id"
                )
            finally:
                await connection.close()
            assert_migration_ok(url, "upgrade", "head")
            connection = await connect(url)
            try:
                user = await connection.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
                assert user["email"] == "legacy@example.com"
                assert user["password_hash"] == "existing-hash"
                assert user["is_active"] is True
                assert user["created_at"].timestamp() == 1700000000
            finally:
                await connection.close()

    asyncio.run(scenario())


def test_legacy_suppliers_stop_migration_without_data_loss(database_url):
    async def scenario():
        async with temporary_database(database_url) as url:
            assert_migration_ok(url, "upgrade", "b54de5027f26")
            connection = await connect(url)
            try:
                supplier_id = await connection.fetchval(
                    "INSERT INTO suppliers (name, contact_email) "
                    "VALUES ('Keep me', 'legacy@example.com') RETURNING id"
                )
            finally:
                await connection.close()
            result = alembic_command(url, "upgrade", "head")
            assert result.returncode != 0
            assert "Legacy suppliers have no owner" in result.stderr
            connection = await connect(url)
            try:
                assert (
                    await connection.fetchval("SELECT version_num FROM alembic_version")
                    == "b54de5027f26"
                )
                assert (
                    await connection.fetchval(
                        "SELECT name FROM suppliers WHERE id = $1", supplier_id
                    )
                    == "Keep me"
                )
                assert not await connection.fetchval(
                    "SELECT EXISTS(SELECT FROM information_schema.columns "
                    "WHERE table_name = 'suppliers' AND column_name = 'user_id')"
                )
            finally:
                await connection.close()

    asyncio.run(scenario())
