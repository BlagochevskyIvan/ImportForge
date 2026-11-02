import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src import main

pytestmark = pytest.mark.integration


def test_startup_and_shutdown_with_postgresql(database_url, monkeypatch):
    async def scenario():
        engine = create_async_engine(database_url, hide_parameters=True)
        monkeypatch.setattr(main, "engine", engine)
        async with main.app.router.lifespan_context(main.app):
            async with engine.connect() as connection:
                assert await connection.scalar(text("SELECT 1")) == 1
        assert engine.pool.checkedout() == 0

    asyncio.run(scenario())
