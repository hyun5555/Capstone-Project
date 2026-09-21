# backend/app/services/evidence.py
"""
비교 항목별로 "근거가 되는 청크"를 찾아 준다. (ChromaDB 는 위험도를 계산하지 않고 근거 검색만 한다.)

analyze 에서 두 문서를 청킹해 저장한 뒤 항목별 질의로 Top-K 청크를 가져온다.
검색된 청크는 다음 단계(LangChain RAG)에서 LLM 에 넘기고, 화면/보고서에 출처로 보여줄 수 있다.
"""
from __future__ import annotations

from app.services.chunker import case_id_for, chunk_document
from app.services.documents import PropertyDoc

# 항목 → 검색 질의. (항목 이름은 document_compare.COMPARABLE_FIELDS 와 같다)
FIELD_QUERIES = {
    "소유자명": "소유자 소유권보존 소유권이전 소유자 현황",
    "건물 용도": "건물 주용도 용도",
    "구조 유형": "건물 구조 철근콘크리트 벽돌",
    "전용면적": "전용면적 전유부분 건물의 표시",
    "연면적": "연면적 층별 면적",
    "준공년도": "사용승인일 신축 준공",
    "권리사항": "근저당권 채권최고액 압류 가압류 전세권 임차권 가처분 경매",
}


def index_documents(store, registry: PropertyDoc, building: PropertyDoc, size: int, overlap: int) -> str:
    """두 문서를 청킹해서 저장하고 case_id 를 돌려준다. 같은 내용을 다시 넣어도 중복 저장되지 않는다."""
    case_id = case_id_for(registry, building)
    store.upsert(chunk_document(registry, case_id, size, overlap) + chunk_document(building, case_id, size, overlap))
    return case_id


# 항목별로 찾을 문서 종류. 정해지지 않은 항목은 두 문서 모두에서 찾는다.
FIELD_DOC_TYPE = {"권리사항": "registry"}      # 권리(근저당·압류 등)는 등기부에만 있다
STRATEGIES = ("plain", "balanced", "adaptive")

# adaptive 전략의 항목별 Top-K. 실제 임베딩으로 청크 크기 300, k=1/2/3/5 를 재 본 결과(evaluation --phase retrieval)에서,
# 항목마다 필요한 근거 묶음을 모두 찾는 데 필요한 최소 K 를 골랐다. 항목은 서로 독립된 질의라서 항목별로 K 를 달리해도
# 그 항목의 적중은 같은 K 로 잰 값과 같다.
#   전용면적: k=1 에서 7/7, 소유자명과 구조 유형: k=2 에서 14/14, 권리사항: k=2 에서 5/5 (여유로 3),
#   건물 용도와 연면적과 준공년도: k=5 에서야 13/14, 14/14, 11/14 (k=3 은 7/14, 7/14, 9/14)
# 합계 23개로, 모든 항목을 k=5 로 하는 것(35개)과 근거 적중은 같고 프롬프트는 약 1/3 짧다.
FIELD_TOP_K = {"전용면적": 1, "소유자명": 2, "구조 유형": 2, "권리사항": 3, "건물 용도": 5, "연면적": 5, "준공년도": 5}


def retrieve_evidence(store, case_id: str, top_k: int, strategy: str = "plain") -> dict:
    """
    {항목: [{chunk_id, doc_type, section, rank_no, text, distance}, ...]}
    LangChain 리트리버(CaseChunkRetriever)로 항목별 질의를 차례로 실행한다. (ChromaDB 호출은 스레드 안전하지 않아 병렬로 돌리지 않는다)
    strategy: "plain"(가까운 순 Top-K) | "balanced"(두 문서 청크를 각각 하나 이상 포함)
              | "adaptive"(balanced 에 항목별 Top-K(FIELD_TOP_K)를 적용. top_k 는 표에 없는 항목에만 쓴다)
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"알 수 없는 검색 전략입니다: {strategy}")
    from app.services.lc_retriever import CaseChunkRetriever

    def search(name: str):
        retriever = CaseChunkRetriever(
            store=store, case_id=case_id,
            top_k=FIELD_TOP_K.get(name, top_k) if strategy == "adaptive" else top_k,
            doc_type=FIELD_DOC_TYPE.get(name), balanced=(strategy != "plain"),
        )
        return retriever.invoke(FIELD_QUERIES[name])

    names = list(FIELD_QUERIES)
    results = [search(name) for name in names]

    return {
        name: [
            {
                "chunk_id": d.metadata["chunk_id"],
                "doc_type": d.metadata.get("doc_type"),
                "section": d.metadata.get("section"),
                "rank_no": d.metadata.get("rank_no") or None,
                "text": d.page_content,
                "distance": d.metadata["distance"],
            }
            for d in docs
        ]
        for name, docs in zip(names, results)
    }


def collect_evidence(store, registry: PropertyDoc, building: PropertyDoc, size: int, overlap: int, top_k: int,
                     strategy: str = "plain"):
    """(case_id, evidence) — 저장과 검색을 한 번에."""
    case_id = index_documents(store, registry, building, size, overlap)
    return case_id, retrieve_evidence(store, case_id, top_k, strategy)
