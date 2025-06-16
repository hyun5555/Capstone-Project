# app/api/endpoints/building.py

from fastapi import APIRouter, HTTPException
from app.clients.building_api import get_building_title_info
from app.schemas.building import TitleInfoItem, TitleInfoRequest

router = APIRouter(prefix="/building", tags=["건축물대장"])

@router.post("/title-info", response_model=dict, summary="건축물대장 표제부 조회 (POST)")
async def title_info_post(request: TitleInfoRequest):
    plat_gb_cd = "1"
    bun = request.mainAddressNo.zfill(4)
    ji = request.subAddressNo.zfill(4)
    real_estate_unique_number = f"{request.bcode}{plat_gb_cd}{bun}{ji}0"

    body = {
        "roadName": request.roadName,
        "mainAddressNo": request.mainAddressNo,
        "subAddressNo": request.subAddressNo,
        "address": request.roadName,
        "type": "0"
    }

    try:
        data = await get_building_title_info(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if data.get("continue2Way"):
        raise HTTPException(status_code=404, detail="2-way 주소 매칭 실패 (해당 주소 없음)")

    if data.get("resDocNo"):
        result = TitleInfoItem.model_validate(data)
        return result.model_dump()

    raise HTTPException(status_code=500, detail="예상치 못한 응답 형식")