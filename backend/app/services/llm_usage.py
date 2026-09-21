# backend/app/services/llm_usage.py
"""
LLM 호출 횟수, 토큰, 지연 시간을 기록하는 LangChain 콜백. (평가 스크립트와 운영 로깅에서 같이 쓴다)

    recorder = UsageRecorder()
    chain.invoke(inputs, config={"callbacks": [recorder]})
    recorder.summary()   # {"calls": 2, "errors": 0, "prompt_tokens": ..., "completion_tokens": ..., "latency_s": ...}

토큰 수는 OpenAI 응답의 usage 를 그대로 읽는다. 응답에 usage 가 없으면 0 으로 두고 missing_usage 로 알려 준다.
"""
import time
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import BaseCallbackHandler


def _usage_from_result(response: Any) -> Optional[Dict[str, int]]:
    """LLMResult 에서 (prompt_tokens, completion_tokens) 를 찾는다. langchain-core 0.1.x / 0.3.x 둘 다 대응."""
    llm_output = getattr(response, "llm_output", None) or {}
    usage = llm_output.get("token_usage") or llm_output.get("usage")
    if isinstance(usage, dict) and ("prompt_tokens" in usage or "completion_tokens" in usage):
        return {"prompt_tokens": int(usage.get("prompt_tokens") or 0), "completion_tokens": int(usage.get("completion_tokens") or 0)}
    total_in = total_out = 0
    found = False
    for generations in getattr(response, "generations", None) or []:
        for gen in generations:
            meta = getattr(getattr(gen, "message", None), "usage_metadata", None)
            if isinstance(meta, dict):
                found = True
                total_in += int(meta.get("input_tokens") or 0)
                total_out += int(meta.get("output_tokens") or 0)
    return {"prompt_tokens": total_in, "completion_tokens": total_out} if found else None


class UsageRecorder(BaseCallbackHandler):
    def __init__(self):
        self._started: Dict[Any, float] = {}
        self.calls: List[dict] = []
        self.errors = 0

    # 채팅 모델은 on_chat_model_start, 일반 LLM 은 on_llm_start 를 호출한다.
    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        self._started[run_id] = time.perf_counter()

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):
        self._started[run_id] = time.perf_counter()

    def on_llm_end(self, response, *, run_id, **kwargs):
        started = self._started.pop(run_id, None)
        usage = _usage_from_result(response)
        self.calls.append({
            "latency_s": (time.perf_counter() - started) if started is not None else 0.0,
            "prompt_tokens": usage["prompt_tokens"] if usage else 0,
            "completion_tokens": usage["completion_tokens"] if usage else 0,
            "missing_usage": usage is None,
        })

    def on_llm_error(self, error, *, run_id, **kwargs):
        started = self._started.pop(run_id, None)
        self.errors += 1
        self.calls.append({
            "latency_s": (time.perf_counter() - started) if started is not None else 0.0,
            "prompt_tokens": 0, "completion_tokens": 0, "missing_usage": True, "error": type(error).__name__,
        })

    def reset(self):
        self._started.clear()
        self.calls.clear()
        self.errors = 0

    def summary(self) -> dict:
        return {
            "calls": len(self.calls),
            "errors": self.errors,
            "prompt_tokens": sum(c["prompt_tokens"] for c in self.calls),
            "completion_tokens": sum(c["completion_tokens"] for c in self.calls),
            "latency_s": round(sum(c["latency_s"] for c in self.calls), 4),
            "missing_usage": sum(1 for c in self.calls if c["missing_usage"]),
        }
