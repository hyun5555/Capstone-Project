from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.db.session import get_db
from app.models.analysis_cases import AnalysisJob
from app.models.property import Property
from app.models.user import User
from app.services.auth import get_current_user, get_password_hash, verify_password
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

router = APIRouter()

# ─────────────────────────────
# 📦 Pydantic 모델 정의
# ─────────────────────────────

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=72)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: EmailStr
    username: Optional[str] = None
    phone: Optional[str] = None  # ✅ 출력 모델에 phone 포함

@router.get("/me", response_model=UserOut)
async def read_me(current_user: User = Depends(get_current_user)):
    return current_user

# ─────────────────────────────
# ✅ 단일 사용자 조회
# ─────────────────────────────

@router.get("/by-email", response_model=UserOut)
async def read_user_by_email(email: str, current_user: User = Depends(get_current_user)):
    if current_user.email != email:
        raise HTTPException(status_code=403, detail="다른 사용자의 정보에는 접근할 수 없습니다.")
    return current_user



# ─────────────────────────────
# ✅ 사용자 정보 수정
# ─────────────────────────────

@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="다른 사용자의 정보는 수정할 수 없습니다.")
    user = current_user

    if user_update.username is not None:
        user.username = user_update.username
    if user_update.password is not None:
        user.hashed_password = get_password_hash(user_update.password)
    if user_update.email is not None:
        user.email = user_update.email
    if user_update.phone is not None:
        user.phone = user_update.phone

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다.")
    return user


# ─────────────────────────────
# ✅ 사용자 삭제
# ─────────────────────────────

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="다른 사용자의 계정은 삭제할 수 없습니다.")
    await db.execute(delete(AnalysisJob).where(AnalysisJob.user_id == user_id))
    await db.execute(delete(Property).where(Property.owner_id == user_id))
    await db.delete(current_user)
    await db.commit()
    return {"detail": "User deleted"}

# ─────────────────────────────
# ✅ 비밀번호 변경
# ─────────────────────────────

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)

@router.put("/change-password/{user_id}")
async def change_password(
    user_id: str,
    payload: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="다른 사용자의 비밀번호는 변경할 수 없습니다.")
    user = current_user
    if not user.hashed_password or not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.hashed_password = get_password_hash(payload.new_password)
    await db.commit()

    return {"message": "비밀번호가 성공적으로 변경되었습니다."}
