# backend/app/services/chunker.py
"""
정규화된 문서(PropertyDoc)를 검색용 청크로 나눈다. (외부 라이브러리 의존 없음)

- 청크 단위는 문서의 논리 구획(표제부/갑구/을구의 항목 하나, 건축물대장의 개요/층별현황/소유자현황)이다.
  한 구획이 CHUNK_SIZE 보다 길 때만 CHUNK_OVERLAP 만큼 겹쳐서 더 나눈다.
- 청크 앞에 "[등기부 을구 순위 2]" 같은 머리말을 붙여서, 청크 하나만 봐도 어느 문서의 어디인지 알 수 있게 한다.
- 임베딩/저장 전에 개인정보(소유자 이름, 주민번호, 전화번호, 명의인 주소)를 마스킹한다.
- 청크 ID 는 내용에서 결정적으로 만든다(SHA-256). 같은 문서를 다시 넣어도 중복 저장되지 않는다.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from app.services.documents import PropertyDoc
from app.utils.masking import mask_text

DOC_LABEL = {"registry": "등기부", "building": "건축물대장"}


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: dict = field(default_factory=dict)


def split_text(text: str, size: int, overlap: int) -> list:
    """size 글자 이하로 나눈다. 가능하면 줄바꿈/공백에서 끊고, 앞 조각의 끝 overlap 글자를 다음 조각에 겹친다."""
    if size <= 0:
        raise ValueError("size 는 1 이상이어야 합니다.")
    if not 0 <= overlap < size:
        raise ValueError("overlap 은 0 이상, size 미만이어야 합니다.")
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []

    pieces, start, n = [], 0, len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            window_from = start + int(size * 0.6)
            cut = max(text.rfind("\n", window_from, end), text.rfind(" ", window_from, end))
            if cut > start:
                end = cut
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)       # 항상 앞으로 나아가도록
    return pieces


def _chunk_id(case_id: str, doc_type: str, section_index: int, chunk_index: int, text: str) -> str:
    payload = json.dumps([case_id, doc_type, section_index, chunk_index, text], ensure_ascii=False, separators=(",", ":"))
    return f"chunk-{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def chunk_document(doc: PropertyDoc, case_id: str, size: int, overlap: int) -> list:
    chunks = []
    label = DOC_LABEL.get(doc.doc_type, doc.doc_type)
    cancelled = {(r.section, r.rank_no) for r in doc.rights if r.cancelled}
    for si, section in enumerate(doc.sections):
        header = f"[{label} {section.name}" + (f" 순위 {section.rank_no}" if section.rank_no else "")
        # 나중에 말소된 권리는 청크만 봐도 알 수 있게 표시한다 (LLM 이 유효한 권리로 오해하지 않도록).
        header += (" 말소됨]" if (section.name, section.rank_no) in cancelled else "]")
        body = mask_text(section.text, doc.owner_names)
        room = max(size - len(header) - 1, 1)
        for ci, piece in enumerate(split_text(body, room, min(overlap, room - 1))):
            text = f"{header} {piece}"
            chunks.append(Chunk(
                id=_chunk_id(case_id, doc.doc_type, si, ci, text),
                text=text,
                metadata={
                    "case_id": case_id,
                    "doc_type": doc.doc_type,
                    "section": section.name,
                    "rank_no": section.rank_no or "",       # Chroma 메타데이터는 None 을 허용하지 않는다
                    "section_index": si,
                    "chunk_index": ci,
                },
            ))
    return chunks


def case_id_for(registry: PropertyDoc, building: PropertyDoc) -> str:
    """분석 한 건을 가리키는 ID. 같은 주소·같은 내용이면 같은 ID 가 된다."""
    payload = json.dumps(
        [registry.address, [s.text for s in registry.sections], [s.text for s in building.sections]],
        ensure_ascii=False, separators=(",", ":"),
    )
    return f"case-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"
