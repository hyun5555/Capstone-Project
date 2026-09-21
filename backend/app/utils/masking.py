# backend/app/utils/masking.py
"""
개인정보 마스킹 (OpenAI 임베딩/LLM 호출 및 ChromaDB 저장 전에 사용)

원칙
- 소유자 이름 같은 개인정보는 서버 안에서만 비교하고, 외부 API 로는 나가지 않게 한다.
- 문서에서 알려진 이름(소유자 목록)은 그대로 치환하고, 나머지는 패턴 기반으로 최대한 가린다.
- 패턴 기반 마스킹은 "최선의 노력(best-effort)" 이며 100% 를 보장하지 않는다.
  (예: 문서 본문에 라벨 없이 등장하는 개인 이름은 못 잡을 수 있음)
"""
from __future__ import annotations

import re
from typing import Iterable

# 주민등록번호 (뒷자리 일부/전부 마스킹되어 있어도 앞 6자리는 가림)
_RRN = re.compile(r"(?<!\d)\d{6}\s*-\s*[\d*●○xX]{1,7}(?![\d*])")
# 주민번호 뒤에 이어지는 주소(그 줄의 나머지)
_ADDR_AFTER_RRN = re.compile(r"(\[주민번호\])[ \t]+(?=\S)[^\n]*")
# 전화번호
_PHONE = re.compile(r"\b0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}\b")
# 라벨 뒤에 나오는 사람 이름(2~4자 한글) — 라벨은 유지하고 이름만 치환
_LABELED_NAME = re.compile(
    r"(소유자|채무자|임차인|임대인|임차권자|전세권자|근저당권자|권리자|신청인|채권자)(\s*[:：]?\s*)([가-힣]{2,4})(?![가-힣])"
)
# 법인/기관 이름 힌트 — 이런 단어가 들어간 토큰은 개인이 아니므로 가리지 않는다.
_ORG_HINTS = (
    "은행", "금융", "신협", "새마을", "조합", "캐피탈", "저축", "보증", "공사", "공단",
    "주식회사", "유한회사", "재단", "법인", "보험", "증권", "농협", "수협", "카드", "리스",
)


def _is_org(token: str) -> bool:
    return any(h in token for h in _ORG_HINTS)


def mask_text(text: str, known_names: Iterable[str] = ()) -> str:
    """텍스트에서 개인정보를 치환한 새 문자열을 반환한다."""
    if not text:
        return text

    masked = text

    # 1) 문서에서 이미 알고 있는 이름 → [소유자N]
    for idx, name in enumerate(_unique_names(known_names), start=1):
        masked = masked.replace(name, f"[소유자{idx}]")

    # 2) 주민등록번호 / 전화번호
    masked = _RRN.sub("[주민번호]", masked)
    # 등기부에서 주민번호 바로 뒤에 오는 것은 등기명의인의 주소이므로 그 줄의 나머지를 가린다.
    masked = _ADDR_AFTER_RRN.sub(r"\1 [주소]", masked)
    masked = _PHONE.sub("[전화번호]", masked)

    # 3) 라벨 기반 이름 (법인명은 제외)
    def _sub(m: re.Match) -> str:
        label, sep, name = m.group(1), m.group(2), m.group(3)
        if _is_org(name) or name.startswith("[") :
            return m.group(0)
        return f"{label}{sep}[이름]"

    masked = _LABELED_NAME.sub(_sub, masked)
    return masked


def _unique_names(names: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for n in names:
        n = (n or "").strip()
        # 1글자 이름/빈 문자열은 오탐이 커서 제외
        if len(n) >= 2 and n not in seen:
            seen.append(n)
    # 긴 이름부터 치환해야 부분 문자열 충돌이 없다
    return sorted(seen, key=len, reverse=True)


# ─────────────────────────────────────────────────────────────
# 앱/로그로 나가는 응답용 마스킹 (표시용)
# ─────────────────────────────────────────────────────────────

def mask_person_name(name: str) -> str:
    """'홍길동' → '홍*동', '김수' → '김*', '남궁민수' → '남**수'. 법인명(주식회사 등)은 그대로 둔다."""
    name = (name or "").strip()
    if not name or _is_org(name):
        return name
    if len(name) == 1:
        return "*"
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


def mask_address_detail(addr: str) -> str:
    """개인(소유자) 주소는 앞 두 단어(시·구)만 남기고 가린다."""
    parts = (addr or "").replace("+", " ").split()
    if not parts:
        return ""
    return " ".join(parts[:2]) + " ***"


def mask_building_response(data: dict) -> dict:
    """
    CODEF 건축물대장 응답을 앱에 돌려주기 전에 개인정보를 가린 복사본으로 만든다.
    - 소유자 이름: 가운데 글자 마스킹 / 주민등록번호: 전부 가림 / 소유자 주소: 시·구만 남김
    원본 dict 는 바꾸지 않는다.
    """
    import copy

    masked = copy.deepcopy(data)
    owners = masked.get("resOwnerList")
    if isinstance(owners, list):
        for o in owners:
            if not isinstance(o, dict):
                continue
            if o.get("resOwner"):
                o["resOwner"] = mask_person_name(str(o["resOwner"]).replace("+", " "))
            if o.get("resIdentityNo"):
                o["resIdentityNo"] = "******-*******"
            if o.get("resUserAddr"):
                o["resUserAddr"] = mask_address_detail(str(o["resUserAddr"]))
    return masked


def mask_json(value, known_names: Iterable[str] = ()):
    """
    임의의 JSON(dict/list/str)의 모든 문자열 값에 mask_text 를 적용한 복사본을 돌려준다.
    캡처한 CODEF 응답을 저장·공유(fixture)하기 전에 쓴다. 패턴 기반이라 100% 는 아니므로 공유 전에 눈으로 확인할 것.
    """
    names = list(known_names)
    if isinstance(value, dict):
        return {k: mask_json(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_json(v, names) for v in value]
    if isinstance(value, str):
        return mask_text(value, names)
    return value
