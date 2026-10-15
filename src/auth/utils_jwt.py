from datetime import UTC, datetime, timedelta

import jwt

from src.core.config import PRIVATE_KEY_PATH, PUBLIC_KEY_PATH, TOKEN_EXPIRATION_MINUTES
from src.models.user import UserRead


def encode_jwt(payload: dict, private_key: str | None = None) -> str:
    if private_key is None:
        private_key = PRIVATE_KEY_PATH.read_text()
    now = datetime.now(UTC)
    claims = {**payload, "iat": now, "exp": now + timedelta(minutes=TOKEN_EXPIRATION_MINUTES)}

    return jwt.encode(claims, private_key, algorithm="RS256")


def decode_jwt(token: str, public_key: str | None = None) -> dict:
    if public_key is None:
        public_key = PUBLIC_KEY_PATH.read_text()
    return jwt.decode(
        token, public_key, algorithms=["RS256"], options={"require": ["sub", "exp", "iat"]}
    )

def get_user_id_from_jwt(token: str, public_key: str | None = None) -> UserRead:
    payload = decode_jwt(token, public_key)
    return UserRead(id=int(payload["sub"]), username=payload["username"], email=payload["email"])
