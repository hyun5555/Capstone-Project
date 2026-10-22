"""법률 챗봇 전용 평가: python -m evaluation.chatbot [--dry-run] [--yes]."""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path


SCENARIOS = [
    ("계약 전", "등기부등본에서 무엇을 확인해야 하나요?", {"hug-contract-checklist"}),
    ("계약 전", "임대인과 소유자가 같은지 어떻게 확인하나요?", {"hug-owner-check"}),
    ("계약 전", "전세보증보험 가입 가능 여부는 언제 확인하나요?", {"hug-return-guarantee-process"}),
    ("계약 전", "안전한 공인중개사무소인지 확인하는 방법을 알려주세요.", {"hug-realtor-check"}),
    ("계약 중", "계약서에서 반드시 확인할 항목을 알려주세요.", {"hug-contract-checklist"}),
    ("계약 중", "전세사기 예방 특약에는 무엇을 넣어야 하나요?", {"hug-special-terms"}),
    ("계약 중", "계약금을 누구 계좌로 보내야 하나요?", {"hug-deposit-account"}),
    ("계약 중", "잔금 전에 등기부를 다시 확인해야 하나요?", {"hug-contract-checklist"}),
    ("계약 후", "전입신고와 확정일자는 언제 받아야 하나요?", {"housing-lease-act-article-3", "housing-lease-act-article-3-2"}),
    ("계약 후", "임대차계약 신고 방법을 알려주세요.", {"rtms-rental-report"}),
    ("계약 후", "전세보증금 반환보증 가입 절차를 알려주세요.", {"hug-return-guarantee-process"}),
    ("계약 후", "보증금을 돌려받지 못할 때 무엇부터 해야 하나요?", {"housing-lease-act-article-3-3"}),
]

OUT_OF_SCOPE = [
    "오늘 날씨가 어떤가요?",
    "파이썬 정렬 코드를 알려주세요.",
    "저녁 메뉴를 추천해 주세요.",
    "영어 이메일을 번역해 주세요.",
    "주식 종목을 추천해 주세요.",
]


def _fake_llm():
    from langchain_core.messages import AIMessage
    from langchain_core.runnables import RunnableLambda
    return RunnableLambda(lambda _: AIMessage(content="검색된 공식 자료를 확인하세요. [1]"))


def run_suite(store, llm, effort: str, corpus_path: str, chunk_size: int, overlap: int, top_k: int) -> dict:
    from app.services.legal_rag import CITATION, answer_legal_question
    from app.services.llm_usage import UsageRecorder
    from evaluation.metrics import percentile

    records = []
    for stage, question, expected in SCENARIOS + [(None, q, set()) for q in OUT_OF_SCOPE]:
        usage = UsageRecorder()
        started = time.perf_counter()
        result = answer_legal_question(
            question, stage=stage, store=store, llm=llm, corpus_path=corpus_path,
            chunk_size=chunk_size, chunk_overlap=overlap, top_k=top_k,
            callbacks=[usage], include_debug=True,
        )
        elapsed = time.perf_counter() - started
        retrieved = set(result.get("debug", {}).get("retrieved_source_ids", []))
        cited = {int(value) for value in CITATION.findall(result["answer"])}
        returned = {source["number"] for source in result["sources"]}
        u = usage.summary()
        records.append({
            "stage": stage,
            "question": question,
            "out_of_scope": not expected,
            "mode": result["mode"],
            "expected_source_ids": sorted(expected),
            "retrieved_source_ids": sorted(retrieved),
            "retrieval_hits": len(expected & retrieved),
            "retrieval_total": len(expected),
            "wrong_citation": bool(cited - returned),
            "prompt_tokens": u["prompt_tokens"],
            "completion_tokens": u["completion_tokens"],
            "llm_calls": u["calls"],
            "latency_s": elapsed,
            "answer": result["answer"],
        })

    in_scope = [record for record in records if not record["out_of_scope"]]
    outside = [record for record in records if record["out_of_scope"]]
    latencies = [record["latency_s"] for record in records]
    return {
        "reasoning_effort": effort,
        "metrics": {
            "retrieval_top_k_recall": sum(r["retrieval_hits"] for r in in_scope) / sum(r["retrieval_total"] for r in in_scope),
            "wrong_citation_rate": sum(r["wrong_citation"] for r in in_scope) / len(in_scope),
            "out_of_scope_refusal_rate": sum(r["mode"] == "insufficient" for r in outside) / len(outside),
            "answer_rate": sum(r["mode"] == "rag" for r in in_scope) / len(in_scope),
            "prompt_tokens": sum(r["prompt_tokens"] for r in records),
            "completion_tokens": sum(r["completion_tokens"] for r in records),
            "llm_calls": sum(r["llm_calls"] for r in records),
            "latency_p50_s": percentile(latencies, 50),
            "latency_p95_s": percentile(latencies, 95),
        },
        "records": records,
    }


def render_report(meta: dict, suites: list[dict]) -> str:
    lines = ["# 챗봇 평가 결과", "", f"실행 시각: {meta['started']} / 모델: {meta['model']} / Top-K: {meta['top_k']}"]
    if meta["dry_run"]:
        lines += ["", "> DRY RUN: 가짜 임베딩과 답변으로 평가 배관만 확인했습니다."]
    lines += ["", "| reasoning | 검색 재현율 | 잘못된 인용 | 범위 밖 거절 | 답변률 | 입력/출력 토큰 | p50/p95(s) |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for suite in suites:
        m = suite["metrics"]
        lines.append(
            f"| {suite['reasoning_effort']} | {m['retrieval_top_k_recall']:.1%} | {m['wrong_citation_rate']:.1%} | "
            f"{m['out_of_scope_refusal_rate']:.1%} | {m['answer_rate']:.1%} | {m['prompt_tokens']}/{m['completion_tokens']} | "
            f"{m['latency_p50_s']:.2f}/{m['latency_p95_s']:.2f} |"
        )
    lines += ["", "## 질문별 결과", "", "| reasoning | 단계 | 질문 | mode | 검색 적중 | 지연(s) |",
              "| --- | --- | --- | --- | --- | --- |"]
    for suite in suites:
        for record in suite["records"]:
            hit = "-" if not record["retrieval_total"] else f"{record['retrieval_hits']}/{record['retrieval_total']}"
            lines.append(
                f"| {suite['reasoning_effort']} | {record['stage'] or '범위 밖'} | {record['question']} | "
                f"{record['mode']} | {hit} | {record['latency_s']:.2f} |"
            )
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true", help="실제 API 호출 확인을 건너뜁니다.")
    parser.add_argument("--reasoning", default="none,low")
    parser.add_argument("--out-dir", default="eval_results/chatbot")
    args = parser.parse_args(argv)
    if args.dry_run:
        os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        os.environ.setdefault("SECRET_KEY", "dry-run-secret-key-at-least-32-bytes")

    from app.config import CHUNK_OVERLAP, CHUNK_SIZE, LEGAL_CORPUS_PATH, LLM_MODEL, RETRIEVAL_TOP_K
    efforts = [value.strip() for value in args.reasoning.split(",") if value.strip()]
    if not args.dry_run and not args.yes:
        if input(f"OpenAI LLM을 최대 {len(efforts) * len(SCENARIOS)}회 호출합니다. 계속할까요? (y/N) ").strip().lower() != "y":
            return 1

    real = None
    if args.dry_run:
        from app.services.chunk_store import ChunkStore
        from evaluation.fake_store import FakeCollection
        store, make_llm = ChunkStore(FakeCollection()), lambda _: _fake_llm()
    else:
        from evaluation.env import RealEnvironment
        from app.services.explain_chain import get_llm
        real = RealEnvironment()
        store, make_llm = real.make_store(CHUNK_SIZE, CHUNK_OVERLAP), lambda effort: get_llm(reasoning_effort=effort)

    try:
        suites = [run_suite(store, make_llm(effort), effort, LEGAL_CORPUS_PATH, CHUNK_SIZE, CHUNK_OVERLAP, RETRIEVAL_TOP_K)
                  for effort in efforts]
    finally:
        if real:
            real.close()

    meta = {"started": datetime.now().isoformat(timespec="seconds"), "model": LLM_MODEL,
            "top_k": RETRIEVAL_TOP_K, "dry_run": args.dry_run}
    directory = Path(args.out_dir) / (datetime.now().strftime("%Y%m%d-%H%M%S") + ("-dry" if args.dry_run else ""))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "results.json").write_text(json.dumps({"meta": meta, "suites": suites}, ensure_ascii=False, indent=2), encoding="utf-8")
    report = render_report(meta, suites)
    (directory / "report.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"저장했습니다: {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
