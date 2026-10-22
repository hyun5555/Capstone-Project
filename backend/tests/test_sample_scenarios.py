import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long")

from app.schemas.analyze import AnalyzeRequest
from app.services.document_compare import build_findings, compare_documents, unverified_fields
from app.services.document_source import SampleDataMissing, load_sample_documents
from app.services.risk_score import calculate_risk_score


SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
SCENARIOS = json.loads((SAMPLE_DIR / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]


class SampleScenarioTest(unittest.TestCase):
    def test_every_scenario_normalizes_and_scores_as_documented(self):
        self.assertEqual(set(SCENARIOS), {
            "safe", "owner_mismatch", "active_seizure", "excessive_mortgage",
            "cancelled_rights", "violation_nonresidential", "lease_rights",
        })

        for name, item in SCENARIOS.items():
            with self.subTest(name=name), patch("app.services.risk_score.check_defaulter", return_value=False):
                docs = load_sample_documents("합성 테스트 주소", str(SAMPLE_DIR), name)
                comparison = compare_documents(docs.registry, docs.building)
                request, expected = item["request"], item["expected"]
                risk = calculate_risk_score(
                    build_findings(docs.registry, docs.building, comparison),
                    {"보증금": request["deposit"], "시세": request["marketPrice"]},
                )

                self.assertEqual(unverified_fields(comparison), [])
                self.assertEqual(comparison["소유자명"]["status"], expected["owner_status"])
                self.assertEqual(sorted(r.type for r in docs.registry.active_rights), expected["active_rights"])
                self.assertEqual(risk["score"], expected["risk_score"])
                self.assertEqual(risk["grade"], expected["risk_grade"])
                self.assertIn(name, docs.notes[0])

    def test_unknown_scenario_is_rejected(self):
        with self.assertRaises(SampleDataMissing):
            load_sample_documents("합성 테스트 주소", str(SAMPLE_DIR), "missing")

        with self.assertRaises(ValidationError):
            AnalyzeRequest(address="x", deposit=1, marketPrice=1, scenario="../secrets")


if __name__ == "__main__":
    unittest.main()
