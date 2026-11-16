"""
시간대별 리포트 (T8) — Status_Log 를 시간 단위로 GROUP BY 한 평균 dB 에 시간대별 매출·재생 이력을 붙여 준다.

  GET /api/report?user_id=&date=      차트 1장(막대: 매출 / 선: 평균 dB)에 바로 쓰는 형태
    hours[]: avg_db / max_db / min_db / samples / crowd_level / sales_amount / order_count / plays / requests
    summary: 가장 붐빈 시간, 가장 한산한 시간, 매출 최고 시간, 소음-매출 상관계수, 점주용 한 줄 제안
"""
import datetime as dt
import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Feedback, SalesHourly, StatusLog, Track, User
from ..security import ensure_owner
from ..services import aware
from ..settings import KST
from .seats import LABEL_KO, crowd_from_db

router = APIRouter(prefix="/api", tags=["report"])


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy), 2)


def _kst_hour_counts(rows, day: dt.date) -> dict[int, int]:
    out: dict[int, int] = {}
    for t in rows:
        t = aware(t)
        if t is None:
            continue
        k = t.astimezone(KST)
        if k.date() == day:
            out[k.hour] = out.get(k.hour, 0) + 1
    return out


def _suggestion(hours: list[dict]) -> str | None:
    with_data = [h for h in hours if h["avg_db"] is not None]
    if not with_data:
        return None
    quiet = min(with_data, key=lambda h: h["avg_db"])
    busy = max(with_data, key=lambda h: h["avg_db"])
    if quiet["hour"] == busy["hour"]:
        return None
    msg = f"{busy['hour']}시가 가장 붐볐고 {quiet['hour']}시가 가장 한산했어요."
    if quiet["sales_amount"] is not None and busy["sales_amount"] is not None and busy["sales_amount"] > 0:
        msg += f" {quiet['hour']}시 매출은 {busy['hour']}시의 {round(100 * quiet['sales_amount'] / busy['sales_amount'])}% 예요."
    return msg + f" {quiet['hour']}시에 할인·이벤트를 해 보면 빈 시간대를 채울 수 있어요."


@router.get("/report")
def get_report(
    request: Request,
    user_id: int,
    date: dt.date | None = Query(None, description="YYYY-MM-DD (한국시간). 비우면 오늘"),
    start_hour: int = Query(0, ge=0, le=23),
    end_hour: int = Query(23, ge=0, le=23),
    fill_empty: bool = Query(True, description="데이터가 없는 시간도 avg_db=null 로 포함 (차트 X축 유지용)"),
    db: Session = Depends(get_db),
):
    if start_hour > end_hour:
        raise HTTPException(422, "start_hour 는 end_hour 보다 클 수 없습니다")
    ensure_owner(request, user_id)
    if not db.get(User, user_id):
        raise HTTPException(404, "사용자를 찾을 수 없습니다")

    day = date or dt.datetime.now(KST).date()
    lo = f"{day.isoformat()}T{start_hour:02d}"
    hi = f"{day.isoformat()}T{end_hour:02d}"
    base = (StatusLog.user_id == user_id, StatusLog.hour_bucket >= lo, StatusLog.hour_bucket <= hi)

    rows = db.execute(
        select(
            StatusLog.hour_bucket,
            func.avg(StatusLog.noise_db),
            func.max(StatusLog.noise_db),
            func.min(StatusLog.noise_db),
            func.count(StatusLog.id),
        ).where(*base).group_by(StatusLog.hour_bucket).order_by(StatusLog.hour_bucket)
    ).all()
    by_bucket = {r[0]: r for r in rows}

    sales = {s.hour_bucket: s for s in db.scalars(select(SalesHourly).where(
        SalesHourly.user_id == user_id, SalesHourly.hour_bucket >= lo, SalesHourly.hour_bucket <= hi)).all()}

    # 재생/요청 이력: 하루 전후로 넉넉히 가져와서 한국시간으로 나눈다 (SQLite 는 시간대 저장을 안 해서 SQL 로 자르기 어려움)
    lo_utc = dt.datetime.combine(day, dt.time(0), KST) - dt.timedelta(hours=1)
    hi_utc = dt.datetime.combine(day, dt.time(23, 59, 59), KST) + dt.timedelta(hours=1)
    plays = _kst_hour_counts(db.scalars(select(Track.played_at).where(
        Track.user_id == user_id, Track.played_at.is_not(None),
        Track.played_at >= lo_utc.astimezone(dt.timezone.utc), Track.played_at <= hi_utc.astimezone(dt.timezone.utc))).all(), day)
    reqs = _kst_hour_counts(db.scalars(select(Feedback.created_at).where(
        Feedback.user_id == user_id,
        Feedback.created_at >= lo_utc.astimezone(dt.timezone.utc), Feedback.created_at <= hi_utc.astimezone(dt.timezone.utc))).all(), day)

    hours = []
    for h in range(start_hour, end_hour + 1):
        bucket = f"{day.isoformat()}T{h:02d}"
        r, s = by_bucket.get(bucket), sales.get(bucket)
        if r is None and s is None and not fill_empty:
            continue
        avg = None if r is None else round(float(r[1]), 1)
        level = crowd_from_db(avg)
        hours.append({
            "hour": h, "label": bucket,
            "avg_db": avg,
            "max_db": None if r is None else round(float(r[2]), 1),
            "min_db": None if r is None else round(float(r[3]), 1),
            "samples": 0 if r is None else int(r[4]),
            "crowd_level": level, "crowd_label": LABEL_KO[level],
            "sales_amount": None if s is None else s.sales_amount,
            "order_count": None if s is None else s.order_count,
            "plays": plays.get(h, 0),
            "requests": reqs.get(h, 0),
        })

    total = db.execute(
        select(func.avg(StatusLog.noise_db), func.max(StatusLog.noise_db), func.count(StatusLog.id)).where(*base)
    ).one()
    overall = {
        "avg_db": None if total[0] is None else round(float(total[0]), 1),
        "max_db": None if total[1] is None else round(float(total[1]), 1),
        "samples": int(total[2]),
        "total_sales": sum(s.sales_amount for s in sales.values()) if sales else None,
        "total_orders": sum(s.order_count for s in sales.values()) if sales else None,
    }

    with_db = [h for h in hours if h["avg_db"] is not None]
    with_sales = [h for h in hours if h["sales_amount"] is not None]
    both = [h for h in with_db if h["sales_amount"] is not None]
    summary = {
        "busiest_hour": max(with_db, key=lambda h: h["avg_db"])["hour"] if with_db else None,
        "quietest_hour": min(with_db, key=lambda h: h["avg_db"])["hour"] if with_db else None,
        "peak_sales_hour": max(with_sales, key=lambda h: h["sales_amount"])["hour"] if with_sales else None,
        "noise_sales_correlation": pearson([h["avg_db"] for h in both], [float(h["sales_amount"]) for h in both]),
        "correlation_hours": len(both),
        "suggestion": _suggestion(hours),
    }
    return {"user_id": user_id, "date": day.isoformat(), "start_hour": start_hour, "end_hour": end_hour,
            "hours": hours, "overall": overall, "summary": summary}
