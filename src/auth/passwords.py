"""Password helpers do not need JWT keys or a database connection."""

import bcrypt


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if not password_bytes or len(password_bytes) > 72:
        raise ValueError("Password must contain between 1 and 72 UTF-8 bytes")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def validate_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False
