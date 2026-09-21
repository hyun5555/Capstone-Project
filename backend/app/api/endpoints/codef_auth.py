# app/api/endpoints/codef_auth.py
# CODEF 토큰은 서버 내부(codef_client)에서만 쓰고 API 로 돌려주지 않는다. (기존 GET /codef/token 제거)
from fastapi import APIRouter, HTTPException

from app.clients.codef_client import CodefError, get_codef_client, http_status_for
from app.schemas.codef import ConnectedIdRequest
from app.utils.codef_rsa import encrypt_codef_password

router = APIRouter(prefix="/codef", tags=["CODEF 인증"])


# ✅ Connected ID 등록
@router.post("/register-connected-id")
async def register_connected_id_api(data: ConnectedIdRequest):
    client = get_codef_client()
    try:
        client.require(CODEF_PUBLIC_KEY=client.settings.public_key)
        body = {
            "organization": data.organization,
            "realEstateName": data.realEstateName,
            "password": encrypt_codef_password(data.password),
            "loginType": "1",
            "isConsent": True,
            "isIdentity": True,
        }
        result = await client.post("/v1/account/real-estate/register", body)
    except CodefError as e:
        raise HTTPException(status_code=http_status_for(e), detail=e.message)
    except ValueError as e:                      # 암호화 실패 (키 형식 등)
        raise HTTPException(status_code=500, detail=str(e))

    connected_id = result.get("connectedId")
    if not connected_id:
        raise HTTPException(status_code=502, detail="CODEF 응답에 connectedId 가 없습니다.")
    return {"connectedId": connected_id}
