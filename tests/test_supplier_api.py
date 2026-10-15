import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

from src.api import dependencies
from src.api.routers import suppliers
from src.auth import jwt as auth_jwt
from src.db.models import User
from src.main import app
from tests.conftest import isolated_sessions

pytestmark = pytest.mark.integration


@pytest.fixture
def signing_key(tmp_path, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key_path = tmp_path / "public.pem"
    public_key_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    monkeypatch.setattr(auth_jwt, "PUBLIC_KEY_PATH", public_key_path)
    return key


@asynccontextmanager
async def authenticated_client(database_url, monkeypatch, signing_key):
    async with isolated_sessions(database_url) as sessions:

        @asynccontextmanager
        async def get_test_session():
            async with sessions() as session:
                yield session

        monkeypatch.setattr(dependencies, "get_session", get_test_session)
        monkeypatch.setattr(suppliers, "get_session", get_test_session)

        async with sessions() as session, session.begin():
            owner = User(username="owner", email="owner@example.com", password_hash="unused")
            other = User(username="other", email="other@example.com", password_hash="unused")
            inactive = User(
                username="inactive",
                email="inactive@example.com",
                password_hash="unused",
                is_active=False,
            )
            session.add_all([owner, other, inactive])
            await session.flush()
            ids = {"owner": owner.id, "other": other.id, "inactive": inactive.id}

        def authorization(user_id, *, expired=False):
            now = datetime.now(UTC)
            token = jwt.encode(
                {
                    "sub": str(user_id),
                    "iat": now - timedelta(minutes=2),
                    "exp": now + timedelta(minutes=-1 if expired else 5),
                },
                signing_key,
                algorithm="RS256",
            )
            return {"Authorization": f"Bearer {token}"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, ids, authorization


def test_supplier_lifecycle_and_ownership(database_url, monkeypatch, signing_key):
    async def scenario():
        async with authenticated_client(database_url, monkeypatch, signing_key) as context:
            client, ids, authorization = context
            owner = authorization(ids["owner"])
            other = authorization(ids["other"])
            data = {"name": "Supplier", "contact_email": "supplier@example.com"}

            created = await client.post("/suppliers", json=data, headers=owner)
            assert created.status_code == 201, created.text
            supplier = created.json()
            assert supplier["user_id"] == ids["owner"]
            assert supplier["is_active"] is True
            path = f"/suppliers/{supplier['id']}"

            found = await client.get(path, headers=owner)
            assert found.status_code == 200
            assert found.json() == supplier
            listed = await client.get("/suppliers", headers=owner)
            assert listed.status_code == 200
            assert listed.json() == [supplier]
            assert (await client.get("/suppliers", headers=other)).json() == []
            assert (await client.get(path, headers=other)).status_code == 404
            forbidden = await client.patch(path, json={"name": "Stolen"}, headers=other)
            assert forbidden.status_code == 404

            updated = await client.patch(path, json={"name": "Renamed"}, headers=owner)
            assert updated.status_code == 200, updated.text
            assert updated.json() == {**supplier, "name": "Renamed"}
            persisted = await client.get(path, headers=owner)
            assert persisted.json() == updated.json()
            assert (await client.get("/suppliers/-1", headers=owner)).status_code == 404
            missing = await client.patch("/suppliers/-1", json={"name": "Missing"}, headers=owner)
            assert missing.status_code == 404

    asyncio.run(scenario())


def test_supplier_authentication(database_url, monkeypatch, signing_key):
    async def scenario():
        async with authenticated_client(database_url, monkeypatch, signing_key) as context:
            client, ids, authorization = context
            invalid_headers = [
                {},
                {"Authorization": "Bearer invalid"},
                authorization(ids["owner"], expired=True),
                authorization(ids["inactive"]),
                authorization(-1),
            ]
            for headers in invalid_headers:
                for method, path, body in [
                    ("GET", "/suppliers", None),
                    ("POST", "/suppliers", {"name": "S", "contact_email": "s@example.com"}),
                    ("GET", "/suppliers/1", None),
                    ("PATCH", "/suppliers/1", {"name": "Changed"}),
                    ("GET", "/users/me", None),
                ]:
                    response = await client.request(method, path, json=body, headers=headers)
                    assert response.status_code == 401, response.text
                    assert response.headers["www-authenticate"] == "Bearer"

    asyncio.run(scenario())


def test_supplier_validation_and_pagination(database_url, monkeypatch, signing_key):
    async def scenario():
        async with authenticated_client(database_url, monkeypatch, signing_key) as context:
            client, ids, authorization = context
            headers = authorization(ids["owner"])
            for index in range(2):
                response = await client.post(
                    "/suppliers",
                    json={"name": f"Supplier {index}", "contact_email": "s@example.com"},
                    headers=headers,
                )
                assert response.status_code == 201
                supplier_id = response.json()["id"]
            page = await client.get("/suppliers?offset=1&limit=1", headers=headers)
            assert page.status_code == 200
            assert [item["id"] for item in page.json()] == [supplier_id]
            for query in ["offset=-1", "limit=0", "limit=101"]:
                response = await client.get(f"/suppliers?{query}", headers=headers)
                assert response.status_code == 422
            for body in [{}, {"name": None}, {"user_id": ids["other"]}]:
                response = await client.patch(
                    f"/suppliers/{supplier_id}", json=body, headers=headers
                )
                assert response.status_code == 422
            response = await client.post(
                "/suppliers",
                json={
                    "name": "Fake owner",
                    "contact_email": "s@example.com",
                    "user_id": ids["other"],
                },
                headers=headers,
            )
            assert response.status_code == 422
            unchanged = await client.get(f"/suppliers/{supplier_id}", headers=headers)
            assert unchanged.json()["user_id"] == ids["owner"]
            assert unchanged.json()["name"] == "Supplier 1"

    asyncio.run(scenario())
