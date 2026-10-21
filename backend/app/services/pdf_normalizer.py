"""PDF에서 추출한 텍스트를 기존 PropertyDoc 구조로 정규화한다."""
from __future__ import annotations

import re

from app.services.codef_normalizer import normalize_registry_response
from app.services.documents import PropertyDoc, Section, parse_float, parse_year
from app.services.pdf_extractor import ExtractedPdf, PdfContentError

_REGISTRY_TITLE = re.compile(r"등기사항\s*(?:전부)?\s*증명서")
_REGISTRY_SECTION = re.compile(r"표\s*제\s*부|갑\s*구|을\s*구")
_BUILDING_TITLE = re.compile(r"건축물\s*대장")

_ADDRESS_ALIASES = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원", "충청북도": "충북",
    "충청남도": "충남", "전북특별자치도": "전북", "전라북도": "전북", "전라남도": "전남",
    "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주",
}


def _compact(text: str) -> str:
    for source, target in _ADDRESS_ALIASES.items():
        text = text.replace(source, target)
    text = re.sub(r"\([^)]*\)", "", text)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def _address_matches(address: str, text: str) -> bool:
    key = _compact(address)
    return bool(key) and key in _compact(text)


def _registry_section_name(heading: str) -> str:
    compact = re.sub(r"\s+", "", heading)
    return {"표제부": "표제부", "갑구": "갑구", "을구": "을구"}.get(compact, "기타")


def _registry_segments(pdf: ExtractedPdf) -> list[tuple[str, str, int]]:
    segments: list[tuple[str, str, int]] = []
    current = "표제부"
    for page in pdf.pages:
        matches = list(_REGISTRY_SECTION.finditer(page.text))
        if not matches:
            if page.text.strip():
                segments.append((current, page.text.strip(), page.page_no))
            continue
        if matches[0].start() > 0:
            prefix = page.text[:matches[0].start()].strip()
            if prefix:
                segments.append((current, prefix, page.page_no))
        for index, match in enumerate(matches):
            current = _registry_section_name(match.group())
            end = matches[index + 1].start() if index + 1 < len(matches) else len(page.text)
            body = page.text[match.start():end].strip()
            if body:
                segments.append((current, body, page.page_no))
    return segments


def _with_registry_pages(doc: PropertyDoc, segments: list[tuple[str, str, int]]) -> PropertyDoc:
    for section in doc.sections:
        needle = re.sub(r"\s+", "", section.text)
        for name, text, page_no in segments:
            if name == section.name and needle in re.sub(r"\s+", "", text):
                section.page_no = page_no
                break
    return doc


def normalize_registry_pdf(pdf: ExtractedPdf, address: str) -> PropertyDoc:
    text = pdf.text
    if not _REGISTRY_TITLE.search(text) or not _REGISTRY_SECTION.search(text):
        raise PdfContentError("등기부등본 PDF를 확인할 수 없습니다.")
    if not _address_matches(address, text):
        raise PdfContentError("선택한 주소와 등기부등본의 주소가 일치하지 않습니다.")

    segments = _registry_segments(pdf)
    data = {"sections": [
        {"resType": name, "resContents": section_text}
        for name, section_text, _ in segments
    ]}
    doc = _with_registry_pages(normalize_registry_response(data, address), segments)
    if not doc.owner_names:
        raise PdfContentError("등기부등본에서 현재 소유자를 읽지 못했습니다.")
    return doc


def _label_value(text: str, label: str) -> str | None:
    match = re.search(
        rf"(?:{label})[ \t]*[:：]?[ \t]*(?:\r?\n[ \t]*)?([^\r\n│|]+)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    value = re.split(r"\s{3,}", match.group(1).strip(), maxsplit=1)[0].strip(" :：")
    return value or None


def _building_owner(text: str) -> list[str]:
    value = _label_value(text, r"소\s*유\s*자(?:\s*현\s*황)?|성\s*명")
    if not value:
        return []
    match = re.match(r"([가-힣]{2,4}|(?:주식회사|\(주\)|㈜)?[가-힣A-Za-z0-9()]{2,30})", value)
    return [match.group(1)] if match else []


def normalize_building_pdf(pdf: ExtractedPdf, address: str) -> PropertyDoc:
    text = pdf.text
    required_labels = sum(bool(re.search(pattern, text)) for pattern in (
        r"주\s*용\s*도", r"구\s*조", r"(?:전용|연)\s*면\s*적",
    ))
    if not _BUILDING_TITLE.search(text) or required_labels < 2:
        raise PdfContentError("건축물대장 PDF를 확인할 수 없습니다.")
    if not _address_matches(address, text):
        raise PdfContentError("선택한 주소와 건축물대장의 주소가 일치하지 않습니다.")

    usage = _label_value(text, r"주\s*용\s*도")
    if not usage:
        raise PdfContentError("건축물대장에서 주용도를 읽지 못했습니다.")
    structure = _label_value(text, r"구\s*조")
    exclusive = _label_value(text, r"전\s*용\s*면\s*적|전유부분(?:의\s*건물)?의?\s*면\s*적")
    total = _label_value(text, r"연\s*면\s*적")
    approval = _label_value(text, r"사용\s*승인(?:일|일자)?")

    violation = None
    violation_match = re.search(r"위반\s*건축물[^\r\n]*", text)
    if violation_match:
        violation = not bool(re.search(r"아님|없음|해당\s*없|정상", violation_match.group()))

    return PropertyDoc(
        doc_type="building",
        address=address,
        owner_names=_building_owner(text),
        usage=usage,
        structure=structure,
        area_exclusive=parse_float(exclusive),
        area_total=parse_float(total),
        build_year=parse_year(approval),
        violation=violation,
        sections=[
            Section("건축물대장", page.text, page_no=page.page_no)
            for page in pdf.pages if page.text.strip()
        ],
    )
