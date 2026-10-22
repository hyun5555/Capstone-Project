import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long")

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.api.endpoints.chatbot import ChatRequest, chatbot_response
from app.services.chunk_store import ChunkStore
from app.services.legal_rag import (
    DISCLAIMER, INSUFFICIENT_ANSWER, _retrieve_documents, answer_legal_question, index_legal_corpus, load_legal_chunks,
)
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

    def test_legal_query_hint_is_batched_and_rrf_ranked(self):
        class Store:
            def __init__(self):
                self.queries = None

            def search(self, case_id, queries, n_results=3, doc_type=None):
                self.queries = queries
                common = {"id": "law", "text": "법 조문", "metadata": {"source_id": "law"}, "distance": .2}
                noise = {"id": "noise", "text": "일반 안내", "metadata": {"source_id": "noise"}, "distance": .1}
                return [[noise, common], [common, noise]]

        store = Store()
        docs = _retrieve_documents(store, "legal", "전입신고와 확정일자는 언제 받나요?", 1)
        self.assertEqual(len(store.queries), 2)
        self.assertIn("우선변제권", store.queries[1])
        self.assertEqual([doc.metadata["chunk_id"] for doc in docs], ["law"])

    def test_stage_is_in_context_and_only_cited_sources_are_returned(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(corpus_file(directory))
            data = json.loads(path.read_text(encoding="utf-8"))
            data["documents"].append({
                "id": "law-2", "title": "확정일자 안내", "publisher": "공식기관",
                "url": "https://example.test/law-2", "effective_date": "2026-01-02",
                "text": "확정일자는 우선변제권 요건을 갖추는 데 사용됩니다.",
            })
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            captured = {}

            def respond(value):
                captured["prompt"] = value.to_string()
                return AIMessage(content="확정일자를 확인하세요. [2]")

            result = answer_legal_question(
                "임대차 계약 후 확정일자는 언제 받나요?", stage="계약 후",
                store=ChunkStore(FakeCollection()), llm=RunnableLambda(respond), corpus_path=str(path),
                chunk_size=600, chunk_overlap=100, top_k=2,
            )
            self.assertIn("계약 단계:\n계약 후", captured["prompt"])
            self.assertEqual([source["number"] for source in result["sources"]], [2])

    def test_invalid_or_missing_citation_and_out_of_scope_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = corpus_file(directory)
            store = ChunkStore(FakeCollection())
            for answer in ("근거 번호가 없습니다.", "없는 근거입니다. [9]"):
                result = answer_legal_question(
                    "전입신고가 필요한가요?", store=store,
                    llm=RunnableLambda(lambda _, text=answer: AIMessage(content=text)), corpus_path=path,
                    chunk_size=600, chunk_overlap=100, top_k=1,
                )
                self.assertEqual(result["mode"], "insufficient")
                self.assertEqual(result["sources"], [])
                self.assertIn(INSUFFICIENT_ANSWER, result["answer"])

            out_of_scope = answer_legal_question("오늘 저녁 메뉴를 추천해 주세요.")
            self.assertEqual(out_of_scope["mode"], "insufficient")
            self.assertEqual(out_of_scope["sources"], [])


class ChatbotFallbackTest(unittest.TestCase):
    def test_rag_failure_does_not_use_database_keyword(self):
        with patch("app.api.endpoints.chatbot.answer_legal_question", side_effect=RuntimeError("offline")):
            result = asyncio.run(chatbot_response(ChatRequest(message="대항력이 뭐예요?")))
        self.assertEqual(result["mode"], "unavailable")
        self.assertEqual(result["sources"], [])

    def test_contract_stage_is_forwarded(self):
        expected = {"answer": "ok", "sources": [], "mode": "rag"}
        with patch("app.api.endpoints.chatbot.answer_legal_question", return_value=expected) as mocked:
            result = asyncio.run(chatbot_response(ChatRequest(message="계약서를 확인해 주세요.", stage="계약 중")))
        self.assertEqual(result, expected)
        mocked.assert_called_once_with("계약서를 확인해 주세요.", stage="계약 중")


if __name__ == "__main__":
    unittest.main()
