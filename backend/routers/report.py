"""시간대별 소음 리포트 (T8) — Status_Log 를 시간 단위로 GROUP BY 해서 평균 dB 추이를 준다."""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import StatusLog, User
from ..settings import KST

router = APIRouter(prefix="/api", tags=["report"])


@router.get("/report")
def get_report(
    user_id: int,
    date: dt.date | None = Query(None, description="YYYY-MM-DD (한국시간). 비우면 오늘"),
    start_hour: int = Query(0, ge=0, le=23),
    end_hour: int = Query(23, ge=0, le=23),
    fill_empty: bool = Query(True, description="데이터가 없는 시간도 avg_db=null 로 포함 (차트 X축 유지용)"),
    db: Session = Depends(get_db),
):
    if start_hour > end_hour:
        raise HTTPException(422, "start_hour 는 end_hour 보다 클 수 없습니다")
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

    hours = []
    for h in range(start_hour, end_hour + 1):
        bucket = f"{day.isoformat()}T{h:02d}"
        r = by_bucket.get(bucket)
        if r is None:
            if fill_empty:
                hours.append({"hour": h, "label": bucket, "avg_db": None, "max_db": None, "min_db": None, "samples": 0})
            continue
        hours.append({
            "hour": h, "label": bucket,
            "avg_db": round(float(r[1]), 1), "max_db": round(float(r[2]), 1),
            "min_db": round(float(r[3]), 1), "samples": int(r[4]),
        })

    total = db.execute(
        select(func.avg(StatusLog.noise_db), func.max(StatusLog.noise_db), func.count(StatusLog.id)).where(*base)
    ).one()
    overall = {
        "avg_db": None if total[0] is None else round(float(total[0]), 1),
        "max_db": None if total[1] is None else round(float(total[1]), 1),
        "samples": int(total[2]),
    }
    return {"user_id": user_id, "date": day.isoformat(), "start_hour": start_hour, "end_hour": end_hour,
            "hours": hours, "overall": overall}
