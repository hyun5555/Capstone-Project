import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr
from app.db.session import get_db
from app.models.user import User
from app.services.auth import get_password_hash, verify_password
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

router = APIRouter()

# ─────────────────────────────
# 📦 Pydantic 모델 정의
# ─────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    password: str
    phone: Optional[str] = None  # ✅ 사용자 생성 시 휴대폰도 받을 수 있게 추가

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: EmailStr
    username: Optional[str] = None
    phone: Optional[str] = None  # ✅ 출력 모델에 phone 포함

# ─────────────────────────────
# ✅ 사용자 생성
# ─────────────────────────────

@router.post("/", response_model=UserOut)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.email))
    db_user = result.scalars().first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = get_password_hash(user.password)
    new_user = User(
        user_id=str(uuid.uuid4()),
        email=user.email,
        username=user.username,
        hashed_password=hashed_pw,
        phone=user.phone
    )
    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    return new_user

# ─────────────────────────────
# ✅ 전체 사용자 조회
# ─────────────────────────────

@router.get("/", response_model=List[UserOut])
async def read_users(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).offset(skip).limit(limit))
    return list(result.scalars().all())

# ─────────────────────────────
# ✅ 단일 사용자 조회
# ─────────────────────────────

@router.get("/by-email", response_model=UserOut)
async def read_user_by_email(email: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user



# ─────────────────────────────
# ✅ 사용자 정보 수정
# ─────────────────────────────

@router.put("/{user_id}", response_model=UserOut)
async def update_user(user_id: str, user_update: UserUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_update.username is not None:
        user.username = user_update.username
    if user_update.password is not None:
        user.hashed_password = get_password_hash(user_update.password)
    if user_update.email is not None:
        user.email = user_update.email
    if user_update.phone is not None:
        user.phone = user_update.phone

    await db.commit()
    await db.refresh(user)
    return user


# ─────────────────────────────
# ✅ 사용자 삭제
# ─────────────────────────────

@router.delete("/{user_id}")
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
    return {"detail": "User deleted"}

# ─────────────────────────────
# ✅ 비밀번호 변경
# ─────────────────────────────

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

@router.put("/change-password/{user_id}")
async def change_password(
    user_id: str,
    payload: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.hashed_password or not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.hashed_password = get_password_hash(payload.new_password)
    await db.commit()

    return {"message": "비밀번호가 성공적으로 변경되었습니다."}
