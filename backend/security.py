"""
비밀번호 해싱(scrypt, 표준 라이브러리) + 로그인 토큰(JWT, HS256) + 점주 본인 확인 (T1)

AUTH_REQUIRED=false (기본, 개발용) : 토큰 없이도 동작. 토큰을 보내면 검사는 한다.
AUTH_REQUIRED=true  (배포용)      : 점주 전용 API 는 'Authorization: Bearer <토큰>' 이 있어야 하고, 토큰 주인 = user_id 여야 한다.
"""
import hashlib
import hmac
import os
import secrets
import time

import jwt
from fastapi import HTTPException, Request

from .settings import settings

_N, _R, _P = 2 ** 14, 8, 1
_ALGO = "HS256"
_runtime_secret = settings.jwt_secret or secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_hex, hash_hex = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(dk, bytes.fromhex(hash_hex))
    except (ValueError, TypeError):
        return False


def create_token(user_id: int) -> str:
    now = int(time.time())
    payload = {"sub": str(user_id), "iat": now, "exp": now + int(settings.token_ttl_hours * 3600)}
    return jwt.encode(payload, _runtime_secret, algorithm=_ALGO)


def decode_token(token: str) -> int:
    """유효하면 user_id, 아니면 401"""
    try:
        payload = jwt.decode(token, _runtime_secret, algorithms=[_ALGO])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "로그인이 만료되었습니다. 다시 로그인하세요")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(401, "로그인 토큰이 올바르지 않습니다")


def token_user_id(request: Request) -> int | None:
    auth = request.headers.get("Authorization", "")
    if not auth:
        return None
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Authorization 헤더는 'Bearer <토큰>' 형식이어야 합니다")
    return decode_token(token.strip())


def ensure_owner(request: Request, user_id: int) -> None:
    """점주 전용 API 에서 호출. 토큰이 있으면 주인 확인, AUTH_REQUIRED 면 토큰 필수."""
    tid = token_user_id(request)
    if tid is None:
        if settings.auth_required:
            raise HTTPException(401, "로그인이 필요합니다")
        return
    if tid != user_id:
        raise HTTPException(403, "다른 매장의 데이터에는 접근할 수 없습니다")
