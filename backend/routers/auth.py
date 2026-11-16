"""로그인 (T1 ↔ T7 연동) — POST /api/auth/login 으로 토큰 발급, GET /api/auth/me 로 확인"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import create_token, token_user_id, verify_password
from ..settings import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.strip().lower()))
    # 이메일이 없을 때와 비밀번호가 틀릴 때 같은 메시지 (가입 여부를 알려주지 않기 위해)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다")
    return {"access_token": create_token(user.id), "token_type": "bearer", "user_id": user.id,
            "expires_in": int(settings.token_ttl_hours * 3600)}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    uid = token_user_id(request)
    if uid is None:
        raise HTTPException(401, "로그인이 필요합니다")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "탈퇴했거나 없는 계정입니다")
    return {"user_id": user.id, "email": user.email, "store_name": user.store_name}
