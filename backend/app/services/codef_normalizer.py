# backend/app/services/codef_normalizer.py
"""
CODEF 응답(등기부등본, 건축물대장)을 공통 구조(PropertyDoc)로 정규화한다.

⚠ CODEF 응답 스키마는 상품/버전에 따라 다를 수 있으므로 "특정 경로에 값이 있다" 고 가정하지 않고,
   응답 트리 전체를 순회하면서 resContents / resType 등을 수집하는 방식으로 구현했다.
   실제 응답을 받아 보고 맞지 않는 부분은 이 파일의 정규식/키 이름만 조정하면 된다.
   (원본 응답은 개인정보를 포함하므로 로그로 남기지 않는다.)
"""
from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any, Iterator, Optional

from app.services.documents import (
    PropertyDoc, Right, Section, parse_amount_won, parse_float, parse_year,
)

# ─────────────────────────────────────────────────────────────
# 공통: 응답 본문 디코딩
# ─────────────────────────────────────────────────────────────

def decode_codef_body(raw_text: str) -> dict:
    """
    CODEF 응답 본문(JSON, 대개 URL 인코딩됨)을 dict 로 바꾼다.
    URL 인코딩된 경우에만 unquote_plus 를 적용해서, 평문 JSON 안의 '+' 가 망가지지 않게 한다.
    """
    text = (raw_text or "").strip()
    if text.startswith("%7B") or text.startswith("%5B"):
        text = urllib.parse.unquote_plus(text)
    return json.loads(text)


def clean_text(value: Any) -> str:
    """CODEF 값의 '+'(공백)·개행 표기를 정리한다."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("+", " ")).strip()


# ─────────────────────────────────────────────────────────────
# 등기부등본
# ─────────────────────────────────────────────────────────────

_ENTRY_SPLIT = re.compile(r"\n(?=\s*\d{1,3}(?:-\d+)?\s+\S)")

# 권리 키워드. 순서 주의: '가압류' 를 '압류' 보다 먼저 검사한다.
_RIGHT_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    # '임의경매로 인한 소유권이전' 같은 이전 등기와 헷갈리지 않도록 '개시결정' 만 본다.
    ("경매개시결정", re.compile(r"경매개시결정")),
    ("가압류", re.compile(r"가압류")),
    ("압류", re.compile(r"(?<!가)압류")),
    ("가처분", re.compile(r"가처분")),
    ("가등기", re.compile(r"가등기")),
    ("신탁", re.compile(r"신탁")),
    ("근저당권", re.compile(r"근저당권")),
    ("전세권", re.compile(r"전세권")),
    ("임차권", re.compile(r"임차권")),
)

_USAGE_KEYWORDS = (
    "아파트", "다세대주택", "연립주택", "다가구주택", "단독주택", "오피스텔", "도시형생활주택",
    "제1종근린생활시설", "제2종근린생활시설", "근린생활시설", "공동주택", "업무시설", "판매시설", "공장", "창고시설",
)
_STRUCTURE_RE = re.compile(
    r"((?:경량)?(?:철골철근콘크리트|철근콘크리트|철골|철근|시멘트벽돌|벽돌|조적|목|석)[가-힣]{0,6}?(?:구조|조))(?![가-힣])"
)


def _iter_codef_texts(node: Any, hint: str = "") -> Iterator[tuple[str, str, Optional[str]]]:
    """응답 트리를 순회하며 (구 힌트, 본문, 순위번호) 를 낸다."""
    if isinstance(node, dict):
        this_hint = hint
        for key in ("resType", "resRegistrationType", "resTitle", "resSection"):
            v = node.get(key)
            # 표제부/갑구/을구 를 가리키는 값일 때만 구 힌트를 바꾼다. (하위 항목의 다른 resType 이 상위 힌트를 덮어쓰지 않도록)
            if isinstance(v, str) and any(k in v for k in ("표제", "갑구", "을구")):
                this_hint = clean_text(v)
                break
        contents = node.get("resContents")
        if isinstance(contents, str) and contents.strip():
            rank = node.get("resNumber")
            yield this_hint, contents, (clean_text(rank) if rank not in (None, "") else None)
        for k, v in node.items():
            if k == "resContents":
                continue
            yield from _iter_codef_texts(v, this_hint)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_codef_texts(item, hint)


def _classify_section(hint: str, text: str) -> str:
    h = hint or ""
    if "표제" in h:
        return "표제부"
    if "갑구" in h:
        return "갑구"
    if "을구" in h:
        return "을구"
    if re.search(r"채권최고액|근저당|전세권|임차권", text):
        return "을구"
    if re.search(r"소유권|압류|가압류|가처분|가등기|경매|신탁", text):
        return "갑구"
    if re.search(r"㎡|구조|건물의\s*표시|층", text):
        return "표제부"
    return "기타"


def _rank_of(entry_text: str, given: Optional[str]) -> Optional[str]:
    if given:
        return given
    m = re.match(r"\s*(\d{1,3}(?:-\d+)?)\s", entry_text)
    return m.group(1) if m else None


def normalize_registry_response(data: dict, address: str = "") -> PropertyDoc:
    """CODEF 등기부등본 응답(data 부분) → PropertyDoc."""
    doc = PropertyDoc(doc_type="registry", address=address)

    seen: set[str] = set()
    entries: list[tuple[str, str, Optional[str]]] = []   # (구, 본문, 순위번호)
    for hint, text, rank in _iter_codef_texts(data):
        raw_text = text.replace("+", " ").strip()
        # 요약/이력에 같은 내용이 중복으로 실리는 경우가 있어 본문 기준으로 중복 제거
        key = re.sub(r"\s+", "", raw_text)
        if not key or key in seen:
            continue
        seen.add(key)
        for piece in _ENTRY_SPLIT.split(raw_text):
            piece = piece.strip()
            if piece:
                entries.append((_classify_section(hint, piece), piece, _rank_of(piece, rank)))

    cancel_targets: list[tuple[str, str]] = []   # (구, 말소 대상 순위번호)
    owner_entries: list[str] = []

    for section, text, rank in entries:
        doc.sections.append(Section(name=section, text=text, rank_no=rank))

        if section == "표제부":
            _fill_title_part(doc, text)
            continue

        if re.search(r"등기\s*말소|말소\s*등기|\d+(?:-\d+)?\s*번\S{0,20}말소", text):
            for m in re.finditer(r"(\d{1,3})(?:-\d+)?\s*번", text):
                cancel_targets.append((section, m.group(1)))
            continue

        if section == "갑구" and re.search(r"소유권이전|소유권보존", text):
            owner_entries.append(text)
            # 소유자 이름·주소에 권리 키워드가 있어도 권리 등기로 오인하지 않는다.
            # 단, 신탁을 원인으로 한 소유권이전은 신탁 위험으로 계속 판독한다.
            if not re.search(r"원인\s*신탁|신탁재산", text):
                continue

        for right_type, pattern in _RIGHT_PATTERNS:
            if pattern.search(text):
                amount = 0
                if right_type == "근저당권":
                    idx = text.find("채권최고액")
                    amount = parse_amount_won(text[idx: idx + 40] if idx >= 0 else text)
                doc.rights.append(Right(type=right_type, amount=amount, rank_no=rank, section=section))

    for section, rank_no in cancel_targets:
        for r in doc.rights:
            if r.section == section and r.rank_no == rank_no:
                r.cancelled = True

    if owner_entries:
        doc.owner_names = _extract_owner_names(owner_entries[-1])
    return doc


def _extract_owner_names(entry_text: str) -> list[str]:
    names = re.findall(
        r"(?:소유자|공유자)\s+(?:지분\s*(?:\d+분의\s*\d+|[\d/]+)\s+)?([가-힣㈜()A-Za-z0-9]{2,20})", entry_text
    )
    out: list[str] = []
    for n in names:
        if n not in out and n not in {"및", "지분"}:
            out.append(n)
    return out


def _fill_title_part(doc: PropertyDoc, text: str) -> None:
    if doc.structure is None:
        m = _STRUCTURE_RE.search(text)
        if m:
            doc.structure = m.group(1)
    if doc.usage is None:
        m = re.search(r"용도\s*[:：]?\s*([가-힣()·]+)", text)
        if m:
            doc.usage = m.group(1)
        else:
            for kw in _USAGE_KEYWORDS:
                if kw in text:
                    doc.usage = kw
                    break
    if doc.area_exclusive is None:
        m = re.search(r"전용면적\s*[:：]?\s*([\d,.]+)\s*㎡?", text)
        if m:
            doc.area_exclusive = parse_float(m.group(1))
        else:
            m = re.search(r"(?:건물번호|전유부분)[^\n]*?([\d.]+)\s*㎡", text)
            if m:
                doc.area_exclusive = parse_float(m.group(1))
    if doc.area_total is None:
        m = re.search(r"연면적\s*[:：]?\s*([\d,.]+)\s*㎡?", text)
        if m:
            doc.area_total = parse_float(m.group(1))
    if doc.build_year is None:
        m = re.search(r"(19\d{2}|20\d{2})\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일\s*신축", text)
        if m:
            doc.build_year = int(m.group(1))


# ─────────────────────────────────────────────────────────────
# 건축물대장
# ─────────────────────────────────────────────────────────────

def normalize_building_response(data: dict, address: str = "") -> PropertyDoc:
    """CODEF 건축물대장 응답(data 부분) → PropertyDoc."""
    doc = PropertyDoc(doc_type="building", address=clean_text(data.get("resUserAddr")) or address)

    owners = data.get("resOwnerList") or []
    doc.owner_names = [clean_text(o.get("resOwner")) for o in owners if clean_text(o.get("resOwner"))]

    statuses = [s for s in (data.get("resBuildingStatusList") or []) if isinstance(s, dict)]
    if statuses:
        main = max(statuses, key=lambda s: parse_float(s.get("resArea")) or 0.0)
        doc.usage = clean_text(main.get("resUseType")) or None
        doc.structure = clean_text(main.get("resStructure")) or None
        areas = [parse_float(s.get("resArea")) for s in statuses]
        areas = [a for a in areas if a is not None]
        doc.area_total = round(sum(areas), 2) if areas else None

    # 상세 목록에 명시된 연면적/전용면적이 있으면 그것을 우선한다.
    for detail in (data.get("resDetailList") or []):
        if not isinstance(detail, dict):
            continue
        label = clean_text(detail.get("resType"))
        value = detail.get("resContents")
        if "연면적" in label and parse_float(value) is not None:
            doc.area_total = parse_float(value)
        elif "전용면적" in label and parse_float(value) is not None:
            doc.area_exclusive = parse_float(value)

    doc.build_year = _find_use_approval_year(data)

    violation = data.get("resViolationStatus")
    if violation is not None:
        text = clean_text(violation)
        # "위반건축물 아님" / "해당없음" 같은 부정 표현에 '위반' 이 들어 있어도 위반으로 보지 않는다.
        doc.violation = "위반" in text and not re.search(r"아님|없음|없다|비해당|해당\s*없", text)

    doc.sections = _building_sections(data, doc)
    return doc


def _find_use_approval_year(node: Any) -> Optional[int]:
    """'사용승인' 라벨이 붙은 값에서 연도를 찾는다. 발급일(resIssueDate)은 사용하지 않는다."""
    if isinstance(node, dict):
        joined = " ".join(str(v) for v in node.values() if isinstance(v, (str, int, float)))
        if "사용승인" in joined or any("사용승인" in str(k) for k in node.keys()):
            for k, v in node.items():
                if "사용승인" in str(k):
                    y = parse_year(v)
                    if y:
                        return y
            for v in node.values():
                if isinstance(v, str) and "사용승인" not in v:
                    y = parse_year(v)
                    if y:
                        return y
        for v in node.values():
            y = _find_use_approval_year(v)
            if y:
                return y
    elif isinstance(node, list):
        for item in node:
            y = _find_use_approval_year(item)
            if y:
                return y
    return None


def _building_sections(data: dict, doc: PropertyDoc) -> list[Section]:
    sections: list[Section] = []
    overview = [
        f"주소: {doc.address}",
        f"주용도: {doc.usage or '정보 없음'}",
        f"구조: {doc.structure or '정보 없음'}",
        f"연면적: {doc.area_total if doc.area_total is not None else '정보 없음'}㎡",
        f"사용승인 연도: {doc.build_year or '정보 없음'}",
        f"위반건축물 여부: {'해당' if doc.violation else ('해당 없음' if doc.violation is False else '정보 없음')}",
    ]
    note = clean_text(data.get("resNote"))
    if note:
        overview.append(f"비고: {note}")
    sections.append(Section(name="건축물개요", text="\n".join(overview)))

    floors = [
        f"{clean_text(s.get('resFloor'))} {clean_text(s.get('resStructure'))} {clean_text(s.get('resUseType'))} {clean_text(s.get('resArea'))}㎡"
        for s in (data.get("resBuildingStatusList") or []) if isinstance(s, dict)
    ]
    if floors:
        sections.append(Section(name="층별현황", text="\n".join(floors)))

    changes = [
        " ".join(clean_text(v) for v in c.values() if isinstance(v, (str, int, float)))
        for c in (data.get("resChangeList") or []) if isinstance(c, dict)
    ]
    changes = [c for c in changes if c]
    if changes:
        sections.append(Section(name="변동사항", text="\n".join(changes)))

    owners = data.get("resOwnerList") or []
    if owners:
        lines = [
            f"소유자 {clean_text(o.get('resOwner'))} 지분 {clean_text(o.get('resOwnershipStake'))} "
            f"변동일 {clean_text(o.get('resChangeDate'))} 사유 {clean_text(o.get('resChangeReason'))}"
            for o in owners if isinstance(o, dict)
        ]
        sections.append(Section(name="소유자현황", text="\n".join(lines)))
    return sections
