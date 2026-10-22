# backend/app/api/endpoints/properties.py
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from typing import List, Optional

from app.db.session import get_db
from app.models.property import Property
from app.clients.building_api import get_building_title_info
from app.clients.registry_api import get_registry_info
from app.clients.codef_client import CodefError, http_status_for
from app.services.codef_normalizer import normalize_building_response, normalize_registry_response
from app.services.auth import get_current_user
from app.services.rate_limit import analysis_rate_limit
from app.utils.masking import mask_person_name
from app.models.user import User

# 라우터 생성
router = APIRouter(prefix="/property", tags=["Property"])


def _upsert_property_docs(docs):
    from app.services.vector_db import upsert_property_docs
    return upsert_property_docs(docs)

# Pydantic 모델
class PropertyCreate(BaseModel):
    address: str
    detail_address: Optional[str] = None
    property_value: Optional[float] = None
    estimated_price: Optional[float] = None
    risk_summary: Optional[str] = None

class PropertyUpdate(BaseModel):
    detail_address: Optional[str] = None
    property_value: Optional[float] = None
    estimated_price: Optional[float] = None
    risk_summary: Optional[str] = None

class PropertyOut(PropertyCreate):
    model_config = ConfigDict(from_attributes=True)

    property_id: int

# CRUD Endpoints
@router.post("/", response_model=PropertyOut)
async def create_property(
    property: PropertyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new_property = Property(owner_id=current_user.user_id, **property.model_dump())
    db.add(new_property)
    await db.commit()
    await db.refresh(new_property)
    return new_property

@router.get("/", response_model=List[PropertyOut])
async def read_properties(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Property).where(Property.owner_id == current_user.user_id).offset(skip).limit(min(limit, 100))
    )
    return list(result.scalars().all())

@router.get("/{property_id}", response_model=PropertyOut)
async def read_property(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Property).where(Property.property_id == property_id, Property.owner_id == current_user.user_id)
    )
    prop = result.scalars().first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

@router.put("/{property_id}", response_model=PropertyOut)
async def update_property(
    property_id: int,
    prop_update: PropertyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Property).where(Property.property_id == property_id, Property.owner_id == current_user.user_id)
    )
    prop = result.scalars().first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    for key, value in prop_update.model_dump(exclude_unset=True).items():
        setattr(prop, key, value)
    await db.commit()
    await db.refresh(prop)
    return prop

@router.delete("/{property_id}")
async def delete_property(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Property).where(Property.property_id == property_id, Property.owner_id == current_user.user_id)
    )
    prop = result.scalars().first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    await db.delete(prop)
    await db.commit()
    return {"detail": "Property deleted"}

# Ingest Endpoint: 외부 API 호출 및 VectorDB 저장
@router.post(
    "/ingest",
    summary="주소 입력 → 건축물대장·등기부조회 → VectorDB 저장"
)
async def ingest_property(
    address: str = Query(..., description="전체 주소"),
    road_name: str = Query(..., description="도로명"),
    main_address_no: str = Query(..., description="본번"),
    sub_address_no: str = Query("0", description="부번"),
    _current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(analysis_rate_limit),
):
    try:
        building_item = await get_building_title_info(road_name, main_address_no, sub_address_no)
        registry_data = await get_registry_info(address)
        if not isinstance(building_item, dict):
            raise HTTPException(status_code=502, detail="건축물대장 응답 형식 오류")
    except CodefError as e:
        raise HTTPException(status_code=http_status_for(e), detail=e.message)

    building = normalize_building_response(building_item, address)
    registry = normalize_registry_response(registry_data, address)
    case_id = hashlib.sha256(address.encode("utf-8")).hexdigest()[:16]
    owners = ", ".join(mask_person_name(name) for name in registry.owner_names) or "확인 불가"
    rights = ", ".join(sorted({right.type for right in registry.active_rights})) or "없음"
    docs = [
        {
            "id": f"building-{case_id}",
            "text": f"건축물대장 주소: {address}, 용도: {building.usage}, 구조: {building.structure}, 연면적: {building.area_total}",
            "metadata": {"source": "building", "address": address},
        },
        {
            "id": f"registry-{case_id}",
            "text": f"등기부 주소: {address}, 소유자: {owners}, 유효 권리: {rights}, 채권최고액: {registry.max_claim_amount}",
            "metadata": {"source": "registry", "address": address},
        },
    ]

    # 4) VectorDB Upsert
    try:
        await run_in_threadpool(_upsert_property_docs, docs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VectorDB upsert 실패: {type(e).__name__}")

    return {"message": "VectorDB에 저장 완료", "ingested": len(docs), "ids": [d["id"] for d in docs]}
