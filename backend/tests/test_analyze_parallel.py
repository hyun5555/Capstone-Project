import asyncio
import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret")

from app.api.endpoints.analyze import analyze_property
from app.schemas.analyze import AnalyzeRequest


class AnalyzeParallelTest(unittest.TestCase):
    def test_independent_work_overlaps_in_both_phases(self):
        first_phase = threading.Barrier(3, timeout=2)
        second_phase = threading.Barrier(2, timeout=2)
        document = SimpleNamespace(usage="다세대주택", area_exclusive=84.9)
        docs = SimpleNamespace(registry=document, building=document, source="sample", notes=[])
        market = SimpleNamespace(value_won=500_000_000, source="provided", note="", to_dict=lambda: {})
        comparison = {"소유자명": {"status": "일치"}}
        explained = {
            "소유자명": {"explanation": "일치", "source": "llm", "grounded": True, "evidence": []},
            "권리사항": {"explanation": "없음", "source": "llm", "grounded": True, "evidence": []},
        }
        risk = {"score": 0.0, "grade": "안전", "reasons": [], "factors": [], "skipped": [],
                "incomplete": False, "ratios": {}}

        def compare(*_):
            first_phase.wait()
            return comparison

        def evidence(*_):
            first_phase.wait()
            return "case", {}, ""

        async def price(*_):
            await asyncio.to_thread(first_phase.wait)
            return market

        def explain(*_):
            second_phase.wait()
            return explained

        def score(*_):
            second_phase.wait()
            return risk

        with patch.multiple(
            "app.api.endpoints.analyze",
            load_sample_documents=lambda *_: docs,
            _compare=compare,
            _collect_evidence=evidence,
            resolve_market_price=price,
            build_findings=lambda *_: {},
            explain_with_evidence=explain,
            calculate_risk_score=score,
            unverified_fields=lambda *_: [],
        ):
            result = asyncio.run(analyze_property(AnalyzeRequest(
                address="합성 주소", deposit=300_000_000, marketPrice=500_000_000, scenario="safe"
            )))

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["risk_grade"], "안전")


if __name__ == "__main__":
    unittest.main()
