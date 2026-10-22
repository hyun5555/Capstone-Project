from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.session import get_db
from app.models.analysis_cases import AnalysisJob
from app.models.user import User
from app.services.auth import get_current_user

router = APIRouter(prefix="/vector", tags=["VectorDB"])


@router.get("/search")
async def vector_search(
    q: str = Query(..., min_length=1, max_length=500),
    case_id: str = Query(..., min_length=8, max_length=64),
    top: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    질의(q)에 대해 상위(top)개의 유사 문서 반환.
    현재 사용자가 완료한 분석 건의 청크만 검색한다.
    """
    result = await db.execute(select(AnalysisJob).where(
        AnalysisJob.user_id == current_user.user_id,
        AnalysisJob.case_id == case_id,
        AnalysisJob.status == "succeeded",
    ))
    if result.scalars().first() is None:
        raise HTTPException(status_code=404, detail="분석 건을 찾을 수 없습니다.")
    from app.services.vector_db import get_chunk_store
    hits = await run_in_threadpool(lambda: get_chunk_store().search(case_id, [q], n_results=top)[0])
    return {"query": q, "case_id": case_id, "results": hits}
