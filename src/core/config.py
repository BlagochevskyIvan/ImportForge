from os import getenv
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
DATABASE_URL = getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be configured")

if not DATABASE_URL.startswith("postgresql+asyncpg://"):
    raise RuntimeError("DATABASE_URL must use the postgresql+asyncpg driver")

PUBLIC_KEY_PATH = BASE_DIR / "certs" / "public_key.pem"
PRIVATE_KEY_PATH = BASE_DIR / "certs" / "private_key.pem"

TOKEN_EXPIRATION_MINUTES = int(getenv("TOKEN_EXPIRATION_MINUTES", "15"))
if TOKEN_EXPIRATION_MINUTES <= 0:
    raise RuntimeError("TOKEN_EXPIRATION_MINUTES must be positive")

REFRESH_TOKEN_EXPIRATION_DAYS = int(getenv("REFRESH_TOKEN_EXPIRATION_DAYS", "7"))
if REFRESH_TOKEN_EXPIRATION_DAYS <= 0:
    raise RuntimeError("REFRESH_TOKEN_EXPIRATION_DAYS must be positive")
REFRESH_COOKIE_SECURE = getenv("REFRESH_COOKIE_SECURE", "false").lower() == "true"
AUTH_ALLOWED_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in getenv(
        "AUTH_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
}
SQL_ECHO = getenv("SQL_ECHO", "false").lower() == "true"
