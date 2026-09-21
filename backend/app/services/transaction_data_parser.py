# backend/app/services/transaction_data_parser.py
import re
import PublicDataReader as pdr
import xml.etree.ElementTree as ET
import asyncio
import xmltodict
import statistics
from datetime import datetime
from collections import defaultdict, OrderedDict, Counter
from dateutil.relativedelta import relativedelta
from app.clients.jeonse_price_api import fetch_jeonse_price_data
from app.clients.address_api import fetch_juso_data
from app.clients.trade_price_api import fetch_trade_price_data

def clean_name(name: str) -> str:
  # 괄호 안 내용 제거, 숫자 동호수 제거, 공백 제거, 소문자화
  name = re.sub(r"\([^)]*\)", "", name)  # 괄호 제거
  name = re.sub(r"[0-9]+동?", "", name)   # '102동' 같은 문자열 제거
  name = re.sub(r"\s+", "", name)        # 공백 제거
  return name.lower()                    # 소문자 통일

# 동 이름 추출 함수 (예: '서울특별시 마포구 서교동' → '서교동')
def extract_dong_from_address(address: str) -> str:
  match = re.search(r'\s([가-힣]+동)\b', address)
  return match.group(1) if match else None

def resolve_region_code_from_address(address: str) -> str:
  """
  PublicDataReader를 통해 주소 문자열에서 시군구 코드를 추출
  :param address: 예) "서울특별시 강남구 청담동"
  :return: 시군구 코드 문자열 (예: "11680")
  """
  bdong_df = pdr.code_bdong()

  for _, row in bdong_df.iterrows():
    sido = str(row['시도명']).strip()
    sigungu = str(row['시군구명']).strip()

    # 시군구가 비어있거나 의미 없는 경우 건너뜀
    if not sigungu or sigungu.lower() == 'nan':
      continue

    full_region = f"{sido} {sigungu}"

    # 주소에서 시군구 코드 추출
    if full_region in address:
      region_code = str(row["법정동코드"])[:5]
      print(f"주소: {address} / 지역 코드: {region_code} / 시군구명: {sigungu}")
      return region_code

  raise ValueError("주소에서 시군구 코드를 찾을 수 없습니다.")

# 주소를 입력받아 가장 최근 전세 실거래가 반환
async def fetch_exact_jeonse_records(address: str, house_type: str = "아파트"):
  region_code = resolve_region_code_from_address(address)
  current_ym = datetime.today()

  print(f"주소: {address} / 지역 코드: {region_code}")

  # 도로명주소 상세 검색
  jibun = None
  try:
    juso_response = await fetch_juso_data(keyword=address, current_page=1, count_per_page=1)
    juso_list = juso_response.get("results", {}).get("juso", [])
    if juso_list:
      juso_info = juso_list[0]
      road_address = juso_info.get("roadAddr")
      building_name = juso_info.get("bdNm")
      jibun_main = juso_info.get("lnbrMnnm", "").strip()  # 본번
      jibun_sub = juso_info.get("lnbrSlno", "").strip()   # 부번

      if jibun_main:
        if jibun_sub and jibun_sub != "0":
          jibun = f"{jibun_main}-{jibun_sub}"
        else:
          jibun = jibun_main
        print(f"📌 최종 지번: {jibun}")
      else:
        raise ValueError("지번 본번(lnbrMnnm)이 없습니다.")

      print(f"도로명주소: {road_address} / 건물명: {building_name} / 지번: {jibun}")
    else:
      print("도로명주소 검색 결과가 없습니다.")
  except Exception as e:
    print(f"도로명주소 API 호출 중 오류: {e}")

    if not jibun:
      raise ValueError("지번을 확인할 수 없습니다.")

  type_map = {
    "아파트": "apt",
    "오피스텔": "offi",
    "연립다세대": "rh",
    "단독다가구": "sh"
  }
  property_code = type_map.get(house_type)

  if not property_code:
    raise ValueError("지원하지 않는 주택 유형입니다.")

  MAX_RETRIES = 12

  for i in range(MAX_RETRIES):
    deal_ym = current_ym.strftime("%Y%m")
    print(f"🔍 {i+1}회차 시도: {deal_ym} 조회 중...")
    items = await fetch_jeonse_price_data(region_code, deal_ym, property_code)
    if not items:
      current_ym -= relativedelta(months=1)
      continue

    print(f"✅ {deal_ym} 데이터 {len(items)}건 확인됨")

    # dict → xml 변환
    dict_items = [item.dict() for item in items]
    xml_dict = {
      "response": {
        "body": {
          "items": {
            "item": dict_items
          }
        }
      }
    }
    xml_str = xmltodict.unparse(xml_dict, pretty=True)
    # XML 파싱
    parsed = parse_real_estate_xml(xml_str, house_type=house_type, transaction_type="전세")

    # 최근 날짜 순으로 정렬
    all_records = []
    for records in parsed.values():
      all_records.extend(records)

    # 건물명이 일치하는 레코드만 필터링
    jibun_matched = [r for r in all_records if r.get("jibun", "") == jibun]
    if jibun_matched:
      # 가장 최근 거래 한 건만 추출
      latest_record = sorted(jibun_matched, key=lambda x: x["deal_date"], reverse=True)[0]
      return latest_record.get("deposit")
    current_ym -= relativedelta(months=1)

  print("❌ 해당 주소의 실거래 데이터(지번 일치 기준)가 없습니다.")
  return None

# 정확한 주소가 아닌 동네 단위 전세 실거래가 추출
async def get_latest_price_by_region(address: str, house_type: str, trade_type: str, min_records: int = 100, max_months: int =12):
  if trade_type == "전세":
    fetch_fn = fetch_jeonse_price_data
  elif trade_type == "매매":
    fetch_fn = fetch_trade_price_data
  else:
    raise ValueError("거래 유형은 '전세' 또는 '매매'만 가능합니다.")

  region_code = resolve_region_code_from_address(address)
  target_dong = extract_dong_from_address(address)
  if not target_dong:
    raise ValueError("주소에서 동 정보를 추출할 수 없습니다.")

  current_ym = datetime.today()
  type_map = {
    "아파트": "apt",
    "오피스텔": "offi",
    "연립다세대": "rh",
    "단독다가구": "sh"
  }
  property_code = type_map.get(house_type)
  if not property_code:
    raise ValueError("지원하지 않는 주택 유형입니다.")

  matched_records = []
  tried_months = 0

  while tried_months < max_months:
    deal_ym = current_ym.strftime("%Y%m")
    items = await fetch_fn(region_code, deal_ym, property_code)
    if items:
      dict_items = [item.dict() for item in items]
      xml_dict = {
        "response": {
          "body": {
            "items": {
              "item": dict_items
            }
          }
        }
      }
      xml_str = xmltodict.unparse(xml_dict, pretty=True)
      parsed = parse_real_estate_xml(xml_str, house_type, trade_type)

      for record_list in parsed.values():
        # 법정동명이 정확히 일치하는 데이터만 필터링
        matched_records.extend([
          r for r in record_list
          if r.get("umdNm") == target_dong
        ])
      if len(matched_records) >= min_records:
        break

    current_ym -= relativedelta(months=1)
    tried_months += 1

  if not matched_records:
    return {
      "deposits": [],
      "areas": [],
      "period": "",
      "names": [],
      "all_records": []
    }
  matched_records = sorted(matched_records, key=lambda x: x["deal_date"], reverse=True)
  date_objs = [datetime.strptime(r["deal_date"], "%Y-%m-%d") for r in matched_records]
  start_date = min(date_objs).strftime("%Y.%m")
  end_date = max(date_objs).strftime("%Y.%m")

  prices = []
  if(trade_type == "전세"): prices = [r["deposit"] for r in matched_records if r["deposit"] > 0]
  elif (trade_type == "매매"): prices = [r["deal_amount"] for r in matched_records if r["deal_amount"] > 0]
  names = [r["name"] for r in matched_records if r["name"] and r["name"] != "unknown"]
  areas = [r["area"] for r in matched_records if r["area"] > 0]

  return {
    "prices": prices,
    "areas": areas,
    "period": f"{start_date}~{end_date}",
    "names": names,
    "all_records": matched_records
  }

async def summarize_transaction_by_address(address: str, house_type: str, allow_small_sample: bool = True):
  try:
    jeonse_result = await get_latest_price_by_region(address, house_type, "전세")
    deposits = jeonse_result.get("prices", [])
    areas = jeonse_result.get("areas", [])
    jeonse_period = jeonse_result.get("period", "")
    jeonse_names = set(jeonse_result.get("names", []))
    cleaned_jeonse_names = {clean_name(n) for n in jeonse_names}
    jeonse_all_records = jeonse_result.get("all_records", [])

    if not deposits or not areas or len(deposits) != len(areas):
        return {
          "status": "no_data",
          "message": "해당 주소의 거래 데이터가 부족하거나 일치하지 않습니다."
        }

    # 매매 데이터 수집
    trade_result = await get_latest_price_by_region(address, house_type, "매매")
    trade_names = set(trade_result.get("names", []))
    cleaned_trade_names = {clean_name(n) for n in trade_names}
    trade_all_records = trade_result.get("all_records", [])
    trade_period = trade_result.get("period", "")
    trade_prices = trade_result.get("prices", [])

    # 공통 거래일(date) 추출 (전세/매매 모두에 존재하는 거래일만)
    jeonse_dates = set(r["deal_date"] for r in jeonse_all_records)
    trade_dates = set(r["deal_date"] for r in trade_all_records)
    common_dates = jeonse_dates.intersection(trade_dates)

    if not common_dates:
      return {
        "status": "no_data",
        "message": "전세와 매매 데이터에 공통된 거래일이 없습니다."
      }

    # 공통 거래일에 해당하는 데이터만 필터링
    jeonse_all_records = [r for r in jeonse_all_records if r["deal_date"] in common_dates]
    trade_all_records = [r for r in trade_all_records if r["deal_date"] in common_dates]

    # 이후 공통 단지명 필터링 기존대로 진행
    jeonse_names = set(r["name"] for r in jeonse_all_records if r["name"])
    trade_names = set(r["name"] for r in trade_all_records if r["name"])

    cleaned_jeonse_names = {clean_name(n) for n in jeonse_names}
    cleaned_trade_names = {clean_name(n) for n in trade_names}
    common_cleaned_names = cleaned_jeonse_names.intersection(cleaned_trade_names)

    common_names = set(
        r["name"] for r in jeonse_all_records if clean_name(r["name"]) in common_cleaned_names
    ).intersection(
        r["name"] for r in trade_all_records if clean_name(r["name"]) in common_cleaned_names
    )

    if not common_names:
      return {
        "status": "no_data",
        "message": "전세와 매매 데이터에 공통된 단지가 없습니다."
      }

    # 공통된 단지명 기준으로 전세/매매 데이터 필터링
    jeonse_all_records = [r for r in jeonse_all_records if r["name"] in common_names]
    trade_all_records = [r for r in trade_all_records if r["name"] in common_names]

    #print(jeonse_all_records)
    deposits = [r["deposit"] for r in jeonse_all_records if r["deposit"] > 0]
    areas = [r["area"] for r in jeonse_all_records if r["area"] > 0]
    trade_prices = [r["deal_amount"] for r in trade_all_records if r["deal_amount"] > 0]

    deposit_per_m2_list = [d / a for d, a in zip(deposits, areas) if a > 0]

    if not deposit_per_m2_list:
      return {
        "status": "no_data",
        "message": "면적 정보가 없어 평당 보증금을 계산할 수 없습니다."
      }

    # 통계량 계산
    avg_per_m2 = round(statistics.mean(deposit_per_m2_list))
    min_index = deposit_per_m2_list.index(min(deposit_per_m2_list))
    max_index = deposit_per_m2_list.index(max(deposit_per_m2_list))

    min_per_m2 = round(deposit_per_m2_list[min_index])
    max_per_m2 = round(deposit_per_m2_list[max_index])

    min_record = jeonse_all_records[min_index]
    max_record = jeonse_all_records[max_index]

    # ✅ IQR 기반 이상치 제거
    q1 = statistics.quantiles(deposit_per_m2_list, n=4)[0]
    q3 = statistics.quantiles(deposit_per_m2_list, n=4)[2]
    iqr = q3 - q1
    clean_per_m2 = [v for v in deposit_per_m2_list if (q1 - 1.5 * iqr) <= v <= (q3 + 1.5 * iqr)]
    reliability = "높음" if len(clean_per_m2) / len(deposit_per_m2_list) >= 0.8 else "보통"

    # 가장 많이 거래된 면적대 (소수점 포함 평형)
    area_counter = Counter([round(a, 1) for a in areas if a > 0])
    most_traded_area, most_traded_area_count = area_counter.most_common(1)[0] if area_counter else ("정보 없음", 0)

    # 가장 많이 거래된 아파트 이름
    name_counter = Counter([r["name"] for r in jeonse_all_records if r.get("name")])
    most_traded_name, most_traded_name_count = name_counter.most_common(1)[0] if name_counter else ("정보 없음", 0)

    # 평균 매매가 평당 가격 계산용 변수
    all_trade_per_m2 = [
      r["deal_amount"] / r["area"] for r in trade_all_records
      if r["deal_amount"] > 0 and r["area"] > 0
    ]
    avg_trade_per_m2 = round(statistics.mean(all_trade_per_m2)) if all_trade_per_m2 else None

    # 공통 단지별 전세가율 계산
    jeonse_ratios = []
    ratios_by_area_group = defaultdict(list)

    for name in common_names:
      # 단지별 전세 거래
      j_records = [r for r in jeonse_all_records if r["name"] == name and r["deposit"] > 0 and r["area"] > 0]
      t_records = [r for r in trade_all_records if r["name"] == name and r["deal_amount"] > 0 and r["area"] > 0]
      if not j_records or not t_records:
        continue

      # 면적 그룹핑: 5㎡ 단위 (예: 84.2㎡ → 85㎡)
      j_area_groups = defaultdict(list)
      for r in j_records:
        area_group = round(r["area"])
        j_area_groups[area_group].append(r)

      t_area_groups = defaultdict(list)
      for r in t_records:
        area_group = round(r["area"])
        t_area_groups[area_group].append(r)

        print(f"{name}: 전세 면적 그룹 {list(j_area_groups.keys())}, 매매 면적 그룹 {list(t_area_groups.keys())}")

      # 유사 면적대 매칭 (±5㎡)
      for j_area in j_area_groups:
        matched_t_areas = [t_area for t_area in t_area_groups if abs(t_area - j_area) <= 5]
        for t_area in matched_t_areas:
          j_group = j_area_groups[j_area]
          t_group = t_area_groups[t_area]
          print(f"{name} - 면적 {j_area}㎡ ≈ {t_area}㎡: 전세 {len(j_group)}건, 매매 {len(t_group)}건")

          # 거래 수 제한 조건 유연화
          if not allow_small_sample and (len(j_group) < 3 or len(t_group) < 3):
            continue

          j_per_m2 = [r["deposit"] / r["area"] for r in j_group if r["area"] > 0]
          t_per_m2 = [r["deal_amount"] / r["area"] for r in t_group if r["area"] > 0]

          if j_per_m2 and t_per_m2:
            avg_jeonse = statistics.mean(j_per_m2)
            avg_trade = statistics.mean(t_per_m2)
            if avg_trade > 0:
              ratio = (avg_jeonse / avg_trade) * 100
              jeonse_ratios.append(ratio)
              key = f"{(j_area + t_area)//2}"
              ratios_by_area_group[key].append(ratio)

              print(f"[전세가율] 단지: {name}, 전세 면적: {j_area}㎡, 매매 면적: {t_area}㎡ → 전세가율: {round(ratio, 2)}%")
    if not jeonse_ratios:
      return {"status": "no_data", "message": "신뢰 가능한 전세가율을 계산할 수 없습니다."}

    # 최종 요약
    jeonse_ratio = round(statistics.mean(jeonse_ratios), 2)
    if jeonse_ratio >= 90:
      risk_level = "위험"
    elif jeonse_ratio >= 70:
      risk_level = "주의"
    else:
      risk_level = "안전"

    # ✅ 전세가율 이상치 제거 적용 평균 계산 (clean_ratios 사용)
    if len(jeonse_ratios) >= 2:
      q1_ratio = statistics.quantiles(jeonse_ratios, n=4)[0]
      q3_ratio = statistics.quantiles(jeonse_ratios, n=4)[2]
      iqr_ratio = q3_ratio - q1_ratio
      clean_ratios = [r for r in jeonse_ratios if (q1_ratio - 1.5 * iqr_ratio) <= r <= (q3_ratio + 1.5 * iqr_ratio)]
      filtered_jeonse_ratio = round(statistics.mean(clean_ratios), 2) if clean_ratios else None
    else:
      clean_ratios = []
      filtered_jeonse_ratio = None

    filtered_jeonse_ratio = round(statistics.mean(clean_ratios), 2) if clean_ratios else None

    # ✅ 면적대별 전세가율 + 건수 출력용 dict 생성
    ratios_by_area_group_with_count = {
      str(k): {
        "average_ratio": round(statistics.mean(v), 2),
        "count": len(v)
      }
      for k, v in ratios_by_area_group.items() if len(v) >= 2
    }

    return {
          "status": "ok",
          "region": address,
          "house_type": house_type,
          "period": jeonse_period,
          "average_deposit_per_m2": avg_per_m2,
          "min_deposit_per_m2": min_per_m2,
          "max_deposit_per_m2": max_per_m2,
          "total_transaction_count": len(deposits),
          "most_traded_area": most_traded_area,
          "most_traded_area_count": most_traded_area_count,
          "most_traded_name": most_traded_name,
          "most_traded_name_count": most_traded_name_count,
          "recent_deposit_samples": deposits[:5],
          "min_record": min_record,
          "max_record": max_record,
          "reliability": reliability,
          "sale_period": trade_period,
          "average_sale_per_m2": avg_trade_per_m2,
          "jeonse_ratio": jeonse_ratio,
          "risk_level": risk_level,
          "filtered_jeonse_ratio": filtered_jeonse_ratio,
          "ratios_by_area_group_detailed": ratios_by_area_group_with_count,
    }

  except Exception as e:
    return {
      "status": "error",
      "message": f"데이터 분석 중 오류 발생: {e}"
    }

def parse_real_estate_xml(xml_str: str, house_type: str, transaction_type: str):
  """
  XML 문자열을 파싱하여 시/도 코드별로 데이터를 분류
  :param xml_str: XML 형식 문자열
  :param house_type: "아파트", "오피스텔", "연립다세대", "단독다가구"
  :param transaction_type: "전세" 또는 "매매"
  :return: 시/도 코드별 데이터 dict
  """
  root = ET.fromstring(xml_str)
  grouped_data = defaultdict(list)
  bdong_df = pdr.code_bdong()

  for item in root.findall(".//item"):
    # 공통 필드 추출
    try:
      deal_year = item.findtext("dealYear")
      deal_month = item.findtext("dealMonth")
      deal_day = item.findtext("dealDay")
      area = item.findtext("excluUseAr") or item.findtext("totalFloorAr")
      sgg_code = item.findtext("sggCd")
      jibun = item.findtext("jibun")
      floor = item.findtext("floor")
      umdNm = item.findtext("umdNm")

      # 건물 이름 (유형별 다름)
      if house_type == "아파트":
        name = item.findtext("aptNm")
      elif house_type == "오피스텔":
        name = item.findtext("offiNm")
      elif house_type == "연립다세대":
        name = item.findtext("mhouseNm")
      elif house_type == "단독다가구":
        name = item.findtext("houseType")  # "다가구" 또는 "단독"
      else:
        name = "unknown"

      # 거래유형별 필드 추출
      if transaction_type == "전세":
        deposit = item.findtext("deposit")
        price = None
      elif transaction_type == "매매":
        price = item.findtext("dealAmount")
        deposit = None
      else:
        raise ValueError("지원하지 않는 거래 유형입니다.")

      sido_code = sgg_code[:2]  # 시/도 코드 추출

      # 법정동코드 앞 5자리가 sgg_code와 일치하는 행을 찾기
      match_row = bdong_df[bdong_df["법정동코드"].astype(str).str.startswith(sgg_code)]

      if not match_row.empty:
        sido_name = match_row.iloc[0]["시도명"]
        sgg_name = match_row.iloc[0]["시군구명"]
      else:
        sido_name = "알수없음"
        sgg_name = "알수없음"

      data = OrderedDict([
        ("sgg_code", sgg_code),
        ("sido_name", sido_name),
        ("sgg_name", sgg_name),
        ("umdNm", umdNm),
        ("jibun", jibun),
        ("name", name),
        ("deal_date", f"{deal_year}-{deal_month.zfill(2)}-{deal_day.zfill(2)}"),
        ("area", float(area) if area else 0),
        ("floor", int(floor) if floor and floor.isdigit() else None),
      ])
      # 거래유형별 금액 정보 추가
      if transaction_type == "전세":
        data["deposit"] = int(deposit.replace(",", "")) if deposit else 0
      elif transaction_type == "매매":
        data["deal_amount"] = int(price.replace(",", "")) if price else 0

      grouped_data[sido_code].append(data)

    except Exception as e:
      print("Error parsing item:", e)

  return grouped_data

# __main__에서 실행
if __name__ == "__main__":
  address = "서울특별시 영등포구 여의나루로 121"
  house_type = "아파트"  # 필요 시 변경 가능

  record = asyncio.run(fetch_exact_jeonse_records(address, house_type))
  print(record)
