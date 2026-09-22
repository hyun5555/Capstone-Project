import asyncio
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret")

from app.api.endpoints import property as property_api
from app.api.endpoints import users as users_api
from app.main import app


class _Scalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _Result:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return _Scalars(self.values)


class _AsyncSession:
    def __init__(self, values):
        self.values = values

    async def execute(self, _statement):
        return _Result(self.values)


class AsyncCrudTest(unittest.TestCase):
    def test_list_endpoints_use_async_execute(self):
        user = SimpleNamespace(user_id="u1", email="u@example.com", username="u", phone=None)
        prop = SimpleNamespace(property_id=1, address="서울", detail_address=None,
                               property_value=None, estimated_price=None, risk_summary=None)

        self.assertEqual(asyncio.run(users_api.read_users(db=_AsyncSession([user]))), [user])
        self.assertIsNone(users_api.UserOut.model_validate(user).phone)
        self.assertEqual(asyncio.run(property_api.read_properties(db=_AsyncSession([prop]))), [prop])

    def test_property_route_is_not_double_prefixed(self):
        paths = {route.path for route in app.routes}
        self.assertIn("/property/", paths)
        self.assertNotIn("/property/property/", paths)

    def test_ingest_uses_current_codef_clients(self):
        fixture_dir = Path(__file__).parent / "fixtures"
        building = json.loads((fixture_dir / "building_response.json").read_text(encoding="utf-8"))["data"]
        registry = json.loads((fixture_dir / "registry_response.json").read_text(encoding="utf-8"))["data"]
        building_call = AsyncMock(return_value=building)
        registry_call = AsyncMock(return_value=registry)

        with patch.object(property_api, "get_building_title_info", building_call), \
             patch.object(property_api, "get_registry_info", registry_call), \
             patch.object(property_api, "upsert_property_docs") as upsert:
            result = asyncio.run(property_api.ingest_property(
                address="서울특별시 강남구 테스트로 100",
                road_name="서울특별시 강남구 테스트로",
                main_address_no="100",
                sub_address_no="0",
            ))

        building_call.assert_awaited_once_with("서울특별시 강남구 테스트로", "100", "0")
        registry_call.assert_awaited_once_with("서울특별시 강남구 테스트로 100")
        self.assertEqual(result["ingested"], 2)
        self.assertEqual(upsert.call_count, 1)


if __name__ == "__main__":
    unittest.main()
