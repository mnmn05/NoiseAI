"""
음악 생성 (T5 + T8)

  POST /api/tracks/generate     프롬프트 만들고 Replicate 생성 시작 -> 바로 응답 (생성은 백그라운드에서 진행)
  GET  /api/tracks/{id}         상태 확인 (pending / processing / succeeded / failed) — 프론트가 폴링
  GET  /api/tracks/next         아직 안 틀어준 가장 오래된 완성곡 (재생 대기열)
  POST /api/tracks/{id}/played  재생 완료 표시
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import db as dbmod
from .. import replicate_client, storage
from ..db import get_db
from ..models import StatusLog, Track, User, utcnow
from ..prompt_engine import StoreProfile, build_prompt_detail
from ..settings import settings

router = APIRouter(prefix="/api/tracks", tags=["tracks"])

RECENT_NOISE_SECONDS = 30      # noise_db 를 안 보내면 최근 30초 평균을 쓴다


class GenerateRequest(BaseModel):
    user_id: int
    noise_db: float | None = Field(default=None, ge=0.0, le=140.0)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:                       # SQLite 는 시간대를 저장하지 않아 UTC 로 간주
        dt = dt.replace(tzinfo=utcnow().tzinfo)
    return dt.isoformat(timespec="seconds")


def _track_out(t: Track) -> dict:
    return {
        "id": t.id, "user_id": t.user_id, "status": t.status, "prompt": t.prompt,
        "audio_url": t.audio_url, "is_played": t.is_played, "error": t.error,
        "created_at": _iso(t.created_at), "completed_at": _iso(t.completed_at),
    }


def _recent_avg_noise(db: Session, user_id: int) -> float | None:
    cutoff = utcnow() - timedelta(seconds=RECENT_NOISE_SECONDS)
    v = db.scalar(select(func.avg(StatusLog.noise_db)).where(
        StatusLog.user_id == user_id, StatusLog.created_at >= cutoff))
    return None if v is None else float(v)


async def run_generation(track_id: int):
    """백그라운드 작업: Replicate 생성 -> 완료 대기 -> 음원 저장 -> DB 갱신. 어떤 오류든 track 을 failed 로 남긴다."""
    with dbmod.SessionLocal() as s:
        track = s.get(Track, track_id)
        if track is None:
            return
        track.status = "processing"
        prompt = track.prompt
        s.commit()

    try:
        async with replicate_client.make_client() as rc:
            pred = await replicate_client.create_prediction(rc, prompt)
            with dbmod.SessionLocal() as s:
                s.get(Track, track_id).prediction_id = pred["id"]
                s.commit()
            done = await replicate_client.wait_for_prediction(rc, pred["id"])
            audio_url = replicate_client.extract_output_url(done)
        if settings.download_audio:
            audio_url = await storage.save_remote_audio(audio_url, track_id)
        result = {"status": "succeeded", "audio_url": audio_url, "error": None}
    except Exception as e:  # noqa: BLE001  (실패 원인을 DB 에 남기는 게 목적)
        result = {"status": "failed", "audio_url": None, "error": f"{type(e).__name__}: {e}"[:500]}

    with dbmod.SessionLocal() as s:
        track = s.get(Track, track_id)
        track.status = result["status"]
        track.audio_url = result["audio_url"]
        track.error = result["error"]
        track.completed_at = utcnow()
        s.commit()


@router.post("/generate", status_code=202)
def generate(data: GenerateRequest, background: BackgroundTasks, response: Response, db: Session = Depends(get_db)):
    user = db.get(User, data.user_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")

    # 같은 매장에서 생성 중인 곡이 있으면 새로 만들지 않는다 (클라이언트 실수로 과금이 폭주하는 것 방지)
    window = utcnow() - timedelta(seconds=settings.poll_timeout + 60)
    active = db.scalar(
        select(Track).where(Track.user_id == user.id, Track.status.in_(("pending", "processing")),
                            Track.created_at >= window).order_by(Track.id.desc())
    )
    if active:
        response.status_code = 200
        return {**_track_out(active), "already_generating": True}

    noise_db = data.noise_db if data.noise_db is not None else _recent_avg_noise(db, user.id)
    profile = StoreProfile(category=user.category, age_group=user.age_group, gender=user.gender, mood=user.mood)
    result = build_prompt_detail(noise_db, profile, settings.prompt_strategy)

    track = Track(user_id=user.id, prompt=result.prompt, status="pending")
    db.add(track)
    db.commit()
    background.add_task(run_generation, track.id)
    return {
        **_track_out(track),
        "already_generating": False,
        "noise_db_used": None if noise_db is None else round(noise_db, 1),
        "noise_level": result.noise_level,
        "keywords": result.keywords,
        "dropped_keywords": result.dropped,
    }


@router.get("/next")
def next_track(user_id: int, db: Session = Depends(get_db)):
    t = db.scalar(select(Track).where(Track.user_id == user_id, Track.status == "succeeded",
                                      Track.is_played.is_(False)).order_by(Track.id.asc()))
    if not t:
        raise HTTPException(404, "재생 대기 중인 곡이 없습니다")
    return _track_out(t)


@router.get("")
def list_tracks(user_id: int, status: str | None = None, limit: int = Query(20, ge=1, le=200),
                db: Session = Depends(get_db)):
    stmt = select(Track).where(Track.user_id == user_id)
    if status:
        stmt = stmt.where(Track.status == status)
    rows = db.scalars(stmt.order_by(Track.id.desc()).limit(limit)).all()
    return [_track_out(t) for t in rows]


@router.get("/{track_id}")
def get_track(track_id: int, db: Session = Depends(get_db)):
    t = db.get(Track, track_id)
    if not t:
        raise HTTPException(404, "곡을 찾을 수 없습니다")
    return _track_out(t)


@router.post("/{track_id}/played")
def mark_played(track_id: int, db: Session = Depends(get_db)):
    t = db.get(Track, track_id)
    if not t:
        raise HTTPException(404, "곡을 찾을 수 없습니다")
    t.is_played = True
    db.commit()
    return _track_out(t)
