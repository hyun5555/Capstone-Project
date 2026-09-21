# app/services/risk_score.py
"""
전세 위험 점수 (서버 규칙). LLM 은 점수를 정하지 않는다.

점수는 0~100 이고 클수록 위험하다. (risk_factor 가중치 합이 1.0)

시세 정책
- 시세를 알 수 없으면(transaction_data["시세"] 가 None/0) 임의의 값으로 채우지 않는다.
  근저당 비율과 깡통 위험은 계산하지 않고, 이유를 skipped 로 돌려준다. (이때 점수는 나머지 항목만 합한 값이다.)

단위: 금액은 모두 원(₩). (실거래가 API 의 만원 단위는 market_price.py 에서 원으로 바꿔서 들어온다.)
"""
import requests
from bs4 import BeautifulSoup

risk_factor = {
    # 세부항목 기준 가중치 (AHP 분석 기반 최종 가중치)
    "소유자불일치": {"weight": 0.1471, "severity": "심각"},
    "소유권침해요소": {"weight": 0.0725, "severity": "심각"},
    "임차권등기명령": {"weight": 0.1384, "severity": "주의"},
    "전세권설정": {"weight": 0.0690, "severity": "주의"},
    "위반건축물": {"weight": 0.0723, "severity": "심각"},
    "불법용도": {"weight": 0.0633, "severity": "심각"},

    # AHP에서 항목 단일로 판단된 위험 요소
    "근저당권": {"weight": 0.2465, "severity": "심각"},
    "깡통위험": {"weight": 0.1909, "severity": "심각"},
}

OWNERSHIP_RISK_RIGHTS = ("경매개시결정", "압류", "가압류", "가처분", "가등기", "신탁")
NON_RESIDENTIAL_CATEGORIES = ("업무", "상업", "공업", "기타")
MAX_OWNERS_TO_CHECK = 3

PRICE_UNKNOWN_REASON = "시세를 확인하지 못해 계산하지 않았습니다."


def safe_divide(a, b, default=None):
    """a / b. b 가 0/None 이거나 숫자가 아니면 default. (예전 default=1 은 시세 0 을 '근저당 100%' 로 만들었다.)"""
    try:
        return a / b if b else default
    except (TypeError, ValueError):
        return default


def _positive_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


class _Tally:
    """점수, 이유, 항목별 반영 내역을 모은다."""

    def __init__(self):
        self.score = 0.0
        self.reasons = []
        self.severities = []
        self.factors = []
        self.skipped = []

    def add(self, key, factor, reason):
        info = risk_factor[key]
        points = info["weight"] * 100 * factor
        self.score += points
        self.reasons.append(reason)
        self.severities.append(info["severity"])
        self.factors.append({"key": key, "reason": reason, "points": round(points, 1), "severity": info["severity"]})

    def skip(self, key, reason):
        self.skipped.append({"key": key, "reason": reason})


# 리스트를 기반으로 위험 등급 판단, 점수는 보조 지표로 사용
def classify_risk_by_severity(score, severities):
    severe = severities.count("심각")
    caution = severities.count("주의")

    if severe >= 3:
        return "매우 위험"
    elif severe >= 2:
        return "위험"
    elif severe >= 1 or caution >= 2:
        return "주의"
    else:
        if score >= 70:
            return "매우 위험"
        elif score >= 40:
            return "위험"
        elif score >= 20:
            return "주의"
        else:
            return "안전"


def _owners_mismatch(findings: dict):
    """True / False / None(판단 못 함). document_compare 의 결과(소유자_불일치)를 우선 쓴다."""
    if "소유자_불일치" in findings:
        return findings["소유자_불일치"]
    reg, bld = (findings.get("등기부_소유자") or "").strip(), (findings.get("건축물대장_소유자") or "").strip()
    if not reg or not bld:      # 한쪽이 비어 있는 것은 '불일치'가 아니라 '확인 못 함'
        return None
    return reg != bld


def _split_names(text):
    return [n.strip() for n in (text or "").split(",") if n.strip()][:MAX_OWNERS_TO_CHECK]


def calculate_risk_score(findings: dict, transaction_data: dict = None) -> dict:
    """
    findings: document_compare.build_findings() 결과.
    transaction_data: {"보증금": 원, "시세": 원 또는 None}

    반환: score, grade, reasons, factors(항목별 반영 점수), skipped(계산하지 못한 항목과 이유),
          incomplete(skipped 가 있으면 True), ratios(계산한 비율, %)
    """
    transaction_data = transaction_data or {}
    tally = _Tally()
    rights = findings.get("위험_권리_목록", []) or []

    # 1. 소유권 관련 위험
    if _owners_mismatch(findings) is True:
        tally.add("소유자불일치", 1.0, "소유자 불일치")
    if any(r in rights for r in OWNERSHIP_RISK_RIGHTS):
        tally.add("소유권침해요소", 1.0, "소유권 침해 요소 있음")

    # 2. 기존 전세권 및 임차권 위험(복합적인 요인, 실제 위험 낮음)
    if "임차권" in rights:
        tally.add("임차권등기명령", 1.0, "임차권 등기명령 존재")
    if any(check_defaulter(n) for n in _split_names(findings.get("등기부_소유자"))):
        tally.add("전세권설정", 1.0, "상습 채무불이행자 공개 내역에 포함됨")
    elif "전세권" in rights:
        tally.add("전세권설정", 0.6, "이전 전세권 설정")

    # 3, 4. 시세가 있어야 계산할 수 있는 항목 (근저당 비율, 깡통 위험)
    pledge = int(findings.get("채권최고액", 0) or 0)
    deposit = int(_positive_number(transaction_data.get("보증금")) or 0)
    price = _positive_number(transaction_data.get("시세"))
    ratios = {}

    if price is None:
        if pledge > 0:
            tally.skip("근저당권", PRICE_UNKNOWN_REASON)
        tally.skip("깡통위험", PRICE_UNKNOWN_REASON)
    else:
        pledge_ratio = safe_divide(pledge, price) * 100
        margin_ratio = safe_divide(pledge + deposit, price) * 100
        ratios = {"근저당비율": round(pledge_ratio, 1), "근저당_보증금_합계비율": round(margin_ratio, 1)}

        # 근저당권 설정 위험 (단일 항목이면서 실질 위험도 높음)
        if pledge_ratio >= 60:
            tally.add("근저당권", 1.0, "근저당이 시세 대비 과다")
        elif pledge_ratio >= 45:
            tally.add("근저당권", 0.6, "근저당이 다소 높음")
        elif pledge_ratio >= 30:
            tally.add("근저당권", 0.3, "근저당 있음")

        # 깡통주택 위험도 (단일 항목이면서 높지만 근저당보다 변동성이 큼)
        if margin_ratio >= 90:
            tally.add("깡통위험", 1.0, "깡통주택 가능성 매우 높음")
        elif margin_ratio >= 80:
            tally.add("깡통위험", 0.65, "깡통 위험 있음")

    # 5. 건축물 적법성/용도. 확인하지 못한 값(None)은 위험으로 세지 않는다.
    if findings.get("위반건축물") is True:
        tally.add("위반건축물", 1.0, "위반건축물 중대")

    category = findings.get("용도분류")
    if findings.get("불법용도변경"):
        tally.add("불법용도", 1.0, "불법 용도변경 의심")
    elif category == "근린생활":
        tally.add("불법용도", 1.0, "근린생활시설 — 주거용으로 쓰이면 불법개조 여부 확인 필요")
    elif category in NON_RESIDENTIAL_CATEGORIES:
        tally.add("불법용도", 1.0, "비주거 건물")
    elif category is None:
        # 용도분류를 주지 않는 호출(예전 형식)만: 용도 문자열이 있고 '주거용'이 아니면 비주거로 본다.
        usage = findings.get("건물 용도")
        if usage and usage != "주거용":
            tally.add("불법용도", 1.0, "비주거 건물")

    incomplete = bool(tally.skipped)
    grade = classify_risk_by_severity(tally.score, tally.severities)
    if incomplete and grade == "안전":
        grade = "판단불가"   # 가중치 44% 를 차지하는 두 항목을 못 봤으므로 '안전' 이라고 하지 않는다.

    return {
        "score": round(tally.score, 1),
        "grade": grade,
        "reasons": tally.reasons,
        "factors": tally.factors,
        "skipped": tally.skipped,
        "incomplete": incomplete,
        "ratios": ratios,
    }


# 상습 채무불이행자 명단 조회
def check_defaulter(name_to_check):
    if not name_to_check:
        return False
    url = "https://www.molit.go.kr/USR/WPGE0201/m_37180/DTL.jsp"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
    except requests.RequestException:
        return False

    soup = BeautifulSoup(response.text, 'html.parser')
    # 페이지 구조에 따라 적절한 선택자 사용
    table = soup.find('table')
    if not table:
        return False

    rows = table.find_all('tr')[1:]  # 헤더를 제외한 행들
    for row in rows:
        cols = row.find_all('td')
        if cols:
            name = cols[0].get_text(strip=True)
            if name == name_to_check:
                return True

    return False
