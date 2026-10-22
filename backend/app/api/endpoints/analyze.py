import asyncio
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.clients.codef_client import CodefError, get_codef_client, http_status_for
from app.config import (
    ANALYSIS_DATA_SOURCE, CHUNK_OVERLAP, CHUNK_SIZE, CODEF_SAMPLE_DIR, OPENAI_API_KEY, RETRIEVAL_STRATEGY,
    RETRIEVAL_TOP_K, PDF_ANALYSIS_CONCURRENCY, PDF_ANALYSIS_TIMEOUT_SEC,
)
from app.db.session import AsyncSessionLocal, get_db
from app.models.analysis_cases import AnalysisJob
from app.models.user import User
from app.schemas.analyze import AnalyzeRequest
from app.services.document_compare import MATCH, MISMATCH, UNKNOWN, build_findings, compare_documents, unverified_fields
from app.services.document_source import (
    MissingAddressParts, SampleDataMissing, load_codef_documents, load_pdf_documents, load_sample_documents,
)
from app.services.chunker import case_id_for
from app.services.evidence import collect_evidence
from app.services.market_price import resolve_market_price
from app.services.pdf_extractor import MAX_PDF_BYTES, PdfError
from app.services.rag_explain import RIGHTS_FIELD, explain_with_evidence
from app.services.risk_score import calculate_risk_score
from app.services.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)
_pdf_slots = asyncio.Semaphore(max(1, PDF_ANALYSIS_CONCURRENCY))

# 항목별 화면 점수. 앱은 "높을수록 위험" 으로 막대와 색을 그리므로 일치=낮게, 불일치=높게, 비교불가=중간.
_ITEM_SCORE = {MATCH: 10, MISMATCH: 80, UNKNOWN: 50}


def _llm_judge(field: str, reg_value: str, bld_value: str):
    """표현이 다른 용도/구조만 LLM 에 물어본다. 이름 같은 개인정보는 보내지 않는다. 실패하면 None."""
    from app.services.sllm_model import compare_flags_llm   # OPENAI_API_KEY 가 없으면 여기서 실패 → None
    flags = compare_flags_llm({field: reg_value}, {field: bld_value}, field_list=[field])
    return flags.get(field)


def _collect_evidence(reg, bld):
    """두 문서를 청킹·저장하고 항목별 근거 청크를 검색한다. (case_id, evidence, 메모). 실패해도 분석은 계속한다."""
    case_id = case_id_for(reg, bld)
    if not OPENAI_API_KEY:
        return case_id, {}, "OPENAI_API_KEY 가 없어 근거 청크 검색을 건너뛰었습니다."
    try:
        from app.services.vector_db import get_chunk_store
        _, evidence = collect_evidence(
            get_chunk_store(), reg, bld, CHUNK_SIZE, CHUNK_OVERLAP, RETRIEVAL_TOP_K, RETRIEVAL_STRATEGY
        )
        return case_id, evidence, ""
    except Exception as e:
        return case_id, {}, f"근거 청크 검색에 실패했습니다: {type(e).__name__}"


def _compare(reg, bld):
    return compare_documents(reg, bld, semantic_judge=_llm_judge)


def _build_notices(market, deposit, docs_notes, evidence_note):
    """화면에 그대로 보여 줄 안내 문장."""
    notices = list(docs_notes)
    if evidence_note:
        notices.append(evidence_note)
    if market.source == "molit_median":
        notices.append(f"시세: {market.value_won:,}원 — {market.note}")
    elif market.source == "unavailable":
        notices.append(f"시세를 알 수 없어 근저당 비율과 깡통 위험은 판단불가로 처리했습니다. ({market.note})")
    if deposit <= 0:
        notices.append("전세 보증금이 0원으로 입력되어 깡통 위험 계산에서 보증금이 빠졌습니다.")
    return notices


async def _analyze_loaded_docs(docs, address: str, deposit: int, market_price: int = None):
    reg, bld = docs.registry, docs.building
    comparison, evidence_result, market = await asyncio.gather(
        run_in_threadpool(_compare, reg, bld),
        run_in_threadpool(_collect_evidence, reg, bld),
        resolve_market_price(
            address, bld.usage or reg.usage, bld.area_exclusive or reg.area_exclusive, market_price
        ),
    )
    findings = build_findings(reg, bld, comparison)
    case_id, evidence, evidence_note = evidence_result
    # LLM 설명과 위험 점수는 서로 독립적이다. check_defaulter 는 블로킹 호출이라 둘 다 스레드에서 실행한다.
    explained, risk = await asyncio.gather(
        run_in_threadpool(explain_with_evidence, comparison, evidence, findings),
        run_in_threadpool(calculate_risk_score, findings, {"보증금": deposit, "시세": market.value_won}),
    )

    risk_items = [
        {
            "title": name,
            "status": item["status"],
            "score": _ITEM_SCORE[item["status"]],
            "explanation": explained[name]["explanation"],
            "explanation_source": explained[name]["source"],
            "grounded": explained[name]["grounded"],
            "evidence": explained[name]["evidence"],
        }
        for name, item in comparison.items()
    ]

    return {
        "success": True,
        "data": {
            "address": address,
            "risk_score": risk["score"],
            "risk_grade": risk["grade"],
            "risk_reasons": risk["reasons"],
            "risk_factors": risk["factors"],
            "risk_skipped": risk["skipped"],
            "risk_incomplete": risk["incomplete"],
            "risk_ratios": risk["ratios"],
            "market_price": market.to_dict(),
            "risk_items": risk_items,
            "rights": explained[RIGHTS_FIELD],
            "unverified": unverified_fields(comparison),
            "data_source": docs.source,
            "document_processing": getattr(docs, "processing", {}),
            "notes": _build_notices(market, deposit, docs.notes, evidence_note),
            "case_id": case_id,
            "evidence": evidence,
        },
    }


async def _store_completed_job(db: AsyncSession, user_id: str, result: dict) -> str:
    job_id = str(uuid.uuid4())
    db.add(AnalysisJob(
        job_id=job_id,
        user_id=user_id,
        status="succeeded",
        stage="분석 완료",
        case_id=result["data"]["case_id"],
        result=result,
    ))
    await db.commit()
    return job_id


@router.post("/")
async def analyze_property(
    data: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        if ANALYSIS_DATA_SOURCE == "sample":
            docs = load_sample_documents(data.address, CODEF_SAMPLE_DIR, data.scenario)
        else:
            docs = await load_codef_documents(
                get_codef_client(), data.address, data.roadName, data.mainAddressNo, data.subAddressNo
            )
    except MissingAddressParts as e:
        raise HTTPException(status_code=422, detail=str(e))
    except CodefError as e:
        raise HTTPException(status_code=http_status_for(e), detail=e.message)
    except SampleDataMissing as e:
        raise HTTPException(status_code=500, detail=str(e))
    result = await _analyze_loaded_docs(docs, data.address, data.deposit, data.marketPrice)
    result["data"]["job_id"] = await _store_completed_job(db, current_user.user_id, result)
    return result


async def _read_pdf(upload: UploadFile) -> bytes:
    try:
        data = await upload.read(MAX_PDF_BYTES + 1)
    finally:
        await upload.close()
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF는 파일당 20MB 이하여야 합니다.")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=422, detail="PDF 파일 형식이 아닙니다.")
    return data


async def _process_pdf(
    registry_data: bytes,
    building_data: bytes,
    address: str,
    deposit: int,
    market_price: int = None,
    job_id: str = None,
):
    if job_id:
        await _update_job(job_id, status="processing", stage="PDF 텍스트와 OCR을 처리하는 중")
    docs = await _load_pdf_documents_with_limits(registry_data, building_data, address)
    if job_id:
        await _update_job(job_id, stage="문서 근거와 위험 요소를 분석하는 중")
    return await _analyze_loaded_docs(docs, address, deposit, market_price)


async def _load_pdf_documents_with_limits(registry_data: bytes, building_data: bytes, address: str):
    await _pdf_slots.acquire()
    task = asyncio.create_task(run_in_threadpool(load_pdf_documents, registry_data, building_data, address))

    def release_slot(done_task):
        _pdf_slots.release()
        if not done_task.cancelled():
            done_task.exception()

    # The worker thread cannot be killed safely; keep its slot until it really exits after a timeout.
    task.add_done_callback(release_slot)
    return await asyncio.wait_for(asyncio.shield(task), timeout=PDF_ANALYSIS_TIMEOUT_SEC)


async def _run_with_pdf_limits(*args, **kwargs):
    return await asyncio.wait_for(_process_pdf(*args, **kwargs), timeout=PDF_ANALYSIS_TIMEOUT_SEC)


async def _update_job(job_id: str, **values) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(AnalysisJob, job_id)
        if job is None:
            return
        for key, value in values.items():
            setattr(job, key, value)
        await db.commit()


async def _run_pdf_job(job_id: str, registry_data: bytes, building_data: bytes,
                       address: str, deposit: int, market_price: int = None) -> None:
    try:
        result = await _run_with_pdf_limits(
            registry_data, building_data, address, deposit, market_price, job_id=job_id
        )
        await _update_job(
            job_id,
            status="succeeded",
            stage="분석 완료",
            case_id=result["data"]["case_id"],
            result=result,
            error=None,
        )
    except asyncio.TimeoutError:
        await _update_job(job_id, status="failed", stage="분석 실패", error="PDF 분석 시간이 초과되었습니다.")
    except PdfError as exc:
        await _update_job(job_id, status="failed", stage="분석 실패", error=str(exc))
    except Exception:
        logger.exception("PDF 비동기 분석 실패: job_id=%s", job_id)
        await _update_job(job_id, status="failed", stage="분석 실패", error="PDF 분석 중 오류가 발생했습니다.")


@router.post("/pdf")
async def analyze_pdf(
    registry_pdf: UploadFile = File(...),
    building_pdf: UploadFile = File(...),
    address: str = Form(...),
    deposit: int = Form(...),
    marketPrice: int = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not address.strip():
        raise HTTPException(status_code=422, detail="주소를 입력해 주세요.")
    registry_data, building_data = await asyncio.gather(_read_pdf(registry_pdf), _read_pdf(building_pdf))
    try:
        result = await _run_with_pdf_limits(
            registry_data, building_data, address.strip(), deposit, marketPrice
        )
    except PdfError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="PDF 분석 시간이 초과되었습니다.")
    result["data"]["job_id"] = await _store_completed_job(db, current_user.user_id, result)
    return result


@router.post("/pdf/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_pdf_job(
    background_tasks: BackgroundTasks,
    registry_pdf: UploadFile = File(...),
    building_pdf: UploadFile = File(...),
    address: str = Form(...),
    deposit: int = Form(..., gt=0),
    marketPrice: int = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not address.strip():
        raise HTTPException(status_code=422, detail="주소를 입력해 주세요.")
    registry_data, building_data = await asyncio.gather(_read_pdf(registry_pdf), _read_pdf(building_pdf))
    job_id = str(uuid.uuid4())
    db.add(AnalysisJob(job_id=job_id, user_id=current_user.user_id, status="queued", stage="분석 대기 중"))
    await db.commit()
    # shortcut: queued PDF bytes live in one API process, use durable object storage and a worker queue before multi-worker deployment.
    background_tasks.add_task(
        _run_pdf_job, job_id, registry_data, building_data, address.strip(), deposit, marketPrice
    )
    return {"job_id": job_id, "status": "queued", "stage": "분석 대기 중"}


@router.get("/pdf/jobs/{job_id}")
async def get_pdf_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(AnalysisJob).where(
        AnalysisJob.job_id == job_id,
        AnalysisJob.user_id == current_user.user_id,
    ))
    job = result.scalars().first()
    if job is None:
        raise HTTPException(status_code=404, detail="분석 작업을 찾을 수 없습니다.")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "stage": job.stage,
        "error": job.error,
        "result": job.result if job.status == "succeeded" else None,
    }
