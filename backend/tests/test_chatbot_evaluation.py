import os
import tempfile
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long")

from app.services.chunk_store import ChunkStore
from evaluation.chatbot import OUT_OF_SCOPE, SCENARIOS, _fake_llm, run_suite
from evaluation.fake_store import FakeCollection


class ChatbotEvaluationTest(unittest.TestCase):
    def test_dry_suite_measures_all_17_questions(self):
        corpus = os.path.join(os.path.dirname(__file__), "..", "legal_data", "legal_sources.json")
        suite = run_suite(ChunkStore(FakeCollection()), _fake_llm(), "dry", corpus, 600, 100, 3)
        self.assertEqual(len(suite["records"]), len(SCENARIOS) + len(OUT_OF_SCOPE))
        self.assertEqual(suite["metrics"]["out_of_scope_refusal_rate"], 1.0)
        self.assertEqual(suite["metrics"]["wrong_citation_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
