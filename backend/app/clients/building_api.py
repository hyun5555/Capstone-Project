# backend/app/clients/building_api.py
# ─────────────────────────────────────────
# CODEF 기반 건축물대장(표제부) 조회 API client

import httpx
from fastapi import HTTPException
from app.config import CODEF_API_HOST
from app.clients.codef_auth import get_second_codef_token
from app.utils.codef_rsa import encrypt_codef_password
import urllib.parse
import json
import os

from dotenv import load_dotenv
load_dotenv()

CODEF_BUILDING_URL = f"{CODEF_API_HOST}/v1/kr/public/mw/building-register/general"

async def get_building_title_info(body: dict) -> dict:
    token = await get_second_codef_token()

    address = body.get("fullAddress") or body.get("address")
    main_no = body.get("mainAddressNo")
    sub_no = body.get("subAddressNo")
    type_ = body.get("type")

    raw_id = os.getenv("CODEF_USER_ID")
    raw_pw = os.getenv("CODEF_USER_PW")

    request_body = {
        "organization": "0001",
        "loginType": "1",
        "userId": raw_id,
        "userPassword": encrypt_codef_password(raw_pw.strip()),
        "address": address,
        "mainAddressNo": main_no,
        "subAddressNo": sub_no,
        "type": type_
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print("[요청 보냄] body:", request_body)

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            resp = await client.post(CODEF_BUILDING_URL, headers=headers, json=request_body)
            print("[응답 수신] status:", resp.status_code)
            print("[응답 수신] body:", resp.text)
            resp.raise_for_status()

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"CODEF HTTP 오류: {e.response.status_code}, 내용: {e.response.text}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"CODEF 요청 실패: {str(e)}")

    try:
        decoded_text = urllib.parse.unquote(resp.text)
        data = json.loads(decoded_text)
    except Exception:
        raise HTTPException(status_code=502, detail=f"CODEF 응답 JSON 파싱 실패: {resp.text if resp else 'No response'}")

    if "data" not in data:
        raise HTTPException(status_code=502, detail=f"CODEF 응답 데이터 이상: {data}")

    return data["data"]

    
