from datetime import UTC, datetime, timedelta

import jwt
import pytest

from scripts.generate_keys import generate_keys
from src.auth import jwt as auth_jwt


@pytest.fixture
def jwt_keys(tmp_path, monkeypatch):
    generate_keys(tmp_path)
    private = tmp_path / "private_key.pem"
    public = tmp_path / "public_key.pem"
    monkeypatch.setattr(auth_jwt, "PRIVATE_KEY_PATH", private)
    monkeypatch.setattr(auth_jwt, "PUBLIC_KEY_PATH", public)
    return private.read_text(), public.read_text()


def test_jwt_roundtrip_with_configured_keys(jwt_keys):
    token = auth_jwt.encode_jwt({"sub": "42", "iat": 0, "exp": 0})
    payload = auth_jwt.decode_jwt(token)
    assert auth_jwt.get_user_id_from_jwt(token) == 42
    assert payload["sub"] == "42"
    assert payload["iat"] > 0
    assert payload["exp"] - payload["iat"] == auth_jwt.TOKEN_EXPIRATION_MINUTES * 60


def test_jwt_roundtrip_with_explicit_keys(jwt_keys):
    private, public = jwt_keys
    token = auth_jwt.encode_jwt({"sub": "7"}, private)
    assert auth_jwt.decode_jwt(token, public)["sub"] == "7"
    assert auth_jwt.get_user_id_from_jwt(token, public) == 7


@pytest.mark.parametrize("missing_claim", ["sub", "iat", "exp"])
def test_jwt_requires_claims(jwt_keys, missing_claim):
    private, _ = jwt_keys
    now = datetime.now(UTC)
    payload = {"sub": "1", "iat": now, "exp": now + timedelta(minutes=5)}
    del payload[missing_claim]
    token = jwt.encode(payload, private, algorithm="RS256")
    with pytest.raises(jwt.MissingRequiredClaimError):
        auth_jwt.decode_jwt(token)


def test_jwt_rejects_expired_tokens(jwt_keys):
    private, _ = jwt_keys
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": "1", "iat": now - timedelta(minutes=2), "exp": now - timedelta(minutes=1)},
        private,
        algorithm="RS256",
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        auth_jwt.decode_jwt(token)


def test_jwt_rejects_wrong_signature(jwt_keys, tmp_path):
    generate_keys(tmp_path / "other")
    other_private = (tmp_path / "other" / "private_key.pem").read_text()
    token = auth_jwt.encode_jwt({"sub": "1"}, other_private)
    with pytest.raises(jwt.InvalidSignatureError):
        auth_jwt.decode_jwt(token)


def test_jwt_rejects_unapproved_algorithm(jwt_keys):
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": "1", "iat": now, "exp": now + timedelta(minutes=5)},
        "test-secret-that-is-at-least-32-bytes",
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidAlgorithmError):
        auth_jwt.decode_jwt(token)


def test_user_id_must_be_an_integer(jwt_keys):
    token = auth_jwt.encode_jwt({"sub": "not-an-id"})
    with pytest.raises(ValueError):
        auth_jwt.get_user_id_from_jwt(token)
