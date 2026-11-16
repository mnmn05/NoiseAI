"""점주 계정/매장 설정 (T1) — 가입·조회·수정. 로그인은 routers/auth.py"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, new_public_id
from ..prompt_engine import OPTIONS, STRATEGY_ALIASES, STRATEGY_LABEL_KO, normalize_strategy
from ..security import ensure_owner, hash_password

router = APIRouter(prefix="/api", tags=["users"])


def _check_strategy(v):
    if v is None:
        return v
    if str(v).strip().lower() not in STRATEGY_ALIASES and str(v).strip() not in STRATEGY_ALIASES:
        raise ValueError("noise_strategy 는 안정형/활기형 (stable/lively) 중 하나여야 합니다")
    return normalize_strategy(v)


class UserCreate(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    store_name: str | None = Field(default=None, max_length=100)
    gender: str | None = Field(default=None, max_length=20)
    age_group: str | None = Field(default=None, max_length=20)
    category: str | None = Field(default=None, max_length=30)
    mood: str | None = Field(default=None, max_length=30)
    noise_strategy: str | None = Field(default=None, max_length=10)   # 안정형 / 활기형 (비우면 안정형)
    total_seats: int = Field(default=0, ge=0, le=1000)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        local, _, domain = v.partition("@")
        if not local or "." not in domain or " " in v:
            raise ValueError("이메일 형식이 올바르지 않습니다")
        return v

    @field_validator("noise_strategy")
    @classmethod
    def _strategy(cls, v):
        return _check_strategy(v)


class StoreSettingsUpdate(BaseModel):
    store_name: str | None = Field(default=None, max_length=100)
    gender: str | None = Field(default=None, max_length=20)
    age_group: str | None = Field(default=None, max_length=20)
    category: str | None = Field(default=None, max_length=30)
    mood: str | None = Field(default=None, max_length=30)
    noise_strategy: str | None = Field(default=None, max_length=10)
    total_seats: int | None = Field(default=None, ge=0, le=1000)

    @field_validator("noise_strategy")
    @classmethod
    def _strategy(cls, v):
        return _check_strategy(v)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    store_name: str | None
    gender: str | None
    age_group: str | None
    category: str | None
    mood: str | None
    noise_strategy: str
    noise_strategy_ko: str
    total_seats: int
    public_id: str | None


def user_out(u: User) -> UserOut:
    strat = normalize_strategy(u.noise_strategy)
    return UserOut(id=u.id, email=u.email, store_name=u.store_name, gender=u.gender, age_group=u.age_group,
                   category=u.category, mood=u.mood, noise_strategy=strat, noise_strategy_ko=STRATEGY_LABEL_KO[strat],
                   total_seats=u.total_seats or 0, public_id=u.public_id)


@router.get("/options")
def get_options():
    """회원가입 화면의 선택지 (업종/연령대/분위기/성별/소음 대응 방식)"""
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
        noise_strategy=data.noise_strategy or "stable",
        total_seats=data.total_seats,
        public_id=new_public_id(),
    )
    db.add(user)
    db.commit()
    return user_out(user)


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    ensure_owner(request, user_id)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")
    return user_out(user)


@router.patch("/users/{user_id}/store", response_model=UserOut)
def update_store(user_id: int, data: StoreSettingsUpdate, request: Request, db: Session = Depends(get_db)):
    ensure_owner(request, user_id)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is None and key in ("noise_strategy", "total_seats"):
            continue   # 필수 성격의 값은 null 로 지우지 않음
        setattr(user, key, value)
    db.commit()
    return user_out(user)
