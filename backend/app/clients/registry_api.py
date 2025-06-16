import httpx
from fastapi import HTTPException
from app.config import CODEF_API_HOST
from app.clients.codef_auth import get_second_codef_token
from app.utils.codef_rsa import encrypt_codef_password
import urllib.parse
import json
import os

CODEF_REGISTRY_URL = f"{CODEF_API_HOST}/v1/kr/public/real-estate/register"

async def get_registry_info(body: dict) -> dict:
    token = await get_second_codef_token()

    # 사용자가 입력한 주소 관련 정보
    jibun = body.get("jibun")  # 예: "123-45"
    organization = body.get("organization", "0004")  # 기본값 사용
    realEstateName = body.get("realEstateName")
    raw_pw = os.getenv("CODEF_USER_PW")

    if not raw_pw:
        raise HTTPException(status_code=500, detail="CODEF 비밀번호 환경변수가 설정되지 않았습니다.")

    request_body = {
        "organization": organization,
        "loginType": "1",  # 공인인증서 방식 (0: 일반)
        "realEstateName": realEstateName,
        "password": encrypt_codef_password(raw_pw.strip()),
        "connectedId": os.getenv("CODEF_CONNECTED_ID"),
        "type": "J",  # 지번 기반
        "isIdentity": True,
        "isConsent": True
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            resp = await client.post(CODEF_REGISTRY_URL, headers=headers, json=request_body)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"CODEF 오류: {e.response.status_code}, {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"요청 실패: {str(e)}")

    try:
        decoded = urllib.parse.unquote(resp.text)
        data = json.loads(decoded)
    except Exception:
        raise HTTPException(status_code=502, detail="CODEF 응답 파싱 실패")

    if "data" not in data:
        raise HTTPException(status_code=502, detail=f"CODEF 응답 이상: {data}")

    return data["data"]



async def register_connected_id(data: dict) -> str:
    """
    CODEF 추가 인증 등록 (Connected ID 발급)
    :param data: {
        "organization": "0004",
        "realEstateName": "서울특별시 강남구 역삼동 123-45",
        "password": "사용자 입력 비밀번호"
    }
    :return: connectedId 문자열
    """
    token = await get_codef_token()

    encrypted_pw = encrypt_codef_password(data["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    body = {
        "organization": data.get("organization", "0004"),
        "realEstateName": data["realEstateName"],
        "password": encrypted_pw,
        "loginType": "1",     # 공인인증서 로그인
        "isConsent": True,
        "isIdentity": True
    }

    url = "https://development.codef.io/v1/account/real-estate/register"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        result = response.json()
        return result["data"]["connectedId"]