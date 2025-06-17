# backend/app/clients/registry_api.py
import httpx
from fastapi import HTTPException
from app.config import CODEF_API_HOST
from app.clients.codef_auth import get_second_codef_token
from app.utils.codef_rsa import encrypt_codef_password
from app.utils.registry_parser import extract_fields_from_rescontents
import urllib.parse
import json
import os

CODEF_REGISTRY_URL = f"{CODEF_API_HOST}/v1/kr/public/real-estate/register"

async def get_registry_info(body: dict) -> dict:
    token = await get_second_codef_token()

    # 사용자 입력 정보
    organization = body.get("organization", "0004")
    realEstateName = body.get("realEstateName")
    raw_pw = os.getenv("CODEF_USER_PW")

    if not raw_pw:
        raise HTTPException(status_code=500, detail="CODEF 비밀번호 환경변수가 설정되지 않았습니다.")

    request_body = {
        "organization": organization,
        "phoneNo": os.getenv("CODEF_PHONE_NO"),  # 전화번호 반드시 포함
        "password": encrypt_codef_password(raw_pw.strip()),
        "inquiryType": "3",  # 예: 도로명 주소로 조회
        "addr_sido": realEstateName.split()[0],   # 시/도
        "address": realEstateName,                # 전체 주소
        "recordStatus": "0",                      # 기본값: 현행
        "isIdentity": True,
        "isConsent": True
    }


    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # API 호출
    try:
        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            resp = await client.post(CODEF_REGISTRY_URL, headers=headers, json=request_body)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"CODEF 오류: {e.response.status_code}, {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"요청 실패: {str(e)}")

    # 응답 디코딩 및 파싱
    try:
        decoded = urllib.parse.unquote(resp.text)
        data = json.loads(decoded)
    except Exception:
        raise HTTPException(status_code=502, detail="CODEF 응답 파싱 실패")

    if "data" not in data:
        raise HTTPException(status_code=502, detail=f"CODEF 응답 이상: {data}")

    # resContents 수집 및 정규식 적용
    res_entries = data["data"].get("resRegisterEntriesList", [])
    contents_blocks = []

    for entry in res_entries:
        for summary in entry.get("resRegistrationSumList", []):
            for cl in summary.get("resContentsList", []):
                for detail in cl.get("resDetailList", []):
                    content = detail.get("resContents")
                    if content:
                        contents_blocks.append(content)

    combined_text = "\n".join(contents_blocks)
    extracted_fields = extract_fields_from_rescontents(combined_text)

    # 추가 정보 수동 매핑
    extracted_fields["propertyLocation"] = realEstateName
    extracted_fields["originalDataId"] = data["data"].get("resOriGinalData")

    return extracted_fields


async def register_connected_id(data: dict) -> str:
    from app.clients.codef_auth import get_codef_token  # 로컬에서 불러오기

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
        "loginType": "1",
        "isConsent": True,
        "isIdentity": True
    }

    url = "https://development.codef.io/v1/account/real-estate/register"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        result = response.json()
        return result["data"]["connectedId"]
