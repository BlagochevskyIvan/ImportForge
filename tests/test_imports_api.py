import asyncio
from uuid import UUID

import pytest
from botocore.exceptions import EndpointConnectionError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers import imports
from src.db.models import SourceFile
from tests.test_supplier_api import authenticated_client
from tests.test_supplier_api import signing_key as signing_key
from tests.test_supplier_config_api import CONFIG

pytestmark = pytest.mark.integration
CSV = "Код;Товар;Цена\n1;Тест;100\n".encode("cp1251")


class FileStorage:
    def __init__(self):
        self.files = {}
        self.deleted = []
        self.unavailable = False

    def upload(self, fileobj, key):
        if self.unavailable:
            raise EndpointConnectionError(endpoint_url="http://storage.invalid")
        self.files[key] = fileobj.read()

    def delete(self, key):
        self.deleted.append(key)
        self.files.pop(key, None)


async def create_supplier(client, headers):
    response = await client.post(
        "/suppliers",
        headers=headers,
        json={"name": "CSV Supplier", "contact_email": "supplier@example.com"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_upload_binds_supplier_and_snapshots_config(database_url, monkeypatch, signing_key):
    async def scenario():
        storage = FileStorage()
        monkeypatch.setattr(imports, "get_storage", lambda: storage)
        async with authenticated_client(database_url, monkeypatch, signing_key) as context:
            from src.api.routers import suppliers

            monkeypatch.setattr(imports, "get_session", suppliers.get_session)
            client, ids, authorization = context
            owner = authorization(ids["owner"])
            supplier_id = await create_supplier(client, owner)
            path = f"/suppliers/{supplier_id}/config"
            await client.put(path, headers=owner, json={"config_data": CONFIG})
            response = await client.post(
                "/imports",
                headers=owner,
                data={"supplier_id": supplier_id},
                files={"file": ("прайс.CSV", CSV, "text/csv")},
            )
            assert response.status_code == 201, response.text
            result = response.json()
            assert result["supplier_id"] == supplier_id
            assert result["status"] == "uploaded"
            assert result["filename"] == "прайс.CSV"
            async with imports.get_session() as session:
                record = await session.get(SourceFile, UUID(result["id"]))
                assert record.supplier_id == supplier_id
                assert record.config_data == CONFIG
                assert storage.files[record.object_key] == CSV
            await client.put(
                path, headers=owner, json={"config_data": {**CONFIG, "delimiter": ","}}
            )
            async with imports.get_session() as session:
                assert (await session.get(SourceFile, UUID(result["id"]))).config_data == CONFIG

    asyncio.run(scenario())


def test_upload_rejects_auth_ownership_missing_config_and_invalid_files(
    database_url, monkeypatch, signing_key
):
    async def scenario():
        storage = FileStorage()
        monkeypatch.setattr(imports, "get_storage", lambda: storage)
        async with authenticated_client(database_url, monkeypatch, signing_key) as context:
            from src.api.routers import suppliers

            monkeypatch.setattr(imports, "get_session", suppliers.get_session)
            client, ids, authorization = context
            owner = authorization(ids["owner"])
            supplier_id = await create_supplier(client, owner)

            async def upload(headers, filename="price.csv", content=CSV, supplier=supplier_id):
                return await client.post(
                    "/imports",
                    headers=headers,
                    data={"supplier_id": supplier},
                    files={"file": (filename, content, "text/csv")},
                )

            assert (await upload({})).status_code == 401
            assert (await upload(authorization(ids["inactive"]))).status_code == 401
            assert (await upload(authorization(ids["other"]))).status_code == 404
            assert (await upload(owner, supplier=987654321)).status_code == 404
            assert (await upload(owner)).status_code == 409
            await client.put(
                f"/suppliers/{supplier_id}/config", headers=owner, json={"config_data": CONFIG}
            )
            assert (await upload(owner, filename="price.txt")).status_code == 415
            assert (await upload(owner, content=b"")).status_code == 422
            assert (await upload(owner, filename="x" * 252 + ".csv")).status_code == 422
            monkeypatch.setattr(imports, "MAX_FILE_SIZE", len(CSV) - 1)
            assert (await upload(owner)).status_code == 413
            assert storage.files == {}
            async with imports.get_session() as session:
                assert await session.scalar(select(func.count()).select_from(SourceFile)) == 0

    asyncio.run(scenario())


def test_upload_storage_failure_and_database_cleanup(database_url, monkeypatch, signing_key):
    async def scenario():
        storage = FileStorage()
        monkeypatch.setattr(imports, "get_storage", lambda: storage)
        async with authenticated_client(database_url, monkeypatch, signing_key) as context:
            from src.api.routers import suppliers

            monkeypatch.setattr(imports, "get_session", suppliers.get_session)
            client, ids, authorization = context
            owner = authorization(ids["owner"])
            supplier_id = await create_supplier(client, owner)
            await client.put(
                f"/suppliers/{supplier_id}/config", headers=owner, json={"config_data": CONFIG}
            )

            async def upload():
                return await client.post(
                    "/imports",
                    headers=owner,
                    data={"supplier_id": supplier_id},
                    files={"file": ("price.csv", CSV, "text/csv")},
                )

            storage.unavailable = True
            assert (await upload()).status_code == 502
            assert storage.files == {}
            storage.unavailable = False
            flush = AsyncSession.flush

            async def fail_metadata(session, *args, **kwargs):
                if any(isinstance(item, SourceFile) for item in session.new):
                    raise SQLAlchemyError("simulated metadata write failure")
                return await flush(session, *args, **kwargs)

            monkeypatch.setattr(AsyncSession, "flush", fail_metadata)
            assert (await upload()).status_code == 500
            assert len(storage.deleted) == 1
            assert storage.files == {}
            async with imports.get_session() as session:
                assert await session.scalar(select(func.count()).select_from(SourceFile)) == 0

    asyncio.run(scenario())
