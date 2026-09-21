import logging

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from app.services.legal_rag import answer_legal_question

router = APIRouter()
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    message: str

@router.post("/chat")
async def chatbot_response(req: ChatRequest):
    query = req.message.strip()
    if not query:
        raise HTTPException(status_code=422, detail="질문을 입력해 주세요.")
    if len(query) > 1000:
        raise HTTPException(status_code=422, detail="질문은 1,000자 이하로 입력해 주세요.")

    try:
        return await run_in_threadpool(answer_legal_question, query)
    except Exception as exc:
        logger.warning("법률 RAG 답변 실패: %s", type(exc).__name__)
        return {
            "answer": "현재 공식 자료를 검색하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            "sources": [],
            "mode": "unavailable",
        }
