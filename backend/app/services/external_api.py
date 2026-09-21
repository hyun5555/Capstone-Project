# app/services/external_api.py
import requests
from app.config import (
    API_KEY,
    APT_JEONSE_PRICE_URL,
    APT_TRADE_PRICE_URL,
    BUILDING_API_URL,
    CONFM_KEY,
    JUSO_API_URL,
    OFFI_JEONSE_PRICE_URL,
    OFFI_TRADE_PRICE_URL,
    REGISTRY_API_URL,
    RH_JEONSE_PRICE_URL,
    RH_TRADE_PRICE_URL,
    SERVICE_KEY,
    SH_JEONSE_PRICE_URL,
    SH_TRADE_PRICE_URL,
)

def fetch_registry_data(query_params: dict) -> dict:
    """등기부등본 API 호출"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    resp = requests.get(REGISTRY_API_URL, params=query_params, headers=headers)
    resp.raise_for_status()
    return resp.json()

def fetch_building_data(query_params: dict) -> dict:
    """건축물대장 API 호출"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    resp = requests.get(BUILDING_API_URL, params=query_params, headers=headers)
    resp.raise_for_status()
    return resp.json()

def fetch_apt_jeonse_price_data(query_params: dict) -> dict:
    """아파트_전월세_실거래가 API 호출"""
    params = {
        "serviceKey": SERVICE_KEY,
        "_type": "json",
        **query_params
    }
    resp = requests.get(APT_JEONSE_PRICE_URL, params=params)
    resp.raise_for_status()
    return resp.json()

def fetch_offi_jeonse_price_data(query_params: dict) -> dict:
    """오피스텔_전월세_실거래가 API 호출"""
    params = {
        "serviceKey": SERVICE_KEY,
        "_type": "json",
        **query_params
    }
    resp = requests.get(OFFI_JEONSE_PRICE_URL, params=params)
    resp.raise_for_status()
    return resp.json()

def fetch_rh_jeonse_price_data(query_params: dict) -> dict:
    """연립다세대_전월세_실거래가 API 호출(row house)"""
    params = {
        "serviceKey": SERVICE_KEY,
        "_type": "json",
        **query_params
    }
    resp = requests.get(RH_JEONSE_PRICE_URL, params=params)
    resp.raise_for_status()
    return resp.json()

def fetch_sh_jeonse_price_data(query_params: dict) -> dict:
    """단독/다가구_전월세_실거래가 API 호출(single house)"""
    params = {
        "serviceKey": SERVICE_KEY,
        "_type": "json",
        **query_params
    }
    resp = requests.get(SH_JEONSE_PRICE_URL, params=params)
    resp.raise_for_status()
    return resp.json()

def fetch_apt_trade_price_data(query_params: dict) -> dict:
    """아파트_매매_실거래가 API 호출"""
    params = {
        "serviceKey": SERVICE_KEY,
        "_type": "json",
        **query_params
    }
    resp = requests.get(APT_TRADE_PRICE_URL, params=params)
    resp.raise_for_status()
    return resp.json()

def fetch_offi_trade_price_data(query_params: dict) -> dict:
    """오피스텔_매매_실거래가 API 호출"""
    params = {
        "serviceKey": SERVICE_KEY,
        "_type": "json",
        **query_params
    }
    resp = requests.get(OFFI_TRADE_PRICE_URL, params=params)
    resp.raise_for_status()
    return resp.json()

def fetch_rh_trade_price_data(query_params: dict) -> dict:
    """연립다세대_매매_실거래가 API 호출"""
    params = {
        "serviceKey": SERVICE_KEY,
        "_type": "json",
        **query_params
    }
    resp = requests.get(RH_TRADE_PRICE_URL, params=params)
    resp.raise_for_status()
    return resp.json()

def fetch_sh_trade_price_data(query_params: dict) -> dict:
    """단독/다가구_매매_실거래가 API 호출"""
    params = {
        "serviceKey": SERVICE_KEY,
        "_type": "json",
        **query_params
    }
    resp = requests.get(SH_TRADE_PRICE_URL, params=params)
    resp.raise_for_status()
    return resp.json()

def fetch_juso_data(query_params: dict) -> dict:
    "도로명주소 검색 API 호출"
    params = {
        "confmKey": JUSO_API_URL,
        "_type": "json",
        **query_params
    }
    resp = requests.get(JUSO_API_URL, params=params)
    resp.raise_for_status()
    return resp.json()

def extract_metadata(api_response: dict) -> dict:
    """
    API 응답에서 핵심 메타데이터(예: 소유자, 주소, 세부내용 등)를 뽑아
    새로운 dict 형태로 리턴합니다.
    """
    # **여기에는 실제 API 스펙에 맞춘 필드 매핑을 넣으세요.**
    return {
        "owner": api_response.get("ownerName") or api_response.get("owner"),
        "address": api_response.get("address"),
        "details": api_response.get("detailInfo") or api_response.get("details"),
    }
