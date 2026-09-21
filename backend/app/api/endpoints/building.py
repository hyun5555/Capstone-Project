# app/api/endpoints/building.py
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.clients.building_api import get_building_title_info
from app.clients.codef_client import CodefError, http_status_for
from app.config import ANALYSIS_DATA_SOURCE, CODEF_SAMPLE_DIR
from app.schemas.building import TitleInfoRequest
from app.services.document_source import SAMPLE_BUILDING_FILE, SampleDataMissing, read_sample_response
from app.utils.masking import mask_building_response

router = APIRouter(prefix="/building", tags=["건축물대장"])


@router.post("/title-info", response_model=dict, summary="건축물대장 표제부 조회 (POST)")
async def title_info_post(request: TitleInfoRequest):
    try:
        if ANALYSIS_DATA_SOURCE == "sample":
            data = read_sample_response(Path(CODEF_SAMPLE_DIR) / SAMPLE_BUILDING_FILE)
        else:
            data = await get_building_title_info(request.roadName, request.mainAddressNo, request.subAddressNo)
    except CodefError as e:
        raise HTTPException(status_code=http_status_for(e), detail=e.message)
    except SampleDataMissing as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not data.get("resDocNo"):
        raise HTTPException(status_code=502, detail="예상치 못한 응답 형식")

    # 소유자 이름·주민번호·주소는 앱으로 그대로 내보내지 않는다.
    return mask_building_response(data)
