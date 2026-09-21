# app/api/endpoints/analyze.py
from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from app.clients.codef_client import CodefError, get_codef_client, http_status_for
from app.config import (
    ANALYSIS_DATA_SOURCE, CHUNK_OVERLAP, CHUNK_SIZE, CODEF_SAMPLE_DIR, OPENAI_API_KEY, RETRIEVAL_STRATEGY,
    RETRIEVAL_TOP_K,
)
from app.schemas.analyze import AnalyzeRequest
from app.services.document_compare import MATCH, MISMATCH, UNKNOWN, build_findings, compare_documents, unverified_fields
from app.services.document_source import (
    MissingAddressParts, SampleDataMissing, load_codef_documents, load_sample_documents,
)
from app.services.chunker import case_id_for
from app.services.evidence import collect_evidence
from app.services.market_price import resolve_market_price
from app.services.rag_explain import RIGHTS_FIELD, explain_with_evidence
from app.services.risk_score import calculate_risk_score

router = APIRouter()

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


@router.post("/")
async def analyze_property(data: AnalyzeRequest):
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

    reg, bld = docs.registry, docs.building
    comparison = await run_in_threadpool(_compare, reg, bld)
    findings = build_findings(reg, bld, comparison)
    case_id, evidence, evidence_note = await run_in_threadpool(_collect_evidence, reg, bld)
    explained = await run_in_threadpool(explain_with_evidence, comparison, evidence, findings)

    # 시세: 사용자 입력 → 같은 동 최근 매매 실거래가 중앙값 → 판단불가(None). 임의의 값으로 채우지 않는다.
    market = await resolve_market_price(
        data.address, bld.usage or reg.usage, bld.area_exclusive or reg.area_exclusive, data.marketPrice
    )
    # check_defaulter 가 외부 사이트를 호출(블로킹)하므로 스레드에서 계산한다.
    risk = await run_in_threadpool(
        calculate_risk_score, findings, {"보증금": data.deposit, "시세": market.value_won}
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
            "address": data.address,
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
            "notes": _build_notices(market, data.deposit, docs.notes, evidence_note),
            "case_id": case_id,
            "evidence": evidence,
        },
    }
