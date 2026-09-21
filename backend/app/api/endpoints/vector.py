from typing import Optional

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from app.services.vector_db import get_chunk_store, query_similar_documents

router = APIRouter(prefix="/vector", tags=["VectorDB"])


@router.get("/search")
async def vector_search(q: str, top: int = 5, case_id: Optional[str] = None):
    """
    질의(q)에 대해 상위(top)개의 유사 문서 반환.
    case_id 를 주면 그 분석 건의 청크만 검색한다 (분석 응답의 case_id 를 그대로 사용).
    """
    if case_id:
        hits = await run_in_threadpool(lambda: get_chunk_store().search(case_id, [q], n_results=top)[0])
        return {"query": q, "case_id": case_id, "results": hits}

    results = query_similar_documents(q, top)
    return {"query": q, "results": results}
