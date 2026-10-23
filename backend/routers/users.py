"""점주 계정/매장 설정 (T1) — 가입·조회·수정. 로그인(토큰 발급)은 팀에서 담당자를 정한 뒤 security.verify_password 로 구현."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..prompt_engine import OPTIONS
from ..security import hash_password

router = APIRouter(prefix="/api", tags=["users"])


class UserCreate(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    store_name: str | None = Field(default=None, max_length=100)
    gender: str | None = Field(default=None, max_length=20)
    age_group: str | None = Field(default=None, max_length=20)
    category: str | None = Field(default=None, max_length=30)
    mood: str | None = Field(default=None, max_length=30)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        local, _, domain = v.partition("@")
        if not local or "." not in domain or " " in v:
            raise ValueError("이메일 형식이 올바르지 않습니다")
        return v


class StoreSettingsUpdate(BaseModel):
    store_name: str | None = Field(default=None, max_length=100)
    gender: str | None = Field(default=None, max_length=20)
    age_group: str | None = Field(default=None, max_length=20)
    category: str | None = Field(default=None, max_length=30)
    mood: str | None = Field(default=None, max_length=30)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    store_name: str | None
    gender: str | None
    age_group: str | None
    category: str | None
    mood: str | None


@router.get("/options")
def get_options():
    """회원가입 화면의 선택지 (업종/연령대/분위기/성별)"""
    return OPTIONS


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(409, "이미 가입된 이메일입니다")
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        store_name=data.store_name,
        gender=data.gender,
        age_group=data.age_group,
        category=data.category,
        mood=data.mood,
    )
    db.add(user)
    db.commit()
    return user


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")
    return user


@router.patch("/users/{user_id}/store", response_model=UserOut)
def update_store(user_id: int, data: StoreSettingsUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.commit()
    return user
