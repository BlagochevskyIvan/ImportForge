from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import DATABASE_URL, SQL_ECHO

engine = create_async_engine(
    DATABASE_URL,
    echo=SQL_ECHO,
    hide_parameters=True,
    pool_pre_ping=True,
)

asyncsession = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with asyncsession() as session:
        yield session


if __name__ == "__main__":
    raise SystemExit("Use 'make migrate' to create or update the database schema through Alembic.")
