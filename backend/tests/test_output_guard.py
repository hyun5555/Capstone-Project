"""
서버 검사(output_guard)와 rag_explain 연동 테스트. LLM 이 근거에 없는 숫자나 문서에 없는 권리를 말하면 기본 문장으로 대체된다.
"""
import json
import os
import unittest
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long")

from app.services.codef_normalizer import normalize_building_response, normalize_registry_response
from app.services.document_compare import build_findings, compare_documents
from app.services.output_guard import check_explanation, extract_numbers, ungrounded_numbers
from app.services.rag_explain import RIGHTS_FIELD, explain_with_evidence

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RIGHTS = "권리사항"


def chunk(cid, text, doc_type="registry", section="을구"):
    return {"chunk_id": cid, "doc_type": doc_type, "section": section, "rank_no": None, "text": text, "distance": 0.1}


class NumberCheckTest(unittest.TestCase):
    def test_korean_units_match_plain_amounts(self):
        source = "근저당권설정 채권최고액 금240,000,000원"
        self.assertEqual(ungrounded_numbers("채권최고액은 2억 4천만원입니다.", source), [])
        self.assertEqual(ungrounded_numbers("채권최고액은 240,000,000원입니다.", source), [])
        self.assertEqual(ungrounded_numbers("채권최고액은 3억원입니다.", source), ["300000000"])

    def test_small_numbers_and_areas(self):
        self.assertEqual(extract_numbers("5층 제501호 84.9㎡ 1,050.3㎡ 2014년"), {"501", "84.9", "1050.3", "2014"})
        self.assertEqual(ungrounded_numbers("전용면적은 84.9㎡입니다.", "전용면적 84.9㎡"), [])
        self.assertEqual(ungrounded_numbers("전용면적은 99.9㎡입니다.", "전용면적 84.9㎡"), ["99.9"])


class RightsCheckTest(unittest.TestCase):
    def check(self, text, active, source=""):
        return check_explanation(RIGHTS, text, source, set(active), RIGHTS)

    def test_accepts_active_rights_and_negations(self):
        self.assertEqual(self.check("현재 유효한 권리는 근저당권입니다. 압류는 없습니다.", ["근저당권"]), [])
        self.assertEqual(self.check("가압류는 말소되어 지금은 효력이 없고, 근저당권만 남아 있습니다.", ["근저당권"]), [])
        self.assertEqual(self.check("위험 권리는 확인되지 않았습니다.", []), [])

    def test_comma_separated_list_shares_the_final_predicate(self):
        # 실제 LLM 이 자주 쓰는 형태. 쉼표로 나열한 권리 전부가 "없다" 는 뜻이다.
        for text in ("현재 유효한 근저당권, 압류, 가압류 등 위험 권리는 확인되지 않았습니다.",
                     "등기부에 근저당권, 압류, 가압류가 없습니다.",
                     "근저당권, 압류, 가압류가 모두 말소되었습니다."):
            self.assertEqual(self.check(text, []), [], text)
        self.assertEqual(self.check("현재 유효한 권리는 근저당권입니다. 압류, 가압류는 없습니다.", ["근저당권"]), [])
        # 나열한 권리가 "있다" 는 뜻이면 모두 있다고 본다
        self.assertEqual(self.check("근저당권, 전세권이 설정되어 있습니다.", ["근저당권", "전세권"]), [])
        self.assertIn("phantom_right:전세권", self.check("근저당권, 전세권이 설정되어 있습니다.", ["근저당권"]))
        # 서로 다른 절은 따로 본다
        self.assertIn("missing_right:근저당권", self.check("가압류는 말소되었습니다.", ["근저당권"]))
        self.assertEqual(self.check("근저당권이 설정되어 있고, 압류는 없습니다.", ["근저당권"]), [])

    def test_rejects_right_not_in_document(self):
        self.assertIn("phantom_right:압류", self.check("근저당권과 압류가 있습니다.", ["근저당권"]))
        self.assertIn("phantom_right:근저당권", self.check("근저당권 채권최고액 0원이 있습니다.", []))

    def test_rejects_omitted_or_cancelled_active_right(self):
        self.assertIn("missing_right:압류", self.check("근저당권이 설정되어 있습니다.", ["근저당권", "압류"]))
        self.assertIn("missing_right:근저당권", self.check("근저당권은 말소되었습니다.", ["근저당권"]))

    def test_rights_are_checked_only_for_the_rights_field(self):
        self.assertEqual(check_explanation("건물 용도", "근저당권과 압류가 있습니다.", "", {"근저당권"}, RIGHTS), [])


class RagIntegrationTest(unittest.TestCase):
    def setUp(self):
        load = lambda n: json.loads((FIXTURES / n).read_text(encoding="utf-8"))["data"]
        self.reg = normalize_registry_response(load("registry_response.json"), "서울특별시 강남구 테스트로 100")
        self.bld = normalize_building_response(load("building_response.json"), "서울특별시 강남구 테스트로 100")
        self.comparison = compare_documents(self.reg, self.bld)
        self.findings = build_findings(self.reg, self.bld, self.comparison)
        self.evidence = {
            "소유자명": [chunk("c1", "소유권이전 소유자 [소유자1]", section="갑구")],
            RIGHTS_FIELD: [chunk("c2", "근저당권설정 채권최고액 금60,000,000원")],
        }

    def ask(self, owner_text, rights_text):
        def llm(_):
            return {"소유자명": {"explanation": owner_text, "evidence_ids": ["E1"]},
                    RIGHTS_FIELD: {"explanation": rights_text, "evidence_ids": ["E2"]}}
        return explain_with_evidence(self.comparison, self.evidence, self.findings, llm)

    def test_good_answer_is_kept(self):
        out = self.ask("두 문서의 소유자가 같습니다.", "현재 유효한 권리는 채권최고액 6천만원의 근저당권입니다.")
        self.assertEqual((out["소유자명"]["source"], out[RIGHTS_FIELD]["source"]), ("llm", "llm"))
        self.assertNotIn("guard", out[RIGHTS_FIELD])

    def test_invented_amount_is_replaced_with_default_sentence(self):
        out = self.ask("두 문서의 소유자가 같습니다.", "현재 유효한 권리는 채권최고액 1억원의 근저당권입니다.")
        item = out[RIGHTS_FIELD]
        self.assertEqual(item["source"], "default")
        self.assertIn("60,000,000", item["explanation"])                       # 서버가 만든 정확한 문장
        self.assertEqual(item["guard"], ["ungrounded_number:100000000"])
        self.assertEqual(out["소유자명"]["source"], "llm")                        # 다른 항목은 영향이 없다

    def test_invented_right_is_replaced(self):
        out = self.ask("두 문서의 소유자가 같습니다.", "근저당권과 압류가 설정되어 있습니다.")
        self.assertEqual(out[RIGHTS_FIELD]["source"], "default")
        self.assertIn("phantom_right:압류", out[RIGHTS_FIELD]["guard"])


if __name__ == "__main__":
    unittest.main()
