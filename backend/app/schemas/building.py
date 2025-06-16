# app/schemas/building.py

from pydantic import BaseModel
from typing import Optional, List

# 요청 받을 때 사용할 스키마
class TitleInfoRequest(BaseModel):
    fullAddress: str          # 전체주소(참고용)
    roadName: str             # 도로명
    bcode: str                # 법정동코드
    mainAddressNo: str        # 본번
    subAddressNo: str         # 부번
    price: int
    
# CODEF 응답 받을 때 사용할 스키마
class ResDetailItem(BaseModel):
    resType: Optional[str]      # 상세 정보 유형 코드
    resContents: Optional[str]  # 상세 내용 (예: 건축물명 등)

class ResBuildingStatusItem(BaseModel):
    resType: Optional[str]      # 구분 (ex. 주, 부속 등)
    resFloor: Optional[str]     # 층수 (ex. 1, 2, 옥탑 등)
    resStructure: Optional[str] # 구조 (ex. 철근콘크리트구조 등)
    resUseType: Optional[str]   # 용도 (ex. 공동주택, 근린생활시설 등)
    resArea: Optional[str]      # 면적 (m²)

class ResOwnerItem(BaseModel):
    resOwner: Optional[str]          # 소유자 성명
    resIdentityNo: Optional[str]     # 소유자 주민등록번호 (마스킹)
    resUserAddr: Optional[str]       # 소유자 주소
    resOwnershipStake: Optional[str] # 소유 지분 비율
    resChangeDate: Optional[str]     # 소유권 변동일
    resChangeReason: Optional[str]   # 변동 사유

class TitleInfoItem(BaseModel):
    resDocNo: Optional[str]            # 문서번호 (발급 번호)
    commUniqeNo: Optional[str]         # 건축물대장 고유번호
    resReceiptNo: Optional[str]        # 접수번호
    resAddrDong: Optional[str]         # 행정동명 (법정동명)
    resNumber: Optional[str] = None    # 관리번호
    resUserAddr: Optional[str]         # 사용자가 입력한 전체주소
    commAddrLotNumber: Optional[str]   # 지번 주소
    commAddrRoadName: Optional[str]    # 도로명 주소
    resNote: Optional[str]             # 비고란
    resIssueDate: Optional[str]        # 발급일자
    resIssueOgzNm: Optional[str]       # 발급기관명
    resOriGinalData: Optional[str]     # 원본 데이터 식별정보

    resDetailList: Optional[List[ResDetailItem]]              # 상세정보 리스트
    resBuildingStatusList: Optional[List[ResBuildingStatusItem]] # 층별현황 리스트
    resLicenseClassList: Optional[List[dict]]                 # 허가 정보 리스트
    resParkingLotStatusList: Optional[List[dict]]             # 주차장 현황 리스트
    resAuthStatusList: Optional[List[dict]]                   # 인증 현황 리스트
    resChangeList: Optional[List[dict]]                       # 변동사항 리스트
    resOwnerList: Optional[List[ResOwnerItem]]                # 소유자 리스트
    
    resViolationStatus: Optional[str]   # 위반건축물 여부
