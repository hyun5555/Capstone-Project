# backend/app/services/market_price.py
"""
매매 시세(원) 결정.

- 사용자가 값을 직접 보냈으면 그 값을 쓴다.
- 없으면 국토부 실거래가에서 "같은 동, 최근 매매, 비슷한 면적(±10%)" 거래의 중앙값을 추정값으로 쓴다.
- 그것도 못 구하면 None 을 돌려준다. 임의의 상수(예: 10억)로 채우지 않는다 — 위험 점수가 왜곡되기 때문이다.
- 실거래가 API 의 금액 단위는 만원이므로 여기서 원 단위로 바꾼다.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

MAN_WON = 10_000


# 실거래가 조회 범위. get_latest_price_by_region 은 월 단위로 API 를 여러 번 호출하므로 너무 넓게 잡지 않는다.
MIN_RECORDS = 30
MAX_MONTHS = 6
AREA_BAND = 0.10        # 전용면적 ±10% 이내 거래를 우선 사용
MIN_SIMILAR = 3         # 비슷한 면적 거래가 이 수 이상일 때만 면적으로 좁힌다


@dataclass
class MarketPrice:
    value_won: Optional[int]
    source: str          # "user" | "molit_median" | "unavailable"
    note: str = ""

    def to_dict(self) -> dict:
        return {"value_won": self.value_won, "source": self.source, "note": self.note}


def house_type_from_usage(usage: Optional[str]) -> Optional[str]:
    """건물 용도 문자열 → 실거래가 API 의 주택 유형. 매핑할 수 없으면 None."""
    u = (usage or "").replace(" ", "")
    if "오피스텔" in u:
        return "오피스텔"
    if "아파트" in u:
        return "아파트"
    if "연립" in u or "다세대" in u:
        return "연립다세대"
    if "단독" in u or "다가구" in u:
        return "단독다가구"
    return None


async def _default_fetcher(address: str, house_type: str) -> dict:
    # 무거운 의존성(PublicDataReader 등)이 있어서 실제로 쓸 때만 import 한다.
    from app.services.transaction_data_parser import get_latest_price_by_region
    return await get_latest_price_by_region(address, house_type, "매매", MIN_RECORDS, MAX_MONTHS)


async def resolve_market_price(
    address: str,
    usage: Optional[str],
    area_exclusive: Optional[float],
    provided_won: Optional[int] = None,
    fetcher: Optional[Callable[[str, str], Awaitable[dict]]] = None,
) -> MarketPrice:
    if provided_won and provided_won > 0:
        return MarketPrice(int(provided_won), "user", "사용자가 입력한 시세")

    house_type = house_type_from_usage(usage)
    if house_type is None:
        return MarketPrice(None, "unavailable", "건물 용도로 주택 유형을 알 수 없어 실거래가를 조회하지 못했습니다.")

    try:
        result = await (fetcher or _default_fetcher)(address, house_type)
    except ValueError:       # 주소에서 시군구/동을 못 찾은 경우 (파서가 ValueError 로 알린다)
        return MarketPrice(None, "unavailable", "주소에서 지역(시군구·동)을 특정하지 못해 실거래가를 조회하지 못했습니다.")
    except Exception as e:   # 외부 API/파싱 오류는 분석 전체를 막지 않는다. 응답 내용은 노출하지 않는다.
        return MarketPrice(None, "unavailable", f"실거래가 조회에 실패했습니다({type(e).__name__}).")

    records = [r for r in (result.get("all_records") or []) if (r.get("deal_amount") or 0) > 0]
    if area_exclusive:
        similar = [r for r in records if r.get("area") and abs(r["area"] - area_exclusive) <= area_exclusive * AREA_BAND]
        if len(similar) >= MIN_SIMILAR:
            records = similar
    if not records:
        return MarketPrice(None, "unavailable", "같은 동의 최근 매매 실거래 내역이 없습니다.")

    median_man = statistics.median(r["deal_amount"] for r in records)
    return MarketPrice(
        int(median_man * MAN_WON),
        "molit_median",
        f"같은 동 최근 매매 실거래 {len(records)}건의 중앙값(추정치, 해당 건물의 정확한 시세가 아님)",
    )
