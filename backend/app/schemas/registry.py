# app/schemas/registry.py
from pydantic import BaseModel
from typing import Optional, List

# 🔹 요청 스키마
class RegistryRequest(BaseModel):
    realEstateName: str         # 예: 서울특별시 강남구 역삼동 123-45
    password: str               # 사용자 비밀번호 (백엔드에서 RSA 암호화)
    organization: Optional[str] = "0004"  # 기관 코드 (기본값)

# 🔹 응답 스키마
class ResOwnerInfo(BaseModel):
    ownerName: Optional[str]           # 소유자 이름
    ownerIdMasked: Optional[str]       # 주민번호 마스킹
    ownershipShare: Optional[str]      # 지분 비율
    changeDate: Optional[str]          # 소유권 변동일
    changeReason: Optional[str]        # 변동 사유

class ResMortgageInfo(BaseModel):
    mortgageHolder: Optional[str]      # 채권자
    mortgageAmount: Optional[str]      # 채권최고액
    registrationDate: Optional[str]    # 등기일
    registrationReason: Optional[str]  # 등기원인

class RegistryData(BaseModel):
    regNumber: Optional[str]               # 등기번호
    regOffice: Optional[str]               # 등기소명
    propertyLocation: Optional[str]        # 부동산 소재지
    propertyKind: Optional[str]            # 부동산 종류 (예: 대지, 건물)
    regDate: Optional[str]                 # 등기일자
    note: Optional[str]                    # 비고란

    ownerList: Optional[List[ResOwnerInfo]] = []
    mortgageList: Optional[List[ResMortgageInfo]] = []

    originalDataId: Optional[str] = None   # 원본 식별자 (PDF 등)

