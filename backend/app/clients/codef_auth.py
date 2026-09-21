# app/clients/codef_auth.py
# 토큰 발급은 codef_client.CodefClient 로 통합되었다. 이 파일은 기존 import 호환용이며 서버 내부에서만 쓴다.
from app.clients.codef_client import get_codef_client


async def get_codef_token() -> str:
    return await get_codef_client().get_token()
