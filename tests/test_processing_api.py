import asyncio
import csv
import io
from threading import Event
from uuid import uuid4

import pytest
from botocore.exceptions import EndpointConnectionError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.routers import files, suppliers
from src.db.models import ImportRun, SourceFile, Supplier, User
from src.services.import_processor import ProcessingInProgressError, process_import
from tests.conftest import alembic_command, temporary_database
from tests.test_imports_api import CSV, FileStorage, create_supplier
from tests.test_supplier_api import authenticated_client
from tests.test_supplier_api import signing_key as signing_key
from tests.test_supplier_config_api import CONFIG

pytestmark = pytest.mark.integration


async def upload(client, owner, supplier_id, content=CSV):
    response = await client.post(
        "/imports",
        headers=owner,
        data={"supplier_id": supplier_id},
        files={"file": ("price.csv", content, "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_processing_snapshot_downloads_ownership_and_idempotency(
    database_url, monkeypatch, signing_key
):
    async def scenario():
        storage = FileStorage()
        monkeypatch.setattr(files, "get_storage", lambda: storage)
        async with authenticated_client(database_url, monkeypatch, signing_key) as context:
            monkeypatch.setattr(files, "get_session", suppliers.get_session)
            client, ids, authorization = context
            owner, other = authorization(ids["owner"]), authorization(ids["other"])
            supplier_id = await create_supplier(client, owner)
            path = f"/suppliers/{supplier_id}/config"
            await client.put(path, headers=owner, json={"config_data": CONFIG})
            content = 'Код;Товар;Цена\n A-1 ;"Чай; зелёный";"12,50"\n2;Кружка;abc\n'.encode(
                "cp1251"
            )
            file_id = await upload(client, owner, supplier_id, content)
            changed = {**CONFIG, "delimiter": "|", "encoding": "utf-8"}
            await client.put(path, headers=owner, json={"config_data": changed})

            for method, url in [
                ("GET", f"/imports/{file_id}"),
                ("GET", f"/imports/{file_id}/download"),
                ("POST", f"/imports/{file_id}/process"),
                ("GET", f"/imports?supplier_id={supplier_id}"),
            ]:
                assert (await client.request(method, url)).status_code == 401
                assert (await client.request(method, url, headers=other)).status_code == 404
            assert (await client.get("/imports/not-a-uuid", headers=owner)).status_code == 422
            assert (
                await client.get(f"/imports/{file_id}/download?kind=result", headers=owner)
            ).status_code == 409
            assert (
                await client.get(f"/imports/{file_id}/download", headers=owner)
            ).content == content
            response = await client.post(f"/imports/{file_id}/process", headers=owner)
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["status"] == "completed"
            assert result["processing_result"] == {
                "total_rows": 2,
                "successful_rows": 1,
                "failed_rows": 1,
                "error": None,
            }
            assert "result_key" not in result["processing_result"]
            for kind in ["result", "errors"]:
                download = await client.get(
                    f"/imports/{file_id}/download?kind={kind}", headers=owner
                )
                assert download.status_code == 200, download.text
                rows = list(csv.DictReader(io.StringIO(download.content.decode("utf-8-sig"))))
                if kind == "result":
                    assert rows == [{"sku": "A-1", "name": "Чай; зелёный", "price": "12.50"}]
                else:
                    assert len(rows) == 1 and "price" in rows[0]["error"]
            assert (await client.get(f"/imports/{file_id}", headers=owner)).json() == result
            assert (
                await client.get(f"/imports?supplier_id={supplier_id}", headers=owner)
            ).json() == [result]
            objects = dict(storage.files)
            assert (
                await client.post(f"/imports/{file_id}/process", headers=owner)
            ).json() == result
            assert storage.files == objects
            await client.delete(path, headers=owner)
            assert (
                await client.get(f"/imports/{file_id}/download?kind=result", headers=owner)
            ).status_code == 200

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "content",
    [
        "Код;Товар\n1;Чай\n".encode("cp1251"),
        'Код;Товар;Цена\n1;Чай;1\n2;"broken\n'.encode("cp1251"),
    ],
)
def test_file_errors_are_persisted_without_partial_artifacts(
    database_url, monkeypatch, signing_key, content
):
    async def scenario():
        storage = FileStorage()
        monkeypatch.setattr(files, "get_storage", lambda: storage)
        async with authenticated_client(database_url, monkeypatch, signing_key) as context:
            monkeypatch.setattr(files, "get_session", suppliers.get_session)
            client, ids, authorization = context
            owner = authorization(ids["owner"])
            supplier_id = await create_supplier(client, owner)
            await client.put(
                f"/suppliers/{supplier_id}/config", headers=owner, json={"config_data": CONFIG}
            )
            file_id = await upload(client, owner, supplier_id, content)
            result = await client.post(f"/imports/{file_id}/process", headers=owner)
            assert result.status_code == 200, result.text
            assert result.json()["status"] == "failed"
            assert result.json()["processing_result"]["error"]
            assert len(storage.files) == 1
            assert (await client.get(f"/imports/{file_id}", headers=owner)).json() == result.json()
            assert (
                await client.get(f"/imports/{file_id}/download?kind=result", headers=owner)
            ).status_code == 409

    asyncio.run(scenario())


def test_failed_artifact_upload_is_cleaned_and_can_be_retried(
    database_url, monkeypatch, signing_key
):
    async def scenario():
        storage = FileStorage()
        monkeypatch.setattr(files, "get_storage", lambda: storage)
        async with authenticated_client(database_url, monkeypatch, signing_key) as context:
            monkeypatch.setattr(files, "get_session", suppliers.get_session)
            client, ids, authorization = context
            owner = authorization(ids["owner"])
            supplier_id = await create_supplier(client, owner)
            await client.put(
                f"/suppliers/{supplier_id}/config", headers=owner, json={"config_data": CONFIG}
            )
            file_id = await upload(client, owner, supplier_id)
            original_upload = storage.upload

            def broken_upload(fileobj, key):
                original_upload(fileobj, key)
                if key.endswith("errors.csv"):
                    raise EndpointConnectionError(endpoint_url="http://storage.invalid")

            monkeypatch.setattr(storage, "upload", broken_upload)
            result = await client.post(f"/imports/{file_id}/process", headers=owner)
            assert result.json()["status"] == "failed"
            assert len(storage.files) == 1
            assert len(storage.deleted) == 2
            monkeypatch.setattr(storage, "upload", original_upload)
            result = await client.post(f"/imports/{file_id}/process", headers=owner)
            assert result.json()["status"] == "completed", result.text
            assert len(storage.files) == 3

    asyncio.run(scenario())


def test_parallel_requests_process_the_file_once(database_url):
    async def scenario():
        async with temporary_database(database_url) as url:
            migration = alembic_command(url, "upgrade", "head")
            assert migration.returncode == 0, migration.stderr
            engine = create_async_engine(url, hide_parameters=True)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            storage = FileStorage()
            started, release = Event(), Event()
            try:
                async with sessions() as session, session.begin():
                    user = User(username="owner", email="owner@example.com", password_hash="unused")
                    session.add(user)
                    await session.flush()
                    supplier = Supplier(user_id=user.id, name="CSV", contact_email="s@example.com")
                    session.add(supplier)
                    await session.flush()
                    file_id, user_id = uuid4(), user.id
                    session.add(
                        SourceFile(
                            id=file_id,
                            supplier_id=supplier.id,
                            filename="price.csv",
                            object_key="raw/test.csv",
                            config_data=CONFIG,
                        )
                    )
                storage.files["raw/test.csv"] = CSV
                download = storage.download

                def slow_download(key, fileobj):
                    started.set()
                    if not release.wait(10):
                        raise RuntimeError("test did not release download")
                    download(key, fileobj)

                storage.download = slow_download
                first = asyncio.create_task(
                    process_import(
                        file_id, user_id=user_id, storage=storage, session_factory=sessions
                    )
                )
                try:
                    assert await asyncio.to_thread(started.wait, 5)
                    async with sessions() as session:
                        assert (
                            await session.scalar(
                                select(ImportRun).where(ImportRun.source_file_id == file_id)
                            )
                        ).status == "processing"
                    with pytest.raises(ProcessingInProgressError):
                        await process_import(
                            file_id, user_id=user_id, storage=storage, session_factory=sessions
                        )
                finally:
                    release.set()
                    result = await first
                assert result.status == "completed"
                assert len(storage.files) == 3
                assert (
                    await process_import(
                        file_id, user_id=user_id, storage=storage, session_factory=sessions
                    )
                ) == result
                assert len(storage.files) == 3
            finally:
                release.set()
                await engine.dispose()

    asyncio.run(scenario())
