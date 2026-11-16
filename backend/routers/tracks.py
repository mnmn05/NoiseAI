"""
음악 생성 (T5 + T8)

  POST /api/tracks/generate     곡 재생이 시작될 때 플레이어가 호출 -> 다음 곡 생성 시작 (바로 응답, 생성은 백그라운드)
  GET  /api/tracks/{id}         상태 확인 (pending / processing / succeeded / failed) — 프론트가 폴링
  GET  /api/tracks/next         다음에 틀 곡: 손님 요청곡(priority 높은 순) -> 오래된 자동곡 순. 재구성으로 빠진 곡은 제외
  POST /api/tracks/{id}/played  재생 완료 표시
"""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import db as dbmod
from .. import replicate_client, storage
from ..db import get_db
from ..models import Track, User, utcnow
from ..security import ensure_owner
from ..services import aware, enqueue_generation
from ..settings import settings

router = APIRouter(prefix="/api/tracks", tags=["tracks"])


class GenerateRequest(BaseModel):
    user_id: int
    noise_db: float | None = Field(default=None, ge=0.0, le=140.0)   # 비우면 최근 4분 평균 사용


def _iso(dt: datetime | None) -> str | None:
    dt = aware(dt)
    return None if dt is None else dt.isoformat(timespec="seconds")


def track_out(t: Track) -> dict:
    return {
        "id": t.id, "user_id": t.user_id, "status": t.status, "prompt": t.prompt,
        "audio_url": t.audio_url, "is_played": t.is_played, "error": t.error,
        "created_at": _iso(t.created_at), "completed_at": _iso(t.completed_at),
        "source": t.source, "priority": t.priority, "is_skipped": t.is_skipped,
        "noise_level": t.noise_level, "situation": t.situation, "played_at": _iso(t.played_at),
    }


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
def generate(data: GenerateRequest, background: BackgroundTasks, response: Response, request: Request,
             db: Session = Depends(get_db)):
    ensure_owner(request, data.user_id)
    user = db.get(User, data.user_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")
    track, info, created = enqueue_generation(db, user, background, source="auto", noise_db=data.noise_db)
    if not created:
        # 같은 매장에서 생성 중인 자동곡이 있으면 새로 만들지 않는다 (클라이언트 실수로 과금이 폭주하는 것 방지)
        response.status_code = 200
        return {**track_out(track), "already_generating": True}
    return {**track_out(track), "already_generating": False, **info}


@router.get("/next")
def next_track(user_id: int, db: Session = Depends(get_db)):
    t = db.scalar(select(Track).where(Track.user_id == user_id, Track.status == "succeeded",
                                      Track.is_played.is_(False), Track.is_skipped.is_(False))
                  .order_by(Track.priority.desc(), Track.id.asc()))
    if not t:
        raise HTTPException(404, "재생 대기 중인 곡이 없습니다 (기본 BGM 으로 이어서 재생하세요)")
    return track_out(t)


@router.get("")
def list_tracks(user_id: int, status: str | None = None, limit: int = Query(20, ge=1, le=200),
                db: Session = Depends(get_db)):
    stmt = select(Track).where(Track.user_id == user_id)
    if status:
        stmt = stmt.where(Track.status == status)
    rows = db.scalars(stmt.order_by(Track.id.desc()).limit(limit)).all()
    return [track_out(t) for t in rows]


@router.get("/{track_id}")
def get_track(track_id: int, db: Session = Depends(get_db)):
    t = db.get(Track, track_id)
    if not t:
        raise HTTPException(404, "곡을 찾을 수 없습니다")
    return track_out(t)


@router.post("/{track_id}/played")
def mark_played(track_id: int, db: Session = Depends(get_db)):
    t = db.get(Track, track_id)
    if not t:
        raise HTTPException(404, "곡을 찾을 수 없습니다")
    if not t.is_played:
        t.is_played = True
        t.played_at = utcnow()
        db.commit()
    return track_out(t)
