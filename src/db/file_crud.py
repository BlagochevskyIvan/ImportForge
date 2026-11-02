from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import SourceFile, Supplier


async def get_file_by_id(
    session: AsyncSession, file_id: UUID, *, user_id: int, for_update: bool = False
) -> SourceFile | None:
    statement = (
        select(SourceFile)
        .join(Supplier, Supplier.id == SourceFile.supplier_id)
        .where(SourceFile.id == file_id, Supplier.user_id == user_id)
    )
    if for_update:
        statement = statement.with_for_update(of=SourceFile)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_files(
    session: AsyncSession, supplier_id: int, *, user_id: int, offset: int = 0, limit: int = 20
) -> list[SourceFile]:
    statement = (
        select(SourceFile)
        .join(Supplier, Supplier.id == SourceFile.supplier_id)
        .where(SourceFile.supplier_id == supplier_id, Supplier.user_id == user_id)
        .order_by(SourceFile.created_at.desc(), SourceFile.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.scalars(statement)
    return list(result.all())
