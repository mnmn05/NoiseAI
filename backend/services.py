"""
공통 로직 (T5·T8) — 여러 라우터가 같이 쓰는 계산과 '곡 생성 예약'

  recent_noise_avg    최근 N초 평균 dB (히스테리시스용 3~5분 창)
  occupancy_info      좌석 점유율 / 빈자리 / 예상 대기시간
  enqueue_generation  프롬프트 만들고 Track 을 만든 뒤 백그라운드 생성 예약 (자동/손님 요청 공통)
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Feedback, SeatEvent, StatusLog, Track, User, utcnow
from .prompt_engine import StoreProfile, build_prompt_detail, normalize_strategy
from .settings import settings

# ---- 튜닝 값 ----
NOISE_AVG_WINDOW_SEC = 240        # 분위기 전환 판단용 평균 창 (4분 = 계획서의 3~5분)
NOISE_MIN_SAMPLES = 20            # 이보다 적으면(약 1분 미만) 평균을 믿지 않고 직전 구간 유지
SEAT_MAX_MINUTES = 180            # 퇴석 기록이 없어도 이 시간이 지나면 빈자리로 간주
DWELL_LOOKBACK_DAYS = 7           # 평균 체류시간 계산 기간
DEFAULT_DWELL_MIN = 60            # 체류 기록이 없을 때 평균 체류시간 가정(분)
QUIET_REQUEST_HOLD_SEC = 600      # '조용했으면' 버튼 효과 유지 시간 (10분)
REBUILD_KEEP_MIN = 30             # '전체 재구성' 키워드를 자동 생성에 계속 쓰는 시간 (30분)
MAX_ACTIVE_REQUESTS = 2           # 동시에 생성 중일 수 있는 손님 요청곡 수 (과금 폭주 방지)
REQUEST_PRIORITY = 10             # 1곡 추가 / 재구성 요청곡
QUIET_PRIORITY = 20               # '조용했으면' 보정곡 (가장 먼저)


def aware(dt: datetime | None) -> datetime | None:
    """SQLite 는 시간대를 저장하지 않으므로 UTC 로 간주"""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=utcnow().tzinfo)


def recent_noise_avg(db: Session, user_id: int, seconds: int = NOISE_AVG_WINDOW_SEC,
                     min_samples: int = NOISE_MIN_SAMPLES) -> float | None:
    cutoff = utcnow() - timedelta(seconds=seconds)
    avg, cnt = db.execute(select(func.avg(StatusLog.noise_db), func.count(StatusLog.id)).where(
        StatusLog.user_id == user_id, StatusLog.created_at >= cutoff)).one()
    if avg is None or (cnt or 0) < min_samples:
        return None
    return float(avg)


# ---------------------------------------------------------------- 좌석
@dataclass
class OccupancyInfo:
    total_seats: int
    occupied_seats: int
    occupied: list            # [{"seat_id", "since", "party_size"}]
    occupancy: float | None   # 0~1, 좌석 수를 모르면 None
    free_seats: int | None
    avg_dwell_min: float
    expected_wait_min: int | None   # 빈자리가 있으면 0, 좌석 수를 모르면 None


def occupancy_info(db: Session, user: User, now: datetime | None = None) -> OccupancyInfo:
    now = now or utcnow()
    since = now - timedelta(days=DWELL_LOOKBACK_DAYS)
    rows = db.scalars(select(SeatEvent).where(SeatEvent.user_id == user.id, SeatEvent.created_at >= since)
                      .order_by(SeatEvent.created_at, SeatEvent.id)).all()

    latest: dict[str, SeatEvent] = {}
    open_at: dict[str, datetime] = {}
    dwells: list[float] = []
    for ev in rows:
        t = aware(ev.created_at)
        if ev.event == "occupy":
            open_at[ev.seat_id] = t
        elif ev.event == "release" and ev.seat_id in open_at:
            minutes = (t - open_at.pop(ev.seat_id)).total_seconds() / 60
            if 1 <= minutes <= SEAT_MAX_MINUTES:          # 너무 짧거나(오입력) 긴(퇴석 누락) 기록은 평균에서 제외
                dwells.append(minutes)
        latest[ev.seat_id] = ev

    expire = now - timedelta(minutes=SEAT_MAX_MINUTES)
    occupied = [
        {"seat_id": sid, "since": aware(ev.created_at).isoformat(timespec="seconds"), "party_size": ev.party_size,
         "_t": aware(ev.created_at)}
        for sid, ev in latest.items() if ev.event == "occupy" and aware(ev.created_at) >= expire
    ]
    avg_dwell = sum(dwells) / len(dwells) if dwells else float(DEFAULT_DWELL_MIN)

    total = user.total_seats or 0
    n = len(occupied)
    if total > 0 and rows:      # 최근 7일 키오스크 기록이 하나도 없으면 '0% 점유'가 아니라 '모름'
        occ = min(1.0, n / total)
        free = max(0, total - n)
        if free > 0:
            wait = 0
        else:   # 가장 먼저 일어날 것 같은 자리(앉은 지 가장 오래된 자리)의 남은 시간
            elapsed = max((now - o["_t"]).total_seconds() / 60 for o in occupied)
            wait = int(round(max(0.0, avg_dwell - elapsed)))
            wait = max(wait, 5)   # 평균보다 오래 앉아 있어도 '0분'이라 하지 않음 (최소 5분 안내)
    else:
        occ, free, wait = None, None, None
    for o in occupied:
        o.pop("_t")
    return OccupancyInfo(total_seats=total, occupied_seats=n, occupied=occupied, occupancy=occ, free_seats=free,
                         avg_dwell_min=round(avg_dwell, 1), expected_wait_min=wait)


# ---------------------------------------------------------------- 곡 생성 예약
def quiet_requested(db: Session, user_id: int) -> bool:
    cutoff = utcnow() - timedelta(seconds=QUIET_REQUEST_HOLD_SEC)
    return db.scalar(select(func.count(Feedback.id)).where(
        Feedback.user_id == user_id, Feedback.mode == "quiet", Feedback.created_at >= cutoff)) > 0


def active_guest_keywords(user: User) -> list[str]:
    until = aware(user.guest_keywords_until)
    if not user.guest_keywords or until is None or until < utcnow():
        return []
    return [k for k in user.guest_keywords.split(",") if k]


def last_noise_level(db: Session, user_id: int) -> str | None:
    return db.scalar(select(Track.noise_level).where(Track.user_id == user_id, Track.noise_level.is_not(None))
                     .order_by(Track.id.desc()).limit(1))


def active_tracks(db: Session, user_id: int, source: str | None = None):
    window = utcnow() - timedelta(seconds=settings.poll_timeout + 60)
    stmt = select(Track).where(Track.user_id == user_id, Track.status.in_(("pending", "processing")),
                               Track.created_at >= window)
    if source == "auto":
        stmt = stmt.where(Track.source == "auto")
    elif source == "request":
        stmt = stmt.where(Track.source != "auto")
    return db.scalars(stmt.order_by(Track.id.desc())).all()


def enqueue_generation(db: Session, user: User, background: BackgroundTasks, *, source: str = "auto",
                       noise_db: float | None = None, guest_keywords: list[str] | None = None,
                       feedback_id: int | None = None, force_quiet: bool = False) -> tuple[Track, dict, bool]:
    """
    반환: (track, 판정 정보, 새로 만들었는지)
    source: auto(곡 시작 시 다음 곡) / request(손님 1곡 추가·재구성) / quiet('조용했으면' 보정)
    auto 는 생성 중인 auto 곡이 있으면 새로 만들지 않는다. 손님 요청은 동시에 MAX_ACTIVE_REQUESTS 까지만.
    """
    from .routers.tracks import run_generation   # 순환 import 방지

    if source == "auto":
        existing = active_tracks(db, user.id, "auto")
        if existing:
            return existing[0], {}, False
    elif len(active_tracks(db, user.id, "request")) >= MAX_ACTIVE_REQUESTS:
        raise HTTPException(429, "요청곡을 만드는 중입니다. 잠시 후 다시 시도해 주세요")

    measured = noise_db if noise_db is not None else recent_noise_avg(db, user.id)
    occ = occupancy_info(db, user)
    prev = last_noise_level(db, user.id)
    guest = guest_keywords if guest_keywords is not None else active_guest_keywords(user)
    quiet = force_quiet or quiet_requested(db, user.id)
    strategy = normalize_strategy(user.noise_strategy, default=normalize_strategy(settings.prompt_strategy))

    profile = StoreProfile(category=user.category, age_group=user.age_group, gender=user.gender, mood=user.mood,
                           noise_strategy=strategy)
    res = build_prompt_detail(measured, profile, strategy, prev_level=prev, occupancy=occ.occupancy,
                              quiet_requested=quiet, guest_keywords=guest)

    priority = {"auto": 0, "request": REQUEST_PRIORITY, "quiet": QUIET_PRIORITY}[source]
    track = Track(user_id=user.id, prompt=res.prompt, status="pending", source=source, priority=priority,
                  noise_level=res.noise_level, situation=res.situation, feedback_id=feedback_id)
    db.add(track)
    db.commit()
    background.add_task(run_generation, track.id)
    info = {
        "noise_db_used": None if measured is None else round(measured, 1),
        "noise_level": res.noise_level,
        "situation": res.situation,
        "strategy": res.strategy,
        "occupancy": None if occ.occupancy is None else round(occ.occupancy, 2),
        "guest_keywords": guest,
        "keywords": res.keywords,
        "dropped_keywords": res.dropped,
    }
    return track, info, True


def skip_queue(db: Session, user_id: int) -> int:
    """'전체 재구성' / '조용했으면' : 아직 안 튼 곡(완성·생성 중)을 대기열에서 뺀다. 이미 진행 중인 생성은 끝까지 가지만 재생되지 않는다."""
    rows = db.scalars(select(Track).where(
        Track.user_id == user_id, Track.is_played.is_(False), Track.is_skipped.is_(False),
        Track.status.in_(("pending", "processing", "succeeded")))).all()
    for t in rows:
        t.is_skipped = True
    db.commit()
    return len(rows)
