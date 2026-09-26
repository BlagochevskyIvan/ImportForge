import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import DATABASE_URL
from src.db.models import Base

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
)

asyncsession = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with asyncsession() as session:
        yield session


async def init_db() -> None:
    """Create missing tables; existing schemas are not migrated."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _main() -> None:
    try:
        await init_db()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
