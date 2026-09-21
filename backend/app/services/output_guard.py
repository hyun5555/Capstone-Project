# backend/app/services/output_guard.py
"""
LLM 이 쓴 설명을 서버가 규칙으로 검사한다. (LLM 출력을 믿지 않고 확인한다)

- 근거 자료(값과 청크)에 없는 숫자(금액, 연도, 면적)를 쓰면 그 설명을 버린다.
- 권리사항 설명이 문서에 없는 권리를 있다고 하거나, 현재 유효한 권리를 빠뜨리거나 말소됐다고 하면 버린다.
버려진 항목은 rag_explain 이 서버가 만든 기본 문장으로 대체한다. 틀린 설명보다 기본 문장이 안전하기 때문이다.
평가(evaluation.metrics)도 같은 함수를 써서, 서비스가 거르는 기준과 평가 기준이 같다.
휴리스틱이라 오탐이 있을 수 있다. 오탐이 나도 결과는 기본 문장이므로 틀린 정보가 나가지는 않는다.
"""
import re
from typing import List, Optional, Set

RIGHT_PATTERNS = {
    "경매개시결정": r"경매",
    "가압류": r"가압류",
    "압류": r"(?<!가)압류",
    "가처분": r"가처분",
    "가등기": r"가등기",
    "신탁": r"신탁",
    "전세권": r"전세권",
    "임차권": r"임차권",
    "근저당권": r"근저당",
}
_NEGATION = ("말소", "해제", "해지", "없", "않", "제외", "아닙니다", "효력이 없", "삭제")
_CLAUSE_END = re.compile(r"[.,;!?\n]|[며고] |지만|으나|는데")
_BEFORE_WORDS = ("말소된", "말소되었던", "해제된", "해지된", "과거", "이전에")


_PREDICATE_END = re.compile(r"(다|요|고|며|서|면|지만|으나|는데)$")
_MAX_TAIL = 150


def _is_bare(segment: str) -> bool:
    """서술어로 끝나지 않는 절 (예: '압류', '가압류 등 위험 권리'). 나열의 한 항목이라 뒤 절이 서술을 맡는다."""
    return _PREDICATE_END.search(segment.strip()) is None


def _clause_after(text: str, pos: int) -> str:
    """
    권리 이름 뒤에서 그 권리를 서술하는 절. 쉼표로 나열한 경우('근저당권, 압류, 가압류 등은 없습니다')에는
    서술어가 나올 때까지 뒤 절을 이어 붙인다. 문장이 끝나면 멈춘다.
    """
    clause = ""
    while True:
        tail = text[pos:pos + 60]
        end = _CLAUSE_END.search(tail)
        segment = tail[: end.start()] if end else tail
        clause += segment
        if not end or end.group() != "," or not _is_bare(segment) or len(clause) > _MAX_TAIL:
            return clause
        pos += end.end()


def asserted_rights(text: str) -> Set[str]:
    """
    설명이 '현재 있다' 고 말하는 권리 종류. 같은 절 안에 말소/없음 표현이 있으면 있다고 하지 않은 것으로 본다.
    쉼표로 나열한 권리는 마지막 서술어를 함께 받는다. ('근저당권, 압류는 확인되지 않았습니다' 는 둘 다 없다는 뜻)
    """
    found: Set[str] = set()
    for right, pattern in RIGHT_PATTERNS.items():
        for m in re.finditer(pattern, text):
            clause_after = _clause_after(text, m.end())
            head = text[max(0, m.start() - 10):m.start()]
            cut = max((head.rfind(d) for d in (".", ",", ";", "\n")), default=-1)
            clause_before = head[cut + 1:]
            if any(w in clause_after for w in _NEGATION) or any(w in clause_before for w in _BEFORE_WORDS):
                continue
            found.add(right)
    return found


def mentioned_rights(text: str) -> Set[str]:
    """부정 여부와 상관없이 언급된 권리 종류."""
    return {right for right, pattern in RIGHT_PATTERNS.items() if re.search(pattern, text)}


_KOREAN_AMOUNT = re.compile(
    r"(?:(\d[\d,]*)\s*억)?\s*(?:(\d[\d,]*)\s*천\s*(?:만)?)?\s*(?:(\d[\d,]*)\s*만)?"
)
_PLAIN_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _to_int(s: Optional[str]) -> int:
    return int(s.replace(",", "")) if s else 0


def extract_numbers(text: str) -> Set[str]:
    """
    텍스트에 나온 숫자를 비교 가능한 문자열 집합으로 만든다.
    '2억 4천만원' 같은 한글 단위 금액은 원 단위 정수로 바꾸고, 그 밖의 숫자는 쉼표를 뺀 문자열로 둔다.
    두 자리 이하의 정수(순위, 층 등)는 무시한다.
    """
    numbers: Set[str] = set()
    remaining = []
    last = 0
    for m in _KOREAN_AMOUNT.finditer(text):
        if m.end() == m.start() or not (m.group(1) or m.group(2) or m.group(3)):
            continue
        eok, cheon, man = _to_int(m.group(1)), _to_int(m.group(2)), _to_int(m.group(3))
        won = eok * 10**8 + cheon * 1000 * 10**4 + man * 10**4
        numbers.add(str(won))
        remaining.append(text[last:m.start()])
        last = m.end()
    remaining.append(text[last:])
    for token in _PLAIN_NUMBER.findall(" ".join(remaining)):
        token = token.replace(",", "").rstrip(".")
        if "." in token or len(token) >= 3:
            numbers.add(token)
    return numbers


def mentions_amount(explanation: str, won: int) -> bool:
    """설명에 이 금액이 (어떤 표기로든) 들어 있는가."""
    return str(won) in extract_numbers(explanation)


def ungrounded_numbers(explanation: str, source_text: str) -> List[str]:
    """설명에 있는데 근거 자료(값 + 청크)에는 없는 숫자."""
    source = extract_numbers(source_text)
    return sorted(n for n in extract_numbers(explanation) if n not in source)



def check_explanation(field: str, explanation: str, source_text: str, active_rights: Optional[Set[str]] = None,
                      rights_field: Optional[str] = None) -> List[str]:
    """
    문제가 있으면 사유 목록, 없으면 []. 사유: "ungrounded_number:<숫자>", "phantom_right:<권리>", "missing_right:<권리>".
    active_rights 는 서버가 확인한 현재 유효한 권리 종류. rights_field 항목에만 권리 검사를 한다.
    """
    reasons = ["ungrounded_number:" + n for n in ungrounded_numbers(explanation, source_text)]
    if rights_field and field == rights_field and active_rights is not None:
        asserted = asserted_rights(explanation)
        reasons += ["phantom_right:" + r for r in sorted(asserted - set(active_rights))]
        reasons += ["missing_right:" + r for r in sorted(set(active_rights) - asserted)]
    return reasons
