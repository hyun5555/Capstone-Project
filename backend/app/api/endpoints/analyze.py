from fastapi import APIRouter
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.clients.building_api import get_building_title_info
from app.services.sllm_model import (
    extract_fields,
    compare_flags_gpt4,
    generate_explanations,
    compile_report
)
import json
from pathlib import Path

router = APIRouter()

@router.post("/analyze/", response_model=AnalyzeResponse)
async def analyze_property(data: AnalyzeRequest):
    # ✅ 1. registry.json의 절대 경로 (프로젝트 루트 기준 backend/registry.json)
    BASE_DIR = Path(__file__).resolve().parent.parent  # /backend
    registry_path = BASE_DIR / "registry.json"         # /backend/registry.json

    if not registry_path.exists():
        raise FileNotFoundError(f"등기부 JSON 파일이 없습니다: {registry_path}")

    with open(registry_path, "r", encoding="utf-8") as f:
        registry_data = json.load(f)

    # ✅ 2. 건축물대장 API 호출
    building_data = await get_building_title_info(data.address)

    # ✅ 3. 문장 텍스트 구성
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

    # ✅ 4. 필드 추출 및 GPT 분석
    reg_fields = extract_fields(reg_text)
    bld_fields = extract_fields(bld_text)
    flags = compare_flags_gpt4(reg_fields, bld_fields)
    explanations = generate_explanations(flags, reg_fields, bld_fields)
    report = compile_report("case_001", data.address, flags, explanations)

    return AnalyzeResponse(
        address=data.address,
        flags=flags,
        explanations=explanations,
        report=report
    )
