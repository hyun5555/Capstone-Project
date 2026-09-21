# backend/app/clients/registry_api.py
# CODEF 등기부등본 조회. 공통 로직(토큰·암호화·오류 처리)은 codef_client.py 에 있다.
from app.clients.codef_client import fetch_registry, get_codef_client


async def get_registry_info(address: str) -> dict:
    """주소로 등기부등본을 조회해 CODEF 응답의 data 부분(원본)을 돌려준다. 실패하면 CodefError."""
    return await fetch_registry(get_codef_client(), address)
