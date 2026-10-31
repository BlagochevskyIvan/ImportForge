"""CSV configuration versions; the latest ID supplies settings for future uploads."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ImportConfig, Supplier
from src.schemas.import_config import CsvConfig


async def _lock_supplier(session: AsyncSession, supplier_id: int, *, user_id: int) -> int | None:
    # Serialize version creation/deletion, including the first save with no config to lock.
    statement = (
        select(Supplier.id)
        .where(Supplier.id == supplier_id, Supplier.user_id == user_id)
        .with_for_update()
    )
    return await session.scalar(statement)


async def _insert_config(
    session: AsyncSession, supplier_id: int, config_data: CsvConfig
) -> ImportConfig:
    config = ImportConfig(supplier_id=supplier_id, config_data=config_data.model_dump(mode="json"))
    session.add(config)
    await session.flush()
    return config


async def get_config(
    session: AsyncSession, supplier_id: int, *, user_id: int
) -> ImportConfig | None:
    statement = (
        select(ImportConfig)
        .join(Supplier, Supplier.id == ImportConfig.supplier_id)
        .where(Supplier.id == supplier_id, Supplier.user_id == user_id)
        .order_by(ImportConfig.id.desc())
        .limit(1)
    )
    return await session.scalar(statement)


async def create_config(
    session: AsyncSession, supplier_id: int, config_data: CsvConfig, *, user_id: int
) -> ImportConfig | None:
    if await _lock_supplier(session, supplier_id, user_id=user_id) is None:
        return None
    return await _insert_config(session, supplier_id, config_data)


async def save_config(
    session: AsyncSession, supplier_id: int, config_data: CsvConfig, *, user_id: int
) -> ImportConfig | None:
    """Append changed settings; an identical PUT keeps the current version."""
    if await _lock_supplier(session, supplier_id, user_id=user_id) is None:
        return None
    current = await get_config(session, supplier_id, user_id=user_id)
    if current is not None and current.config_data == config_data.model_dump(mode="json"):
        return current
    return await _insert_config(session, supplier_id, config_data)


async def delete_config(session: AsyncSession, supplier_id: int, *, user_id: int) -> bool:
    if await _lock_supplier(session, supplier_id, user_id=user_id) is None:
        return False
    # Remove all versions so deleting the current config cannot reactivate an older one.
    # Uploaded files keep their independent config_data snapshots.
    result = await session.execute(
        delete(ImportConfig).where(ImportConfig.supplier_id == supplier_id)
    )
    return result.rowcount > 0
