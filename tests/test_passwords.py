import pytest

from src.auth.passwords import hash_password, validate_password


def test_hash_and_verify():
    encoded = hash_password("StrongPassword123")
    assert isinstance(encoded, str)
    assert encoded != "StrongPassword123"
    assert validate_password("StrongPassword123", encoded)
    assert not validate_password("wrong-password", encoded)
    assert not validate_password("я" * 37, encoded)
    assert not validate_password("anything", "invalid-hash")


@pytest.mark.parametrize("password", ["", "a" * 73, "я" * 37])
def test_hash_rejects_unsupported_length(password):
    with pytest.raises(ValueError):
        hash_password(password)
