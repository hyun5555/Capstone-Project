import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret")

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.api.endpoints.chatbot import ChatRequest, chatbot_response
from app.services.chunk_store import ChunkStore
from app.services.legal_rag import DISCLAIMER, answer_legal_question, index_legal_corpus, load_legal_chunks
from evaluation.fake_store import FakeCollection


def corpus_file(directory: str) -> str:
    path = Path(directory) / "legal.json"
    path.write_text(json.dumps({
        "documents": [{
            "id": "law-1",
            "title": "대항력 안내",
            "publisher": "공식기관",
            "url": "https://example.test/law-1",
            "effective_date": "2026-01-02",
            "text": "주택 인도와 전입신고를 마치면 대항력 요건을 갖출 수 있습니다.",
        }]
    }, ensure_ascii=False), encoding="utf-8")
    return str(path)


class LegalRagTest(unittest.TestCase):
    def test_chunks_are_deterministic_and_keep_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            path = corpus_file(directory)
            case_a, chunks_a = load_legal_chunks(path, 600, 100)
            case_b, chunks_b = load_legal_chunks(path, 600, 100)
            self.assertEqual(case_a, case_b)
            self.assertEqual([c.id for c in chunks_a], [c.id for c in chunks_b])
            self.assertEqual(chunks_a[0].metadata["url"], "https://example.test/law-1")
            self.assertEqual(chunks_a[0].metadata["doc_type"], "legal")

    def test_index_is_idempotent_and_answer_has_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            path = corpus_file(directory)
            store = ChunkStore(FakeCollection())
            case_id = index_legal_corpus(store, path, 600, 100)
            self.assertEqual(store.count(case_id), 1)
            index_legal_corpus(store, path, 600, 100)
            self.assertEqual(store.count(case_id), 1)

            fake_llm = RunnableLambda(lambda _: AIMessage(content="전입신고를 확인하세요. [1]"))
            result = answer_legal_question(
                "대항력이 뭐예요?", store=store, llm=fake_llm, corpus_path=path,
                chunk_size=600, chunk_overlap=100, top_k=1,
            )
            self.assertEqual(result["mode"], "rag")
            self.assertIn(DISCLAIMER, result["answer"])
            self.assertEqual(result["sources"][0]["title"], "대항력 안내")


class ChatbotFallbackTest(unittest.TestCase):
    def test_rag_failure_does_not_use_database_keyword(self):
        with patch("app.api.endpoints.chatbot.answer_legal_question", side_effect=RuntimeError("offline")):
            result = asyncio.run(chatbot_response(ChatRequest(message="대항력이 뭐예요?")))
        self.assertEqual(result["mode"], "unavailable")
        self.assertEqual(result["sources"], [])


if __name__ == "__main__":
    unittest.main()
