import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from scripts.generate_keys import generate_keys
from src.api import dependencies
from src.api.routers import users
from src.auth import jwt as auth_jwt
from src.auth.refresh import hash_refresh_token
from src.db.models import User
from src.main import app
from tests.conftest import alembic_command, isolated_sessions, temporary_database

pytestmark = pytest.mark.integration

CREDENTIALS = {"email": "refresh@example.com", "password": "StrongPassword123"}


@pytest.fixture
def auth_setup(tmp_path, monkeypatch):
    generate_keys(tmp_path)
    monkeypatch.setattr(auth_jwt, "PRIVATE_KEY_PATH", tmp_path / "private_key.pem")
    monkeypatch.setattr(auth_jwt, "PUBLIC_KEY_PATH", tmp_path / "public_key.pem")
    monkeypatch.setattr(users, "REFRESH_COOKIE_SECURE", False)
    monkeypatch.setattr(users, "REFRESH_TOKEN_EXPIRATION_DAYS", 7)
    monkeypatch.setattr(dependencies, "AUTH_ALLOWED_ORIGINS", {"http://localhost:3000"})


@asynccontextmanager
async def api_client(sessions, monkeypatch, *, raise_app_exceptions=True):
    @asynccontextmanager
    async def get_test_session():
        async with sessions() as session:
            yield session

    monkeypatch.setattr(users, "get_session", get_test_session)
    monkeypatch.setattr(dependencies, "get_session", get_test_session)
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions),
        base_url="https://test",
    ) as client:
        yield client


async def register_and_login(client):
    registered = await client.post(
        "/users/auth/register", json={"username": "refresh_user", **CREDENTIALS}
    )
    assert registered.status_code == 201, registered.text
    assert "ref_hash" not in registered.json()
    assert "exp_time" not in registered.json()
    login = await client.post("/users/auth/login", json=CREDENTIALS)
    assert login.status_code == 200, login.text
    return registered.json()["id"], login


def cookie_header(token):
    return {"Cookie": f"refresh_token={token}"}


def test_login_rotation_profile_and_logout(database_url, auth_setup, monkeypatch):
    monkeypatch.setattr(users, "REFRESH_COOKIE_SECURE", True)

    async def scenario():
        async with isolated_sessions(database_url) as sessions:
            async with api_client(sessions, monkeypatch) as client:
                user_id, login = await register_and_login(client)
                raw_token = client.cookies.get("refresh_token")
                assert len(raw_token) == 43
                assert set(login.json()) == {"access_token", "token_type"}
                assert raw_token not in login.text
                cookie = login.headers["set-cookie"]
                for attribute in ("HttpOnly", "Secure", "SameSite=lax", "Max-Age=604800", "Path=/"):
                    assert attribute in cookie
                assert login.headers["cache-control"] == "no-store"
                async with sessions() as session:
                    user = await session.get(User, user_id)
                    assert user.ref_hash == hash_refresh_token(raw_token)
                    assert user.ref_hash != raw_token
                    assert (
                        timedelta(days=6) < user.exp_time - datetime.now(UTC) <= timedelta(days=7)
                    )

                # The browser can restore access even when its previous access JWT has expired.
                expired_access = jwt.encode(
                    {"sub": str(user_id), "iat": 0, "exp": 1},
                    auth_jwt.PRIVATE_KEY_PATH.read_text(),
                    algorithm="RS256",
                )
                assert (
                    await client.get(
                        "/users/me", headers={"Authorization": f"Bearer {expired_access}"}
                    )
                ).status_code == 401
                refreshed = await client.post(
                    "/users/auth/refresh",
                    headers={"Authorization": f"Bearer {expired_access}"},
                )
                assert refreshed.status_code == 200, refreshed.text
                replacement = client.cookies.get("refresh_token")
                assert replacement != raw_token
                assert auth_jwt.get_user_id_from_jwt(refreshed.json()["access_token"]) == user_id
                assert (
                    await client.post("/users/auth/refresh", headers=cookie_header(raw_token))
                ).status_code == 401
                access_headers = {"Authorization": f"Bearer {refreshed.json()['access_token']}"}
                profile = await client.get("/users/me", headers=access_headers)
                assert profile.status_code == 200
                assert profile.json()["id"] == user_id
                assert "ref_hash" not in profile.json()

                logout = await client.post("/users/auth/logout")
                assert logout.status_code == 204
                assert logout.content == b""
                assert "Max-Age=0" in logout.headers["set-cookie"]
                assert client.cookies.get("refresh_token") is None
                async with sessions() as session:
                    user = await session.get(User, user_id)
                    assert user.ref_hash is None
                    assert user.exp_time is None
                assert (
                    await client.post("/users/auth/refresh", headers=cookie_header(replacement))
                ).status_code == 401
                assert (await client.post("/users/auth/logout")).status_code == 204
                assert (
                    await client.post("/users/auth/logout", headers=cookie_header("unknown"))
                ).status_code == 204
                # Revoking refresh does not revoke an already issued access JWT.
                assert (await client.get("/users/me", headers=access_headers)).status_code == 200

    asyncio.run(scenario())


@pytest.mark.parametrize("invalid", ["missing", "unknown", "expired", "inactive", "null_expiry"])
def test_refresh_rejects_invalid_sessions(database_url, auth_setup, monkeypatch, invalid):
    async def scenario():
        async with isolated_sessions(database_url) as sessions:
            async with api_client(sessions, monkeypatch) as client:
                user_id, _ = await register_and_login(client)
                raw_token = client.cookies.get("refresh_token")
                if invalid == "missing":
                    client.cookies.clear()
                elif invalid == "unknown":
                    client.cookies.clear()
                    client.cookies.set("refresh_token", raw_token + "x")
                else:
                    async with sessions() as session, session.begin():
                        user = await session.get(User, user_id)
                        if invalid == "expired":
                            user.exp_time = datetime.now(UTC) - timedelta(seconds=1)
                        elif invalid == "inactive":
                            user.is_active = False
                        else:
                            user.exp_time = None
                response = await client.post("/users/auth/refresh")
                assert response.status_code == 401, response.text
                assert "access_token" not in response.json()
                assert "set-cookie" not in response.headers
                async with sessions() as session:
                    assert (await session.get(User, user_id)).ref_hash == hash_refresh_token(
                        raw_token
                    )

    asyncio.run(scenario())


def test_new_login_replaces_refresh_and_stale_logout_cannot_revoke_it(
    database_url, auth_setup, monkeypatch
):
    async def scenario():
        async with isolated_sessions(database_url) as sessions:
            async with api_client(sessions, monkeypatch) as client:
                await register_and_login(client)
                old_token = client.cookies.get("refresh_token")
                assert (await client.post("/users/auth/login", json=CREDENTIALS)).status_code == 200
                current_token = client.cookies.get("refresh_token")
                assert current_token != old_token
                assert (
                    await client.post("/users/auth/refresh", headers=cookie_header(old_token))
                ).status_code == 401
                assert (
                    await client.post("/users/auth/logout", headers=cookie_header(old_token))
                ).status_code == 204
                # Logout clears the client's cookie, but the current DB secret must remain valid.
                assert (
                    await client.post("/users/auth/refresh", headers=cookie_header(current_token))
                ).status_code == 200

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://attacker.example"},
        {"Origin": "null"},
        {"Origin": "http://localhost:3000.attacker.example"},
        {"Referer": "https://attacker.example/form"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cookie_auth_rejects_untrusted_origins(database_url, auth_setup, monkeypatch, headers):
    async def scenario():
        async with isolated_sessions(database_url) as sessions:
            async with api_client(sessions, monkeypatch) as client:
                user_id, _ = await register_and_login(client)
                token = client.cookies.get("refresh_token")
                for endpoint in ("login", "refresh", "logout"):
                    response = await client.post(
                        f"/users/auth/{endpoint}", json=CREDENTIALS, headers=headers
                    )
                    assert response.status_code == 403, response.text
                    assert "set-cookie" not in response.headers
                async with sessions() as session:
                    assert (await session.get(User, user_id)).ref_hash == hash_refresh_token(token)
                assert (
                    await client.post(
                        "/users/auth/refresh", headers={"Origin": "http://localhost:3000"}
                    )
                ).status_code == 200

    asyncio.run(scenario())


def test_failed_signing_rolls_back_login_and_rotation(database_url, auth_setup, monkeypatch):
    def broken_signer(payload):
        raise RuntimeError("Signing unavailable")

    async def scenario():
        async with isolated_sessions(database_url) as sessions:
            async with api_client(sessions, monkeypatch, raise_app_exceptions=False) as client:
                user_id, _ = await register_and_login(client)
                token = client.cookies.get("refresh_token")
                with monkeypatch.context() as signing_patch:
                    signing_patch.setattr(users, "encode_jwt", broken_signer)
                    for endpoint in ("login", "refresh"):
                        response = await client.post(f"/users/auth/{endpoint}", json=CREDENTIALS)
                        assert response.status_code == 500
                        assert "set-cookie" not in response.headers
                        async with sessions() as session:
                            user = await session.get(User, user_id)
                            assert user.ref_hash == hash_refresh_token(token)
                assert (await client.post("/users/auth/refresh")).status_code == 200

    asyncio.run(scenario())


def test_parallel_refresh_allows_only_one_success(database_url, auth_setup, monkeypatch):
    async def scenario():
        # Separate committed connections are essential: one shared SAVEPOINT cannot prove locking.
        async with temporary_database(database_url) as url:
            migration = alembic_command(url, "upgrade", "head")
            assert migration.returncode == 0, migration.stderr
            engine = create_async_engine(url, hide_parameters=True)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with api_client(sessions, monkeypatch) as client:
                    user_id, _ = await register_and_login(client)
                    original = client.cookies.get("refresh_token")
                    # Hold the user lock so both HTTP requests reach their competing UPDATEs.
                    async with sessions() as lock_session, lock_session.begin():
                        await lock_session.scalar(
                            select(User).where(User.id == user_id).with_for_update()
                        )
                        requests = [
                            asyncio.create_task(
                                client.post("/users/auth/refresh", headers=cookie_header(original))
                            )
                            for _ in range(2)
                        ]
                        await asyncio.sleep(0.1)
                        assert all(not task.done() for task in requests)
                    responses = await asyncio.gather(*requests)
                    assert sorted(response.status_code for response in responses) == [200, 401]
                    winner = next(response for response in responses if response.status_code == 200)
                    replacement = winner.cookies.get("refresh_token")
                    async with sessions() as session:
                        assert (await session.get(User, user_id)).ref_hash == hash_refresh_token(
                            replacement
                        )
                    assert (
                        await client.post("/users/auth/refresh", headers=cookie_header(replacement))
                    ).status_code == 200
            finally:
                await engine.dispose()

    asyncio.run(scenario())
