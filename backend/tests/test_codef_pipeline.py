"""
CODEF 연동/정규화/비교/마스킹 테스트 (외부 서버·API 키 없이 실행: python -m unittest discover -s tests -v)

- 픽스처(tests/fixtures/*.json)는 실제 응답이 아니라 구조를 흉내 낸 가상 데이터다.
  실제 응답을 받은 뒤에는 그 마스킹본을 픽스처로 추가해서 같은 테스트를 돌려 보는 것이 좋다.
"""
import asyncio
import contextlib
import io
import json
import logging
import os
import re
import tempfile
import unittest
import urllib.parse
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret")

import httpx

from app.clients import codef_client
from app.clients.codef_client import CodefClient, CodefError, http_status_for
from app.config import CodefSettings
from app.services.codef_normalizer import (
    decode_codef_body, normalize_building_response, normalize_registry_response,
)
from app.services.document_compare import (
    MATCH, MISMATCH, UNKNOWN, build_findings, compare_documents, default_explanation, unverified_fields,
)
from app.services.document_source import (
    MissingAddressParts, SampleDataMissing, load_codef_documents, load_sample_documents,
)
from app.services.documents import PropertyDoc
from app.utils.codef_rsa import normalize_public_key_pem
from app.utils.masking import mask_building_response, mask_json, mask_person_name

BACKEND = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SECRET_PW = "very-secret-password-123"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))["data"]


def make_settings(**overrides):
    base = dict(
        env="prod", client_id="cid", client_secret="csecret", public_key="PUBKEY", api_host="https://api.test",
        oauth_url="https://oauth.test/token", registry_path="/reg", building_path="/bld",
        registry_organization="0004", phone_no="01012345678", user_id="uid", user_pw=SECRET_PW, timeout_sec=5,
    )
    base.update(overrides)
    return CodefSettings(**base)


def run(coro):
    return asyncio.run(coro)


class FakeCodef:
    """httpx MockTransport 핸들러: 토큰 발급 횟수와 받은 요청 본문을 기록한다."""

    def __init__(self, registry=None, building=None, envelope_code="CF-00000", url_encode=False, status=200):
        self.token_calls = 0
        self.bodies = {}
        self.registry = registry if registry is not None else fixture("registry_response.json")
        self.building = building if building is not None else fixture("building_response.json")
        self.code, self.url_encode, self.status = envelope_code, url_encode, status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            self.token_calls += 1
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        body = json.loads(request.content)
        self.bodies[request.url.path] = body
        if self.status != 200:
            return httpx.Response(self.status, text="RAW-BODY-WITH-SECRET " + json.dumps(body))
        data = self.registry if request.url.path == "/reg" else self.building
        text = json.dumps({"result": {"code": self.code, "message": "msg"}, "data": data}, ensure_ascii=False)
        if self.url_encode:
            text = urllib.parse.quote_plus(text)
        return httpx.Response(200, text=text)


def make_client(fake, settings=None):
    return CodefClient(settings or make_settings(), transport=httpx.MockTransport(fake))


class NoEncrypt:
    """RSA 라이브러리(pycryptodome) 없이도 요청 본문 구성을 시험하기 위해 암호화만 가짜로 바꾼다."""

    def __enter__(self):
        self._orig = codef_client._encrypt
        codef_client._encrypt = lambda pw: "ENC(" + pw + ")"

    def __exit__(self, *exc):
        codef_client._encrypt = self._orig


# ─────────────────────────────────────────────────────────────
class CodefClientTest(unittest.TestCase):
    def test_token_is_cached_across_requests(self):
        fake = FakeCodef()
        client = make_client(fake)

        async def go():
            await client.post("/reg", {"a": 1})
            await client.post("/bld", {"a": 1})

        run(go())
        self.assertEqual(fake.token_calls, 1)

    def test_urlencoded_response_is_decoded(self):
        client = make_client(FakeCodef(url_encode=True))
        data = run(client.post("/bld", {}))
        self.assertEqual(data["resDocNo"], "SAMPLE-0001")

    def test_codef_error_code_is_reported_without_body(self):
        client = make_client(FakeCodef(envelope_code="CF-12345"))
        with self.assertRaises(CodefError) as cm:
            run(client.post("/bld", {}))
        self.assertEqual(cm.exception.code, "CF-12345")
        self.assertEqual(http_status_for(cm.exception), 502)

    def test_http_error_does_not_leak_response_or_request_body(self):
        client = make_client(FakeCodef(status=500))
        with self.assertRaises(CodefError) as cm:
            run(client.post("/reg", {"password": SECRET_PW}))
        self.assertNotIn("RAW-BODY", cm.exception.message)
        self.assertNotIn(SECRET_PW, cm.exception.message)

    def test_two_way_is_reported(self):
        client = make_client(FakeCodef(building={"continue2Way": True}))
        with self.assertRaises(CodefError) as cm:
            run(client.post("/bld", {}))
        self.assertTrue(cm.exception.continue2way)
        self.assertEqual(http_status_for(cm.exception), 404)

    def test_missing_settings_named_in_error(self):
        client = make_client(FakeCodef(), make_settings(client_id=None))
        with self.assertRaises(CodefError) as cm:
            run(client.post("/reg", {}))
        self.assertIn("CODEF_CLIENT_ID", cm.exception.message)
        self.assertEqual(http_status_for(cm.exception), 500)

    def test_requests_use_given_address_parts_not_hardcoded_values(self):
        fake = FakeCodef()
        client = make_client(fake)
        with NoEncrypt():
            run(codef_client.fetch_building(client, "서울특별시 강남구 테스트로", "100", "3"))
            run(codef_client.fetch_registry(client, "서울특별시 강남구 테스트로 100"))
        b = fake.bodies["/bld"]
        self.assertEqual((b["address"], b["mainAddressNo"], b["subAddressNo"]), ("서울특별시 강남구 테스트로", "100", "3"))
        self.assertEqual(fake.bodies["/reg"]["address"], "서울특별시 강남구 테스트로 100")
        self.assertEqual(fake.bodies["/reg"]["addr_sido"], "서울특별시")
        self.assertEqual(fake.bodies["/reg"]["phoneNo"], "01012345678")
        self.assertTrue(fake.bodies["/reg"]["password"].startswith("ENC("))     # 평문 비밀번호가 나가지 않는다

    def test_nothing_is_printed_or_logged(self):
        fake = FakeCodef()
        client = make_client(fake)
        out, err = io.StringIO(), io.StringIO()
        with self.assertLogs(level="DEBUG") as logs, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), NoEncrypt():
            logging.getLogger("probe").debug("probe")   # assertLogs 는 로그가 1건은 있어야 통과
            run(codef_client.fetch_building(client, "테스트로", "100", "0"))
        everything = out.getvalue() + err.getvalue() + "\n".join(logs.output)
        self.assertNotIn(SECRET_PW, everything)
        self.assertNotIn("이임", everything)          # 응답 본문(소유자명)도 출력/로그에 없다
        self.assertNotIn("Bearer", everything)


class StaticSecurityChecksTest(unittest.TestCase):
    """소스 수준 회귀 방지: 예전에 있던 문제가 다시 들어오지 않게 한다."""

    def source(self, rel):
        return (BACKEND / rel).read_text(encoding="utf-8")

    def test_tls_verification_is_not_disabled(self):
        for rel in ("app/clients/codef_client.py", "app/clients/registry_api.py", "app/clients/building_api.py",
                    "app/clients/codef_auth.py", "app/api/endpoints/codef_auth.py"):
            self.assertNotRegex(self.source(rel), r"verify\s*=\s*False", rel)

    def test_no_print_in_codef_paths(self):
        for rel in ("app/clients/codef_client.py", "app/clients/registry_api.py", "app/clients/building_api.py",
                    "app/api/endpoints/analyze.py", "app/api/endpoints/building.py", "app/api/endpoints/registry.py",
                    "app/api/endpoints/codef_auth.py"):
            self.assertNotRegex(self.source(rel), r"(?m)^\s*print\(", rel)

    def test_token_endpoint_removed_and_prefix_not_duplicated(self):
        self.assertNotIn('"/token"', self.source("app/api/endpoints/codef_auth.py"))
        main = self.source("app/main.py")
        self.assertNotRegex(main, r"codef_auth\.router,\s*prefix")

    def test_analyze_has_no_hardcoded_address_parts_or_sample_file(self):
        src = self.source("app/api/endpoints/analyze.py")
        self.assertNotIn('"101"', src)
        self.assertNotIn("registry.json", src)
        self.assertNotIn("resIssueDate", src)          # 발급일로 준공년도를 만들지 않는다

    def test_analyze_route_is_root_of_router(self):
        self.assertIn('@router.post("/")', self.source("app/api/endpoints/analyze.py"))


# ─────────────────────────────────────────────────────────────
class NormalizerTest(unittest.TestCase):
    def test_registry_fixture(self):
        doc = normalize_registry_response(fixture("registry_response.json"), "주소")
        self.assertEqual(doc.owner_names, ["이임대"])           # 최신 소유권이전 기준
        self.assertEqual(doc.usage, "다세대주택")
        self.assertEqual(doc.structure, "철근콘크리트구조")
        self.assertEqual(doc.area_exclusive, 84.9)
        self.assertEqual(doc.area_total, 1050.3)
        self.assertEqual(doc.build_year, 2014)

    def test_registry_cancelled_rights_are_excluded(self):
        doc = normalize_registry_response(fixture("registry_response.json"))
        active = [(r.type, r.amount) for r in doc.active_rights]
        self.assertEqual(active, [("근저당권", 60_000_000)])     # 1번 근저당 말소, 가압류 말소
        self.assertEqual(doc.max_claim_amount, 60_000_000)

    def test_building_year_comes_from_use_approval_not_issue_date(self):
        data = fixture("building_response.json")
        self.assertTrue(data["resIssueDate"].startswith("2026"))
        doc = normalize_building_response(data)
        self.assertEqual(doc.build_year, 2014)

    def test_building_year_unknown_when_no_use_approval_date(self):
        data = fixture("building_response.json")
        data["resDetailList"] = [d for d in data["resDetailList"] if d["resType"] != "사용승인일"]
        self.assertIsNone(normalize_building_response(data).build_year)      # 발급연도로 채우지 않는다

    def test_building_missing_values_stay_none(self):
        doc = normalize_building_response(fixture("building_response.json"))
        self.assertIsNone(doc.area_exclusive)          # 없는 값은 "없음" 문자열이 아니라 None

    def test_violation_parsing(self):
        base = fixture("building_response.json")
        for text, expected in (("", False), ("위반건축물", True), ("위반건축물 아님", False), ("해당없음", False)):
            data = dict(base, resViolationStatus=text)
            self.assertIs(normalize_building_response(data).violation, expected, text)
        data = dict(base)
        data.pop("resViolationStatus")
        self.assertIsNone(normalize_building_response(data).violation)       # 응답에 없으면 확인 못 함

    def test_decode_urlencoded_and_plain_json(self):
        plain = json.dumps({"data": {"a": "x+y"}})
        self.assertEqual(decode_codef_body(plain)["data"]["a"], "x+y")     # 평문의 '+' 는 그대로
        encoded = urllib.parse.quote_plus(plain)
        self.assertEqual(decode_codef_body(encoded)["data"]["a"], "x+y")


# ─────────────────────────────────────────────────────────────
class CompareTest(unittest.TestCase):
    def setUp(self):
        self.reg = normalize_registry_response(fixture("registry_response.json"))
        self.bld = normalize_building_response(fixture("building_response.json"))

    def test_fixture_comparison(self):
        c = compare_documents(self.reg, self.bld)
        self.assertEqual(c["소유자명"]["status"], MATCH)              # '이임대' vs '이임*'
        self.assertEqual(c["건물 용도"]["status"], MATCH)
        self.assertEqual(c["구조 유형"]["status"], MATCH)
        self.assertEqual(c["연면적"]["status"], MATCH)
        self.assertEqual(c["준공년도"]["status"], MATCH)

    def test_missing_value_is_unknown_not_mismatch(self):
        c = compare_documents(self.reg, self.bld)
        self.assertEqual(c["전용면적"]["status"], UNKNOWN)            # 건축물대장에 값이 없음
        self.assertEqual(unverified_fields(c), ["전용면적"])
        self.assertIn("확인", default_explanation("전용면적", c["전용면적"]) + "확인")   # 설명 문장이 만들어진다

    def test_owner_mismatch(self):
        self.bld.owner_names = ["박다른"]
        c = compare_documents(self.reg, self.bld)
        self.assertEqual(c["소유자명"]["status"], MISMATCH)
        f = build_findings(self.reg, self.bld, c)
        self.assertNotEqual(f["등기부_소유자"], f["건축물대장_소유자"])

    def test_owner_match_makes_findings_equal_and_unknown_owner_is_not_a_mismatch(self):
        c = compare_documents(self.reg, self.bld)
        f = build_findings(self.reg, self.bld, c)
        self.assertEqual(f["등기부_소유자"], f["건축물대장_소유자"])
        self.bld.owner_names = []
        c = compare_documents(self.reg, self.bld)
        self.assertEqual(c["소유자명"]["status"], UNKNOWN)
        f = build_findings(self.reg, self.bld, c)
        self.assertEqual(f["등기부_소유자"], f["건축물대장_소유자"])   # 비교불가는 위험(불일치)으로 세지 않는다

    def test_masked_name_needs_same_length(self):
        self.bld.owner_names = ["이*"]                                 # 길이가 다르면 일치로 보지 않는다
        self.assertEqual(compare_documents(self.reg, self.bld)["소유자명"]["status"], MISMATCH)

    def test_results_never_contain_raw_owner_names(self):
        self.bld.owner_names = ["박다른"]
        blob = json.dumps(compare_documents(self.reg, self.bld), ensure_ascii=False)
        self.assertNotIn("이임대", blob)
        self.assertNotIn("박다른", blob)
        self.assertIn("이*대", blob)

    def test_area_tolerance(self):
        self.bld.area_total = 1050.3 * 1.005
        self.assertEqual(compare_documents(self.reg, self.bld)["연면적"]["status"], MATCH)
        self.bld.area_total = 900.0
        self.assertEqual(compare_documents(self.reg, self.bld)["연면적"]["status"], MISMATCH)

    def test_semantic_judge_only_called_when_rules_disagree(self):
        calls = []

        def judge(field, a, b):
            calls.append((field, a, b))
            return MATCH

        compare_documents(self.reg, self.bld, semantic_judge=judge)
        self.assertEqual(calls, [])                                   # 규칙으로 일치하면 LLM 을 부르지 않는다

        self.bld.structure = "철근콘크리트 라멘조 특수구조"
        self.reg.structure = "철골조"
        c = compare_documents(self.reg, self.bld, semantic_judge=judge)
        self.assertEqual(len(calls), 1)
        self.assertEqual(c["구조 유형"]["status"], MATCH)

    def test_semantic_judge_failure_falls_back_to_rule_result(self):
        self.reg.structure, self.bld.structure = "철골조", "철근콘크리트구조"

        def boom(*a):
            raise RuntimeError("no api key")

        self.assertEqual(compare_documents(self.reg, self.bld, semantic_judge=boom)["구조 유형"]["status"], MISMATCH)

    def test_findings_for_risk_score(self):
        f = build_findings(self.reg, self.bld, compare_documents(self.reg, self.bld))
        self.assertEqual(f["채권최고액"], 60_000_000)
        self.assertEqual(f["위험_권리_목록"], ["근저당권"])
        self.assertIs(f["위반건축물"], False)
        self.assertEqual(f["건물 용도"], "주거용")                     # 다세대주택 → 주거용

    def test_comparison_uses_only_shared_fields(self):
        self.assertEqual(list(compare_documents(PropertyDoc("registry"), PropertyDoc("building"))),
                         ["소유자명", "건물 용도", "구조 유형", "전용면적", "연면적", "준공년도"])


# ─────────────────────────────────────────────────────────────
class DocumentSourceTest(unittest.TestCase):
    def test_sample_source_reads_files(self):
        docs = load_sample_documents("주소", str(FIXTURES))
        self.assertEqual(docs.source, "sample")
        self.assertTrue(docs.notes)                                   # 데모 데이터임을 알린다
        self.assertEqual(docs.registry.owner_names, ["이임대"])

    def test_sample_source_accepts_raw_data_without_envelope(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("registry_response.json", "building_response.json"):
                (Path(d) / name).write_text(json.dumps(fixture(name), ensure_ascii=False), encoding="utf-8")
            self.assertEqual(load_sample_documents("주소", d).building.build_year, 2014)

    def test_missing_sample_file(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(SampleDataMissing):
            load_sample_documents("주소", d)

    def test_codef_source_needs_road_name_and_main_no(self):
        for road, main in ((None, "100"), ("테스트로", None), ("", "")):
            with self.assertRaises(MissingAddressParts):
                run(load_codef_documents(make_client(FakeCodef()), "주소", road, main, "0"))

    def test_codef_source_end_to_end(self):
        fake = FakeCodef()
        with NoEncrypt():
            docs = run(load_codef_documents(make_client(fake), "주소", "서울특별시 강남구 테스트로", "100", None))
        self.assertEqual(docs.source, "codef")
        self.assertEqual(fake.bodies["/bld"]["subAddressNo"], "0")     # 부번이 없으면 '0'
        self.assertEqual(docs.building.build_year, 2014)


# ─────────────────────────────────────────────────────────────
class MaskingTest(unittest.TestCase):
    def test_mask_person_name(self):
        self.assertEqual(mask_person_name("홍길동"), "홍*동")
        self.assertEqual(mask_person_name("김수"), "김*")
        self.assertEqual(mask_person_name("남궁민수"), "남**수")
        self.assertEqual(mask_person_name("주식회사가상은행"), "주식회사가상은행")     # 법인은 그대로

    def test_building_response_masked_copy(self):
        data = fixture("building_response.json")
        data["resOwnerList"][0]["resOwner"] = "홍길동"
        masked = mask_building_response(data)
        owner = masked["resOwnerList"][0]
        self.assertEqual(owner["resOwner"], "홍*동")
        self.assertEqual(owner["resIdentityNo"], "******-*******")
        self.assertTrue(owner["resUserAddr"].endswith("***"))
        self.assertNotIn("가상로", owner["resUserAddr"])
        self.assertEqual(data["resOwnerList"][0]["resOwner"], "홍길동")       # 원본은 그대로

    def test_mask_json_masks_names_rrn_and_phone(self):
        raw = {"a": ["소유자 홍길동 800101-1234567 연락처 010-1234-5678"], "n": 5}
        masked = json.dumps(mask_json(raw, ["홍길동"]), ensure_ascii=False)
        for secret in ("홍길동", "800101-1234567", "010-1234-5678"):
            self.assertNotIn(secret, masked)


class PublicKeyTest(unittest.TestCase):
    def test_header_is_added_when_missing(self):
        pem = normalize_public_key_pem("MIIBIjANBgkq" + "A" * 100)
        self.assertTrue(pem.startswith("-----BEGIN PUBLIC KEY-----\n"))
        self.assertTrue(pem.endswith("\n-----END PUBLIC KEY-----"))
        self.assertTrue(all(len(line) <= 64 for line in pem.splitlines()[1:-1]))

    def test_existing_pem_and_escaped_newlines(self):
        given = "-----BEGIN PUBLIC KEY-----\\nABC\\n-----END PUBLIC KEY-----"
        self.assertEqual(normalize_public_key_pem(given), given.replace("\\n", "\n"))


if __name__ == "__main__":
    unittest.main()
