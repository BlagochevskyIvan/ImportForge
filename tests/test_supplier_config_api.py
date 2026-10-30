import asyncio

import pytest

from tests.test_supplier_api import authenticated_client
from tests.test_supplier_api import signing_key as signing_key

pytestmark = pytest.mark.integration
CONFIG = {
    "delimiter": ";",
    "encoding": "cp1251",
    "column_mapping": {"Код": "sku", "Товар": "name", "Цена": "price"},
}


def test_config_save_replace_and_ownership(database_url, monkeypatch, signing_key):
    async def scenario():
        async with authenticated_client(database_url, monkeypatch, signing_key) as context:
            client, ids, authorization = context
            owner = authorization(ids["owner"])
            other = authorization(ids["other"])
            supplier = await client.post(
                "/suppliers",
                json={"name": "CSV Supplier", "contact_email": "s@example.com"},
                headers=owner,
            )
            path = f"/suppliers/{supplier.json()['id']}/config"
            empty = await client.get(path, headers=owner)
            assert empty.status_code == 200 and empty.json() is None
            for headers in [{}, other]:
                expected = 401 if not headers else 404
                assert (await client.get(path, headers=headers)).status_code == expected
                assert (
                    await client.put(path, headers=headers, json={"config_data": CONFIG})
                ).status_code == expected
            saved = await client.put(path, headers=owner, json={"config_data": CONFIG})
            assert saved.status_code == 200, saved.text
            assert saved.json()["config_data"] == CONFIG
            assert saved.json()["supplier_id"] == supplier.json()["id"]
            # A saved configuration is no more accessible to another account.
            assert (await client.get(path, headers=other)).status_code == 404
            assert (
                await client.put(path, headers=other, json={"config_data": CONFIG})
            ).status_code == 404
            changed = {**CONFIG, "encoding": "utf-8"}
            replaced = await client.put(path, headers=owner, json={"config_data": changed})
            assert replaced.status_code == 200
            assert replaced.json()["id"] == saved.json()["id"]
            assert (await client.get(path, headers=owner)).json()["config_data"] == changed
            for config in [
                {**CONFIG, "column_mapping": {"a": "sku", "b": "sku", "c": "price"}},
                {**CONFIG, "delimiter": "\n"},
                {**CONFIG, "encoding": "utf-16"},
                {**CONFIG, "extra": True},
                {**CONFIG, "delimiter": None},
                {**CONFIG, "encoding": None},
                {**CONFIG, "column_mapping": {"A": "sku", " A ": "name", "C": "price"}},
            ]:
                assert (
                    await client.put(path, headers=owner, json={"config_data": config})
                ).status_code == 422
            assert (await client.get(path, headers=owner)).json()["config_data"] == changed
            assert (
                await client.put(
                    "/suppliers/-1/config", headers=owner, json={"config_data": CONFIG}
                )
            ).status_code == 404
            assert (await client.get("/suppliers/-1/config", headers=owner)).status_code == 404
            # The old duplicated path must not expose a placeholder handler.
            assert (await client.get("/suppliers/suppliers/1/config")).status_code == 404

    asyncio.run(scenario())


def test_config_defaults_and_normalized_roundtrip(database_url, monkeypatch, signing_key):
    async def scenario():
        async with authenticated_client(database_url, monkeypatch, signing_key) as context:
            client, ids, authorization = context
            owner = authorization(ids["owner"])
            supplier = await client.post(
                "/suppliers",
                json={"name": "Defaults", "contact_email": "defaults@example.com"},
                headers=owner,
            )
            path = f"/suppliers/{supplier.json()['id']}/config"
            body = {
                "config_data": {
                    "column_mapping": {" SKU ": "sku", " Name ": "name", " Price ": "price"}
                }
            }
            saved = await client.put(path, headers=owner, json=body)
            assert saved.status_code == 200, saved.text
            assert saved.json()["config_data"] == {
                "delimiter": ",",
                "encoding": "utf-8",
                "column_mapping": {"SKU": "sku", "Name": "name", "Price": "price"},
            }
            assert (await client.get(path, headers=owner)).json() == saved.json()
            # Sending the same full document again must preserve the resource ID.
            again = await client.put(
                path, headers=owner, json={"config_data": saved.json()["config_data"]}
            )
            assert again.status_code == 200
            assert again.json() == saved.json()

    asyncio.run(scenario())
