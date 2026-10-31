import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.db import config_crud, supplier_crud, user_crud
from src.db.models import ImportConfig
from src.schemas.import_config import CsvConfig
from src.schemas.suppliers import SupplierCreate
from src.schemas.users import UserCreate
from tests.conftest import alembic_command, temporary_database

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("create_only", [False, True])
@pytest.mark.parametrize("same_settings", [False, True])
def test_concurrent_writes_preserve_config_versions(database_url, create_only, same_settings):
    async def scenario():
        async with temporary_database(database_url) as url:
            migration = alembic_command(url, "upgrade", "head")
            assert migration.returncode == 0, migration.stderr
            engine = create_async_engine(url, hide_parameters=True)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with sessions() as session, session.begin():
                    user = await user_crud.create_user(
                        session,
                        UserCreate(
                            username="owner",
                            email="owner@example.com",
                            password="StrongPassword123",
                        ),
                    )
                    supplier = await supplier_crud.create_supplier(
                        session,
                        SupplierCreate(name="Concurrent", contact_email="source@example.com"),
                        user_id=user.id,
                    )
                    user_id, supplier_id = user.id, supplier.id

                write_config = config_crud.create_config if create_only else config_crud.save_config

                async def save(delimiter):
                    async with sessions() as session, session.begin():
                        config = await write_config(
                            session,
                            supplier_id,
                            CsvConfig(
                                delimiter=delimiter,
                                column_mapping={"SKU": "sku", "Name": "name", "Price": "price"},
                            ),
                            user_id=user_id,
                        )
                        return config.id, delimiter

                delimiters = [","] * 3 if same_settings else [",", ";", "|"]
                results = await asyncio.gather(*(save(delimiter) for delimiter in delimiters))
                expected_count = 1 if same_settings and not create_only else 3
                assert len({config_id for config_id, _ in results}) == expected_count
                async with sessions() as session:
                    assert (
                        await session.scalar(select(func.count()).select_from(ImportConfig))
                        == expected_count
                    )
                    for config_id, delimiter in results:
                        version = await session.get(ImportConfig, config_id)
                        assert version.config_data["delimiter"] == delimiter
                    config = await config_crud.get_config(session, supplier_id, user_id=user_id)
                    assert config.id == max(config_id for config_id, _ in results)
            finally:
                await engine.dispose()

    asyncio.run(scenario())
