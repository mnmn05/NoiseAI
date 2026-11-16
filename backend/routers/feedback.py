"""
손님 참여형 분위기 조절 (T8) — 테이블 오더 키오스크의 버튼이 호출

  GET  /api/feedback/options        키오스크에 띄울 키워드 버튼 목록
  POST /api/feedback                키워드 2개 이상 + mode
                                      add_one : 선택 키워드로 1곡만 만들어 '다음 곡'으로 끼워 넣음
                                      rebuild : 아직 안 튼 대기열을 비우고, 30분 동안 자동 생성곡도 이 키워드로 만듦
  POST /api/feedback/quiet          '조용했으면' 버튼 -> dB 와 무관하게 즉시 차분한 곡으로 보정 (10분 유지)
  GET  /api/feedback?user_id=       최근 요청 기록 (점주 대시보드)
"""
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Feedback, User, utcnow
from ..prompt_engine import GUEST_KEYWORDS, normalize_guest_keywords
from ..services import (MAX_ACTIVE_REQUESTS, REBUILD_KEEP_MIN, active_tracks, aware, enqueue_generation,
                        skip_queue)
from .tracks import track_out

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

MIN_KEYWORDS = 2
MAX_KEYWORDS = 5
REQUEST_COOLDOWN_SEC = 30     # 같은 매장 키워드 요청 최소 간격 (버튼 연타/장난 방지)
QUIET_COOLDOWN_SEC = 60       # '조용했으면' 은 1분에 한 번만 새 곡을 만든다


class KeywordRequest(BaseModel):
    user_id: int
    keywords: list[str] = Field(min_length=1, max_length=10)
    mode: str = Field(pattern="^(add_one|rebuild)$")


class QuietRequest(BaseModel):
    user_id: int


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "매장을 찾을 수 없습니다")
    return user


def _recent(db: Session, user_id: int, modes: tuple, seconds: int) -> Feedback | None:
    cutoff = utcnow() - timedelta(seconds=seconds)
    return db.scalar(select(Feedback).where(Feedback.user_id == user_id, Feedback.mode.in_(modes),
                                            Feedback.created_at >= cutoff).order_by(Feedback.id.desc()))


def _ensure_capacity(db: Session, user_id: int):
    """대기열을 건드리기 전에 먼저 확인 (요청곡이 이미 꽉 찼는데 대기열만 비우는 일이 없게)"""
    if len(active_tracks(db, user_id, "request")) >= MAX_ACTIVE_REQUESTS:
        raise HTTPException(429, "요청곡을 만드는 중입니다. 잠시 후 다시 시도해 주세요")


def feedback_out(f: Feedback) -> dict:
    return {"id": f.id, "user_id": f.user_id, "mode": f.mode,
            "keywords": [k for k in (f.keywords or "").split(",") if k], "track_id": f.track_id,
            "created_at": aware(f.created_at).isoformat(timespec="seconds")}


@router.get("/options")
def options():
    return {"keywords": list(GUEST_KEYWORDS), "min_select": MIN_KEYWORDS, "max_select": MAX_KEYWORDS,
            "modes": {"add_one": "이 분위기로 1곡 추가", "rebuild": "전체 플레이리스트를 이 분위기로"}}


@router.post("", status_code=201)
def request_keywords(data: KeywordRequest, background: BackgroundTasks, db: Session = Depends(get_db)):
    user = _get_user(db, data.user_id)
    kws = normalize_guest_keywords(data.keywords)
    if len(kws) < MIN_KEYWORDS:
        raise HTTPException(422, f"키워드를 {MIN_KEYWORDS}개 이상 골라 주세요 (알 수 없는 키워드는 제외됨)")
    if len(kws) > MAX_KEYWORDS:
        raise HTTPException(422, f"키워드는 최대 {MAX_KEYWORDS}개까지 고를 수 있어요")
    if _recent(db, user.id, ("add_one", "rebuild"), REQUEST_COOLDOWN_SEC):
        raise HTTPException(429, "방금 다른 요청이 들어왔어요. 잠시 후 다시 눌러 주세요")

    _ensure_capacity(db, user.id)

    fb = Feedback(user_id=user.id, mode=data.mode, keywords=",".join(kws))
    db.add(fb)
    db.commit()

    skipped = 0
    if data.mode == "rebuild":
        skipped = skip_queue(db, user.id)
        user.guest_keywords = ",".join(kws)
        user.guest_keywords_until = utcnow() + timedelta(minutes=REBUILD_KEEP_MIN)
        db.commit()

    track, info, _ = enqueue_generation(db, user, background, source="request", guest_keywords=kws,
                                        feedback_id=fb.id)
    fb.track_id = track.id
    db.commit()
    return {"feedback": feedback_out(fb), "track": track_out(track), "skipped_tracks": skipped, **info}


@router.post("/quiet", status_code=201)
def request_quiet(data: QuietRequest, background: BackgroundTasks, db: Session = Depends(get_db)):
    user = _get_user(db, data.user_id)
    prev = _recent(db, user.id, ("quiet",), QUIET_COOLDOWN_SEC)
    fb = Feedback(user_id=user.id, mode="quiet")
    db.add(fb)
    db.commit()
    if prev and prev.track_id:
        # 1분 안에 다시 눌림: 기록만 남기고(10분 유지 시간 연장) 곡은 새로 만들지 않음
        return {"feedback": feedback_out(fb), "track": None, "already_requested": True}

    _ensure_capacity(db, user.id)
    skipped = skip_queue(db, user.id)     # 시끄러운 분위기로 만들어 둔 곡은 틀지 않음
    track, info, _ = enqueue_generation(db, user, background, source="quiet", feedback_id=fb.id, force_quiet=True)
    fb.track_id = track.id
    db.commit()
    return {"feedback": feedback_out(fb), "track": track_out(track), "already_requested": False,
            "skipped_tracks": skipped, **info}


@router.get("")
def list_feedback(user_id: int, limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    _get_user(db, user_id)
    rows = db.scalars(select(Feedback).where(Feedback.user_id == user_id)
                      .order_by(Feedback.id.desc()).limit(limit)).all()
    return [feedback_out(f) for f in rows]
