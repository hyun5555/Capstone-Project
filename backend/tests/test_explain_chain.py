"""
LangChain 체인, 리트리버, 사용량 콜백 테스트. 외부 API 없이 가짜 채팅 모델과 가짜 컬렉션으로 돌린다.
langchain-core 가 없는 환경에서는 건너뛴다. (requirements.txt 에 있으므로 개발 환경과 Docker 에서는 실행된다)
"""
import importlib.util
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret")

from app.services.chunk_store import ChunkStore, select_balanced
from app.services.chunker import case_id_for
from app.services.codef_normalizer import normalize_building_response, normalize_registry_response
from app.services.document_compare import build_findings, compare_documents
from app.services.evidence import FIELD_QUERIES, FIELD_TOP_K, collect_evidence, retrieve_evidence
from evaluation.fake_store import FakeCollection

HAS_LANGCHAIN = importlib.util.find_spec("langchain_core") is not None
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def docs():
    load = lambda n: json.loads((FIXTURES / n).read_text(encoding="utf-8"))["data"]
    return (normalize_registry_response(load("registry_response.json"), "서울특별시 강남구 테스트로 100"),
            normalize_building_response(load("building_response.json"), "서울특별시 강남구 테스트로 100"))


def hit(cid, doc_type, distance):
    return {"id": cid, "text": cid, "metadata": {"doc_type": doc_type}, "distance": distance}


class SelectBalancedTest(unittest.TestCase):
    def test_takes_best_of_each_document_first(self):
        hits = [hit("r1", "registry", .1), hit("r2", "registry", .2), hit("r3", "registry", .3), hit("b1", "building", .5)]
        self.assertEqual([h["id"] for h in select_balanced(hits, 2)], ["r1", "b1"])
        self.assertEqual([h["id"] for h in select_balanced(hits, 3)], ["r1", "r2", "b1"])   # 나머지 자리는 가까운 순, 결과는 거리순

    def test_single_document_or_k_one_or_empty(self):
        hits = [hit("r1", "registry", .1), hit("r2", "registry", .2)]
        self.assertEqual([h["id"] for h in select_balanced(hits, 2)], ["r1", "r2"])
        self.assertEqual([h["id"] for h in select_balanced(hits + [hit("b", "building", .9)], 1)], ["r1"])
        self.assertEqual(select_balanced([], 3), [])
        self.assertEqual(select_balanced(hits, 0), [])

    def test_never_returns_more_than_k_or_duplicates(self):
        hits = [hit(f"r{i}", "registry", i / 10) for i in range(5)] + [hit(f"b{i}", "building", .5 + i / 10) for i in range(5)]
        for k in range(1, 8):
            ids = [h["id"] for h in select_balanced(hits, k)]
            self.assertEqual(len(ids), min(k, len(hits)))
            self.assertEqual(len(ids), len(set(ids)))


@unittest.skipUnless(HAS_LANGCHAIN, "langchain-core 가 필요합니다")
class RetrieverTest(unittest.TestCase):
    def setUp(self):
        self.reg, self.bld = docs()
        self.store = ChunkStore(FakeCollection())
        self.case_id, _ = collect_evidence(self.store, self.reg, self.bld, 600, 100, 3)

    def test_returns_documents_with_metadata_from_this_case_only(self):
        from app.services.lc_retriever import CaseChunkRetriever
        other_reg, other_bld = docs()
        other_reg.address = "다른 주소"
        other_id = case_id_for(other_reg, other_bld)
        self.store.upsert([c for c in __import__("app.services.chunker", fromlist=["x"]).chunk_document(other_reg, other_id, 600, 100)])
        r = CaseChunkRetriever(store=self.store, case_id=self.case_id, top_k=3)
        result = r.invoke("소유권이전 소유자")
        self.assertEqual(len(result), 3)
        for d in result:
            self.assertTrue(d.page_content.startswith("["))
            self.assertEqual(d.metadata["case_id"], self.case_id)
            self.assertIn("chunk_id", d.metadata)
            self.assertIn("distance", d.metadata)

    def test_doc_type_filter_and_balanced(self):
        from app.services.lc_retriever import CaseChunkRetriever
        only_reg = CaseChunkRetriever(store=self.store, case_id=self.case_id, top_k=3, doc_type="registry").invoke("건물 용도")
        self.assertTrue(all(d.metadata["doc_type"] == "registry" for d in only_reg))
        balanced = CaseChunkRetriever(store=self.store, case_id=self.case_id, top_k=2, balanced=True).invoke("소유자 소유권이전 근저당")
        self.assertEqual({d.metadata["doc_type"] for d in balanced}, {"registry", "building"})

    def test_retrieve_evidence_strategies(self):
        plain = retrieve_evidence(self.store, self.case_id, 3, "plain")
        balanced = retrieve_evidence(self.store, self.case_id, 3, "balanced")
        self.assertEqual(set(plain), set(FIELD_QUERIES))
        for name in FIELD_QUERIES:
            self.assertLessEqual(len(balanced[name]), 3)
            self.assertTrue({"chunk_id", "doc_type", "section", "rank_no", "text", "distance"} <= set(balanced[name][0]))
        self.assertTrue(all(c["doc_type"] == "registry" for c in balanced["권리사항"]))    # 권리는 등기부에서만 찾는다
        for name in ("소유자명", "건물 용도", "구조 유형"):
            self.assertEqual({c["doc_type"] for c in balanced[name]}, {"registry", "building"}, name)
        with self.assertRaises(ValueError):
            retrieve_evidence(self.store, self.case_id, 3, "nonsense")

    def test_adaptive_uses_a_different_top_k_per_field(self):
        self.assertEqual(set(FIELD_TOP_K), set(FIELD_QUERIES))          # 모든 항목에 K 가 정해져 있다
        adaptive = retrieve_evidence(self.store, self.case_id, 3, "adaptive")
        total = self.store.count(self.case_id)
        for name, k in FIELD_TOP_K.items():
            self.assertLessEqual(len(adaptive[name]), k, name)
        self.assertEqual(len(adaptive["전용면적"]), 1)
        self.assertEqual(len(adaptive["소유자명"]), 2)
        self.assertEqual(len(adaptive["건물 용도"]), min(5, total))
        self.assertTrue(all(c["doc_type"] == "registry" for c in adaptive["권리사항"]))
        for name in ("소유자명", "건물 용도"):     # balanced 처럼 두 문서를 모두 포함한다
            self.assertEqual({c["doc_type"] for c in adaptive[name]}, {"registry", "building"}, name)
        # top_k 인자는 표에 없는 항목에만 쓰이므로, 바꿔도 결과가 같다
        self.assertEqual(adaptive, retrieve_evidence(self.store, self.case_id, 1, "adaptive"))


@unittest.skipUnless(HAS_LANGCHAIN, "langchain-core 가 필요합니다")
class ExplainChainTest(unittest.TestCase):
    PAYLOAD = ("[항목] 소유자명\n판정: 일치\n값: 등기부='가*일' / 건축물대장='가*일'\n근거 청크:\n<E1 출처=등기부/갑구>\n소유권이전\n</E1>\n"
               "<E2 출처=건축물대장/소유자현황>\n소유자\n</E2>\n\n[항목] 권리사항\n판정: 서버 집계\n값: 없음\n근거 청크:\n"
               "<E3 출처=등기부/을구>\n근저당\n</E3>")

    def call(self, version, llm, **kw):
        from app.services.explain_chain import make_llm_call
        return make_llm_call(version, llm=llm, **kw)(self.PAYLOAD)

    def test_v2_prompt_separates_role_examples_and_data(self):
        from app.services.explain_chain import _prompt_v2
        messages = _prompt_v2().format_messages(payload="PAYLOAD_TEXT", fields="소유자명")
        self.assertEqual([type(m).__name__ for m in messages], ["SystemMessage", "HumanMessage", "AIMessage", "HumanMessage"])
        self.assertIn("판정 고정", messages[0].content)
        self.assertNotIn("{format_instructions}", messages[0].content)
        self.assertIn('"items"', messages[0].content)
        json.loads(messages[2].content)                                   # few-shot 정답은 유효한 JSON 이다
        self.assertIn("PAYLOAD_TEXT", messages[3].content)
        self.assertNotIn("PAYLOAD_TEXT", messages[0].content)             # 자료는 system 이 아니라 human 에만 들어간다

    def test_few_shot_answer_follows_the_declared_schema(self):
        from app.services.explain_chain import _EXAMPLE_ANSWER, _EXAMPLE_PAYLOAD, normalize_explanations, requested_fields
        fields = requested_fields(_EXAMPLE_PAYLOAD)
        normalized = normalize_explanations(_EXAMPLE_ANSWER, fields)
        self.assertEqual(set(normalized), set(fields))
        for value in normalized.values():
            self.assertTrue(value["evidence_ids"])

    def test_normalize_drops_bad_items_and_keeps_good_ones(self):
        from langchain_core.exceptions import OutputParserException
        from app.services.explain_chain import normalize_explanations
        parsed = {"items": [
            {"field": "소유자명", "explanation": " 같습니다. ", "evidence_ids": ["E1", "E1x", 3, "e2", "E2"]},
            {"field": "소유자명", "explanation": "중복", "evidence_ids": []},           # 같은 항목은 첫 번째만
            {"field": "없는항목", "explanation": "x", "evidence_ids": []},               # 요청하지 않은 항목
            {"field": "권리사항", "explanation": "  ", "evidence_ids": []},               # 빈 설명
            "not a dict",
        ]}
        self.assertEqual(normalize_explanations(parsed, ["소유자명", "권리사항"]),
                         {"소유자명": {"explanation": "같습니다.", "evidence_ids": ["E1", "E2"]}})
        for bad in ({}, {"items": "x"}, {"items": []}, [], "text", {"items": [{"field": "x"}]}):
            with self.assertRaises(OutputParserException):
                normalize_explanations(bad, ["소유자명"])

    def test_v2_recovers_from_one_malformed_answer_with_retry(self):
        from evaluation.fakes import FakeChatModel
        from app.services.llm_usage import UsageRecorder
        rec = UsageRecorder()
        result = self.call("v2", FakeChatModel(fail_first=1), callbacks=[rec])
        self.assertEqual(set(result), {"소유자명", "권리사항"})
        self.assertEqual(result["소유자명"]["evidence_ids"], ["E1", "E2"])
        self.assertEqual(rec.summary()["calls"], 2)                            # 첫 호출 실패 + 재시도

    def test_v2_gives_up_after_max_attempts(self):
        from langchain_core.exceptions import OutputParserException
        from evaluation.fakes import FakeChatModel
        with self.assertRaises(OutputParserException):
            self.call("v2", FakeChatModel(fail_first=2))
        llm = FakeChatModel(fail_first=1)
        with self.assertRaises(OutputParserException):
            self.call("v2", llm, max_attempts=1)
        self.assertEqual(llm.calls_made, 1)

    def test_v1_is_the_plain_baseline_without_retry_or_validation(self):
        from evaluation.fakes import FakeChatModel
        result = self.call("v1", FakeChatModel())
        self.assertEqual(set(result), {"소유자명", "권리사항"})                # 항목명이 키인 예전 형식
        with self.assertRaises(Exception):
            self.call("v1", FakeChatModel(fail_first=1))                        # 재시도 없이 바로 실패

    def test_unknown_version_and_missing_key(self):
        from app.services.explain_chain import build_explain_chain, get_llm
        with self.assertRaises(ValueError):
            build_explain_chain("v9", object())
        with patch("app.config.OPENAI_API_KEY", ""), self.assertRaises(RuntimeError):
            get_llm()

    def test_plugs_into_rag_explain_and_marks_answers_as_llm(self):
        from evaluation.fakes import FakeChatModel
        from app.services.explain_chain import make_llm_call
        from app.services.rag_explain import explain_with_evidence
        reg, bld = docs()
        comparison = compare_documents(reg, bld)
        findings = build_findings(reg, bld, comparison)
        store = ChunkStore(FakeCollection())
        _, evidence = collect_evidence(store, reg, bld, 600, 100, 3, "balanced")
        out = explain_with_evidence(comparison, evidence, findings, make_llm_call("v2", llm=FakeChatModel()))
        self.assertEqual(out["소유자명"]["source"], "llm")
        self.assertTrue(out["소유자명"]["grounded"])
        self.assertTrue(all(c["chunk_id"].startswith("chunk-") for c in out["소유자명"]["evidence"]))
        broken = explain_with_evidence(comparison, evidence, findings, make_llm_call("v2", llm=FakeChatModel(fail_first=5)))
        self.assertEqual(broken["소유자명"]["source"], "default")              # 형식이 계속 틀리면 기본 문장


@unittest.skipUnless(HAS_LANGCHAIN, "langchain-core 가 필요합니다")
class UsageRecorderTest(unittest.TestCase):
    def test_records_tokens_calls_and_latency(self):
        from evaluation.fakes import FakeChatModel
        from app.services.llm_usage import UsageRecorder
        rec = UsageRecorder()
        FakeChatModel().invoke("안녕", config={"callbacks": [rec]})
        s = rec.summary()
        self.assertEqual((s["calls"], s["errors"], s["missing_usage"]), (1, 0, 0))
        self.assertGreater(s["prompt_tokens"], 0)
        self.assertGreater(s["completion_tokens"], 0)
        rec.reset()
        self.assertEqual(rec.summary()["calls"], 0)

    def test_usage_from_message_metadata_and_missing_usage(self):
        from app.services.llm_usage import _usage_from_result
        gen = SimpleNamespace(message=SimpleNamespace(usage_metadata={"input_tokens": 10, "output_tokens": 4}))
        self.assertEqual(_usage_from_result(SimpleNamespace(llm_output=None, generations=[[gen]])),
                         {"prompt_tokens": 10, "completion_tokens": 4})
        self.assertEqual(_usage_from_result(SimpleNamespace(llm_output={"token_usage": {"prompt_tokens": 7, "completion_tokens": 2}}, generations=[])),
                         {"prompt_tokens": 7, "completion_tokens": 2})
        self.assertIsNone(_usage_from_result(SimpleNamespace(llm_output={}, generations=[])))

    def test_error_is_counted(self):
        from app.services.llm_usage import UsageRecorder
        rec = UsageRecorder()
        rec.on_llm_start({}, ["x"], run_id="r1")
        rec.on_llm_error(RuntimeError("boom"), run_id="r1")
        self.assertEqual((rec.summary()["calls"], rec.summary()["errors"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
