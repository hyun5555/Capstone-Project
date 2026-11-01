import asyncio
import json
import os
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long")

from app.api.endpoints.analyze import (
    AnalysisCorrections, _job_response, _store_completed_job, correct_analysis_history,
)
from app.models.analysis_cases import AnalysisJob, VectorDeletion
from app.services.analysis_cleanup import cleanup_queued_cases


class _Scalars:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value[0] if isinstance(self.value, list) and self.value else self.value

    def all(self):
        if self.value is None:
            return []
        return self.value if isinstance(self.value, list) else [self.value]


class _Result:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return _Scalars(self.value)


class _Db:
    def __init__(self, value):
        self.value = value
        self.commits = 0
        self.added = []
        self.deleted = []
        self.merged = []

    async def execute(self, _statement):
        return _Result(self.value)

    async def commit(self):
        self.commits += 1

    def add(self, value):
        self.added.append(value)

    async def merge(self, value):
        self.merged.append(value)

    async def delete(self, value):
        self.deleted.append(value)


class _SequenceDb(_Db):
    def __init__(self, values):
        super().__init__(None)
        self.values = list(values)

    async def execute(self, _statement):
        return _Result(self.values.pop(0))


def _job():
    job = AnalysisJob(job_id="job-1", user_id="user-1", status="succeeded", stage="분석 완료", case_id="case-1")
    job.created_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    job.result = {"success": True, "data": {
        "address": "서울 테스트",
        "risk_score": 0,
        "risk_grade": "안전",
        "risk_rule_version": "old",
        "market_price": {"value_won": 500_000_000},
        "notes": [],
        "review_fields": {
            "registry_owner": "이*대",
            "building_owner": "이*대",
            "owner_mismatch": False,
            "active_rights": [],
            "max_claim_amount": 0,
            "building_violation": False,
            "building_usage": "주거용",
            "deposit": 300_000_000,
            "market_price": 500_000_000,
        },
    }}
    return job


class AnalysisHistoryTest(unittest.TestCase):
    def test_history_reports_vector_retention_status(self):
        job = _job()
        self.assertEqual(_job_response(job)["vector_status"], "retained")
        job.created_at = datetime.utcnow() - timedelta(days=365)
        self.assertEqual(_job_response(job)["vector_status"], "expired")

    def test_completed_job_stores_its_public_job_id_in_result(self):
        db = _Db(None)
        result = {"success": True, "data": {"case_id": "case-1"}}
        job_id = asyncio.run(_store_completed_job(db, "user-1", result))
        self.assertEqual(result["data"]["job_id"], job_id)
        self.assertEqual(db.added[0].result["data"]["job_id"], job_id)

    def test_correction_masks_names_and_recalculates_codes(self):
        job = _job()
        result = asyncio.run(correct_analysis_history(
            job.job_id,
            AnalysisCorrections(
                registry_owner="홍길동",
                building_owner="김철수",
                active_rights=["압류"],
                max_claim_amount=100_000_000,
                deposit=300_000_000,
                market_price=500_000_000,
            ),
            db=_Db(job),
            current_user=SimpleNamespace(user_id="user-1"),
        ))
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("홍길동", encoded)
        self.assertNotIn("김철수", encoded)
        self.assertEqual(result["data"]["review_fields"]["registry_owner"], "홍*동")
        detected = {item["code"] for item in result["data"]["risk_codes"] if item["status"] == "detected"}
        self.assertIn("OWNER_MISMATCH", detected)
        self.assertIn("REGISTRY_SEIZURE", detected)

    def test_unknown_right_is_rejected(self):
        with self.assertRaises(ValidationError):
            AnalysisCorrections(active_rights=["범죄이력"])

    def test_vector_case_is_deleted_only_without_retained_reference(self):
        calls = []
        first = VectorDeletion(case_id="case-1")
        second = VectorDeletion(case_id="case-2")
        with patch("app.services.analysis_cleanup._delete_case", side_effect=calls.append):
            deleted = asyncio.run(cleanup_queued_cases(_SequenceDb([[first], None])))
            retained = asyncio.run(cleanup_queued_cases(_SequenceDb([[second], "job-2"])))
        self.assertEqual(deleted, ["case-1"])
        self.assertEqual(retained, [])
        self.assertEqual(calls, ["case-1"])


if __name__ == "__main__":
    unittest.main()
