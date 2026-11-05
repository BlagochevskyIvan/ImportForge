import asyncio
import csv
import io
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.routers import files, suppliers
from src.db.models import ImportRun, SourceFile, Supplier, User
from src.services.import_processor import create_import_run, execute_import_run
from tests.conftest import isolated_sessions
from tests.test_imports_api import FileStorage, create_supplier
from tests.test_supplier_api import authenticated_client
from tests.test_supplier_api import signing_key as signing_key

pytestmark = pytest.mark.integration

TEXT = {
    "delimiter": ";",
    "columns": [{"source": "Компания", "target": "организация", "required": True}],
}
AMOUNT = {
    "delimiter": ";",
    "columns": [{"source": "Сумма", "target": "стоимость", "type": "decimal"}],
}
CONTENT = 'Компания;Сумма\n ООО Тест ;"-12,50"\n'.encode()


def test_upload_before_config_multiple_runs_snapshots_history_and_access(
    database_url, monkeypatch, signing_key
):
    async def scenario():
        storage = FileStorage()
        monkeypatch.setattr(files, "get_storage", lambda: storage)
        async with authenticated_client(database_url, monkeypatch, signing_key) as (
            client,
            ids,
            authorization,
        ):
            monkeypatch.setattr(files, "get_session", suppliers.get_session)
            owner, other = authorization(ids["owner"]), authorization(ids["other"])
            supplier_id = await create_supplier(client, owner)
            config_path = f"/suppliers/{supplier_id}/config"
            response = await client.post(
                "/imports",
                headers=owner,
                data={"supplier_id": supplier_id},
                files={"file": ("feed.csv", CONTENT, "text/csv")},
            )
            assert response.status_code == 201, response.text
            file_id = response.json()["id"]
            assert response.json()["latest_run"] is None
            runs_path = f"/imports/{file_id}/runs"
            assert (await client.post(runs_path, headers=owner)).status_code == 409
            configs = []
            for name, data in [("Организации", TEXT), ("Суммы", AMOUNT)]:
                saved = await client.put(
                    config_path, headers=owner, json={"name": name, "config_data": data}
                )
                assert saved.status_code == 200, saved.text
                configs.append(saved.json())
            listing = await client.get(f"/suppliers/{supplier_id}/configs", headers=owner)
            assert [item["id"] for item in listing.json()] == [
                item["id"] for item in reversed(configs)
            ]
            assert (
                await client.get(f"/suppliers/{supplier_id}/configs", headers=other)
            ).status_code == 404
            assert (await client.get(runs_path)).status_code == 401
            assert (await client.get(runs_path, headers=other)).status_code == 404
            runs = []
            for config in configs:
                response = await client.post(
                    runs_path, headers=owner, json={"config_id": config["id"]}
                )
                assert response.status_code == 201, response.text
                run = response.json()
                assert run["status"] == "completed"
                assert run["config_data"] == config["config_data"]
                assert run["config_name"] == config["name"]
                assert run["attempt_count"] == 1
                assert run["started_at"] <= run["finished_at"]
                assert "result_key" not in run["processing_result"]
                runs.append(run)
            assert runs[0]["id"] != runs[1]["id"]
            assert len((await client.get(runs_path, headers=owner)).json()) == 2
            latest = (await client.get(f"/imports/{file_id}", headers=owner)).json()
            assert latest["latest_run"]["id"] == runs[-1]["id"]
            assert (
                await client.post(f"/imports/{file_id}/process", headers=owner)
            ).json() == latest
            for run, expected in zip(
                runs, [{"организация": "ООО Тест"}, {"стоимость": "-12.50"}], strict=True
            ):
                path = f"{runs_path}/{run['id']}"
                assert (await client.get(path, headers=other)).status_code == 404
                assert (await client.get(path, headers=owner)).json() == run
                result = await client.get(
                    f"/imports/{file_id}/download?kind=result&run_id={run['id']}", headers=owner
                )
                assert list(csv.DictReader(io.StringIO(result.content.decode("utf-8-sig")))) == [
                    expected
                ]
            # Same owner, different supplier: configuration IDs still cannot cross supplier boundaries.
            another_id = await create_supplier(client, owner)
            wrong = await client.put(
                f"/suppliers/{another_id}/config", headers=owner, json={"config_data": TEXT}
            )
            assert (
                await client.post(runs_path, headers=owner, json={"config_id": wrong.json()["id"]})
            ).status_code == 404
            assert (
                await client.post(runs_path, headers=other, json={"config_id": configs[0]["id"]})
            ).status_code == 404
            assert (
                await client.get(
                    f"/imports/{file_id}/download?kind=result&run_id={uuid4()}", headers=owner
                )
            ).status_code == 404
            # Deleting saved configurations must not remove run snapshots or output artifacts.
            assert (await client.delete(config_path, headers=owner)).json() is True
            for run in runs:
                record = (await client.get(f"{runs_path}/{run['id']}", headers=owner)).json()
                assert record["config_id"] is None
                assert record["config_data"] == run["config_data"]
                assert (
                    await client.get(
                        f"/imports/{file_id}/download?kind=result&run_id={run['id']}", headers=owner
                    )
                ).status_code == 200
            assert len(storage.files) == 5

    asyncio.run(scenario())


def test_snapshot_is_taken_before_execution_and_survives_config_deletion(
    database_url, monkeypatch, signing_key
):
    async def scenario():
        storage = FileStorage()
        monkeypatch.setattr(files, "get_storage", lambda: storage)
        async with authenticated_client(database_url, monkeypatch, signing_key) as (
            client,
            ids,
            authorization,
        ):
            monkeypatch.setattr(files, "get_session", suppliers.get_session)
            owner = authorization(ids["owner"])
            supplier_id = await create_supplier(client, owner)
            config_path = f"/suppliers/{supplier_id}/config"
            saved = (
                await client.put(
                    config_path, headers=owner, json={"name": "Исходный", "config_data": TEXT}
                )
            ).json()
            uploaded = await client.post(
                "/imports",
                headers=owner,
                data={"supplier_id": supplier_id},
                files={"file": ("feed.csv", CONTENT, "text/csv")},
            )
            file_id = UUID(uploaded.json()["id"])
            _, run, _ = await create_import_run(
                file_id,
                user_id=ids["owner"],
                config_id=saved["id"],
                session_factory=files.get_session,
            )
            assert run.status == "queued" and run.attempt_count == 0
            await client.delete(config_path, headers=owner)
            result = await execute_import_run(
                run.id,
                file_id=file_id,
                user_id=ids["owner"],
                storage=storage,
                session_factory=files.get_session,
            )
            assert result.status == "completed"
            assert result.config_data == saved["config_data"]
            assert result.config_id is None
            before = dict(storage.files)
            assert (
                await execute_import_run(
                    run.id,
                    file_id=file_id,
                    user_id=ids["owner"],
                    storage=storage,
                    session_factory=files.get_session,
                )
                == result
            )
            assert storage.files == before

    asyncio.run(scenario())


def test_database_enforces_active_run_uniqueness_status_and_counter(database_url):
    async def scenario():
        async with isolated_sessions(database_url) as sessions:
            async with sessions() as session, session.begin():
                user = User(username="runs", email="runs@example.com", password_hash="unused")
                session.add(user)
                await session.flush()
                supplier = Supplier(user_id=user.id, name="Runs", contact_email="s@example.com")
                session.add(supplier)
                await session.flush()
                source = SourceFile(
                    supplier_id=supplier.id, filename="a.csv", object_key="raw/constraints"
                )
                session.add(source)
                await session.flush()
                file_id = source.id
                session.add(ImportRun(source_file_id=file_id, config_name="Test", config_data=TEXT))
            for changes in [
                {},
                {"status": "unknown"},
                {"status": "completed", "attempt_count": -1},
            ]:
                with pytest.raises(IntegrityError):
                    async with sessions() as session, session.begin():
                        session.add(
                            ImportRun(
                                source_file_id=file_id,
                                config_name="Test",
                                config_data=TEXT,
                                **changes,
                            )
                        )
                        await session.flush()
            async with sessions() as session, session.begin():
                run = await session.scalar(
                    select(ImportRun).where(ImportRun.source_file_id == file_id)
                )
                run.status = "completed"
            async with sessions() as session, session.begin():
                session.add(ImportRun(source_file_id=file_id, config_name="Test", config_data=TEXT))
            with pytest.raises(IntegrityError):
                async with sessions() as session, session.begin():
                    await session.delete(await session.get(SourceFile, file_id))
                    await session.flush()

    asyncio.run(scenario())
