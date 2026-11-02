import asyncio
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from scripts.generate_keys import generate_keys
from src.api import dependencies
from src.api.routers import users
from src.auth import jwt as auth_jwt
from src.db.models import User
from src.main import app
from tests.conftest import isolated_sessions

pytestmark = pytest.mark.integration


def test_registration_login_profile_and_inactive_user(database_url, tmp_path, monkeypatch):
    generate_keys(tmp_path)
    monkeypatch.setattr(auth_jwt, "PRIVATE_KEY_PATH", tmp_path / "private_key.pem")
    monkeypatch.setattr(auth_jwt, "PUBLIC_KEY_PATH", tmp_path / "public_key.pem")

    async def scenario():
        async with isolated_sessions(database_url) as sessions:

            @asynccontextmanager
            async def get_test_session():
                async with sessions() as session:
                    yield session

            monkeypatch.setattr(dependencies, "get_session", get_test_session)
            monkeypatch.setattr(users, "get_session", get_test_session)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                data = {
                    "username": "alice",
                    "email": "Alice@Example.com",
                    "password": "StrongPassword123",
                }
                registered = await client.post("/users/auth/register", json=data)
                assert registered.status_code == 201, registered.text
                profile = registered.json()
                assert profile["email"] == "alice@example.com"
                assert "password" not in profile
                assert "password_hash" not in profile

                for duplicate in (
                    {**data, "username": "another"},
                    {**data, "email": "another@example.com"},
                ):
                    response = await client.post("/users/auth/register", json=duplicate)
                    assert response.status_code == 409, response.text

                credentials = {"email": data["email"], "password": data["password"]}
                for invalid in (
                    {**credentials, "email": "missing@example.com"},
                    {**credentials, "password": "WrongPassword123"},
                ):
                    response = await client.post("/users/auth/login", json=invalid)
                    assert response.status_code == 401

                logged_in = await client.post("/users/auth/login", json=credentials)
                assert logged_in.status_code == 200, logged_in.text
                assert logged_in.json()["token_type"] == "bearer"
                token = logged_in.json()["access_token"]
                assert auth_jwt.get_user_id_from_jwt(token) == profile["id"]
                headers = {"Authorization": f"Bearer {token}"}
                me = await client.get("/users/me", headers=headers)
                assert me.status_code == 200, me.text
                assert me.json() == profile

                async with sessions() as session, session.begin():
                    user = await session.get(User, profile["id"])
                    user.is_active = False
                assert (await client.post("/users/auth/login", json=credentials)).status_code == 401
                assert (await client.get("/users/me", headers=headers)).status_code == 401

    asyncio.run(scenario())
