# backend/app/services/documents.py
"""
등기부등본 / 건축물대장을 하나의 공통 구조(PropertyDoc)로 표현하기 위한 모델과 정규화 유틸.

- 이 모듈은 외부 라이브러리(FastAPI, LangChain, ChromaDB)에 의존하지 않는다.
- "무엇을 비교할 수 있는가" 를 코드로 명시한다: 두 문서가 모두 제공하는 필드만 비교 대상이다.
  (채권최고액·권리사항은 등기부에만 있으므로 비교 대상이 아니라 위험 평가의 입력이다.)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# 위험 평가에 쓰는 권리 유형 (표기 통일)
RISK_RIGHT_TYPES = (
    "경매개시결정", "압류", "가압류", "가처분", "가등기", "신탁", "전세권", "임차권", "근저당권",
)

# 두 문서가 모두 제공해서 서로 비교할 수 있는 필드 (순서 = 화면 표시 순서)
COMPARABLE_FIELDS = ("소유자명", "건물 용도", "구조 유형", "전용면적", "연면적", "준공년도")

# 텍스트(의미) 비교가 필요한 필드 — 결정적 규칙으로 못 풀 때만 LLM 이 판단한다.
SEMANTIC_FIELDS = ("건물 용도", "구조 유형")


@dataclass
class Right:
    """등기부에서 추출한 권리 한 건."""
    type: str                       # RISK_RIGHT_TYPES 중 하나
    amount: int = 0                 # 채권최고액(원). 근저당권이 아니면 0
    rank_no: Optional[str] = None   # 순위번호 (예: "3")
    section: Optional[str] = None   # "갑구" | "을구" (말소 대상 순위번호를 같은 구 안에서 찾기 위함)
    cancelled: bool = False         # 말소된 권리는 위험 평가에서 제외


@dataclass
class Section:
    """문서를 청킹하기 전의 논리 구획 (표제부/갑구/을구/건축물 개요 등)."""
    name: str
    text: str
    rank_no: Optional[str] = None
    page_no: Optional[int] = None


@dataclass
class PropertyDoc:
    doc_type: str                              # "registry" | "building"
    address: str = ""
    owner_names: list[str] = field(default_factory=list)   # 개인정보: 서버 내부에서만 사용
    usage: Optional[str] = None
    structure: Optional[str] = None
    area_exclusive: Optional[float] = None
    area_total: Optional[float] = None
    build_year: Optional[int] = None
    rights: list[Right] = field(default_factory=list)
    violation: Optional[bool] = None           # 위반건축물 여부 (건축물대장)
    sections: list[Section] = field(default_factory=list)

    @property
    def active_rights(self) -> list[Right]:
        return [r for r in self.rights if not r.cancelled]

    @property
    def max_claim_amount(self) -> int:
        """말소되지 않은 근저당권 채권최고액 합계(원)."""
        return sum(r.amount for r in self.active_rights if r.type == "근저당권")

    def field_value(self, name: str):
        """COMPARABLE_FIELDS 이름으로 값을 꺼낸다 (없으면 None)."""
        return {
            "소유자명": self.owner_names or None,
            "건물 용도": self.usage,
            "구조 유형": self.structure,
            "전용면적": self.area_exclusive,
            "연면적": self.area_total,
            "준공년도": self.build_year,
        }.get(name)


# ─────────────────────────────────────────────────────────────
# 값 정규화
# ─────────────────────────────────────────────────────────────

def parse_amount_won(text: str) -> int:
    """
    '금120,000,000원', '채권최고액 금 1억2천만원' 같은 문자열에서 금액(원)을 뽑는다.
    숫자 표기가 있으면 그것을 우선하고, 없으면 억/천만/만 단위 한글 표기를 해석한다.
    """
    if not text:
        return 0
    m = re.search(r"(\d[\d,./\s]*\d|\d)\s*원", text)
    if m:
        return int(re.sub(r"\D", "", m.group(1)))
    total = 0
    matched = False
    for pattern, unit in ((r"(\d+)\s*억", 100_000_000), (r"(\d+)\s*천\s*만", 10_000_000),
                          (r"(\d+)\s*백\s*만", 1_000_000), (r"(\d+)\s*만", 10_000)):
        m = re.search(pattern, text)
        if m:
            total += int(m.group(1)) * unit
            matched = True
    return total if matched else 0


def parse_float(value) -> Optional[float]:
    """'84.99㎡', '84.99', 84.99 → 84.99. 못 읽으면 None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", str(value))
    if not m:
        return None
    return float(m.group(0).replace(",", ""))


def parse_year(value) -> Optional[int]:
    """'2014-06-27', '20140627', 2014 → 2014. 못 읽으면 None."""
    if value is None:
        return None
    m = re.search(r"(19\d{2}|20\d{2})", str(value))
    return int(m.group(1)) if m else None


_NAME_NOISE = re.compile(r"[\s()（）㈜]|주식회사|\(주\)")


def normalize_name(name: str) -> str:
    """소유자 이름 비교용 정규화 (공백/괄호/법인 접두어 제거)."""
    return _NAME_NOISE.sub("", name or "")


# 용도 → 대분류. 순서가 중요하다(구체적인 것을 먼저).
_USAGE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("근린생활", ("근린생활", "근생", "제1종근린", "제2종근린")),
    ("오피스텔", ("오피스텔",)),
    ("주거", ("아파트", "다세대", "연립", "다가구", "단독주택", "공동주택", "도시형생활", "주택", "주거", "기숙사")),
    ("업무", ("업무시설", "사무소", "사무")),
    ("상업", ("판매시설", "상가", "점포", "숙박", "위락")),
    ("공업", ("공장", "창고", "공업")),
)


def usage_category(usage: Optional[str]) -> str:
    """'공동주택(아파트)' → '주거', '제2종근린생활시설' → '근린생활' ... 알 수 없으면 '기타'."""
    if not usage:
        return "미상"
    compact = re.sub(r"\s+", "", usage)
    for category, keywords in _USAGE_RULES:
        if any(k in compact for k in keywords):
            return category
    return "기타"


_STRUCTURE_ALIASES = (
    ("철근콘크리트", ("철근콘크리트", "철콘", "rc")),
    ("철골철근콘크리트", ("철골철근콘크리트", "src")),
    ("철골", ("철골구조", "철골조", "일반철골")),
    ("벽돌", ("벽돌", "조적", "시멘트벽돌")),
    ("목", ("목구조", "목조")),
    ("석", ("석조",)),
)


def normalize_structure(structure: Optional[str]) -> Optional[str]:
    """'철근콘크리트구조' / '철근콘크리트조' / '철콘' → '철근콘크리트' (같은 계열로 묶기)."""
    if not structure:
        return None
    compact = re.sub(r"\s+", "", structure).lower()
    # 철골철근콘크리트가 철근콘크리트를 포함하므로 더 구체적인 것을 먼저 확인
    for canonical in ("철골철근콘크리트", "철근콘크리트", "철골", "벽돌", "목", "석"):
        for name, aliases in _STRUCTURE_ALIASES:
            if name == canonical and any(a in compact for a in aliases):
                return name
    return compact
