# backend/evaluation/gold.py
"""
검색 결과 정답(gold) 정의. 시나리오 문서 자체에서 자동으로 만든다. (라벨을 손으로 따로 관리하지 않는다)

한 항목의 정답은 "반드시 근거로 들어와야 하는 청크 묶음(group)" 의 목록이다.
- 두 문서를 비교하는 항목은 등기부 묶음과 건축물대장 묶음이 각각 하나씩 있다. 한쪽 근거만 찾으면 절반만 맞은 것이다.
- 권리사항은 현재 유효한(말소되지 않은) 권리마다 그 권리가 적힌 청크가 한 묶음이다.
청크 하나가 묶음에 속하는지는 문서 종류, 구획 이름, 순위번호, 본문 키워드로 판정한다.
"""
from dataclasses import dataclass
from typing import Iterable, List, Optional

from app.services.documents import PropertyDoc

RIGHTS_FIELD = "권리사항"


@dataclass(frozen=True)
class GoldGroup:
    label: str
    doc_type: str
    section: Optional[str] = None
    keyword: Optional[str] = None
    rank_no: Optional[str] = None

    def matches(self, chunk: dict) -> bool:
        if chunk.get("doc_type") != self.doc_type:
            return False
        if self.section is not None and chunk.get("section") != self.section:
            return False
        if self.rank_no is not None and (chunk.get("rank_no") or None) != self.rank_no:
            return False
        return self.keyword is None or self.keyword in (chunk.get("text") or "")


def _has(doc: PropertyDoc, keyword: str) -> bool:
    return any(keyword in s.text for s in doc.sections)


def _keyword_groups(reg: PropertyDoc, bld: PropertyDoc, reg_kw: Optional[str], bld_kw: Optional[str], label: str) -> List[GoldGroup]:
    groups = []
    if reg_kw and _has(reg, reg_kw):
        groups.append(GoldGroup(f"{label}(등기부)", "registry", keyword=reg_kw))
    if bld_kw and _has(bld, bld_kw):
        groups.append(GoldGroup(f"{label}(건축물대장)", "building", keyword=bld_kw))
    return groups


def gold_groups(field: str, reg: PropertyDoc, bld: PropertyDoc) -> List[GoldGroup]:
    if field == "소유자명":
        groups = []
        if _has(reg, "소유권이전") or _has(reg, "소유권보존"):
            # 소유권이전/소유권보존이 적힌 갑구 청크. 소유자가 여러 번 바뀐 문서도 갑구 청크 중 하나만 들어오면 충족으로 본다.
            groups.append(GoldGroup("소유자(등기부 갑구)", "registry", section="갑구", keyword="소유"))
        if _has(bld, "소유자"):
            groups.append(GoldGroup("소유자(건축물대장)", "building", section="소유자현황"))
        return groups
    if field == "건물 용도":
        return _keyword_groups(reg, bld, reg.usage, bld.usage, "용도")
    if field == "구조 유형":
        return _keyword_groups(reg, bld, reg.structure, bld.structure, "구조")
    if field == "전용면적":
        return _keyword_groups(reg, bld, "전용면적", "전용면적", "전용면적")
    if field == "연면적":
        return _keyword_groups(reg, bld, "연면적", "연면적", "연면적")
    if field == "준공년도":
        return _keyword_groups(reg, bld, "신축", "사용승인", "준공")
    if field == RIGHTS_FIELD:
        return [
            GoldGroup(f"{r.type} {r.section} {r.rank_no}", "registry", section=r.section, rank_no=r.rank_no)
            for r in reg.active_rights
        ]
    return []


def covered(groups: Iterable[GoldGroup], chunks: List[dict]) -> int:
    """chunks 로 채워진 묶음의 수."""
    return sum(1 for g in groups if any(g.matches(c) for c in chunks))
