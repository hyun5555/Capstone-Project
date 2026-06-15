# app/services/sllm_model.py
import os
import sys
import re
import json
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser


# ── 1) 환경 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / ".env"

if not env_path.is_file():
    raise FileNotFoundError(f".env 파일이 없습니다: {env_path}")

load_dotenv(env_path)

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))


# ── 2) OpenAI API 키 로딩
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다")


# ── 3) LangChain LLM 설정
compare_llm = ChatOpenAI(
    model="gpt-4",
    temperature=0,
    api_key=api_key
)

explain_llm = ChatOpenAI(
    model="gpt-4",
    temperature=0.7,
    api_key=api_key
)


# ── 4) 필드 추출 정규표현식 패턴
patterns = {
    "소유자명": r"소유자[:：]?\s*([^,]+)",
    "건물 용도": r"용도[:：]?\s*([^,]+)",
    "구조 유형": r"구조[:：]?\s*([^,]+)",
    "전용면적": r"전용면적[:：]?\s*([^,]+)",
    "공유면적": r"공유면적[:：]?\s*([^,]+)",
    "연면적": r"연면적[:：]?\s*([^,]+)",
    "준공년도": r"준공년도[:：]?\s*([^,]+)",
    "근저당 설정 유무": r"채권최고액[:：]?(\d+|없음)",
    "위험 권리 존재 여부": r"권리[:：]?\s*([^,]+)"
}


# ── 5) 텍스트에서 필드 값 추출
def extract_fields(text: str) -> dict:
    fields = {}
    risk_types = {"경매개시결정", "압류", "가압류", "가등기", "신탁", "전세권", "임차권"}

    for name, pat in patterns.items():
        m = re.search(pat, text)
        value = m.group(1).strip() if m else None

        if name == "위험 권리 존재 여부":
            if value:
                rights = [s.strip() for s in re.split(r"[,\s]+", value)]
                filtered = [r for r in rights if r in risk_types]
                fields["위험 권리 목록"] = filtered
            else:
                fields["위험 권리 목록"] = []
        elif value is not None:
            fields[name] = value

    return fields


# ── 6) LangChain 비교 체인
compare_prompt = ChatPromptTemplate.from_template(
    """
다음은 두 개의 문서에서 추출된 필드 값입니다.

[등기부등본]
{reg}

[건축물대장]
{bld}

다음 필드 목록에 대해 두 문서의 값이 같은지 비교하세요.

필드 목록:
{field_list}

응답 규칙:
- 반드시 JSON 형식으로만 응답하세요.
- 설명 문장은 포함하지 마세요.
- 각 필드 값은 "일치" 또는 "불일치" 중 하나여야 합니다.
- 값이 한쪽에 없거나 의미가 다르면 "불일치"로 판단하세요.

출력 예시:
{{
  "소유자명": "불일치",
  "건물 용도": "일치"
}}
"""
)

compare_chain = compare_prompt | compare_llm | JsonOutputParser()


def compare_flags_gpt4(reg: dict, bld: dict) -> Dict[str, str]:
    try:
        result = compare_chain.invoke({
            "reg": json.dumps(reg, ensure_ascii=False, indent=2),
            "bld": json.dumps(bld, ensure_ascii=False, indent=2),
            "field_list": ", ".join(patterns.keys())
        })

        if not isinstance(result, dict):
            raise ValueError(f"GPT 응답이 dict 형식이 아닙니다: {result}")

        return result

    except Exception as e:
        print("❌ LangChain 비교 체인 실행 실패:", e)
        raise


# ── 7) LangChain 설명 생성 체인
explain_prompt = ChatPromptTemplate.from_template(
    """
다음은 등기부등본과 건축물대장의 필드 비교 결과입니다.

{comparison_lines}

각 항목마다 왜 동일하거나 다른지 짧게 설명해 주세요.

응답 규칙:
- 반드시 JSON 형식으로만 응답하세요.
- 각 key는 항목명이어야 합니다.
- 각 value는 설명 문장이어야 합니다.

출력 예시:
{{
  "소유자명": "등기부등본과 건축물대장의 소유자가 서로 다르므로 불일치로 판단됩니다.",
  "건물 용도": "두 문서 모두 주거용으로 기재되어 있어 일치합니다."
}}
"""
)

explain_chain = explain_prompt | explain_llm | JsonOutputParser()


def generate_explanations(flags: Dict[str, str], reg: dict, bld: dict) -> Dict[str, str]:
    lines = []

    for k, flag in flags.items():
        rv = reg.get(k) or "없음"
        bv = bld.get(k) or "없음"
        lines.append(f"{k}: flag={flag}, 등기부='{rv}', 건축물대장='{bv}'")

    try:
        result = explain_chain.invoke({
            "comparison_lines": "\n".join(lines)
        })

        if not isinstance(result, dict):
            raise ValueError(f"GPT 응답이 dict 형식이 아닙니다: {result}")

        return result

    except Exception as e:
        print("❌ LangChain 설명 생성 체인 실행 실패:", e)
        raise


# ── 8) LangChain 최종 보고서 생성 체인
report_prompt = ChatPromptTemplate.from_template(
    """
다음은 전세계약 비교 결과입니다.

케이스: {case_id}
주소: {address}

{table}

위 표를 바탕으로 사용자에게 제공할 전세계약 위험 분석 요약 보고서를 한 단락으로 작성해 주세요.

작성 기준:
- 핵심 불일치 항목을 중심으로 설명하세요.
- 사용자가 이해하기 쉽게 작성하세요.
- 과도하게 법률 자문처럼 단정하지 마세요.
"""
)

report_chain = report_prompt | explain_llm | StrOutputParser()


def compile_report(case_id: str, address: str, flags: Dict[str, str], explanations: Dict[str, str]) -> str:
    table = "\n".join([
        "항목 | 일치 유무 | 설명",
        "------|---------|------",
        *[
            f"{k} | {flags.get(k, '')} | {explanations.get(k, '')}"
            for k in flags
        ]
    ])

    try:
        return report_chain.invoke({
            "case_id": case_id,
            "address": address,
            "table": table
        })

    except Exception as e:
        print("❌ LangChain 보고서 생성 체인 실행 실패:", e)
        raise


# ── 9) 엔트리 포인트 예시
if __name__ == "__main__":
    sample_reg = extract_fields(
        "소유자: 김철수, 용도: 주거용, 구조: 철근콘크리트, 전용면적: 84.2㎡, "
        "공유면적: 12.1㎡, 연면적: 96.3㎡, 준공년도: 2018, 채권최고액: 120000000, "
        "권리: 근저당권, 압류"
    )

    sample_bld = extract_fields(
        "소유자: 고예지, 용도: 주거용, 구조: 철근콘크리트, 전용면적: 84.2㎡, "
        "공유면적: 12.1㎡, 연면적: 96.3㎡, 준공년도: 2018"
    )

    flags = compare_flags_gpt4(sample_reg, sample_bld)
    explanations = generate_explanations(flags, sample_reg, sample_bld)
    report = compile_report("case_001", "서울시 강남구", flags, explanations)

    print("추출된 등기부 필드:")
    print(json.dumps(sample_reg, ensure_ascii=False, indent=2))

    print("\n추출된 건축물대장 필드:")
    print(json.dumps(sample_bld, ensure_ascii=False, indent=2))

    print("\n일치/불일치 결과:")
    print(json.dumps(flags, ensure_ascii=False, indent=2))

    print("\n설명:")
    print(json.dumps(explanations, ensure_ascii=False, indent=2))

    print("\n최종 보고서:")
    print(report)