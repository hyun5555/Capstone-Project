# backend/evaluation/__main__.py
"""
사용법 (backend 폴더에서, 가상환경을 켠 상태로):

  python -m evaluation --dry-run                       # 키·비용 없이 배관만 확인 (가짜 부품)
  python -m evaluation --phase retrieval               # 청크 크기 x Top-K x 검색 전략. 임베딩만 사용, LLM 호출 없음
  python -m evaluation --phase prompt --repeat 3 \\
      --chunk-size 600 --top-k 3 --strategy balanced \\
      --input-price 0.5 --output-price 2.0             # 프롬프트 v1 vs v2. 가격은 100만 토큰당 USD (직접 입력)
  python -m evaluation --phase full --yes              # 모든 조합 (LLM 호출 수가 많으니 예상 호출 수를 먼저 확인)

결과는 eval_results/<실행시각>/ 에 results.json 과 report.md 로 저장된다.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path


def _ints(text: str):
    return [int(x) for x in text.split(",") if x.strip()]


def _strs(text: str):
    return [x.strip() for x in text.split(",") if x.strip()]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m evaluation", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--phase", choices=["retrieval", "prompt", "full"], default="retrieval")
    p.add_argument("--dry-run", action="store_true", help="가짜 임베딩/LLM 으로 배관만 확인 (API 키 불필요)")
    p.add_argument("--yes", action="store_true", help="LLM 호출 수를 확인하는 질문을 건너뛴다")
    p.add_argument("--scenarios", default="", help="쉼표로 구분한 시나리오 이름 (기본: 전체)")
    p.add_argument("--repeat", type=int, default=3, help="LLM 설정당 반복 횟수 (temperature=1 이라 출력이 매번 달라진다)")
    p.add_argument("--chunk-sizes", default="60,120,300,600", help="retrieval/full 에서 비교할 청크 크기")
    p.add_argument("--overlap-ratio", type=float, default=0.15, help="청크 크기 대비 overlap 비율")
    p.add_argument("--top-ks", default="1,2,3,5", help="retrieval/full 에서 비교할 Top-K")
    p.add_argument("--strategies", default="plain,balanced,adaptive", help="검색 전략 (plain, balanced, adaptive)")
    p.add_argument("--prompts", default="v1,v2", help="비교할 프롬프트 버전")
    p.add_argument("--chunk-size", type=int, default=None, help="prompt phase 에서 고정할 청크 크기 (기본: 설정값)")
    p.add_argument("--top-k", type=int, default=None, help="prompt phase 에서 고정할 Top-K (기본: 설정값)")
    p.add_argument("--strategy", default=None, help="prompt phase 에서 고정할 검색 전략 (기본: 설정값)")
    p.add_argument("--json-mode", action="store_true", help="v1만 OpenAI JSON 모드로 호출(v2는 Structured Outputs 고정)")
    p.add_argument("--input-price", type=float, default=None, help="LLM 입력 가격 (100만 토큰당). 모르면 비워 둔다")
    p.add_argument("--output-price", type=float, default=None, help="LLM 출력 가격 (100만 토큰당). 모르면 비워 둔다")
    p.add_argument("--embedding-price", type=float, default=0.02, help="임베딩 가격 (100만 토큰당, 기본 text-embedding-3-small 공시가)")
    p.add_argument("--currency", default="USD")
    p.add_argument("--out-dir", default="eval_results")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        os.environ.setdefault("SECRET_KEY", "dry-run-secret-key-at-least-32-bytes")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    from app.config import (
        CHUNK_OVERLAP, CHUNK_SIZE, CODEF_SAMPLE_DIR, EMBEDDING_MODEL, LLM_MODEL, RETRIEVAL_STRATEGY, RETRIEVAL_TOP_K,
    )
    from evaluation import report
    from evaluation.runner import (
        Config, aggregate, expand_configs, load_scenarios, pipeline_check, run_all,
    )

    scenarios = load_scenarios(CODEF_SAMPLE_DIR, _strs(args.scenarios) or None)
    size = args.chunk_size or CHUNK_SIZE
    base = Config(size, min(int(size * args.overlap_ratio), size - 1) if args.chunk_size else CHUNK_OVERLAP,
                  args.top_k or RETRIEVAL_TOP_K, (args.strategy or RETRIEVAL_STRATEGY))
    configs = expand_configs(args.phase, _ints(args.chunk_sizes), args.overlap_ratio, _ints(args.top_ks),
                             _strs(args.strategies), _strs(args.prompts), base, args.json_mode)

    llm_configs = [c for c in configs if c.prompt_version]
    est_calls = len(llm_configs) * len(scenarios) * args.repeat
    print(f"시나리오 {len(scenarios)}개, 설정 {len(configs)}개, 예상 LLM 호출 {est_calls}회", flush=True)
    if est_calls and not args.dry_run and not args.yes:
        try:
            if input("실제 OpenAI API 를 호출합니다. 계속할까요? (y/N) ").strip().lower() != "y":
                print("중단했습니다.")
                return 1
        except EOFError:
            print("확인할 수 없어 중단했습니다. --yes 를 붙여 다시 실행하세요.")
            return 1

    real = None
    if args.dry_run:
        from evaluation.env import build_dry_env
        env = build_dry_env()
    else:
        from evaluation.env import RealEnvironment
        real = RealEnvironment()
        env = real.environment()

    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    t0 = time.perf_counter()
    try:
        pipeline = [pipeline_check(n, item, CODEF_SAMPLE_DIR) for n, item in scenarios.items()]
        records = run_all(configs, scenarios, env, CODEF_SAMPLE_DIR, args.repeat, progress=lambda m: print(m, flush=True))
    finally:
        if real:
            real.close()

    aggregates = aggregate(records, args.input_price, args.output_price, args.embedding_price)
    meta = {
        "started": started, "elapsed_s": round(time.perf_counter() - t0, 1), "dry_run": args.dry_run,
        "phase": args.phase, "llm_model": LLM_MODEL, "embedding_model": EMBEDDING_MODEL, "scenarios": len(scenarios),
        "repeat": args.repeat, "input_price": args.input_price, "output_price": args.output_price,
        "embedding_price": args.embedding_price, "currency": args.currency, "json_mode": args.json_mode,
    }
    out_dir = Path(args.out_dir) / (datetime.now().strftime("%Y%m%d-%H%M%S") + ("-dry" if args.dry_run else ""))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps({"meta": meta, "pipeline": pipeline, "aggregates": aggregates, "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    text = report.render(meta, pipeline, aggregates, records)
    (out_dir / "report.md").write_text(text, encoding="utf-8")
    print(text.split("## 5.")[0])          # 설명 원문(5절)은 길어서 파일에만 저장한다
    print(f"저장했습니다: {out_dir}/report.md, {out_dir}/results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
