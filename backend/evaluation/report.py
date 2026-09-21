# backend/evaluation/report.py
"""집계 결과를 사람이 읽는 마크다운으로 만든다."""
from typing import List, Optional


def pct(x: Optional[float]) -> str:
    return "-" if x is None else f"{x * 100:.0f}%"


def num(x: Optional[float], digits: int = 1) -> str:
    return "-" if x is None else f"{x:.{digits}f}"


def ms(x: Optional[float]) -> str:
    return "-" if x is None else f"{x * 1000:.0f}"


def money(x: Optional[float], unit: str) -> str:
    return "가격 미입력" if x is None else f"{x:.5f} {unit}"


def _table(headers: List[str], rows: List[List[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def render(meta: dict, pipeline: List[dict], aggregates: List[dict], records: List[dict]) -> str:
    unit = meta.get("currency", "USD")
    out = ["# 평가 결과"]
    if meta.get("dry_run"):
        out.append("\n> DRY RUN: 가짜 임베딩과 가짜 LLM 으로 돌린 결과입니다. 배관 확인용이며 성능을 나타내지 않습니다.")
    out.append(
        f"\n실행 시각 {meta['started']} / LLM {meta['llm_model']} / 임베딩 {meta['embedding_model']} / "
        f"시나리오 {meta['scenarios']}개 / LLM 설정당 반복 {meta['repeat']}회"
    )
    if meta.get("input_price") is None:
        out.append("\nLLM 가격(--input-price, --output-price)을 입력하지 않아 비용은 계산하지 않았습니다. 토큰 수는 기록했습니다.")

    ok = sum(1 for p in pipeline if p["ok"])
    out.append(f"\n## 1. 규칙 기반 판정 정확도: {ok}/{len(pipeline)}")
    out.append("소유자 일치 여부, 유효 권리 목록, 위험 점수, 등급이 시나리오 기대값과 같은지 확인합니다. LLM 과 설정에 영향을 받지 않습니다.\n")
    out.append(_table(
        ["시나리오", "소유자", "유효 권리", "점수", "등급", "결과"],
        [[p["scenario"], "O" if p["checks"]["owner_status"] else "X", "O" if p["checks"]["active_rights"] else "X",
          f"{p['score']}", p["grade"], "통과" if p["ok"] else "실패"] for p in pipeline],
    ))

    retrieval = [a for a in aggregates if a["config"].startswith("prompt=- ")]
    llm = [a for a in aggregates if not a["config"].startswith("prompt=- ")]

    if retrieval:
        out.append("\n## 2. 근거 검색 (LLM 호출 없음)")
        out.append(
            "근거 적중률은 정답 청크 묶음 중 검색된 비율, 항목 완전 충족은 필요한 묶음을 모두 찾은 항목의 비율, "
            "불필요 청크는 정답 묶음에 속하지 않는 검색 결과의 비율입니다. 프롬프트 글자수는 LLM 에 들어가는 근거 크기의 대리 지표입니다.\n"
        )
        out.append(_table(
            ["설정", "근거 적중률", "항목 완전 충족", "권리 근거 재현율", "불필요 청크", "프롬프트 글자수",
             "검색 p50/p95 (ms)", "임베딩 토큰/건"],
            [[a["config"].replace("prompt=- ", ""), pct(a.get("ret_coverage")), pct(a.get("ret_fields_complete")),
              pct(a.get("ret_rights_recall")), pct(a.get("ret_noise")), num(a.get("ctx_chars"), 0),
              f"{ms(a.get('retrieve_s_p50'))}/{ms(a.get('retrieve_s_p95'))}", num(a.get("embed_tokens_per_analysis"), 0)]
             for a in retrieval],
        ))

    if llm:
        out.append("\n## 3. LLM 설명 품질")
        out.append(
            "호출 성공은 JSON 응답을 받은 비율, 항목 응답률은 LLM 설명이 그대로 쓰인 항목의 비율(나머지는 기본 문장으로 대체), "
            "서버 검사 탈락은 LLM 이 답했지만 근거에 없는 숫자나 문서에 없는 권리, 빠뜨린 권리 때문에 버려진 항목의 비율로, "
            "이 값이 LLM 이 원래 저지른 오류의 크기입니다(아래 지어낸 권리, 말소 오인, 근거 밖 숫자는 검사를 통과한 설명만 재므로 0 에 가깝게 나옵니다). "
            "근거 인용은 유효한 인용이 하나 이상 있는 답변의 비율, 인용 유효는 LLM 이 적은 근거 번호가 실제 제공된 청크였던 비율, "
            "인용 적중은 인용한 청크가 정답 묶음을 채운 비율입니다. 판정 일관은 설명이 서버 판정과 모순되지 않은 비율, "
            "권리 재현은 유효한 권리를 빠뜨리지 않은 비율, 지어낸 권리와 말소 오인은 건수의 평균, 근거 밖 숫자는 근거 자료에 없는 숫자의 비율입니다.\n"
        )
        out.append(_table(
            ["설정", "호출 성공", "항목 응답률", "서버 검사 탈락", "근거 인용", "인용 유효", "인용 적중", "판정 일관", "권리 재현",
             "지어낸 권리", "말소 오인", "근거 밖 숫자", "평균 글자수"],
            [[a["config"], pct(a.get("llm_call_ok")), pct(a.get("llm_items_answered")), pct(a.get("llm_guard_rejected")), pct(a.get("llm_grounded")),
              pct(a.get("llm_citation_valid")), pct(a.get("llm_citation_coverage")), pct(a.get("llm_verdict_ok")),
              pct(a.get("llm_rights_recall")), num(a.get("llm_rights_phantom"), 2),
              num(a.get("llm_rights_cancelled_as_active"), 2), pct(a.get("llm_number_ungrounded")), num(a.get("llm_avg_chars"), 0)]
             for a in llm],
        ))
        out.append("\n## 4. 지연, 토큰, 비용 (분석 1건 기준)")
        out.append("총 지연은 청킹과 임베딩 저장, 근거 검색, LLM 호출을 합한 값입니다. 호출 수가 1보다 크면 형식 검증 실패로 재시도한 것입니다.\n")
        out.append(_table(
            ["설정", "LLM 호출 수", "입력 토큰", "출력 토큰", "LLM p50/p95 (s)", "총 p50/p95 (s)", f"LLM 비용/건 ({unit})",
             f"임베딩 비용/건 ({unit})"],
            [[a["config"], num(a.get("llm_calls"), 2), num(a.get("prompt_tokens"), 0), num(a.get("completion_tokens"), 0),
              f"{num(a.get('llm_s_p50'), 2)}/{num(a.get('llm_s_p95'), 2)}", f"{num(a.get('total_s_p50'), 2)}/{num(a.get('total_s_p95'), 2)}",
              money(a.get("llm_cost_per_analysis"), unit), money(a.get("embed_cost_per_analysis"), unit)]
             for a in llm],
        ))

        out.append("\n## 5. 설명 원문 (각 설정의 첫 번째 반복)")
        out.append("자동 지표가 잡지 못하는 어색한 문장이나 잘못된 설명은 여기서 눈으로 확인합니다. 서버 검사에서 버려진 항목은 LLM 원문을 함께 보여 주니, 검사가 멀쩡한 설명을 오탐했는지 확인하세요.\n")
        for a in llm:
            out.append(f"### {a['config']}")
            first = [r for r in records if r["config"] == a["config"] and r.get("repeat") == 0 and "explanations" in r]
            for r in first:
                out.append(f"- **{r['scenario']}**")
                for field, e in r["explanations"].items():
                    tag = f"{e['source']}, 인용 {len(e['cited'])}건"
                    out.append(f"  - {field} ({e['status']}, {tag}): {e['text']}")
                    if e.get("guard"):
                        out.append(f"    - 서버 검사 탈락 {e['guard']}, LLM 원문: {e.get('llm_text')}")
    return "\n".join(out) + "\n"
