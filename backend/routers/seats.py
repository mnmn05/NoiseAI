"""
키오스크 자리 선택 / 퇴석 (T8) + 가게 공개 혼잡 상태 (T8)

  POST /api/seats/event                 키오스크: 자리 선택 후 주문 = occupy, 결제 완료·직원 정리 = release
  GET  /api/seats?user_id=              점주: 현재 점유 좌석 / 점유율 / 예상 대기시간
  GET  /api/public/status/{public_id}   손님(가게 링크): "지금 한산해요, 조용히 쉬기 좋아요" + 예상 대기 + 한산한 시간대
"""
import datetime as dt
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import SeatEvent, StatusLog, User
from ..services import occupancy_info, recent_noise_avg
from ..settings import KST

router = APIRouter(prefix="/api", tags=["seats", "public"])

# ---- 혼잡도 (대시보드·공개 페이지 공통, 고정 임계값) ----
QUIET_BELOW_DB = 55.0      # 평균 dB 가 이 미만이면 한산
BUSY_FROM_DB = 70.0        # 이 이상이면 혼잡
OCC_BUSY = 0.85            # 점유율이 이 이상이면 혼잡
OCC_QUIET = 0.4            # 이 미만이면 한산
PUBLIC_NOISE_WINDOW_SEC = 300
PUBLIC_MIN_SAMPLES = 10
LABEL_KO = {"quiet": "한산", "normal": "보통", "busy": "혼잡", "unknown": "정보 없음"}


class SeatEventIn(BaseModel):
    user_id: int
    seat_id: str = Field(min_length=1, max_length=30)
    event: str = Field(pattern="^(occupy|release)$")
    party_size: int | None = Field(default=None, ge=1, le=50)


def crowd_from_db(avg_db: float | None) -> str:
    if avg_db is None:
        return "unknown"
    if avg_db >= BUSY_FROM_DB:
        return "busy"
    if avg_db < QUIET_BELOW_DB:
        return "quiet"
    return "normal"


def crowd_from_occupancy(occ: float | None) -> str:
    if occ is None:
        return "unknown"
    if occ >= OCC_BUSY:
        return "busy"
    if occ < OCC_QUIET:
        return "quiet"
    return "normal"


def combined_crowd(avg_db: float | None, occ: float | None) -> str:
    """좌석 정보가 있으면 좌석을 우선 (소음만으로는 '조용한 만석'을 한산으로 오판하기 때문).
    좌석이 '보통' 인데 소음이 혼잡이면 한 단계 올린다. 좌석 정보가 없으면 소음으로."""
    by_occ, by_db = crowd_from_occupancy(occ), crowd_from_db(avg_db)
    if by_occ == "unknown":
        return by_db
    if by_occ == "normal" and by_db == "busy":
        return "busy"
    return by_occ


def public_message(level: str, free_seats: int | None, wait: int | None) -> str:
    if level == "unknown":
        return "실시간 정보가 아직 없어요"
    if wait:
        return f"지금 자리가 모두 찼어요. 예상 대기 약 {wait}분"
    if level == "quiet":
        return "지금 한산해요, 조용히 쉬기 좋아요"
    if level == "normal":
        return "적당히 붐벼요, 바로 앉을 수 있어요"
    if free_seats is not None and free_seats <= 2:
        return f"지금 붐벼요. 남은 자리 {free_seats}석"
    return "지금 붐벼요"


def quiet_hours(db: Session, user_id: int, days: int = 7, top: int = 3) -> list[dict]:
    """최근 며칠간 시간대(0~23시)별 평균 dB 가 낮은 순 — '조용한 곳을 찾는 손님이 시간을 골라 올 수 있게'"""
    since = (dt.datetime.now(KST) - timedelta(days=days)).strftime("%Y-%m-%dT%H")
    rows = db.execute(select(StatusLog.hour_bucket, func.avg(StatusLog.noise_db), func.count(StatusLog.id))
                      .where(StatusLog.user_id == user_id, StatusLog.hour_bucket >= since)
                      .group_by(StatusLog.hour_bucket)).all()
    by_hour: dict[int, list[float]] = {}
    for bucket, avg, cnt in rows:
        if cnt:
            by_hour.setdefault(int(bucket[-2:]), []).append(float(avg))
    ranked = sorted(((sum(v) / len(v), h) for h, v in by_hour.items()))
    return [{"hour": h, "avg_db": round(a, 1), "crowd_level": crowd_from_db(a)} for a, h in ranked[:top]]


def _user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "매장을 찾을 수 없습니다")
    return user


@router.post("/seats/event", status_code=201)
def seat_event(data: SeatEventIn, db: Session = Depends(get_db)):
    user = _user(db, data.user_id)
    db.add(SeatEvent(user_id=user.id, seat_id=data.seat_id.strip(), event=data.event, party_size=data.party_size))
    db.commit()
    info = occupancy_info(db, user)
    return {"result": "success", "occupied_seats": info.occupied_seats, "total_seats": info.total_seats,
            "occupancy": info.occupancy}


@router.get("/seats")
def seats(user_id: int, db: Session = Depends(get_db)):
    user = _user(db, user_id)
    i = occupancy_info(db, user)
    return {"user_id": user.id, "total_seats": i.total_seats, "occupied_seats": i.occupied_seats,
            "free_seats": i.free_seats, "occupancy": None if i.occupancy is None else round(i.occupancy, 2),
            "avg_dwell_min": i.avg_dwell_min, "expected_wait_min": i.expected_wait_min, "occupied": i.occupied}


@router.get("/public/status/{public_id}")
def public_status(public_id: str, db: Session = Depends(get_db)):
    """로그인 없이 누구나 보는 API. 이메일 등 개인정보는 내보내지 않는다."""
    user = db.scalar(select(User).where(User.public_id == public_id))
    if not user:
        raise HTTPException(404, "가게를 찾을 수 없습니다")
    avg = recent_noise_avg(db, user.id, PUBLIC_NOISE_WINDOW_SEC, PUBLIC_MIN_SAMPLES)
    i = occupancy_info(db, user)
    level = combined_crowd(avg, i.occupancy)
    return {
        "store_name": user.store_name,
        "crowd_level": level,
        "crowd_label": LABEL_KO[level],
        "message": public_message(level, i.free_seats, i.expected_wait_min),
        "avg_db": None if avg is None else round(avg, 1),
        "occupancy": None if i.occupancy is None else round(i.occupancy, 2),
        "free_seats": i.free_seats,
        "expected_wait_min": i.expected_wait_min,
        "quiet_hours": quiet_hours(db, user.id),
        "updated_at": dt.datetime.now(KST).isoformat(timespec="seconds"),
    }
