from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from src.api.routers.suppliers import router as suppliers_router
from src.api.routers.users import router as user_router
from src.db.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        yield
    finally:
        await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(suppliers_router, prefix="/suppliers", tags=["suppliers"])
app.include_router(user_router, prefix="/users", tags=["users"])
