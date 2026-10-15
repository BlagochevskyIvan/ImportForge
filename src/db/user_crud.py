"""User persistence. The caller owns the session and commits the transaction."""

from asyncio import to_thread

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.passwords import hash_password
from src.db.models import User
from src.schemas.users import UserCreate, UserUpdate


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    password_hash = await to_thread(hash_password, data.password)
    user = User(username=data.username, email=str(data.email), password_hash=password_hash)
    session.add(user)
    await session.flush()
    return user


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    statement = select(User).where(User.email == email.strip().lower())
    return await session.scalar(statement)


async def update_user(session: AsyncSession, user_id: int, data: UserUpdate) -> User | None:
    user = await get_user_by_id(session, user_id)
    if user is None:
        return None
    changes = data.model_dump(exclude_unset=True)
    password = changes.pop("password", None)
    if password is not None:
        user.password_hash = await to_thread(hash_password, password)
    for field, value in changes.items():
        setattr(user, field, value)
    await session.flush()
    return user


async def delete_user(session: AsyncSession, user_id: int) -> bool:
    user = await get_user_by_id(session, user_id)
    if user is None:
        return False
    await session.delete(user)
    await session.flush()
    return True
