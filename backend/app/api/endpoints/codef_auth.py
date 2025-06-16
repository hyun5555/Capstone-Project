# app/api/endpoints/codef_auth.py

import httpx
import base64
import os
from fastapi import APIRouter, HTTPException, Body
from app.utils.codef_rsa import encrypt_codef_password
from app.schemas.codef import ConnectedIdRequest

router = APIRouter(prefix="/codef", tags=["CODEF 인증"])

# ✅ 내부 유틸 함수
async def get_codef_token():
    client_id = os.getenv("CODEF_CLIENT_ID")
    client_secret = os.getenv("CODEF_CLIENT_SECRET")
    return await _get_token_from_codef(client_id, client_secret)

async def _get_token_from_codef(client_id: str, client_secret: str):
    basic_token = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {basic_token}",
    }
    data = "grant_type=client_credentials&scope=read"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://development.codef.io/oauth/token",
            headers=headers,
            content=data,
        )
        response.raise_for_status()
        return response.json()["access_token"]

# ✅ 테스트용 (Swagger에서 직접 토큰 확인 가능)
@router.get("/token")
async def get_codef_token_api():
    try:
        token = await get_codef_token()
        return {"access_token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Connected ID 등록
@router.post("/register-connected-id")
async def register_connected_id_api(data: ConnectedIdRequest):
    try:
        token = await get_codef_token()
        encrypted_pw = encrypt_codef_password(data.password)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        body = {
            "organization": data.organization,
            "realEstateName": data.realEstateName,
            "password": encrypted_pw,
            "loginType": "1",
            "isConsent": True,
            "isIdentity": True
        }

        url = "https://development.codef.io/v1/account/real-estate/register"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            result = response.json()
            connected_id = result["data"]["connectedId"]

           

            return {"connectedId": connected_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
