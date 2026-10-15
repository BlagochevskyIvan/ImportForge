import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.db import config_crud, supplier_crud, user_crud
from src.db.models import ImportConfig
from src.models.config import CsvConfig
from src.models.suppliers import SupplierCreate
from src.models.user import UserCreate
from tests.conftest import alembic_command, temporary_database

pytestmark = pytest.mark.integration


def test_concurrent_saves_create_one_config(database_url):
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

                async def save(delimiter):
                    async with sessions() as session, session.begin():
                        config = await config_crud.save_config(
                            session,
                            supplier_id,
                            CsvConfig(
                                delimiter=delimiter,
                                column_mapping={"SKU": "sku", "Name": "name", "Price": "price"},
                            ),
                            user_id=user_id,
                        )
                        return config.id

                ids = await asyncio.gather(save(","), save(";"), save("|"))
                assert len(set(ids)) == 1
                async with sessions() as session:
                    assert await session.scalar(select(func.count()).select_from(ImportConfig)) == 1
            finally:
                await engine.dispose()

    asyncio.run(scenario())
