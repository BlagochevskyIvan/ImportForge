"""Opaque refresh secrets. Only their SHA-256 hashes belong in the database."""

import hashlib
import secrets


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
