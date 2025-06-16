# app/api/endpoints/registry.py
from fastapi import APIRouter, HTTPException
from app.schemas.registry import RegistryRequest, RegistryData
from app.clients.registry_api import get_registry_info

router = APIRouter(prefix="/registry", tags=["등기부등본"])

@router.post("/", response_model=RegistryData)
async def fetch_registry_api(data: RegistryRequest):
    try:
        result = await get_registry_info(data.dict())
        return RegistryData(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"등기부등본 조회 실패: {str(e)}")
