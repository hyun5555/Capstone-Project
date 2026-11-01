"""분석 이력과 별도로 Chroma 개인 문서 청크의 보존 기간을 집행한다."""
from __future__ import annotations
from datetime import datetime, timedelta
import logging

from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.config import CHROMA_CHUNK_COLLECTION, CHROMA_PERSIST_DIRECTORY, CHROMA_RETENTION_DAYS
from app.models.analysis_cases import AnalysisJob, VectorDeletion

logger = logging.getLogger(__name__)


def retention_cutoff(now: datetime | None = None) -> datetime:
    return (now or datetime.utcnow()) - timedelta(days=CHROMA_RETENTION_DAYS)


def vector_expires_at(created_at: datetime | None) -> datetime | None:
    return created_at + timedelta(days=CHROMA_RETENTION_DAYS) if created_at else None


def _delete_case(case_id: str) -> None:
    import chromadb
    from chromadb.errors import NotFoundError
    from app.services.chunk_store import ChunkStore

    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY)
    try:
        collection = client.get_collection(CHROMA_CHUNK_COLLECTION)
    except NotFoundError:
        return
    ChunkStore(collection).delete_case(case_id)


async def queue_case_deletions(db, case_ids) -> None:
    for case_id in {value for value in case_ids if value}:
        await db.merge(VectorDeletion(case_id=case_id))


async def cleanup_queued_cases(db) -> list[str]:
    """보존 기간 내의 완료 분석이 다른 사용자에게도 없을 때만 공유 청크를 지운다."""
    deleted = []
    cutoff = retention_cutoff()
    result = await db.execute(select(VectorDeletion))
    for queued in result.scalars().all():
        case_id = queued.case_id
        result = await db.execute(select(AnalysisJob.job_id).where(
            AnalysisJob.case_id == case_id,
            AnalysisJob.status == "succeeded",
            AnalysisJob.created_at >= cutoff,
        ).limit(1))
        if result.scalars().first() is not None:
            continue
        try:
            await run_in_threadpool(_delete_case, case_id)
            await db.delete(queued)
            deleted.append(case_id)
        except Exception:
            logger.exception("Chroma 분석 청크 삭제 실패: case_id=%s", case_id)
    if deleted:
        await db.commit()
    return deleted


async def delete_unreferenced_cases(db, case_ids) -> list[str]:
    """호환용 즉시 요청. 삭제 API는 대기열 기록과 이력 삭제를 한 트랜잭션으로 묶는다."""
    await queue_case_deletions(db, case_ids)
    await db.commit()
    return await cleanup_queued_cases(db)


async def purge_expired_vectors(db) -> list[str]:
    result = await db.execute(select(AnalysisJob.case_id).where(
        AnalysisJob.case_id.isnot(None),
        AnalysisJob.created_at < retention_cutoff(),
    ))
    await queue_case_deletions(db, result.scalars().all())
    await db.commit()
    return await cleanup_queued_cases(db)
