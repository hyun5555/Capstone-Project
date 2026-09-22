# backend/app/clients/address_api.py

import re

import httpx

async def fetch_juso_data(keyword: str, current_page: int, count_per_page: int) -> dict:
  keyword = re.sub(r"(?<=[가-힣])(?=\d)", " ", keyword)
  async with httpx.AsyncClient(timeout=10) as client:
    response = await client.get(
      "https://nominatim.openstreetmap.org/search",
      headers={"User-Agent": "Capstone-Project/1.0"},
      params={
        "q": keyword,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": min(count_per_page, 10),
        "accept-language": "ko",
        "countrycodes": "kr",
      },
    )
    response.raise_for_status()

  payload = response.json()
  juso = []
  seen = set()
  for document in payload:
    address = document.get("address") or {}
    road_name = address.get("road", "")
    building_no = address.get("house_number", "")
    if not road_name or not re.fullmatch(r"\d+(?:-\d+)?", building_no):
      continue
    main_no, _, sub_no = building_no.partition("-")
    road_address = " ".join(filter(None, [
      address.get("city") or address.get("province"),
      address.get("borough") or address.get("county"),
      road_name,
      building_no,
    ]))
    if not road_address or road_address in seen:
      continue
    seen.add(road_address)
    juso.append({
      "roadAddr": road_address,
      "jibunAddr": document.get("display_name", ""),
      "zipNo": address.get("postcode", ""),
      "bdNm": address.get("building") or document.get("name", ""),
      "bdMgtSn": "",
      "detBdNmList": "",
      "siNm": address.get("city") or address.get("province", ""),
      "sggNm": address.get("borough") or address.get("county", ""),
      "emdNm": address.get("suburb") or address.get("quarter", ""),
      "lnbrMnnm": "",
      "lnbrSlno": "",
      "roadName": road_name,
      "bcode": "",
      "mainAddressNo": main_no,
      "subAddressNo": sub_no or "0",
    })

  return {
    "results": {
      "common": {"totalCount": str(len(juso)), "currentPage": str(current_page)},
      "juso": juso,
    }
  }
