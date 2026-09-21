# app/clients/codef_auth.py
# codef 토큰 발급 모듈
import httpx
import base64
from app.config import (
    CODEF_CLIENT_ID,
    CODEF_CLIENT_SECRET,
    SECOND_CODEF_CLIENT_ID,
    SECOND_CODEF_CLIENT_SECRET,
)

async def get_codef_token():
    return await _get_token_from_codef(CODEF_CLIENT_ID, CODEF_CLIENT_SECRET)

async def get_second_codef_token():
    return await _get_token_from_codef(
        SECOND_CODEF_CLIENT_ID,
        SECOND_CODEF_CLIENT_SECRET,
    )

async def _get_token_from_codef(client_id: str, client_secret: str):
    basic_token = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {basic_token}",
    }
    data = "grant_type=client_credentials&scope=read"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth.codef.io/oauth/token",
            headers=headers,
            content=data,
        )
        response.raise_for_status()
        return response.json()["access_token"]
