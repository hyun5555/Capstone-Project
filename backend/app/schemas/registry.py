# app/schemas/registry.py
from pydantic import BaseModel
from typing import Optional


# 🔹 요청 스키마 — 인증정보(비밀번호 등)는 클라이언트가 보내지 않는다. 서버 .env 의 값을 쓴다.
class RegistryRequest(BaseModel):
    address: str                           # 전체 주소


# 🔹 응답 스키마 (정규화된 등기부 요약. 소유자명은 마스킹되어 나간다)
class RegistryData(BaseModel):
    regNumber: Optional[str] = None               # 등기번호 (추출 가능 시)
    regOffice: Optional[str] = None               # 등기소명 (추출 가능 시)
    propertyLocation: Optional[str] = None        # 부동산 소재지
    propertyKind: Optional[str] = None            # 부동산 종류 (예: 대지, 건물)
    regDate: Optional[str] = None                 # 등기일자
    note: Optional[str] = None                    # 비고란

    ownerName: Optional[str] = None               # 소유자명 (마스킹)
    buildingUse: Optional[str] = None             # 건물 용도
    structureType: Optional[str] = None           # 구조 유형
    exclusiveArea: Optional[str] = None           # 전용면적
    sharedArea: Optional[str] = None              # 공유면적
    totalArea: Optional[str] = None               # 연면적
    buildYear: Optional[str] = None               # 준공년도
    hasMortgage: Optional[str] = None             # 근저당 채권최고액 합계(원). 없으면 None
    hasRiskRights: Optional[str] = None           # 말소되지 않은 위험 권리 목록 (쉼표 구분)

    originalDataId: Optional[str] = None          # 원본 식별자 (PDF 등)
