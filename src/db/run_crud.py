"""Ownership-scoped import run reads. Transaction boundaries belong to services."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ImportRun, SourceFile, Supplier

ACTIVE_STATUSES = ("queued", "processing", "retry_wait")


def owned_runs(user_id: int):
    return (
        select(ImportRun)
        .join(SourceFile, SourceFile.id == ImportRun.source_file_id)
        .join(Supplier, Supplier.id == SourceFile.supplier_id)
        .where(Supplier.user_id == user_id)
    )


async def get_run(
    session: AsyncSession, run_id: UUID, *, file_id: UUID, user_id: int
) -> ImportRun | None:
    return await session.scalar(
        owned_runs(user_id).where(ImportRun.id == run_id, ImportRun.source_file_id == file_id)
    )


async def list_runs(
    session: AsyncSession, file_id: UUID, *, user_id: int, offset: int = 0, limit: int = 100
) -> list[ImportRun]:
    result = await session.scalars(
        owned_runs(user_id)
        .where(ImportRun.source_file_id == file_id)
        .order_by(ImportRun.created_at.desc(), ImportRun.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.all())


async def latest_runs(
    session: AsyncSession, file_ids: list[UUID], *, user_id: int
) -> dict[UUID, ImportRun]:
    if not file_ids:
        return {}
    result = await session.scalars(
        owned_runs(user_id)
        .where(ImportRun.source_file_id.in_(file_ids))
        .distinct(ImportRun.source_file_id)
        .order_by(ImportRun.source_file_id, ImportRun.created_at.desc(), ImportRun.id.desc())
    )
    return {run.source_file_id: run for run in result}
