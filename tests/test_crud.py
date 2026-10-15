import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.auth.passwords import validate_password
from src.db import config_crud, supplier_crud, user_crud
from src.db.models import ImportConfig
from src.models.config import CsvConfig
from src.models.suppliers import SupplierCreate, SupplierUpdate
from src.models.user import UserCreate, UserRead, UserUpdate
from tests.conftest import isolated_sessions

pytestmark = pytest.mark.integration


def user_data(name="alice"):
    return UserCreate(username=name, email=f"{name}@example.com", password="StrongPassword123")


def supplier_data():
    return SupplierCreate(name="Supplier", contact_email="supplier@example.com")


def config_data(delimiter=","):
    return CsvConfig(
        delimiter=delimiter, column_mapping={"SKU": "sku", "Name": "name", "Price": "price"}
    )


def test_user_lifecycle_across_sessions(database_url):
    async def scenario():
        async with isolated_sessions(database_url) as sessions:
            async with sessions() as session, session.begin():
                user = await user_crud.create_user(session, user_data())
                user_id = user.id
                assert UserRead.model_validate(user).created_at.tzinfo is not None
            async with sessions() as session, session.begin():
                updated = await user_crud.update_user(
                    session, user_id, UserUpdate(username="renamed", password="AnotherPassword123")
                )
                assert updated.id == user_id
            async with sessions() as session:
                user = await user_crud.get_user_by_email(session, "ALICE@EXAMPLE.COM")
                assert user.username == "renamed"
                assert validate_password("AnotherPassword123", user.password_hash)
                assert not validate_password("StrongPassword123", user.password_hash)
            async with sessions() as session, session.begin():
                assert await user_crud.delete_user(session, user_id)
            async with sessions() as session, session.begin():
                assert await user_crud.get_user_by_id(session, user_id) is None
                assert (
                    await user_crud.update_user(session, user_id, UserUpdate(username="missing"))
                    is None
                )
                assert not await user_crud.delete_user(session, user_id)

    asyncio.run(scenario())


@pytest.mark.parametrize("conflict_field", ["username", "email"])
def test_unique_constraint_rolls_back_transaction(database_url, conflict_field):
    async def scenario():
        async with isolated_sessions(database_url) as sessions:
            async with sessions() as session, session.begin():
                await user_crud.create_user(session, user_data())
            duplicate = user_data("another").model_dump()
            duplicate[conflict_field] = user_data().model_dump()[conflict_field]
            with pytest.raises(IntegrityError):
                async with sessions() as session, session.begin():
                    await user_crud.create_user(session, UserCreate(**duplicate))
            async with sessions() as session, session.begin():
                recovered = await user_crud.create_user(session, user_data("recovered"))
                assert recovered.id is not None

    asyncio.run(scenario())


def test_failed_second_write_rolls_back_first_write(database_url):
    async def scenario():
        async with isolated_sessions(database_url) as sessions:
            with pytest.raises(IntegrityError):
                async with sessions() as session, session.begin():
                    await user_crud.create_user(session, user_data())
                    await supplier_crud.create_supplier(session, supplier_data(), user_id=-1)
            async with sessions() as session:
                assert await user_crud.get_user_by_email(session, "alice@example.com") is None

    asyncio.run(scenario())


def test_supplier_ownership_updates_and_delete_rules(database_url):
    async def scenario():
        async with isolated_sessions(database_url) as sessions:
            async with sessions() as session, session.begin():
                owner = await user_crud.create_user(session, user_data())
                other = await user_crud.create_user(session, user_data("other"))
                supplier = await supplier_crud.create_supplier(
                    session, supplier_data(), user_id=owner.id
                )
                owner_id, other_id, supplier_id = owner.id, other.id, supplier.id
                await config_crud.save_config(session, supplier_id, config_data(), user_id=owner_id)
            async with sessions() as session, session.begin():
                assert await supplier_crud.list_suppliers(session, user_id=other_id) == []
                assert (
                    await supplier_crud.get_supplier_by_id(session, supplier_id, user_id=other_id)
                    is None
                )
                assert (
                    await supplier_crud.update_supplier(
                        session, supplier_id, SupplierUpdate(name="Forbidden"), user_id=other_id
                    )
                    is None
                )
                assert not await supplier_crud.delete_supplier(
                    session, supplier_id, user_id=other_id
                )
                await supplier_crud.update_supplier(
                    session, supplier_id, SupplierUpdate(name="Renamed"), user_id=owner_id
                )
            async with sessions() as session:
                found = await supplier_crud.list_suppliers(session, user_id=owner_id)
                assert [item.name for item in found] == ["Renamed"]
            with pytest.raises(IntegrityError):
                async with sessions() as session, session.begin():
                    await user_crud.delete_user(session, owner_id)
            async with sessions() as session, session.begin():
                assert await supplier_crud.delete_supplier(session, supplier_id, user_id=owner_id)
            async with sessions() as session:
                assert await config_crud.get_config(session, supplier_id, user_id=owner_id) is None
                assert await session.scalar(select(func.count()).select_from(ImportConfig)) == 0

    asyncio.run(scenario())


def test_config_upsert_and_owner_checks(database_url):
    async def scenario():
        async with isolated_sessions(database_url) as sessions:
            async with sessions() as session, session.begin():
                owner = await user_crud.create_user(session, user_data())
                supplier = await supplier_crud.create_supplier(
                    session, supplier_data(), user_id=owner.id
                )
                owner_id, supplier_id = owner.id, supplier.id
                first = await config_crud.save_config(
                    session, supplier_id, config_data(), user_id=owner_id
                )
                config_id = first.id
                second = await config_crud.save_config(
                    session, supplier_id, config_data(";"), user_id=owner_id
                )
                assert second.id == config_id
                assert second.config_data["delimiter"] == ";"
                assert await config_crud.get_config(session, supplier_id, user_id=-1) is None
                assert (
                    await config_crud.save_config(session, supplier_id, config_data(), user_id=-1)
                    is None
                )
                assert not await config_crud.delete_config(session, supplier_id, user_id=-1)
            async with sessions() as session, session.begin():
                assert await session.scalar(select(func.count()).select_from(ImportConfig)) == 1
                config = await config_crud.get_config(session, supplier_id, user_id=owner_id)
                assert config.config_data["delimiter"] == ";"
                assert await config_crud.delete_config(session, supplier_id, user_id=owner_id)
                assert not await config_crud.delete_config(session, supplier_id, user_id=owner_id)

    asyncio.run(scenario())


def test_config_foreign_key_and_unique_constraint(database_url):
    async def scenario():
        async with isolated_sessions(database_url) as sessions:
            with pytest.raises(IntegrityError):
                async with sessions() as session, session.begin():
                    session.add(ImportConfig(supplier_id=-1, config_data={}))
                    await session.flush()
            async with sessions() as session, session.begin():
                user = await user_crud.create_user(session, user_data())
                supplier = await supplier_crud.create_supplier(
                    session, supplier_data(), user_id=user.id
                )
                supplier_id = supplier.id
                await config_crud.save_config(session, supplier_id, config_data(), user_id=user.id)
            with pytest.raises(IntegrityError):
                async with sessions() as session, session.begin():
                    session.add(ImportConfig(supplier_id=supplier_id, config_data={}))
                    await session.flush()

    asyncio.run(scenario())
