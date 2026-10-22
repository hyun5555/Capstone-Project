import asyncio
import io
import os
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pymupdf
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from app.api.endpoints import analyze as analyze_api
from app.api.endpoints.analyze import create_pdf_job
from app.api.endpoints.property import PropertyCreate, create_property
from app.api.endpoints.users import UserUpdate, delete_user, update_user
from app.middleware.body_limit import BodySizeLimitMiddleware
from app.services.auth import create_access_token, get_current_user
from app.services.pdf_extractor import PdfTooLarge, extract_pdf
from app.services.rate_limit import _RateLimiter


class _Scalars:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class _Result:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return _Scalars(self.value)


class _Db:
    def __init__(self, value=None):
        self.value = value
        self.added = []
        self.deleted = []
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _Result(self.value)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        pass

    async def refresh(self, _value):
        pass

    async def delete(self, value):
        self.deleted.append(value)


class SecurityControlsTest(unittest.TestCase):
    def test_jwt_signature_expiry_and_user_lookup_are_enforced(self):
        user = SimpleNamespace(user_id="user-1")
        token = create_access_token({"sub": user.user_id})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        self.assertIs(asyncio.run(get_current_user(credentials=credentials, db=_Db(user))), user)

        expired = create_access_token({"sub": user.user_id}, timedelta(seconds=-1))
        with self.assertRaises(HTTPException) as error:
            asyncio.run(get_current_user(
                credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired), db=_Db(user)
            ))
        self.assertEqual(error.exception.status_code, 401)

    def test_user_cannot_update_another_account(self):
        user = SimpleNamespace(user_id="user-1", phone="010-0000-0000")
        with self.assertRaises(HTTPException) as error:
            asyncio.run(update_user(
                "user-2", UserUpdate(phone="010-1111-1111"), db=_Db(), current_user=user
            ))
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(user.phone, "010-0000-0000")

    def test_account_delete_removes_owned_rows_before_user(self):
        user = SimpleNamespace(user_id="user-1")
        db = _Db()
        result = asyncio.run(delete_user(user.user_id, db=db, current_user=user))
        self.assertEqual(result, {"detail": "User deleted"})
        self.assertEqual(len(db.statements), 2)
        self.assertEqual(db.deleted, [user])

    def test_property_and_pdf_job_are_owned_by_current_user(self):
        user = SimpleNamespace(user_id="user-1")
        property_db = _Db()
        prop = asyncio.run(create_property(
            PropertyCreate(address="서울특별시 강남구 테스트로 100"), db=property_db, current_user=user
        ))
        self.assertEqual(prop.owner_id, user.user_id)

        job_db = _Db()
        background = BackgroundTasks()
        result = asyncio.run(create_pdf_job(
            background,
            UploadFile(file=io.BytesIO(b"%PDF-1.4\n"), filename="registry.pdf"),
            UploadFile(file=io.BytesIO(b"%PDF-1.4\n"), filename="building.pdf"),
            "서울특별시 강남구 테스트로 100",
            300_000_000,
            None,
            db=job_db,
            current_user=user,
        ))
        self.assertEqual(job_db.added[0].user_id, user.user_id)
        self.assertEqual(result["status"], "queued")
        self.assertEqual(len(background.tasks), 1)

    def test_rate_limit_and_request_body_limit(self):
        limiter = _RateLimiter(2)
        limiter.check("user-1")
        limiter.check("user-1")
        with self.assertRaises(HTTPException) as error:
            limiter.check("user-1")
        self.assertEqual(error.exception.status_code, 429)

        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_bytes=5)

        @app.post("/")
        async def read_body(request: Request):
            return {"size": len(await request.body())}

        response = TestClient(app).post("/", content=b"123456")
        self.assertEqual(response.status_code, 413)

    def test_oversized_pdf_page_is_rejected_before_ocr(self):
        document = pymupdf.open()
        document.new_page(width=5000, height=5000)
        data = document.tobytes()
        document.close()
        with self.assertRaises(PdfTooLarge):
            extract_pdf(data)

    def test_timed_out_ocr_keeps_its_concurrency_slot_until_worker_exits(self):
        async def run():
            release_worker = asyncio.Event()
            slots = asyncio.Semaphore(1)

            async def slow_worker(*_args):
                await release_worker.wait()
                return object()

            with patch.object(analyze_api, "_pdf_slots", slots), \
                 patch.object(analyze_api, "PDF_ANALYSIS_TIMEOUT_SEC", 0.01), \
                 patch.object(analyze_api, "run_in_threadpool", slow_worker):
                with self.assertRaises(asyncio.TimeoutError):
                    await analyze_api._load_pdf_documents_with_limits(b"a", b"b", "서울")
                self.assertTrue(slots.locked())
                release_worker.set()
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                self.assertFalse(slots.locked())

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
