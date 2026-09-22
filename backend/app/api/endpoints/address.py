# app/api/endpoints/address.py

from fastapi import APIRouter, HTTPException, Query
from app.clients.address_api import fetch_juso_data
from app.schemas.address import JusoItem
from typing import List

router = APIRouter(prefix="/address", tags=["도로명주소 검색"])

@router.get(
    "/search",
    response_model=List[JusoItem],
    summary="도로명주소 검색 API"
)
async def address_search(
    keyword: str = Query(..., description="검색할 주소 키워드"),
    current_page: int = Query(1, alias="currentPage", description="페이지 번호"),
    count_per_page: int = Query(10, alias="countPerPage", description="페이지당 개수"),
):
  try:
    response = await fetch_juso_data(keyword, current_page, count_per_page)
    juso_list = response.get("results", {}).get("juso") or []
    return juso_list
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
