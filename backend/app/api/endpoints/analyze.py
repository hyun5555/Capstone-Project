# app/api/endpoints/analyze.py

from fastapi import APIRouter
from app.schemas.analyze import AnalyzeRequest
from app.clients.building_api import get_building_title_info
from app.services.sllm_model import (
    extract_fields,
    compare_flags_gpt4,
    generate_explanations,
    compile_report
)
from app.services.risk_score import calculate_risk_score
import json
from pathlib import Path

router = APIRouter()

@router.post("/analyze/")
async def analyze_property(data: AnalyzeRequest):
    # ✅ 등기부 JSON 파일 불러오기
    registry_path = Path(__file__).parent.parent.parent / "backend" / "registry.json"
    if not registry_path.exists():
        raise FileNotFoundError(f"등기부 JSON 파일이 없습니다: {registry_path}")
    with open(registry_path, "r", encoding="utf-8") as f:
        registry_data = json.load(f)

    # ✅ 건축물대장 원시 데이터 불러오기
    building_data_raw = await get_building_title_info({
        "fullAddress": data.address,
        "mainAddressNo": "101",
        "subAddressNo": "0",
        "type": "road"
    })

    # ✅ 안전한 필드 추출
    owner = building_data_raw.get("resOwnerList", [{}])[0].get("resOwner", "없음")
    status_list = building_data_raw.get("resBuildingStatusList", [{}])
    usage = status_list[0].get("resUseType", "없음")
    structure = status_list[0].get("resStructure", "없음")
    area = status_list[0].get("resArea", "없음")
    build_year = building_data_raw.get("resIssueDate", "")[:4] or "없음"

    # ✅ 텍스트 구성
    reg_text = (
        f"소유자: {registry_data['소유자명']}, "
        f"용도: {registry_data['건물 용도']}, "
        f"구조: {registry_data['구조 유형']}, "
        f"전용면적: {registry_data['전용면적']}, "
        f"공유면적: {registry_data['공유면적']}, "
        f"연면적: {registry_data['연면적']}, "
        f"준공년도: {registry_data['준공년도']}, "
        f"채권최고액: {registry_data['근저당 설정 유무']}, "
        f"권리: {registry_data['위험 권리 존재 여부']}"
    )

    bld_text = (
        f"소유자: {owner}, "
        f"용도: {usage}, "
        f"구조: {structure}, "
        f"전용면적: {area}, "
        f"공유면적: 없음, "
        f"연면적: 없음, "
        f"준공년도: {build_year}, "
        f"채권최고액: 없음, 권리: 없음"
    )

    # ✅ 필드 추출 및 비교
    reg_fields = extract_fields(reg_text)
    bld_fields = extract_fields(bld_text)

    flags = compare_flags_gpt4(reg_fields, bld_fields)
    print("📌 GPT-4 플래그 결과:", flags)

    explanations = generate_explanations(flags, reg_fields, bld_fields)
    print("📌 GPT-4 설명 결과:", explanations)

    # ✅ 점수 산출용 메타데이터 구성
    findings = {
        "등기부_소유자": reg_fields.get("소유자명"),
        "건축물대장_소유자": bld_fields.get("소유자명"),
        "위험_권리_목록": reg_fields.get("위험 권리 목록", []),
        "채권최고액": reg_fields.get("근저당 설정 유무", 0),
        "위반건축물": False,
        "불법용도변경": False,
        "건물 용도": reg_fields.get("건물 용도", ""),
    }

    risk_result = calculate_risk_score(
        findings,
        transaction_data={
            "보증금": data.deposit,
            "시세": data.marketPrice
        }
    )
    print("📊 위험도 점수:", risk_result["score"])

    risk_items = []
    for key in flags:
        item = {
            "title": key,
            "score": 100 if flags[key] == "일치" else 30,
            "explanation": explanations.get(key, "설명 없음")
        }
        risk_items.append(item)

    print("📋 리스크 항목 리스트:", risk_items)

    response_data = {
        "success": True,
        "data": {
            "address": data.address,
            "risk_score": risk_result["score"],
            "risk_items": risk_items
        }
    }

    print("📤 최종 응답 데이터:", json.dumps(response_data, ensure_ascii=False, indent=2))
    return response_data