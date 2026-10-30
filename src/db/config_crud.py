"""One CSV configuration per supplier, with ownership checked on every operation."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ImportConfig, Supplier
from src.db.supplier_crud import get_supplier_by_id
from src.schemas.import_config import CsvConfig


class ConfigAlreadyExistsError(ValueError):
    """The supplier already has a configuration; creation must not replace it."""


async def get_config(
    session: AsyncSession, supplier_id: int, *, user_id: int
) -> ImportConfig | None:
    statement = (
        select(ImportConfig)
        .join(Supplier, Supplier.id == ImportConfig.supplier_id)
        .where(Supplier.id == supplier_id, Supplier.user_id == user_id)
    )
    return await session.scalar(statement)


async def create_config(
    session: AsyncSession, supplier_id: int, config_data: CsvConfig, *, user_id: int
) -> ImportConfig | None:
    if await get_supplier_by_id(session, supplier_id, user_id=user_id) is None:
        return None
    statement = (
        insert(ImportConfig)
        .values(supplier_id=supplier_id, config_data=config_data.model_dump(mode="json"))
        .on_conflict_do_nothing(index_elements=[ImportConfig.supplier_id])
        .returning(ImportConfig)
    )
    config = await session.scalar(statement)
    if config is None:
        raise ConfigAlreadyExistsError("Supplier configuration already exists")
    return config


async def save_config(
    session: AsyncSession, supplier_id: int, config_data: CsvConfig, *, user_id: int
) -> ImportConfig | None:
    if await get_supplier_by_id(session, supplier_id, user_id=user_id) is None:
        return None
    payload = config_data.model_dump(mode="json")
    statement = (
        insert(ImportConfig)
        .values(supplier_id=supplier_id, config_data=payload)
        .on_conflict_do_update(
            index_elements=[ImportConfig.supplier_id], set_={"config_data": payload}
        )
        .returning(ImportConfig)
        .execution_options(populate_existing=True)
    )
    return await session.scalar(statement)


async def delete_config(session: AsyncSession, supplier_id: int, *, user_id: int) -> bool:
    config = await get_config(session, supplier_id, user_id=user_id)
    if config is None:
        return False
    await session.delete(config)
    await session.flush()
    return True
