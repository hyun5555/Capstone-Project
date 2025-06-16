from fastapi import APIRouter
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.clients.registry_api import get_registry_info
from app.clients.building_api import get_building_title_info
from app.services.sllm_model import extract_fields, compare_flags_gpt4, generate_explanations, compile_report

router = APIRouter()

@router.post("/analyze/", response_model=AnalyzeResponse)
async def analyze_property(data: AnalyzeRequest):
    # 1. 등기부 / 건축물대장 데이터 불러오기
    registry_data = await get_registry_info(data.address)
    building_data = await get_building_title_info(data.address)

    # 2. 텍스트 가공 (추출된 문장 형태)
    reg_text = f"소유자: {registry_data['owner']}, 용도: {registry_data['usage']}, 구조: {registry_data['structure']}, 전용면적: {registry_data['area']}, 채권최고액: {registry_data['mortgage']}, 권리: {registry_data.get('rights', '없음')}"
    bld_text = f"소유자: {building_data['owner']}, 용도: {building_data['usage']}, 구조: {building_data['structure']}, 전용면적: {building_data['area']}, 채권최고액: 없음, 권리: 없음"

    # 3. 필드 추출
    reg_fields = extract_fields(reg_text)
    bld_fields = extract_fields(bld_text)

    # 4. GPT-4 분석
    flags = compare_flags_gpt4(reg_fields, bld_fields)
    explanations = generate_explanations(flags, reg_fields, bld_fields)
    report = compile_report("case_001", data.address, flags, explanations)

    # 5. 결과 반환
    return AnalyzeResponse(
        address=data.address,
        flags=flags,
        explanations=explanations,
        report=report
    )
