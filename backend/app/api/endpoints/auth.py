import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.models.user import User
from app.services.auth import create_access_token, get_password_hash, verify_password

class SignupEmailRequest(BaseModel):
    email: str
    password: str
    username: Optional[str] = None
    phone: Optional[str] = None  # ✅ 추가 (선택사항)

class LoginEmailRequest(BaseModel):
    email: str
    password: str

router = APIRouter()

# ─────────────────────────────────────
# ✅ 이메일 회원가입
# ─────────────────────────────────────
@router.post("/signup/email", status_code=201)
async def signup_email(
    body: SignupEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    email = body.email
    password = body.password
    username = body.username
    phone = body.phone

    result = await db.execute(
        select(User).where(User.email == email)  # ❌ provider 조건 제거
    )
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = get_password_hash(password)
    new_user = User(
        user_id=str(uuid.uuid4()),
        email=email,
        username=username,
        hashed_password=hashed_pw,
        phone=phone  # ✅ 저장
    )
    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="회원가입 저장에 실패했습니다")

    token = create_access_token({"sub": str(new_user.user_id)})

    return {
        "success": True,
        "access_token": token,
        "user": {
            "user_id": str(new_user.user_id),
            "email": new_user.email,
            "username": new_user.username
        }
    }

# ─────────────────────────────────────
# ✅ 이메일 로그인
# ─────────────────────────────────────
@router.post("/login/email")
async def login_email(
    body: LoginEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    email = body.email
    password = body.password

    result = await db.execute(
        select(User).where(User.email == email)  # ❌ provider 조건 제거
    )
    user = result.scalars().first()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.user_id)})

    return {
        "success": True,
        "access_token": token,
        "user": {
            "user_id": str(user.user_id),
            "email": user.email,
            "username": user.username
        }
    }
