"""평가 도구(evaluation 패키지) 테스트: 지표 계산, 정답 묶음, dry-run 전체 흐름."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long")

from app.services.document_source import load_sample_documents
from app.services.documents import COMPARABLE_FIELDS
from evaluation import metrics
from evaluation.gold import GoldGroup, covered, gold_groups

HAS_LANGCHAIN = importlib.util.find_spec("langchain_core") is not None
SAMPLE_DIR = str(Path(__file__).resolve().parent.parent / "sample_data")


class MetricsTest(unittest.TestCase):
    def test_percentile_and_mean(self):
        self.assertEqual(metrics.percentile([1, 2, 3, 4], 50), 2.5)
        self.assertEqual(metrics.percentile([5], 95), 5)
        self.assertIsNone(metrics.percentile([], 50))
        self.assertEqual(metrics.mean([1, None, 3]), 2)
        self.assertIsNone(metrics.mean([None]))
        self.assertIsNone(metrics.ratio(1, 0))

    def test_verdict_consistency(self):
        self.assertTrue(metrics.verdict_consistent("일치", "두 문서의 소유자가 같습니다."))
        self.assertFalse(metrics.verdict_consistent("일치", "두 문서의 소유자가 서로 다릅니다."))
        self.assertTrue(metrics.verdict_consistent("불일치", "소유자가 서로 다릅니다. 원본을 확인하세요."))
        self.assertFalse(metrics.verdict_consistent("불일치", "두 문서가 같습니다."))
        self.assertTrue(metrics.verdict_consistent("비교불가", "아무 말"))
        self.assertTrue(metrics.has_action("등기부 원본을 확인하세요."))
        self.assertFalse(metrics.has_action("서로 다릅니다."))

    def test_asserted_rights_ignores_negated_and_cancelled_mentions(self):
        f = metrics.asserted_rights
        self.assertEqual(f("현재 유효한 권리는 채권최고액 2억 4천만원의 근저당권입니다. 가압류는 말소되어 지금은 효력이 없습니다."), {"근저당권"})
        self.assertEqual(f("근저당권이 있으며 말소된 가압류는 제외합니다."), {"근저당권"})
        self.assertEqual(f("현재 유효한 근저당·압류·가압류 등 위험 권리는 확인되지 않았습니다."), set())
        self.assertEqual(f("압류와 경매개시결정이 있습니다."), {"압류", "경매개시결정"})
        self.assertEqual(f("과거에 말소된 가압류가 있었습니다."), set())
        self.assertEqual(f("가압류가 있습니다."), {"가압류"})            # '압류' 로 잘못 세지 않는다

    def test_rights_report(self):
        r = metrics.rights_report("근저당권과 가압류가 있습니다.", {"근저당권"}, {"가압류"})
        self.assertEqual((r["recall"], r["phantom"], r["cancelled_as_active"]), (1.0, 0, 1))
        r = metrics.rights_report("전세권이 있습니다.", {"근저당권"}, set())
        self.assertEqual((r["recall"], r["phantom"]), (0.0, 1))
        self.assertIsNone(metrics.rights_report("없습니다.", set(), set())["recall"])

    def test_number_extraction_handles_korean_units(self):
        e = metrics.extract_numbers
        self.assertEqual(e("2억 4천만원"), {"240000000"})
        self.assertEqual(e("1억 5,000만원과 5천만원"), {"150000000", "50000000"})
        self.assertEqual(e("3억원"), {"300000000"})
        self.assertEqual(e("300,000,000원"), {"300000000"})
        self.assertEqual(e("5층 84.9㎡ 2014년 제40001호"), {"84.9", "2014", "40001"})    # 두 자리 이하 정수는 무시
        self.assertTrue(metrics.mentions_amount("채권최고액은 3억원입니다", 300_000_000))
        self.assertFalse(metrics.mentions_amount("채권최고액은 2억원입니다", 300_000_000))

    def test_ungrounded_numbers(self):
        source = "채권최고액 금300,000,000원 보증금 200,000,000원 2014년"
        self.assertEqual(metrics.ungrounded_numbers("채권최고액은 3억원입니다.", source), [])
        self.assertEqual(metrics.ungrounded_numbers("채권최고액은 4억원입니다.", source), ["400000000"])
        self.assertEqual(metrics.ungrounded_numbers("2015년에 지어졌습니다.", source), ["2015"])

    def test_cost_is_none_without_prices(self):
        self.assertIsNone(metrics.token_cost(1000, 100, None, 2.0))
        self.assertAlmostEqual(metrics.token_cost(1_000_000, 500_000, 0.5, 2.0), 1.5)
        self.assertGreater(metrics.estimate_tokens("가나다라마바사"), 0)

    def test_citation_validity(self):
        self.assertEqual(metrics.citation_validity(["E1", "E9", "E2"], ["E1", "E2"]), {"total": 3, "valid": 2})


class GoldTest(unittest.TestCase):
    def test_groups_derived_from_documents(self):
        docs = load_sample_documents("x", SAMPLE_DIR, "lease_rights")
        reg, bld = docs.registry, docs.building
        rights = gold_groups("권리사항", reg, bld)
        self.assertEqual(sorted(g.label for g in rights), ["임차권 을구 2", "전세권 을구 1"])
        self.assertEqual(len(gold_groups("소유자명", reg, bld)), 2)                       # 등기부 + 건축물대장
        safe = load_sample_documents("x", SAMPLE_DIR, "safe")
        self.assertEqual(gold_groups("권리사항", safe.registry, safe.building), [])       # 유효한 권리가 없으면 정답도 없다
        cancelled = load_sample_documents("x", SAMPLE_DIR, "cancelled_rights")
        self.assertEqual(gold_groups("권리사항", cancelled.registry, cancelled.building), [])
        self.assertEqual(gold_groups("없는 항목", reg, bld), [])

    def test_group_matching(self):
        chunk = {"doc_type": "registry", "section": "을구", "rank_no": "2", "text": "[등기부 을구 순위 2] 임차권등기명령"}
        self.assertTrue(GoldGroup("a", "registry", section="을구", rank_no="2").matches(chunk))
        self.assertFalse(GoldGroup("a", "registry", section="을구", rank_no="1").matches(chunk))
        self.assertFalse(GoldGroup("a", "building").matches(chunk))
        self.assertTrue(GoldGroup("a", "registry", keyword="임차권").matches(chunk))
        self.assertFalse(GoldGroup("a", "registry", keyword="근저당").matches(chunk))
        groups = [GoldGroup("a", "registry", keyword="임차권"), GoldGroup("b", "building")]
        self.assertEqual(covered(groups, [chunk]), 1)

    def test_every_field_has_groups_for_every_scenario_document(self):
        import json
        names = json.loads((Path(SAMPLE_DIR) / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
        for name in names:
            docs = load_sample_documents("x", SAMPLE_DIR, name)
            for field in COMPARABLE_FIELDS:
                self.assertTrue(gold_groups(field, docs.registry, docs.building), (name, field))


@unittest.skipUnless(HAS_LANGCHAIN, "langchain-core 가 필요합니다")
class RunnerDryRunTest(unittest.TestCase):
    def test_pipeline_check_passes_for_all_scenarios(self):
        from evaluation.runner import load_scenarios, pipeline_check
        scenarios = load_scenarios(SAMPLE_DIR)
        self.assertEqual(len(scenarios), 7)
        for name, item in scenarios.items():
            self.assertTrue(pipeline_check(name, item, SAMPLE_DIR)["ok"], name)

    def test_unknown_scenario_name(self):
        from evaluation.runner import load_scenarios
        with self.assertRaises(ValueError):
            load_scenarios(SAMPLE_DIR, ["nope"])

    def test_adaptive_config_is_measured_once_per_chunk_size(self):
        from evaluation.runner import Config, expand_configs
        configs = expand_configs("retrieval", [120, 600], 0.15, [2, 3, 5], ["plain", "adaptive"], [], Config())
        self.assertEqual(len(configs), 2 * 3 + 2)
        adaptive = [c for c in configs if c.strategy == "adaptive"]
        self.assertEqual(len(adaptive), 2)
        self.assertTrue(all("k=auto" in c.label for c in adaptive))

    def test_full_flow_with_fakes(self):
        from evaluation import report
        from evaluation.env import build_dry_env
        from evaluation.runner import Config, aggregate, expand_configs, load_scenarios, pipeline_check, run_all
        scenarios = load_scenarios(SAMPLE_DIR, ["safe", "excessive_mortgage"])
        base = Config(600, 100, 3, "balanced")
        configs = expand_configs("retrieval", [120, 600], 0.15, [2, 3], ["plain", "balanced"], [], base) + \
                  expand_configs("prompt", [], 0.15, [], [], ["v1", "v2"], base)
        self.assertEqual(len(configs), 10)
        records = run_all(configs, scenarios, build_dry_env(), SAMPLE_DIR, repeat=2)
        # 검색 전용 설정은 반복하지 않고, LLM 설정은 반복한다
        self.assertEqual(len(records), 8 * 2 + 2 * 2 * 2)
        agg = {a["config"]: a for a in aggregate(records, 1.0, 4.0, 0.02)}
        v2 = agg[base.__class__(600, 100, 3, "balanced", "v2").label]
        self.assertEqual(v2["llm_call_ok"], 1.0)
        # 가짜 LLM 은 청크를 잘라 베끼므로 서버 검사에 걸리는 항목이 있을 수 있다. 답한 항목과 탈락한 항목이 모두 기록된다.
        self.assertGreater(v2["llm_items_answered"], 0.5)
        self.assertIn("llm_guard_rejected", v2)
        self.assertAlmostEqual(v2["llm_items_answered"] + v2["llm_guard_rejected"], 1.0, places=6)
        self.assertGreater(v2["prompt_tokens"], agg[Config(600, 100, 3, "balanced", "v1").label]["prompt_tokens"])   # v2 는 프롬프트가 더 길다
        self.assertGreater(v2["llm_cost_per_analysis"], 0)
        self.assertGreater(v2["embed_cost_per_analysis"], 0)
        self.assertIn("ret_coverage", v2)
        no_price = aggregate(records)[-1]
        self.assertIsNone(no_price["llm_cost_per_analysis"])                    # 가격을 모르면 비용을 만들어 내지 않는다
        text = report.render({"started": "t", "llm_model": "m", "embedding_model": "e", "scenarios": 2, "repeat": 2,
                              "dry_run": True, "input_price": 1.0, "currency": "USD"},
                             [pipeline_check(n, i, SAMPLE_DIR) for n, i in scenarios.items()], list(agg.values()), records)
        for expected in ("DRY RUN", "## 2.", "## 3.", "## 4.", "## 5.", "2/2"):
            self.assertIn(expected, text)

    def test_cli_dry_run_writes_report_and_results(self):
        from evaluation.__main__ import main
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(main(["--phase", "retrieval", "--dry-run", "--scenarios", "safe", "--chunk-sizes", "600",
                                   "--top-ks", "3", "--out-dir", d]), 0)
            run_dirs = list(Path(d).iterdir())
            self.assertEqual(len(run_dirs), 1)
            self.assertTrue((run_dirs[0] / "report.md").exists())
            self.assertTrue((run_dirs[0] / "results.json").exists())

    def test_cli_refuses_real_calls_without_confirmation(self):
        from evaluation.__main__ import main
        from unittest.mock import patch
        with patch("builtins.input", return_value="n"):
            self.assertEqual(main(["--phase", "prompt", "--scenarios", "safe"]), 1)


if __name__ == "__main__":
    unittest.main()
