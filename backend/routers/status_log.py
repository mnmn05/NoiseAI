"""소음 기록 (T1) — 클라이언트(마이크 페이지)가 3초마다 dB 를 보내면 Status_Log 에 쌓는다."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import StatusLog, User, utcnow
from ..settings import KST

router = APIRouter(prefix="/api", tags=["status-log"])


class StatusLogCreate(BaseModel):
    user_id: int
    noise_db: float = Field(ge=0.0, le=140.0)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


@router.post("/status-log", status_code=201)
def create_status_log(data: StatusLogCreate, db: Session = Depends(get_db)):
    if not db.get(User, data.user_id):
        raise HTTPException(404, "사용자를 찾을 수 없습니다")
    now = utcnow()
    row = StatusLog(
        user_id=data.user_id,
        noise_db=round(data.noise_db, 1),
        hour_bucket=now.astimezone(KST).strftime("%Y-%m-%dT%H"),
        created_at=now,
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "user_id": row.user_id, "noise_db": row.noise_db, "hour_bucket": row.hour_bucket}


@router.get("/status-log")
def list_status_log(user_id: int, limit: int = Query(60, ge=1, le=1000), db: Session = Depends(get_db)):
    """최근 기록 (오래된 순) — 실시간 그래프용"""
    rows = db.scalars(
        select(StatusLog).where(StatusLog.user_id == user_id).order_by(StatusLog.id.desc()).limit(limit)
    ).all()
    return [
        {"id": r.id, "noise_db": r.noise_db, "hour_bucket": r.hour_bucket,
         "created_at": _iso(r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=utcnow().tzinfo))}
        for r in reversed(rows)
    ]
