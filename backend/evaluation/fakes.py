# backend/evaluation/fakes.py
"""
--dry-run 용 가짜 부품. API 키와 비용 없이 평가 도구의 배관(수집, 계산, 보고서)이 도는지만 확인한다.
가짜 결과는 실제 성능을 나타내지 않는다. 보고서에도 DRY RUN 으로 표시한다.
"""
import json
import re
from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult


_BLOCK = re.compile(r"^\[항목\] ([^\n]+)\n판정: ([^\n]+)\n값: ([^\n]+)\n근거 청크:\n((?:(?!\n\n\[항목\]).)*)", re.MULTILINE | re.DOTALL)
_ALIAS = re.compile(r"<(E\d+) ")


class FakeChatModel(BaseChatModel):
    """
    LangChain 채팅 모델 흉내. 프롬프트의 [항목] 블록을 읽고 그럴듯한 JSON 을 돌려준다.
    시스템 메시지가 있으면 v2 형식({"items": [...]}), 없으면 v1 형식({"항목": {...}})으로 답한다.
    토큰 수는 글자 수로 어림해서 llm_output 에 넣는다 (비용 계산 배관 확인용).
    """
    fail_first: int = 0          # 처음 N 번은 JSON 이 아닌 문장을 돌려준다 (재시도 확인용)
    calls_made: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake-eval-chat"

    def _generate(self, messages: List[Any], stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> ChatResult:
        self.calls_made += 1
        prompt_text = "\n".join(str(m.content) for m in messages)
        if self.calls_made <= self.fail_first:
            text = "죄송합니다. JSON 이 아닌 답변입니다."
        else:
            last = str(messages[-1].content)
            items = []
            for name, status, fact, chunks in _BLOCK.findall(last):
                aliases = _ALIAS.findall(chunks)
                items.append({
                    "field": name.strip(),
                    "explanation": f"{name.strip()}: 판정은 {status.strip()}입니다. ({fact.strip()[:40]})",
                    "evidence_ids": aliases[:2],
                })
            if any(isinstance(m, SystemMessage) for m in messages):
                text = json.dumps({"items": items}, ensure_ascii=False)
            else:
                text = json.dumps({i["field"]: {"explanation": i["explanation"], "evidence_ids": i["evidence_ids"]} for i in items}, ensure_ascii=False)
        usage = {"prompt_tokens": max(1, len(prompt_text) // 2), "completion_tokens": max(1, len(text) // 2)}
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))], llm_output={"token_usage": usage})
