from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.db.models import User
from src.models.config import CsvConfig, ImportConfigRead
from src.models.suppliers import SupplierCreate, SupplierUpdate
from src.models.user import UserCreate, UserRead, UserUpdate

USER = {"username": "alice", "email": "Alice@Example.com", "password": "StrongPassword123"}
MAPPING = {"Артикул": "sku", "Название": "name", "Цена": "price"}


def test_normalization_keeps_password_unchanged():
    data = UserCreate(**{**USER, "username": " alice ", "password": " password "})
    assert data.username == "alice"
    assert data.email == "alice@example.com"
    assert data.password == " password "


@pytest.mark.parametrize(
    "changes",
    [
        {"username": "  "},
        {"username": "a" * 65},
        {"email": "invalid"},
        {"password": "short"},
        {"password": "a" * 73},
        {"password": "я" * 37},
        {"is_active": True},
        {"password_hash": "client-selected"},
    ],
)
def test_user_input_rejects_invalid_or_server_owned_fields(changes):
    with pytest.raises(ValidationError):
        UserCreate(**{**USER, **changes})


@pytest.mark.parametrize("schema", [UserUpdate, SupplierUpdate])
@pytest.mark.parametrize("payload", [{}, {"is_active": None}, {"id": 1}])
def test_patch_requires_explicit_non_null_allowed_changes(schema, payload):
    with pytest.raises(ValidationError):
        schema(**payload)


def test_patch_only_emits_provided_fields():
    assert UserUpdate(username="renamed").model_dump(exclude_unset=True) == {"username": "renamed"}


def test_read_schema_hides_password_hash_and_reads_orm_attributes():
    user = User(
        id=1,
        username="alice",
        email="alice@example.com",
        password_hash="not-a-public-field",
        is_active=True,
        created_at=datetime.now(UTC),
    )
    response = UserRead.model_validate(user).model_dump()
    assert "password_hash" not in response
    assert "password" not in response


def test_supplier_client_cannot_choose_owner():
    with pytest.raises(ValidationError):
        SupplierCreate(name="Supplier", contact_email="contact@example.com", user_id=2)


@pytest.mark.parametrize("delimiter", ["", "::", "\n", "\r", "\0", '"'])
def test_invalid_csv_delimiter(delimiter):
    with pytest.raises(ValidationError):
        CsvConfig(delimiter=delimiter, column_mapping=MAPPING)


@pytest.mark.parametrize(
    "mapping",
    [
        {"A": "sku"},
        {"A": "sku", "B": "sku", "C": "price"},
        {"A": "sku", "B": "name", "C": "unknown"},
        {" ": "sku", "B": "name", "C": "price"},
        {"A": "sku", " A ": "name", "C": "price"},
    ],
)
def test_mapping_requires_each_known_target_once(mapping):
    with pytest.raises(ValidationError):
        CsvConfig(column_mapping=mapping)


def test_config_is_structured_json():
    config = CsvConfig(delimiter=";", column_mapping=MAPPING)
    response = ImportConfigRead(id=1, supplier_id=2, config_data=config)
    assert response.model_dump()["config_data"]["column_mapping"]["Цена"] == "price"
