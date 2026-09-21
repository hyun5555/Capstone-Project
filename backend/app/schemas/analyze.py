# app/schemas/analyze.py
from pydantic import BaseModel
from typing import Dict, Literal, Optional


class AnalyzeRequest(BaseModel):
    address: str
    deposit: int                      # 전세 보증금 (원)
    # 매매 시세 (원). 없으면 서버가 같은 동의 최근 매매 실거래가 중앙값으로 추정하고, 그것도 못 구하면 '판단불가' 로 처리한다.
    marketPrice: Optional[int] = None
    # 건축물대장 조회용 (주소 검색 결과에서 앱이 그대로 보내 준다). CODEF 조회 모드에서는 roadName, mainAddressNo 가 필요하다.
    roadName: Optional[str] = None
    mainAddressNo: Optional[str] = None
    subAddressNo: Optional[str] = None
    scenario: Optional[Literal[
        "safe",
        "owner_mismatch",
        "active_seizure",
        "excessive_mortgage",
        "cancelled_rights",
        "violation_nonresidential",
        "lease_rights",
    ]] = None


class AnalyzeResponse(BaseModel):
    address: str
    flags: Dict[str, str]
    explanations: Dict[str, str]
    report: str
