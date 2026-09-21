# backend/evaluation/runner.py
"""
시나리오를 설정(청크 크기, overlap, Top-K, 검색 전략, 프롬프트 버전)별로 돌려 지표를 모은다.

한 번의 실행(run_one)이 하는 일은 운영 경로와 같다:
    문서 로드 → 규칙 비교/위험 점수 → 청킹·저장(임베딩) → 항목별 근거 검색 → LLM 설명 → 지표 계산
운영 코드(app.services.*)를 그대로 호출하므로 평가 결과가 운영 동작과 어긋나지 않는다.
"""
import time
from dataclasses import dataclass
from itertools import product
from threading import Lock
from typing import Callable, Dict, List, Optional
from unittest.mock import patch

from app.services.chunk_store import ChunkStore
from app.services.document_compare import build_findings, compare_documents
from app.services.document_source import load_sample_documents
from app.services.evidence import index_documents, retrieve_evidence
from app.services.rag_explain import RIGHTS_FIELD, build_payload, build_targets, explain_with_evidence
from app.services.risk_score import calculate_risk_score

from evaluation import metrics
from evaluation.gold import covered, gold_groups

ADDRESS = "합성 테스트 주소"


@dataclass(frozen=True)
class Config:
    chunk_size: int = 600
    chunk_overlap: int = 100
    top_k: int = 3
    strategy: str = "balanced"
    prompt_version: Optional[str] = None    # None 이면 LLM 을 부르지 않는다 (검색 평가만)
    json_mode: bool = False

    @property
    def label(self) -> str:
        prompt = self.prompt_version or "-"
        k = "auto" if self.strategy == "adaptive" else self.top_k     # adaptive 는 항목별 K 를 쓰므로 하나의 K 가 없다
        return f"prompt={prompt} size={self.chunk_size}/ov={self.chunk_overlap} k={k} {self.strategy}"


class TrackingStore:
    """ChunkStore 를 감싸서 임베딩에 들어간 텍스트의 토큰 수(추정)를 센다."""

    def __init__(self, inner: ChunkStore):
        self.inner = inner
        self._lock = Lock()
        self.index_tokens = 0
        self.query_tokens = 0

    def upsert(self, chunks):
        chunks = list(chunks)
        tokens = sum(metrics.estimate_tokens(c.text) for c in chunks)
        with self._lock:
            self.index_tokens += tokens
        return self.inner.upsert(chunks)

    def search(self, case_id, queries, n_results=3, doc_type=None):
        tokens = sum(metrics.estimate_tokens(q) for q in queries)
        with self._lock:
            self.query_tokens += tokens
        return self.inner.search(case_id, queries, n_results=n_results, doc_type=doc_type)

    def count(self, case_id):
        return self.inner.count(case_id)

    def delete_case(self, case_id):
        return self.inner.delete_case(case_id)


@dataclass
class Environment:
    """평가에 쓰는 외부 부품. 실제(ChromaDB + OpenAI)와 dry-run(가짜)을 같은 모양으로 맞춘다."""
    make_store: Callable[[int, int], TrackingStore]         # (chunk_size, overlap) → 새 컬렉션의 저장소
    make_llm_call: Callable[[Config, list], Callable]       # (config, callbacks) → llm_call(payload) → dict
    dry_run: bool = False


# ── 시나리오 ──────────────────────────────────────────────────
def load_scenarios(sample_dir: str, names: Optional[List[str]] = None) -> Dict[str, dict]:
    import json
    from pathlib import Path
    data = json.loads((Path(sample_dir) / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    if names:
        unknown = [n for n in names if n not in data]
        if unknown:
            raise ValueError(f"알 수 없는 시나리오입니다: {', '.join(unknown)}")
        data = {n: data[n] for n in names}
    return data


def pipeline_check(name: str, item: dict, sample_dir: str) -> dict:
    """규칙 기반 판정이 시나리오의 기대값과 같은가. LLM 과 무관하며 설정에 따라 달라지지 않는다."""
    docs = load_sample_documents(ADDRESS, sample_dir, name)
    comparison = compare_documents(docs.registry, docs.building)
    request, expected = item["request"], item["expected"]
    with patch("app.services.risk_score.check_defaulter", return_value=False):   # 외부 사이트를 부르지 않는다
        risk = calculate_risk_score(
            build_findings(docs.registry, docs.building, comparison),
            {"보증금": request["deposit"], "시세": request.get("marketPrice")},
        )
    checks = {
        "owner_status": comparison["소유자명"]["status"] == expected["owner_status"],
        "active_rights": sorted(r.type for r in docs.registry.active_rights) == sorted(expected["active_rights"]),
        "risk_score": risk["score"] == expected["risk_score"],
        "risk_grade": risk["grade"] == expected["risk_grade"],
    }
    return {"scenario": name, "ok": all(checks.values()), "checks": checks,
            "score": risk["score"], "grade": risk["grade"]}


# ── 검색 지표 ────────────────────────────────────────────────
def retrieval_metrics(evidence: dict, reg, bld) -> dict:
    covered_total = groups_total = 0
    fields_with_groups = fields_complete = 0
    rights_covered = rights_groups = 0
    noise_chunks = all_chunks = 0
    per_field = {}
    for field, chunks in evidence.items():
        groups = gold_groups(field, reg, bld)
        got = covered(groups, chunks)
        per_field[field] = {"groups": len(groups), "covered": got, "chunks": len(chunks)}
        covered_total += got
        groups_total += len(groups)
        if groups:
            fields_with_groups += 1
            fields_complete += int(got == len(groups))
            all_chunks += len(chunks)
            noise_chunks += sum(1 for c in chunks if not any(g.matches(c) for g in groups))
        if field == RIGHTS_FIELD:
            rights_covered, rights_groups = got, len(groups)
    return {
        "ret_coverage": metrics.ratio(covered_total, groups_total),
        "ret_fields_complete": metrics.ratio(fields_complete, fields_with_groups),
        "ret_rights_recall": metrics.ratio(rights_covered, rights_groups),
        "ret_noise": metrics.ratio(noise_chunks, all_chunks),
        "ret_per_field": per_field,
    }


# ── LLM 출력 지표 ────────────────────────────────────────────
def explanation_metrics(comparison, reg, bld, targets, allowed, captured, explained) -> dict:
    answer = captured.get("answer")
    json_ok = isinstance(answer, dict)
    answered = [n for n in targets if explained[n]["source"] == "llm"]

    raw_total = raw_valid = 0
    for n in targets:
        raw = answer.get(n) if json_ok else None
        ids = raw.get("evidence_ids") if isinstance(raw, dict) else None
        if isinstance(ids, list):
            v = metrics.citation_validity([i for i in ids if isinstance(i, str)], allowed[n])
            raw_total += v["total"]
            raw_valid += v["valid"]

    cite_covered = cite_groups = 0
    for n in answered:
        groups = gold_groups(n, reg, bld)
        cite_groups += len(groups)
        cite_covered += covered(groups, explained[n]["evidence"])

    verdicts, actions = [], []
    for n in answered:
        item = comparison.get(n)
        if item is None or item["status"] not in (metrics.MATCH, metrics.MISMATCH):
            continue
        verdicts.append(metrics.verdict_consistent(item["status"], explained[n]["explanation"]))
        if item["status"] == metrics.MISMATCH:
            actions.append(metrics.has_action(explained[n]["explanation"]))

    active = {r.type for r in reg.active_rights}
    cancelled_only = {r.type for r in reg.rights if r.cancelled} - active
    rights_rec = phantom = cancelled_active = None
    amount_ok = None
    if RIGHTS_FIELD in answered:
        text = explained[RIGHTS_FIELD]["explanation"]
        rep = metrics.rights_report(text, active, cancelled_only)
        rights_rec, phantom, cancelled_active = rep["recall"], rep["phantom"], rep["cancelled_as_active"]
        if reg.max_claim_amount > 0:
            amount_ok = float(metrics.mentions_amount(text, reg.max_claim_amount))

    payload = captured.get("payload", "")
    number_total = number_bad = fabricated_items = 0
    for n in answered:
        nums = metrics.extract_numbers(explained[n]["explanation"])
        bad = metrics.ungrounded_numbers(explained[n]["explanation"], payload)
        number_total += len(nums)
        number_bad += len(bad)
        fabricated_items += int(bool(bad))

    lengths = [len(explained[n]["explanation"]) for n in answered]
    return {
        "llm_call_ok": float(json_ok),
        "llm_items_answered": metrics.ratio(len(answered), len(targets)),
        # LLM 이 답했지만 서버 검사(output_guard)에서 버려진 항목의 비율. 아래 오류 지표는 검사를 통과한 설명만 재므로,
        # LLM 이 원래 저지른 오류의 크기는 이 값으로 본다.
        "llm_guard_rejected": metrics.ratio(sum(1 for n in targets if explained[n].get("guard")), len(targets)),
        "llm_citation_valid": metrics.ratio(raw_valid, raw_total),
        "llm_grounded": metrics.ratio(sum(1 for n in answered if explained[n]["grounded"]), len(answered)),
        "llm_citation_coverage": metrics.ratio(cite_covered, cite_groups),
        "llm_verdict_ok": metrics.ratio(sum(verdicts), len(verdicts)),
        "llm_mismatch_action": metrics.ratio(sum(actions), len(actions)),
        "llm_rights_recall": rights_rec,
        "llm_rights_phantom": phantom,
        "llm_rights_cancelled_as_active": cancelled_active,
        "llm_claim_amount_mentioned": amount_ok,
        "llm_number_ungrounded": metrics.ratio(number_bad, number_total),
        "llm_items_with_fabricated_number": metrics.ratio(fabricated_items, len(answered)),
        "llm_avg_chars": metrics.mean(lengths),
        "llm_over_200_chars": metrics.ratio(sum(1 for n in lengths if n > 200), len(lengths)),
    }


def _rejected_detail(item: dict, answer, name: str) -> dict:
    """서버 검사에서 버려진 항목이면 사유와 LLM 이 쓴 원문을 남긴다. (오탐인지 눈으로 확인하기 위해)"""
    if not item.get("guard"):
        return {}
    raw = answer.get(name) if isinstance(answer, dict) else None
    raw_text = raw.get("explanation") if isinstance(raw, dict) else raw
    return {"guard": item["guard"], "llm_text": raw_text if isinstance(raw_text, str) else None}


# ── 한 번 실행 ───────────────────────────────────────────────
def run_one(name: str, item: dict, config: Config, env: Environment, sample_dir: str, store: TrackingStore,
            indexed: dict, repeat_index: int = 0) -> dict:
    docs = load_sample_documents(ADDRESS, sample_dir, name)
    reg, bld = docs.registry, docs.building
    comparison = compare_documents(reg, bld)
    findings = build_findings(reg, bld, comparison)

    # 청킹·저장은 (청크 크기, overlap, 시나리오) 마다 한 번만 하고, 그때 걸린 시간을 index_s 로 기록한다.
    key = (config.chunk_size, config.chunk_overlap, name)
    if key not in indexed:
        tokens_before = store.index_tokens
        t0 = time.perf_counter()
        case_id = index_documents(store, reg, bld, config.chunk_size, config.chunk_overlap)
        indexed[key] = (case_id, time.perf_counter() - t0, store.index_tokens - tokens_before)
    case_id, index_s, index_tokens = indexed[key]

    query_before = store.query_tokens
    t0 = time.perf_counter()
    evidence = retrieve_evidence(store, case_id, config.top_k, config.strategy)
    retrieve_s = time.perf_counter() - t0

    record = {
        "scenario": name, "config": config.label, "repeat": repeat_index,
        "index_s": index_s, "retrieve_s": retrieve_s,
        "embed_tokens_index": index_tokens,
        "embed_tokens_query": store.query_tokens - query_before,
    }
    record.update(retrieval_metrics(evidence, reg, bld))

    targets = build_targets(comparison, evidence, findings)
    payload_text, allowed = build_payload(targets) if targets else ("", {})
    record["ctx_chars"] = len(payload_text)

    if config.prompt_version and targets:
        from app.services.llm_usage import UsageRecorder
        recorder = UsageRecorder()
        llm_call = env.make_llm_call(config, [recorder])
        captured: dict = {}

        def wrapped(payload):
            captured["payload"] = payload
            try:
                captured["answer"] = llm_call(payload)
            except Exception as e:
                captured["error"] = type(e).__name__
                raise
            return captured["answer"]

        t0 = time.perf_counter()
        explained = explain_with_evidence(comparison, evidence, findings, llm_call=wrapped)
        record["llm_s"] = time.perf_counter() - t0
        usage = recorder.summary()
        record.update({
            "llm_calls": usage["calls"], "llm_errors": usage["errors"], "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"], "llm_call_s": usage["latency_s"],
            "llm_missing_usage": usage["missing_usage"], "llm_error_type": captured.get("error"),
        })
        record.update(explanation_metrics(comparison, reg, bld, targets, allowed, captured, explained))
        record["explanations"] = {
            n: {"status": (comparison.get(n) or {}).get("status", "서버 집계"), "source": v["source"],
                "grounded": v["grounded"], "cited": [c["chunk_id"][-8:] for c in v["evidence"]], "text": v["explanation"],
                **_rejected_detail(v, captured.get("answer"), n)}
            for n, v in explained.items()
        }
    record["total_s"] = index_s + retrieve_s + record.get("llm_s", 0.0)
    return record


# ── 설정 조합 만들기 / 실행 ──────────────────────────────────
def expand_configs(phase: str, sizes: List[int], overlap_ratio: float, top_ks: List[int], strategies: List[str],
                   prompts: List[str], base: Config, json_mode: bool = False) -> List[Config]:
    def overlap(size: int) -> int:
        return min(int(size * overlap_ratio), size - 1)

    def dedupe(items: List[Config]) -> List[Config]:
        # adaptive 는 K 와 무관하므로 청크 크기당 한 번만 잰다
        seen, out = set(), []
        for c in items:
            key = c.label
            if key not in seen:
                seen.add(key)
                out.append(c)
        return out

    if phase == "retrieval":
        return dedupe([Config(s, overlap(s), k, st, None) for s, k, st in product(sizes, top_ks, strategies)])
    if phase == "prompt":
        return [Config(base.chunk_size, base.chunk_overlap, base.top_k, base.strategy, p, json_mode) for p in prompts]
    if phase == "full":
        return dedupe([Config(s, overlap(s), k, st, p, json_mode) for s, k, st, p in product(sizes, top_ks, strategies, prompts)])
    raise ValueError(f"알 수 없는 phase 입니다: {phase}")


def run_all(configs: List[Config], scenarios: Dict[str, dict], env: Environment, sample_dir: str, repeat: int = 1,
            progress: Optional[Callable[[str], None]] = None) -> List[dict]:
    records = []
    stores: Dict[tuple, TrackingStore] = {}
    indexed: dict = {}
    for ci, config in enumerate(configs, 1):
        size_key = (config.chunk_size, config.chunk_overlap)
        if size_key not in stores:
            stores[size_key] = env.make_store(*size_key)
        store = stores[size_key]
        n_repeat = repeat if config.prompt_version else 1
        for name, item in scenarios.items():
            for r in range(n_repeat):
                records.append(run_one(name, item, config, env, sample_dir, store, indexed, r))
        if progress:
            progress(f"[{ci}/{len(configs)}] {config.label}")
    return records


def aggregate(records: List[dict], input_price: Optional[float] = None, output_price: Optional[float] = None,
              embedding_price: Optional[float] = None) -> List[dict]:
    """설정별 평균(또는 백분위수). 가격을 주면 분석 1건당 비용도 계산한다."""
    groups: Dict[str, List[dict]] = {}
    for rec in records:
        groups.setdefault(rec["config"], []).append(rec)

    out = []
    for label, recs in groups.items():
        row: dict = {"config": label, "runs": len(recs)}
        for key in sorted({k for r in recs for k, v in r.items() if isinstance(v, (int, float)) and not isinstance(v, bool)
                           and k not in ("repeat",)}):
            row[key] = metrics.mean(r.get(key) for r in recs)
        for stage in ("retrieve_s", "llm_s", "total_s"):
            vals = [r[stage] for r in recs if stage in r]
            row[f"{stage}_p50"] = metrics.percentile(vals, 50)
            row[f"{stage}_p95"] = metrics.percentile(vals, 95)
        if any("prompt_tokens" in r for r in recs):
            llm_recs = [r for r in recs if "prompt_tokens" in r]
            cost = [metrics.token_cost(r["prompt_tokens"], r["completion_tokens"], input_price, output_price) for r in llm_recs]
            row["llm_cost_per_analysis"] = metrics.mean(cost) if None not in cost else None
        embed = [r["embed_tokens_index"] + r["embed_tokens_query"] for r in recs]
        row["embed_tokens_per_analysis"] = metrics.mean(embed)
        row["embed_cost_per_analysis"] = (row["embed_tokens_per_analysis"] * embedding_price / 1e6
                                          if embedding_price is not None else None)
        out.append(row)
    return out
