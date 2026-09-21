# backend/app/services/document_compare.py
"""
등기부등본 ↔ 건축물대장 비교 (서버 규칙 기반).

핵심 원칙
- 한쪽(또는 양쪽)에 값이 없으면 "불일치" 도, 빈 문자열("없음")과의 비교도 하지 않고 "비교불가" 로 둔다.
  (건축물대장에 원래 없는 값을 없음으로 채워 넣으면 항상 불일치가 되어 위험 점수가 왜곡된다.)
- 명확한 값(숫자·연도·이름)은 규칙으로 판정한다. 표현이 달라 보이는 용도/구조만 semantic_judge(LLM) 에 물어볼 수 있다.
- 결과에 담기는 표시용 값(reg_value / bld_value)은 소유자 이름을 마스킹한 값이다. 원문 이름은 밖으로 나가지 않는다.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from app.services.documents import (
    COMPARABLE_FIELDS, SEMANTIC_FIELDS, PropertyDoc, normalize_name, normalize_structure, usage_category,
)
from app.utils.masking import mask_person_name

MATCH = "일치"
MISMATCH = "불일치"
UNKNOWN = "비교불가"

AREA_TOLERANCE_RATIO = 0.01     # 면적은 1% 이내면 같은 값으로 본다 (표기 반올림 차이)
AREA_TOLERANCE_ABS = 0.05

# semantic_judge(field, reg_value, bld_value) -> "일치" | "불일치" | None(판단 못 함)
SemanticJudge = Callable[[str, str, str], Optional[str]]


def _name_matches(a: str, b: str) -> bool:
    """이름 비교. 한쪽이 '홍*동' 처럼 마스킹돼 있으면 '*' 자리는 무시하고 비교한다."""
    a, b = normalize_name(a), normalize_name(b)
    if "*" not in a and "*" not in b:
        return a == b
    if len(a) != len(b):
        return False
    return all(x == y or x == "*" or y == "*" for x, y in zip(a, b))


def _compare_owners(reg: PropertyDoc, bld: PropertyDoc) -> dict:
    if not reg.owner_names or not bld.owner_names:
        return _item(UNKNOWN, _mask_names(reg.owner_names), _mask_names(bld.owner_names),
                     "한쪽 문서에서 소유자 정보를 확인하지 못했습니다.")
    unmatched_reg = [n for n in reg.owner_names if not any(_name_matches(n, b) for b in bld.owner_names)]
    unmatched_bld = [n for n in bld.owner_names if not any(_name_matches(n, r) for r in reg.owner_names)]
    masked = any("*" in n for n in reg.owner_names + bld.owner_names)
    note = "건축물대장 이름이 일부 가려져 있어 보이는 글자만 비교했습니다." if masked else ""
    status = MATCH if not unmatched_reg and not unmatched_bld else MISMATCH
    return _item(status, _mask_names(reg.owner_names), _mask_names(bld.owner_names), note)


def _mask_names(names: list) -> Optional[str]:
    return ", ".join(mask_person_name(n) for n in names) if names else None


def _item(status: str, reg_value, bld_value, note: str = "") -> dict:
    return {
        "status": status,
        "reg_value": None if reg_value is None else str(reg_value),
        "bld_value": None if bld_value is None else str(bld_value),
        "note": note,
    }


def _compare_number(a: Optional[float], b: Optional[float], unit: str = "") -> dict:
    if a is None or b is None:
        return _item(UNKNOWN, _fmt(a, unit), _fmt(b, unit), "한쪽 문서에 값이 없어 비교하지 않았습니다.")
    tol = max(AREA_TOLERANCE_ABS, max(abs(a), abs(b)) * AREA_TOLERANCE_RATIO)
    return _item(MATCH if abs(a - b) <= tol else MISMATCH, _fmt(a, unit), _fmt(b, unit))


def _fmt(v, unit: str = "") -> Optional[str]:
    if v is None:
        return None
    return f"{v:g}{unit}" if isinstance(v, float) else f"{v}{unit}"


def _compare_year(a: Optional[int], b: Optional[int]) -> dict:
    if a is None or b is None:
        return _item(UNKNOWN, a, b, "한쪽 문서에 값이 없어 비교하지 않았습니다.")
    return _item(MATCH if a == b else MISMATCH, a, b)


def _compare_text(field: str, a: Optional[str], b: Optional[str], judge: Optional[SemanticJudge]) -> dict:
    if not a or not b:
        return _item(UNKNOWN, a, b, "한쪽 문서에 값이 없어 비교하지 않았습니다.")

    if field == "건물 용도":
        ca, cb = usage_category(a), usage_category(b)
        if "미상" in (ca, cb):
            return _item(UNKNOWN, a, b, "용도를 분류하지 못했습니다.")
        same = (ca == cb and ca != "기타") or re.sub(r"\s+", "", a) == re.sub(r"\s+", "", b)
    else:
        na, nb = normalize_structure(a), normalize_structure(b)
        same = na == nb

    if same:
        return _item(MATCH, a, b)

    # 규칙으로는 다르다고 나온 경우에만 의미 비교(LLM)를 시도한다. 판단이 없으면 규칙 결과를 유지한다.
    if judge is not None:
        try:
            verdict = judge(field, a, b)
        except Exception:
            verdict = None
        if verdict in (MATCH, MISMATCH):
            return _item(verdict, a, b, "표현이 달라 의미 기준으로 판단했습니다.")
    return _item(MISMATCH, a, b)


def compare_documents(reg: PropertyDoc, bld: PropertyDoc, semantic_judge: Optional[SemanticJudge] = None) -> dict:
    """{필드명: {status, reg_value, bld_value, note}} — COMPARABLE_FIELDS 순서."""
    result = {}
    for name in COMPARABLE_FIELDS:
        if name == "소유자명":
            result[name] = _compare_owners(reg, bld)
        elif name == "전용면적":
            result[name] = _compare_number(reg.area_exclusive, bld.area_exclusive, "㎡")
        elif name == "연면적":
            result[name] = _compare_number(reg.area_total, bld.area_total, "㎡")
        elif name == "준공년도":
            result[name] = _compare_year(reg.build_year, bld.build_year)
        else:
            judge = semantic_judge if name in SEMANTIC_FIELDS else None
            a = reg.usage if name == "건물 용도" else reg.structure
            b = bld.usage if name == "건물 용도" else bld.structure
            result[name] = _compare_text(name, a, b, judge)
    return result


def default_explanation(field: str, item: dict) -> str:
    """LLM 없이도 항목 설명이 나오도록 하는 기본 문장."""
    status, a, b = item["status"], item["reg_value"], item["bld_value"]
    if status == UNKNOWN:
        return f"{field}: 두 문서 중 한쪽에 값이 없어 비교하지 못했습니다. (등기부: {a or '정보 없음'}, 건축물대장: {b or '정보 없음'})"
    if status == MATCH:
        return f"{field}: 등기부등본({a})과 건축물대장({b})이 일치합니다."
    return f"{field}: 등기부등본({a})과 건축물대장({b})이 서로 다릅니다. 계약 전에 원본을 직접 확인하세요."


def build_findings(reg: PropertyDoc, bld: PropertyDoc, comparison: dict) -> dict:
    """
    calculate_risk_score() 입력 형식으로 바꾼다.
    - 소유자_불일치: True(불일치) / False(일치) / None(비교불가). 비교불가는 위험으로 세지 않는다.
    - 위반건축물: True / False / None(건축물대장에서 확인하지 못함). None 은 위험으로 세지 않는다.
    - 용도분류: '주거' '오피스텔' '근린생활' '업무' ... '미상'. 미상이면 None 으로 넘겨 비주거로 오인하지 않게 한다.
    - 확인하지 못한 비교 항목은 별도로 unverified_fields 로 돌려준다.
    """
    owner_status = comparison["소유자명"]["status"]
    reg_owner = ", ".join(reg.owner_names)
    bld_owner = ", ".join(bld.owner_names) if owner_status == MISMATCH else reg_owner

    usage = bld.usage or reg.usage or ""
    category = usage_category(usage)
    return {
        "등기부_소유자": reg_owner,
        "건축물대장_소유자": bld_owner,
        "소유자_불일치": {MISMATCH: True, MATCH: False}.get(owner_status),
        "위험_권리_목록": sorted({r.type for r in reg.active_rights}),
        "채권최고액": reg.max_claim_amount,
        "위반건축물": bld.violation,
        "불법용도변경": False,
        "용도분류": None if category == "미상" else category,
        # 예전 형식 호환용: 주거/오피스텔은 '주거용' 으로 맞춰 준다.
        "건물 용도": "주거용" if category in ("주거", "오피스텔") else usage,
    }


def unverified_fields(comparison: dict) -> list:
    return [k for k, v in comparison.items() if v["status"] == UNKNOWN]
