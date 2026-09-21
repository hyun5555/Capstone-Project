# backend/app/clients/building_api.py
# CODEF 건축물대장(표제부) 조회. 공통 로직(토큰·암호화·오류 처리)은 codef_client.py 에 있다.
from app.clients.codef_client import fetch_building, get_codef_client


async def get_building_title_info(road_name: str, main_address_no: str, sub_address_no: str) -> dict:
    """도로명·본번·부번으로 건축물대장을 조회해 CODEF 응답의 data 부분(원본)을 돌려준다. 실패하면 CodefError."""
    return await fetch_building(get_codef_client(), road_name, main_address_no, sub_address_no or "0")
