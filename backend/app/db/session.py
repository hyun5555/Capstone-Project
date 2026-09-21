# backend/app/db/session.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import AsyncGenerator
from app.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)

# ✅ 먼저 정의
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# ✅ 필요한 경우 임시로도 사용 가능
SessionLocal = AsyncSessionLocal  

Base = declarative_base()

# ✅ async generator for FastAPI Depends
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
