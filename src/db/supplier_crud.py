"""Every supplier operation requires an owner ID supplied by trusted server code."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Supplier
from src.models.suppliers import SupplierCreate, SupplierUpdate


async def get_supplier_by_id(
    session: AsyncSession, supplier_id: int, *, user_id: int
) -> Supplier | None:
    statement = select(Supplier).where(Supplier.id == supplier_id, Supplier.user_id == user_id)
    return await session.scalar(statement)


async def list_suppliers(
    session: AsyncSession, *, user_id: int, offset: int = 0, limit: int = 100
) -> list[Supplier]:
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("offset must be non-negative and limit must be between 1 and 100")
    statement = (
        select(Supplier)
        .where(Supplier.user_id == user_id)
        .order_by(Supplier.id)
        .offset(offset)
        .limit(limit)
    )
    return list((await session.scalars(statement)).all())


async def create_supplier(session: AsyncSession, data: SupplierCreate, *, user_id: int) -> Supplier:
    supplier = Supplier(user_id=user_id, **data.model_dump())
    session.add(supplier)
    await session.flush()
    return supplier


async def update_supplier(
    session: AsyncSession, supplier_id: int, data: SupplierUpdate, *, user_id: int
) -> Supplier | None:
    supplier = await get_supplier_by_id(session, supplier_id, user_id=user_id)
    if supplier is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    await session.flush()
    return supplier


async def delete_supplier(session: AsyncSession, supplier_id: int, *, user_id: int) -> bool:
    supplier = await get_supplier_by_id(session, supplier_id, user_id=user_id)
    if supplier is None:
        return False
    await session.delete(supplier)
    await session.flush()
    return True
