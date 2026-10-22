"""
청킹 / 청크 저장소 / 근거 검색 테스트 (chromadb·OpenAI 없이 실행).
Chroma 컬렉션은 같은 인터페이스를 가진 가짜 컬렉션으로 대신한다.
"""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long")

from app.services.chunk_store import ChunkStore, case_filter
from app.services.chunker import case_id_for, chunk_document, split_text
from app.services.codef_normalizer import normalize_building_response, normalize_registry_response
from app.services.documents import PropertyDoc, Section
from app.services.evidence import FIELD_QUERIES, collect_evidence
from app.utils.masking import mask_text
from app.api.endpoints.analyze import _collect_evidence

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))["data"]


def docs():
    return normalize_registry_response(load("registry_response.json"), "서울특별시 강남구 테스트로 100"), \
           normalize_building_response(load("building_response.json"), "서울특별시 강남구 테스트로 100")


class FakeCollection:
    """Chroma 컬렉션 흉내: upsert/get/query/delete, where($and 포함), 단어 겹침 기반 거리."""

    def __init__(self):
        self.rows = {}          # id -> (text, metadata)
        self.last_where = None

    def upsert(self, ids, documents, metadatas):
        for i, d, m in zip(ids, documents, metadatas):
            assert all(v is not None for v in m.values()), "Chroma 메타데이터에는 None 을 넣을 수 없다"
            self.rows[i] = (d, m)

    @staticmethod
    def _match(meta, where):
        if "$and" in where:
            return all(FakeCollection._match(meta, w) for w in where["$and"])
        return all(meta.get(k) == v for k, v in where.items())

    def get(self, where=None, include=None):
        return {"ids": [i for i, (_, m) in self.rows.items() if self._match(m, where or {})]}

    def query(self, query_texts, n_results, where=None):
        self.last_where = where
        out = {"ids": [], "documents": [], "metadatas": [], "distances": []}
        for q in query_texts:
            qt = set(q.split())
            scored = []
            for i, (d, m) in self.rows.items():
                if self._match(m, where or {}):
                    scored.append((1 - len(qt & set(d.split())) / max(len(qt), 1), i, d, m))
            scored.sort(key=lambda x: x[0])
            top = scored[:n_results]
            out["ids"].append([t[1] for t in top])
            out["documents"].append([t[2] for t in top])
            out["metadatas"].append([t[3] for t in top])
            out["distances"].append([t[0] for t in top])
        return out

    def delete(self, where):
        for i in self.get(where)["ids"]:
            del self.rows[i]


class SplitTextTest(unittest.TestCase):
    def test_short_text_is_one_piece(self):
        self.assertEqual(split_text("짧은 글", 100, 10), ["짧은 글"])
        self.assertEqual(split_text("   ", 100, 10), [])

    def test_pieces_respect_size_and_overlap(self):
        text = "\n".join(f"{i}번 줄 내용입니다 가나다라마바사" for i in range(1, 40))
        pieces = split_text(text, 120, 30)
        self.assertGreater(len(pieces), 3)
        self.assertTrue(all(len(p) <= 120 for p in pieces))
        for a, b in zip(pieces, pieces[1:]):                # 이어지는 조각은 끝부분이 겹친다
            self.assertTrue(any(a[-k:] == b[:k] for k in range(5, 31)), (a[-40:], b[:40]))
        self.assertTrue(pieces[0].startswith("1번 줄"))
        self.assertTrue(pieces[-1].endswith("39번 줄 내용입니다 가나다라마바사"))

    def test_single_long_word_terminates(self):
        pieces = split_text("가" * 1000, 100, 20)
        self.assertTrue(all(len(p) <= 100 for p in pieces))
        self.assertGreaterEqual(len(pieces), 10)

    def test_invalid_arguments(self):
        with self.assertRaises(ValueError):
            split_text("abc", 10, 10)
        with self.assertRaises(ValueError):
            split_text("abc", 0, 0)


class ChunkDocumentTest(unittest.TestCase):
    def setUp(self):
        self.reg, self.bld = docs()

    def test_one_chunk_per_section_with_header_and_metadata(self):
        chunks = chunk_document(self.reg, "case-x", 600, 100)
        self.assertEqual(len(chunks), len(self.reg.sections))
        third = chunks[2]
        self.assertTrue(third.text.startswith("[등기부 "))
        self.assertEqual(third.metadata["case_id"], "case-x")
        self.assertEqual(third.metadata["doc_type"], "registry")
        self.assertIn(third.metadata["section"], {"표제부", "갑구", "을구", "기타"})
        self.assertIsInstance(third.metadata["rank_no"], str)      # None 이 아니라 ""

    def test_ids_are_deterministic_and_case_specific(self):
        a = [c.id for c in chunk_document(self.reg, "case-x", 600, 100)]
        b = [c.id for c in chunk_document(self.reg, "case-x", 600, 100)]
        c = [c.id for c in chunk_document(self.reg, "case-y", 600, 100)]
        self.assertEqual(a, b)
        self.assertEqual(len(set(a)), len(a))
        self.assertTrue(set(a).isdisjoint(c))

    def test_personal_data_is_masked_before_embedding(self):
        text = "\n".join(c.text for c in chunk_document(self.reg, "c", 600, 100) + chunk_document(self.bld, "c", 600, 100))
        for secret in ("이임대", "김테스트", "800101", "900101", "가상로", "서초구"):
            self.assertNotIn(secret, text, secret)
        self.assertIn("근저당권", text)                 # 권리 내용은 남는다
        self.assertIn("120,000,000", text)

    def test_long_section_is_split_and_every_piece_keeps_header(self):
        doc = PropertyDoc("registry", sections=[Section("을구", "근저당권설정 " + "내용 " * 300, "1")])
        chunks = chunk_document(doc, "c", 200, 40)
        self.assertGreater(len(chunks), 3)
        self.assertTrue(all(c.text.startswith("[등기부 을구 순위 1]") and len(c.text) <= 200 for c in chunks))
        self.assertEqual([c.metadata["chunk_index"] for c in chunks], list(range(len(chunks))))

    def test_cancelled_rights_are_marked_in_header(self):
        texts = [c.text for c in chunk_document(self.reg, "c", 600, 100)]
        self.assertTrue(any(t.startswith("[등기부 을구 순위 1 말소됨]") for t in texts))     # 말소된 1번 근저당
        self.assertTrue(any(t.startswith("[등기부 을구 순위 2]") for t in texts))          # 유효한 2번 근저당

    def test_case_id_depends_on_content(self):
        base = case_id_for(self.reg, self.bld)
        self.assertEqual(base, case_id_for(*docs()))
        self.bld.sections[0] = Section("건축물개요", "다른 내용")
        self.assertNotEqual(base, case_id_for(self.reg, self.bld))

    def test_address_after_rrn_is_masked(self):
        out = mask_text("2 소유권이전 소유자 이임대 800101-******* 서울특별시 서초구 가상로 2\n3 가압류", ["이임대"])
        self.assertIn("[주민번호] [주소]", out)
        self.assertIn("3 가압류", out)


class ChunkStoreTest(unittest.TestCase):
    def setUp(self):
        self.col = FakeCollection()
        self.store = ChunkStore(self.col)
        self.reg, self.bld = docs()

    def test_upsert_is_idempotent(self):
        chunks = chunk_document(self.reg, "case-a", 600, 100)
        self.assertEqual(self.store.upsert(chunks + chunks), len(chunks))
        self.store.upsert(chunks)
        self.assertEqual(self.store.count("case-a"), len(chunks))

    def test_search_never_returns_other_cases(self):
        self.store.upsert(chunk_document(self.reg, "case-a", 600, 100))
        self.store.upsert(chunk_document(self.reg, "case-b", 600, 100))
        hits = self.store.search("case-a", ["근저당권 채권최고액"], n_results=50)[0]
        self.assertTrue(hits)
        self.assertTrue(all(h["metadata"]["case_id"] == "case-a" for h in hits))

    def test_results_are_ranked_and_shaped(self):
        self.store.upsert(chunk_document(self.reg, "case-a", 600, 100))
        hits = self.store.search("case-a", ["근저당권설정 채권최고액"], n_results=2)[0]
        self.assertEqual(len(hits), 2)
        self.assertLessEqual(hits[0]["distance"], hits[1]["distance"])
        self.assertIn("근저당권", hits[0]["text"])
        self.assertEqual(set(hits[0]), {"id", "text", "metadata", "distance"})

    def test_n_results_is_capped_by_available_and_empty_case(self):
        chunks = chunk_document(self.bld, "case-a", 600, 100)
        self.store.upsert(chunks)
        self.assertEqual(len(self.store.search("case-a", ["소유자"], n_results=99)[0]), len(chunks))
        self.assertEqual(self.store.search("nope", ["a", "b"], n_results=3), [[], []])

    def test_doc_type_filter_uses_and(self):
        self.store.upsert(chunk_document(self.reg, "case-a", 600, 100) + chunk_document(self.bld, "case-a", 600, 100))
        hits = self.store.search("case-a", ["소유자"], n_results=20, doc_type="building")[0]
        self.assertTrue(hits and all(h["metadata"]["doc_type"] == "building" for h in hits))
        self.assertEqual(self.col.last_where, case_filter("case-a", "building"))
        self.assertIn("$and", self.col.last_where)

    def test_delete_case(self):
        self.store.upsert(chunk_document(self.reg, "case-a", 600, 100))
        self.store.upsert(chunk_document(self.reg, "case-b", 600, 100))
        self.store.delete_case("case-a")
        self.assertEqual(self.store.count("case-a"), 0)
        self.assertGreater(self.store.count("case-b"), 0)


class EvidenceTest(unittest.TestCase):
    def test_case_id_survives_when_embedding_is_unavailable(self):
        reg, bld = docs()
        with patch("app.api.endpoints.analyze.OPENAI_API_KEY", ""):
            case_id, evidence, note = _collect_evidence(reg, bld)

        self.assertEqual(case_id, case_id_for(reg, bld))
        self.assertEqual(evidence, {})
        self.assertIn("OPENAI_API_KEY", note)

    def test_collect_evidence(self):
        reg, bld = docs()
        store = ChunkStore(FakeCollection())
        case_id, evidence = collect_evidence(store, reg, bld, 600, 100, top_k=4)
        self.assertEqual(set(evidence), set(FIELD_QUERIES))
        self.assertTrue(all(len(v) <= 4 for v in evidence.values()))
        rights = evidence["권리사항"]
        self.assertTrue(rights and all(h["doc_type"] == "registry" for h in rights[:2]))
        self.assertTrue(any("근저당권" in h["text"] for h in rights))        # 을구 근저당 청크가 근거로 잡힌다
        blob = json.dumps(evidence, ensure_ascii=False)
        self.assertNotIn("이임대", blob)
        self.assertNotIn("800101", blob)
        # 같은 문서로 다시 실행해도 같은 case 이고 중복 저장되지 않는다
        n = store.count(case_id)
        again, _ = collect_evidence(store, reg, bld, 600, 100, top_k=2)
        self.assertEqual(again, case_id)
        self.assertEqual(store.count(case_id), n)

    def test_same_documents_are_not_upserted_again(self):
        class CountingStore(ChunkStore):
            def __init__(self, collection):
                super().__init__(collection)
                self.upsert_calls = 0

            def upsert(self, chunks):
                self.upsert_calls += 1
                return super().upsert(chunks)

        reg, bld = docs()
        store = CountingStore(FakeCollection())
        collect_evidence(store, reg, bld, 600, 100, top_k=3)
        collect_evidence(store, reg, bld, 600, 100, top_k=3)
        self.assertEqual(store.upsert_calls, 1)


if __name__ == "__main__":
    unittest.main()
