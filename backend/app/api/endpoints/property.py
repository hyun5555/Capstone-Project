# backend/app/api/endpoints/properties.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.db.session import SessionLocal
from app.models.property import Property
from app.clients.building_api import get_building_title_info
from app.clients.registry_api import get_registry_info
from app.services.vector_db import upsert_property_docs

# 라우터 생성
router = APIRouter(prefix="/property", tags=["Property"])

# DB 세션 의존성

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
    property_id: int

    class Config:
        form_attributes = True

# CRUD Endpoints
@router.post("/", response_model=PropertyOut)
def create_property(property: PropertyCreate, db: Session = Depends(get_db)):
    new_property = Property(**property.dict())
    db.add(new_property)
    db.commit()
    db.refresh(new_property)
    return new_property

@router.get("/", response_model=List[PropertyOut])
def read_properties(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Property).offset(skip).limit(limit).all()

@router.get("/{property_id}", response_model=PropertyOut)
def read_property(property_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.property_id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

@router.put("/{property_id}", response_model=PropertyOut)
def update_property(property_id: int, prop_update: PropertyUpdate, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.property_id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    for key, value in prop_update.dict(exclude_unset=True).items():
        setattr(prop, key, value)
    db.commit()
    db.refresh(prop)
    return prop

# Ingest Endpoint: 외부 API 호출 및 VectorDB 저장
@router.post(
    "/ingest",
    summary="지번 입력 → 건축물대장·등기부조회 → VectorDB 저장"
)
async def ingest_property(
    plat_gb_cd: str = Query(..., description="지번 구분 코드, ex: '0'"),
    bun: str = Query(..., description="지번 본번, ex: '123'"),
    ji: str = Query(..., description="지번 부번, ex: '45'")
):
    # 1) 건축물대장 조회
    real_estate_unique_number = f"{plat_gb_cd.zfill(10)}{bun.zfill(4)}{ji.zfill(4)}"
    try:
        building_item = await get_building_title_info(real_estate_unique_number)
        if not isinstance(building_item, dict):
            raise HTTPException(status_code=502, detail="건축물대장 응답 형식 오류")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"건축물대장 조회 실패: {e}")
    building_items = [building_item]  # 기존 로직과 호환을 위해 리스트로 래핑

    # 2) 등기부등본 조회
    jibun = f"{bun}-{ji}"
    registry_data = await fetch_registry(jibun)

    # 3) VectorDB에 저장할 문서 리스트 생성
    docs = []
    for idx, item in enumerate(building_items):
        summary_text = (
            f"건축물명: {item.get('bldNm')}, "
            f"용도: {item.get('mainPurps')}, "
            f"면적: {item.get('purpsArea')}"
        )
        docs.append({
            "id": f"building_{plat_gb_cd}_{bun}_{ji}_{idx}",
            "text": summary_text,
            "metadata": {"source": "building", "platGbCd": plat_gb_cd, "bun": bun, "ji": ji, **item}
        })

    # 등기부등본 요약
    summary_text = (
        f"소유자: {registry_data.get('ownerName')}, "
        f"등기일: {registry_data.get('regDate')}, "
        f"물건형태: {registry_data.get('propertyKind')}"
    )
    docs.append({
        "id": f"registry_{jibun}",
        "text": summary_text,
        "metadata": {"source": "registry", **registry_data}
    })

    # 4) VectorDB Upsert
    try:
        upsert_property_docs(docs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VectorDB upsert 실패: {e}")

    return {"message": "VectorDB에 저장 완료", "ingested": len(docs), "ids": [d["id"] for d in docs]}
