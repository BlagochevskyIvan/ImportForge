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
def test_concurrent_writes_create_one_config(database_url, create_only):
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
                    try:
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
                    except config_crud.ConfigAlreadyExistsError:
                        return None

                results = await asyncio.gather(save(","), save(";"), save("|"))
                successful = [result for result in results if result is not None]
                assert len(successful) == (1 if create_only else 3)
                assert len({config_id for config_id, _ in successful}) == 1
                async with sessions() as session:
                    assert await session.scalar(select(func.count()).select_from(ImportConfig)) == 1
                    if create_only:
                        config = await config_crud.get_config(session, supplier_id, user_id=user_id)
                        assert config.config_data["delimiter"] == successful[0][1]
            finally:
                await engine.dispose()

    asyncio.run(scenario())
