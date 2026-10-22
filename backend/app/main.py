# backend/app/main.py
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import auth, property, users, building, registry, vector, \
    analyze, chatbot, jeonse_price, address, trade_price, transaction_summary, jeonse_rate, codef_auth
from app.config import CORS_ORIGINS, MAX_REQUEST_BYTES
from app.db.schema import ensure_schema
from app.middleware.body_limit import BodySizeLimitMiddleware
from app.services.rate_limit import analysis_rate_limit, protected_rate_limit, public_rate_limit

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "FastAPI 서버가 정상적으로 작동 중입니다."}


# CORS 설정 예시
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_REQUEST_BYTES)

# startup 이벤트에서 테이블 생성
@app.on_event("startup")
async def on_startup():
    await ensure_schema()

# 라우터 등록
app.include_router(auth.router, prefix="/auth", tags=["auth"])
protected = [Depends(protected_rate_limit)]
analysis_limited = [Depends(analysis_rate_limit)]
app.include_router(property.router, dependencies=protected)
app.include_router(users.router, prefix="/users", tags=["users"], dependencies=protected)
app.include_router(building.router, dependencies=analysis_limited)
app.include_router(registry.router, dependencies=analysis_limited)
app.include_router(vector.router, dependencies=analysis_limited)
app.include_router(analyze.router, prefix="/analyze", tags=["Analyze"], dependencies=analysis_limited)
app.include_router(chatbot.router, prefix="/chatbot", tags=["chatbot"], dependencies=analysis_limited)
app.include_router(jeonse_price.router, dependencies=protected)
app.include_router(trade_price.router, dependencies=protected)
app.include_router(address.router, dependencies=[Depends(public_rate_limit)])
app.include_router(transaction_summary.router, tags=["Transaction Summary"], dependencies=analysis_limited)
app.include_router(jeonse_rate.router, tags=["Rent Rate"], dependencies=analysis_limited)
app.include_router(codef_auth.router, dependencies=analysis_limited)
