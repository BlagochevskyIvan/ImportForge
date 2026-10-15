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
SQL_ECHO = getenv("SQL_ECHO", "false").lower() == "true"
