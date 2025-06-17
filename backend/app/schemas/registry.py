# app/schemas/registry.py
from pydantic import BaseModel
from typing import Optional

# 🔹 요청 스키마
class RegistryRequest(BaseModel):
    organization: str                      # 기관 코드
    phoneNo: str                           # 등록된 전화번호
    password: str                          # 비밀번호 (RSA 암호화)
    inquiryType: str                       # 조회 방식 ("3": 도로명 주소)
    address: str                           # 전체 주소
    addr_sido: Optional[str] = None        # 시/도 (선택, 내부에서 자동 추출 가능)
    recordStatus: Optional[str] = "0"      # 등기기록 상태 ("0": 현행)


# 🔹 응답 스키마 (정규식 기반 추출 결과 포함)
class RegistryData(BaseModel):
    regNumber: Optional[str] = None               # 등기번호 (추출 가능 시)
    regOffice: Optional[str] = None               # 등기소명 (추출 가능 시)
    propertyLocation: Optional[str] = None        # 부동산 소재지
    propertyKind: Optional[str] = None            # 부동산 종류 (예: 대지, 건물)
    regDate: Optional[str] = None                 # 등기일자
    note: Optional[str] = None                    # 비고란

    # 🔸 정규식 기반 추출 필드들
    ownerName: Optional[str] = None               # 소유자명
    buildingUse: Optional[str] = None             # 건물 용도
    structureType: Optional[str] = None           # 구조 유형
    exclusiveArea: Optional[str] = None           # 전용면적
    sharedArea: Optional[str] = None              # 공유면적
    totalArea: Optional[str] = None               # 연면적
    buildYear: Optional[str] = None               # 준공년도
    hasMortgage: Optional[str] = None             # 근저당 설정 유무 (채권최고액)
    hasRiskRights: Optional[str] = None           # 위험 권리 존재 여부 (권리)

    originalDataId: Optional[str] = None          # 원본 식별자 (PDF 등)


