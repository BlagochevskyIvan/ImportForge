"""One refresh session per user. The caller owns the transaction and commit."""

from datetime import datetime

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User


async def save_refresh_token(
    session: AsyncSession, user_id: int, token_hash: str, expires_at: datetime
) -> bool:
    statement = (
        update(User)
        .where(User.id == user_id, User.is_active.is_(True))
        .values(ref_hash=token_hash, exp_time=expires_at)
        .returning(User.id)
    )
    return await session.scalar(statement) is not None


async def rotate_refresh_token(
    session: AsyncSession, old_hash: str, new_hash: str, expires_at: datetime
) -> int | None:
    # PostgreSQL rechecks the WHERE condition after a concurrent updater commits.
    # Exactly one request can replace a particular old hash.
    statement = (
        update(User)
        .where(
            User.ref_hash == old_hash,
            User.exp_time > func.clock_timestamp(),
            User.is_active.is_(True),
        )
        .values(ref_hash=new_hash, exp_time=expires_at)
        .returning(User.id)
    )
    return await session.scalar(statement)


async def revoke_refresh_token(session: AsyncSession, token_hash: str) -> None:
    statement = update(User).where(User.ref_hash == token_hash).values(ref_hash=None, exp_time=None)
    await session.execute(statement)
