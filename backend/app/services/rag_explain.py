# backend/app/services/rag_explain.py
"""
검색된 근거 청크만으로 항목별 설명을 만든다 (RAG).

원칙
- 판정(일치/불일치/비교불가)과 위험 점수는 서버 규칙이 정한다. LLM 은 그 판정을 "설명"하고 근거를 "인용"만 한다.
- LLM 에는 서버가 검색한 청크(이미 개인정보가 마스킹된 텍스트)와 비교 값만 준다. 원본 문서 전체는 주지 않는다.
- LLM 이 인용한 청크 별칭(E1, E2 ...)은 그 항목에 실제로 제공한 청크인지 확인한 뒤에만 근거로 인정한다.
- LLM 이 쓴 설명은 서버가 규칙으로 다시 검사한다(output_guard). 근거에 없는 숫자나 문서에 없는 권리를 말하면 버린다.
- LLM 을 못 쓰거나(키 없음, 오류, 형식 불량) 근거가 없으면 기본 문장으로 대체한다. 분석은 멈추지 않는다.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from app.services.document_compare import UNKNOWN, default_explanation
from app.services.output_guard import check_explanation

logger = logging.getLogger(__name__)

RIGHTS_FIELD = "권리사항"
MAX_EXPLANATION_CHARS = 400

DOC_LABEL = {"registry": "등기부", "building": "건축물대장"}

# llm_call(payload_text) -> {항목: {"explanation": str, "evidence_ids": [별칭]}}
LlmCall = Callable[[str], dict]


def _clean(text: str) -> str:
    # 청크 안의 꺾쇠가 프롬프트의 구분 태그와 섞이지 않게 한다.
    return (text or "").replace("<", "＜").replace(">", "＞")


def _public_chunk(chunk: dict) -> dict:
    return {
        "chunk_id": chunk.get("chunk_id"),
        "doc_type": chunk.get("doc_type"),
        "section": chunk.get("section"),
        "rank_no": chunk.get("rank_no"),
        "page_no": chunk.get("page_no"),
        "text": chunk.get("text"),
    }


def rights_default_explanation(findings: dict) -> str:
    rights = findings.get("위험_권리_목록") or []
    if not rights:
        return "등기부등본에서 현재 유효한 근저당·압류·가압류 등 위험 권리는 확인되지 않았습니다. 계약 전 원본을 다시 확인하세요."
    text = f"등기부등본에 현재 유효한 권리가 확인됩니다: {', '.join(rights)}."
    pledge = int(findings.get("채권최고액") or 0)
    if pledge > 0:
        text += f" 근저당 채권최고액 합계는 {pledge:,}원입니다."
    return text


def _rights_fact(findings: dict) -> str:
    rights = findings.get("위험_권리_목록") or []
    pledge = int(findings.get("채권최고액") or 0)
    return f"현재 유효한 위험 권리: {', '.join(rights) if rights else '없음'} / 근저당 채권최고액 합계: {pledge:,}원"


def build_targets(comparison: dict, evidence: dict, findings: dict) -> dict:
    """LLM 에 물어볼 항목 → {status_text, fact, chunks}. 근거 청크가 없거나 비교불가인 항목은 뺀다."""
    targets = {}
    for name, item in comparison.items():
        chunks = evidence.get(name) or []
        if item["status"] == UNKNOWN or not chunks:
            continue
        fact = f"등기부='{item['reg_value'] or '정보 없음'}' / 건축물대장='{item['bld_value'] or '정보 없음'}'"
        targets[name] = {"status": item["status"], "fact": fact, "chunks": chunks}
    rights_chunks = evidence.get(RIGHTS_FIELD) or []
    if rights_chunks:
        targets[RIGHTS_FIELD] = {"status": "서버 집계", "fact": _rights_fact(findings), "chunks": rights_chunks}
    return targets


def build_payload(targets: dict):
    """(프롬프트에 넣을 텍스트, {항목: {별칭: 청크}}). 같은 청크는 항목이 달라도 같은 별칭을 쓴다."""
    aliases: dict = {}          # chunk_id → 별칭
    allowed: dict = {}          # 항목 → {별칭: 청크}
    blocks = []
    for name, target in targets.items():
        allowed[name] = {}
        lines = [f"[항목] {name}", f"판정: {target['status']}", f"값: {target['fact']}", "근거 청크:"]
        for chunk in target["chunks"]:
            alias = aliases.setdefault(chunk["chunk_id"], f"E{len(aliases) + 1}")
            allowed[name][alias] = chunk
            label = DOC_LABEL.get(chunk.get("doc_type"), chunk.get("doc_type") or "문서")
            lines.append(f"<{alias} 출처={label}/{chunk.get('section') or ''}>")
            lines.append(_clean(chunk.get("text")))
            lines.append(f"</{alias}>")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks), allowed


def _default_llm_call(payload: str) -> dict:
    # LangChain 체인 (프롬프트 버전은 EXPLAIN_PROMPT_VERSION). OPENAI_API_KEY 가 없으면 여기서 예외 → 기본 문장으로 대체
    from app.services.explain_chain import get_default_llm_call
    return get_default_llm_call()(payload)


def _parse_item(raw, allowed_for_item: dict):
    """LLM 응답 한 항목 → (설명, [청크]) 또는 None(쓸 수 없음)."""
    if isinstance(raw, str):
        raw = {"explanation": raw, "evidence_ids": []}
    if not isinstance(raw, dict):
        return None
    text = raw.get("explanation")
    if not isinstance(text, str) or not text.strip():
        return None
    ids = raw.get("evidence_ids")
    cited, seen = [], set()
    for alias in ids if isinstance(ids, list) else []:
        chunk = allowed_for_item.get(alias) if isinstance(alias, str) else None
        if chunk is not None and alias not in seen:      # 제공하지 않은 청크를 인용하면 버린다
            seen.add(alias)
            cited.append(chunk)
    return text.strip()[:MAX_EXPLANATION_CHARS], cited


def explain_with_evidence(comparison: dict, evidence: dict, findings: dict, llm_call: Optional[LlmCall] = None) -> dict:
    """
    반환: {항목: {"explanation", "source": "llm"|"default", "grounded": bool, "evidence": [청크...]}}
    서버 검사에서 LLM 설명이 버려진 항목은 source="default" 이고 "guard" 에 사유 목록이 들어 있다.
    comparison 의 모든 항목과 RIGHTS_FIELD 를 포함한다.
    """
    result = {
        name: {"explanation": default_explanation(name, item), "source": "default", "grounded": False, "evidence": []}
        for name, item in comparison.items()
    }
    result[RIGHTS_FIELD] = {
        "explanation": rights_default_explanation(findings), "source": "default", "grounded": False, "evidence": [],
    }

    targets = build_targets(comparison, evidence or {}, findings)
    if not targets:
        return result

    payload, allowed = build_payload(targets)
    try:
        answer = (llm_call or _default_llm_call)(payload)
    except Exception as e:
        logger.warning("근거 기반 설명 생성 실패, 기본 문장으로 대체합니다: %s", type(e).__name__)
        return result
    if not isinstance(answer, dict):
        logger.warning("근거 기반 설명 응답 형식이 올바르지 않아 기본 문장으로 대체합니다.")
        return result

    active_rights = set(findings.get("위험_권리_목록") or [])
    for name in targets:
        parsed = _parse_item(answer.get(name), allowed[name])
        if parsed is None:
            continue
        text, cited = parsed
        # 서버가 확인할 수 있는 잘못(근거에 없는 숫자, 없는 권리, 빠뜨린 권리)이 있으면 LLM 설명을 버리고 기본 문장을 쓴다.
        source = "\n".join([targets[name]["fact"]] + [c.get("text") or "" for c in targets[name]["chunks"]])
        reasons = check_explanation(name, text, source, active_rights, RIGHTS_FIELD)
        if reasons:
            logger.warning("LLM 설명이 서버 검사를 통과하지 못해 기본 문장으로 대체합니다: %s / %s", name, reasons)
            result[name]["guard"] = reasons
            continue
        result[name] = {
            "explanation": text,
            "source": "llm",
            "grounded": bool(cited),
            "evidence": [_public_chunk(c) for c in cited],
        }
    return result
