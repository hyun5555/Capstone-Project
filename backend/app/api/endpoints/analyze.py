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

@router.post("/")
async def analyze_property(data: AnalyzeRequest):
    registry_path = Path("/home/ubuntu/Capstone-Project/backend/registry.json")



    if not registry_path.exists():
        raise FileNotFoundError(f"등기부 JSON 파일이 없습니다: {registry_path}")

    with open(registry_path, "r", encoding="utf-8") as f:
        registry_data = json.load(f)

    building_data = await get_building_title_info(data.address)

    # 텍스트 구성
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
        f"소유자: {building_data['owner']}, "
        f"용도: {building_data['usage']}, "
        f"구조: {building_data['structure']}, "
        f"전용면적: {building_data['area']}, "
        f"공유면적: {building_data.get('shared_area', '없음')}, "
        f"연면적: {building_data.get('total_area', '없음')}, "
        f"준공년도: {building_data.get('build_year', '없음')}, "
        f"채권최고액: 없음, 권리: 없음"
    )

    reg_fields = extract_fields(reg_text)
    bld_fields = extract_fields(bld_text)

    flags = compare_flags_gpt4(reg_fields, bld_fields)
    explanations = generate_explanations(flags, reg_fields, bld_fields)

    # 리스크 점수 계산을 위한 metadata 구성
    findings = {
        "등기부_소유자": reg_fields.get("소유자명"),
        "건축물대장_소유자": bld_fields.get("소유자명"),
        "위험_권리_목록": reg_fields.get("위험 권리 목록", []),
        "채권최고액": reg_fields.get("근저당 설정 유무", 0),
        "위반건축물": False,
        "불법용도변경": False,
        "건물 용도": reg_fields.get("건물 용도", ""),
    }

    risk_result = calculate_risk_score(findings, transaction_data={"보증금": data.deposit, "시세": data.marketPrice})

    # ✅ Flutter에서 사용하는 형태로 맞춤
    risk_items = []
    for key in flags:
        risk_items.append({
            "title": key,
            "score": 100 if flags[key] == "일치" else 30,
            "explanation": explanations.get(key, "설명 없음")
        })

    return {
        "success": True,
        "data": {
            "address": data.address,
            "risk_score": risk_result["score"],
            "risk_items": risk_items
        }
    }
