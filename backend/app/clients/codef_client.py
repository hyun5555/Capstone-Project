# backend/app/clients/codef_client.py
"""
CODEF API 공통 클라이언트 (토큰 발급·캐시, 요청, 응답 디코딩, 오류 처리).

이전 코드와 달라진 점
- TLS 인증서 검증을 끄지 않는다 (예전 코드의 인증서 검증 비활성화 옵션 제거).
- 요청/응답 본문을 로그로 출력하지 않는다 (비밀번호·개인정보 노출 방지). 오류에는 CODEF 결과코드와 메시지만 담는다.
- 토큰을 만료 직전까지 캐시해서 요청마다 새로 발급받지 않는다.
- 토큰 발급 로직이 여러 파일에 중복돼 있던 것을 이 파일 하나로 합쳤다. 토큰은 외부로 반환하지 않는다.

이 모듈은 FastAPI 에 의존하지 않는다. HTTP 오류로의 변환은 엔드포인트에서 한다.
"""
from __future__ import annotations

import asyncio
import base64
import time
from typing import Optional

import httpx

from app.services.codef_normalizer import decode_codef_body

CODEF_SUCCESS = "CF-00000"


class CodefError(Exception):
    def __init__(self, message: str, *, code: Optional[str] = None, continue2way: bool = False):
        super().__init__(message)
        self.message = message
        self.code = code
        self.continue2way = continue2way


class CodefClient:
    def __init__(self, settings, transport: Optional[httpx.AsyncBaseTransport] = None):
        self._s = settings
        self._transport = transport
        self._token: Optional[str] = None
        self._token_expires_at = 0.0
        self._lock: Optional[asyncio.Lock] = None

    @property
    def settings(self):
        return self._s

    def require(self, **values) -> None:
        """필요한 설정값이 비어 있으면 어떤 환경변수가 없는지 알려 주며 실패한다."""
        missing = [env for env, v in values.items() if not v]
        if missing:
            raise CodefError("필수 환경변수가 설정되지 않았습니다: " + ", ".join(missing), code="CONFIG")

    def _http(self) -> httpx.AsyncClient:
        # verify 옵션을 주지 않는다 = 기본값(True, 인증서 검증)
        return httpx.AsyncClient(timeout=self._s.timeout_sec, transport=self._transport)

    async def get_token(self) -> str:
        self.require(CODEF_CLIENT_ID=self._s.client_id, CODEF_CLIENT_SECRET=self._s.client_secret)
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            if self._token and time.time() < self._token_expires_at:
                return self._token
            basic = base64.b64encode(f"{self._s.client_id}:{self._s.client_secret}".encode()).decode()
            try:
                async with self._http() as client:
                    resp = await client.post(
                        self._s.oauth_url,
                        headers={"Content-Type": "application/x-www-form-urlencoded", "Authorization": f"Basic {basic}"},
                        content="grant_type=client_credentials&scope=read",
                    )
                    resp.raise_for_status()
                    payload = resp.json()
            except httpx.HTTPStatusError as e:
                raise CodefError(f"CODEF 토큰 발급 실패 (HTTP {e.response.status_code})", code="TOKEN") from None
            except Exception as e:
                raise CodefError(f"CODEF 토큰 발급 요청 실패: {type(e).__name__}", code="TOKEN") from None

            token = payload.get("access_token")
            if not token:
                raise CodefError("CODEF 토큰 응답에 access_token 이 없습니다.", code="TOKEN")
            self._token = token
            self._token_expires_at = time.time() + max(60, int(payload.get("expires_in", 3600)) - 60)
            return token

    async def post(self, path: str, body: dict) -> dict:
        """CODEF 상품 API 를 호출하고 성공 시 응답의 data 부분을 돌려준다."""
        self.require(CODEF_API_HOST=self._s.api_host)
        token = await self.get_token()
        url = f"{self._s.api_host.rstrip('/')}{path}"
        try:
            async with self._http() as client:
                resp = await client.post(
                    url, json=body, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise CodefError(f"CODEF 요청 실패 (HTTP {e.response.status_code})", code="HTTP") from None
        except Exception as e:
            raise CodefError(f"CODEF 요청 실패: {type(e).__name__}", code="HTTP") from None

        try:
            envelope = decode_codef_body(resp.text)
        except Exception:
            raise CodefError("CODEF 응답을 JSON 으로 해석하지 못했습니다.", code="PARSE") from None

        result = envelope.get("result") or {}
        data = envelope.get("data")
        code = result.get("code")
        if isinstance(data, dict) and data.get("continue2Way"):
            raise CodefError(
                "추가 인증 또는 주소 선택이 필요합니다 (2-way). 주소를 더 구체적으로 입력해 주세요.",
                code=code, continue2way=True,
            )
        if code is not None and code != CODEF_SUCCESS:
            raise CodefError(f"CODEF 오류 {code}: {result.get('message', '')}", code=code)
        if not isinstance(data, dict):
            raise CodefError("CODEF 응답에 data 가 없습니다.", code=code)
        return data


def http_status_for(err: CodefError) -> int:
    """CodefError 를 API 응답 상태코드로 바꾼다."""
    if err.continue2way:
        return 404          # 주소가 특정되지 않음 / 해당 주소 없음
    if err.code == "CONFIG":
        return 500          # 서버 설정 문제
    return 502              # CODEF 쪽 문제


# ── 상품별 요청 본문 ─────────────────────────────────────────

def _encrypt(password: str) -> str:
    from app.utils.codef_rsa import encrypt_codef_password   # pycryptodome 는 실제로 쓸 때만 import
    return encrypt_codef_password(password.strip())


def build_registry_request(address: str, s) -> dict:
    """
    등기부등본 조회 요청 본문.
    ⚠ organization / inquiryType / 엔드포인트 경로는 CODEF 개발가이드(등기부등본 열람 API)로 반드시 확인하세요.
      경로는 CODEF_REGISTRY_PATH, 기관코드는 CODEF_REGISTRY_ORGANIZATION 환경변수로 바꿀 수 있습니다.
    """
    parts = address.split()
    return {
        "organization": s.registry_organization,
        "phoneNo": s.phone_no,
        "password": _encrypt(s.user_pw),
        "inquiryType": "3",
        "addr_sido": parts[0] if parts else "",
        "address": address,
        "recordStatus": "0",
        "isIdentity": True,
        "isConsent": True,
    }


def build_building_request(road_name: str, main_no: str, sub_no: str, s, type_: str = "0") -> dict:
    return {
        "organization": "0001",
        "loginType": "1",
        "userId": s.user_id,
        "userPassword": _encrypt(s.user_pw),
        "address": road_name,
        "mainAddressNo": main_no,
        "subAddressNo": sub_no,
        "type": type_,
    }


async def fetch_registry(client: CodefClient, address: str) -> dict:
    s = client.settings
    client.require(CODEF_USER_PW=s.user_pw, CODEF_PHONE_NO=s.phone_no, CODEF_PUBLIC_KEY=s.public_key)
    return await client.post(s.registry_path, build_registry_request(address, s))


async def fetch_building(client: CodefClient, road_name: str, main_no: str, sub_no: str) -> dict:
    s = client.settings
    client.require(CODEF_USER_ID=s.user_id, CODEF_USER_PW=s.user_pw, CODEF_PUBLIC_KEY=s.public_key)
    return await client.post(s.building_path, build_building_request(road_name, main_no, sub_no, s))


# ── 앱 전역 클라이언트 (토큰 캐시를 공유) ────────────────────

_client: Optional[CodefClient] = None


def get_codef_client() -> CodefClient:
    global _client
    if _client is None:
        from app.config import codef_settings
        _client = CodefClient(codef_settings)
    return _client


def set_codef_client(client: Optional[CodefClient]) -> None:
    global _client
    _client = client
