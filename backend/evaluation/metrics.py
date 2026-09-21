# backend/evaluation/metrics.py
"""
평가 지표 계산 (순수 함수, 외부 의존 없음).

LLM 이 쓴 설명은 정답 문장과 비교할 수 없으므로 "규칙으로 확인할 수 있는 성질" 만 잰다.
 - 판정과 설명이 모순되지 않는가
 - 유효한 권리를 빠뜨리지 않았는가, 없는 권리를 지어내거나 말소된 권리를 유효하다고 하지 않았는가
 - 근거 자료에 없는 숫자(금액, 연도 등)를 쓰지 않았는가
 - 인용한 근거가 실제로 그 사실이 적힌 청크인가
문장이 자연스러운지 같은 품질은 자동으로 재지 않는다. 결과 파일에 설명 원문을 남기니 눈으로 함께 확인한다.
휴리스틱이라 오탐이 있을 수 있다. 값이 나빠 보이면 설명 원문을 먼저 확인한다.
"""
import math
from typing import Dict, Iterable, List, Optional, Set

# 서비스(output_guard)와 같은 함수를 쓴다. 서비스가 거르는 기준과 평가 기준이 같아야 한다.
from app.services.output_guard import (  # noqa: F401
    RIGHT_PATTERNS, asserted_rights, extract_numbers, mentioned_rights, mentions_amount, ungrounded_numbers,
)

MATCH, MISMATCH = "일치", "불일치"

MISMATCH_WORDS = ("불일치", "다릅니다", "다르게", "다른", "일치하지", "상이")
ACTION_WORDS = ("확인", "대조", "요청", "문의", "발급", "확정")


# ── 통계 ──────────────────────────────────────────────────────
def mean(values: Iterable[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def percentile(values: List[float], p: float) -> Optional[float]:
    """선형 보간 백분위수 (p: 0~100). 값이 없으면 None."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p / 100
    lo, hi = math.floor(rank), math.ceil(rank)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


def ratio(numerator: int, denominator: int) -> Optional[float]:
    return numerator / denominator if denominator else None


# ── 판정과 설명의 일관성 ──────────────────────────────────────
def verdict_consistent(status: str, explanation: str) -> bool:
    """일치 항목의 설명에 '다르다' 는 말이 없고, 불일치 항목의 설명에는 그 말이 있어야 한다."""
    says_different = any(w in explanation for w in MISMATCH_WORDS)
    if status == MATCH:
        return not says_different
    if status == MISMATCH:
        return says_different
    return True


def has_action(explanation: str) -> bool:
    return any(w in explanation for w in ACTION_WORDS)


# ── 권리 언급 ────────────────────────────────────────────────
def rights_report(explanation: str, active: Set[str], cancelled_only: Set[str]) -> dict:
    """
    recall: 유효한 권리 중 설명이 짚은 비율 (유효한 권리가 없으면 None)
    phantom: 문서에 없는 권리를 있다고 말한 종류 수
    cancelled_as_active: 말소된 권리를 현재 유효한 것처럼 말한 종류 수
    """
    asserted = asserted_rights(explanation)
    known = active | cancelled_only
    return {
        "recall": ratio(len(active & asserted), len(active)),
        "phantom": len(asserted - known),
        "cancelled_as_active": len((asserted & cancelled_only) - active),
    }


# ── 금액/숫자 근거 ────────────────────────────────────────────
# ── 근거 인용 ────────────────────────────────────────────────
def citation_validity(raw_ids: List[str], allowed: Iterable[str]) -> Dict[str, int]:
    allowed_set = set(allowed)
    valid = [i for i in raw_ids if i in allowed_set]
    return {"total": len(raw_ids), "valid": len(valid)}


# ── 비용 ─────────────────────────────────────────────────────
def token_cost(prompt_tokens: int, completion_tokens: int, input_price: Optional[float], output_price: Optional[float]) -> Optional[float]:
    """가격은 100만 토큰당. 가격을 모르면 None (임의 값으로 채우지 않는다)."""
    if input_price is None or output_price is None:
        return None
    return prompt_tokens * input_price / 1e6 + completion_tokens * output_price / 1e6


_ENCODER = []


def _encoder():
    """tiktoken 인코더 (한 번만 시도). 없거나 내려받지 못하면 None."""
    if not _ENCODER:
        try:
            import tiktoken
            _ENCODER.append(tiktoken.get_encoding("cl100k_base"))
        except Exception:
            _ENCODER.append(None)
    return _ENCODER[0]


def estimate_tokens(text: str) -> int:
    """임베딩 토큰 추정. tiktoken 이 있으면 그것을 쓰고, 없으면 글자 수 기반 근사(한글은 대략 글자당 1.5 토큰)."""
    enc = _encoder()
    if enc is not None:
        return len(enc.encode(text))
    return max(1, round(len(text) * 1.5))
