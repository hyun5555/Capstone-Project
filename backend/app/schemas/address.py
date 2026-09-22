# app/schemas/address.py

from pydantic import BaseModel
from typing import Optional

class JusoItem(BaseModel):
  roadAddr: str                  # 도로명 주소
  jibunAddr: str                 # 지번 주소
  zipNo: str                     # 우편번호
  bdNm: str                      # 건물명
  bdMgtSn: str                   # 건물관리번호
  detBdNmList: Optional[str]     # 상세건물명
  siNm: str                      # 시도명
  sggNm: str                     # 시군구명
  emdNm: str                     # 읍면동명
  lnbrMnnm: str                  # 지번본번(번지)
  lnbrSlno: str                  # 지번부번(호)
  roadName: str                  # 도로명
  bcode: str                     # 법정동코드
  mainAddressNo: str             # 건물 본번
  subAddressNo: str              # 건물 부번
