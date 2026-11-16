"""
POS 매출 수집 (T8)

  POST /api/sales/upload?user_id=   POS 백오피스에서 내려받은 CSV 업로드 (multipart/form-data, 필드명 file)
  POST /api/sales                   JSON 으로 시간대별 매출 넣기 — 나중에 POS 제휴 API 가 생기면 이 주소로 보내면 됨
  GET  /api/sales?user_id=&date=    하루치 시간대별 매출

CSV 는 두 형태 모두 받는다.
  (1) 시간대별 합계:  시간, 매출, 주문수
  (2) 결제 건별 내역: 일시, 결제금액            (주문수 열이 없으면 행 개수를 주문수로 센다)
같은 시간(한국시간 기준 1시간)은 합쳐서 저장하고, 이미 있는 시간은 새 값으로 덮어쓴다 (같은 파일을 두 번 올려도 두 배가 되지 않음).
엑셀에서 저장한 한글 CSV(CP949)와 UTF-8 모두 읽는다.
"""
import csv
import datetime as dt
import io
import re

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import SalesHourly, User
from ..security import ensure_owner
from ..settings import KST

router = APIRouter(prefix="/api/sales", tags=["sales"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ERRORS_SHOWN = 20

DATETIME_HEADERS = {"hour", "datetime", "일시", "결제일시", "거래일시", "판매일시", "주문일시"}
DATE_HEADERS = {"date", "날짜", "일자", "영업일", "판매일"}
TIME_HEADERS = {"time", "시간", "시각", "시간대"}
AMOUNT_HEADERS = {"sales_amount", "amount", "sales", "매출", "매출액", "판매금액", "결제금액", "금액", "실매출", "합계"}
COUNT_HEADERS = {"order_count", "orders", "count", "주문수", "주문건수", "건수", "판매건수", "결제건수"}

_TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
                 "%Y-%m-%dT%H", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d %H", "%Y.%m.%d %H:%M:%S",
                 "%Y.%m.%d %H:%M", "%Y.%m.%d %H", "%Y%m%d%H%M%S", "%Y%m%d %H:%M")


class SalesRow(BaseModel):
    hour: str = Field(description="한국시간. '2026-11-16T14' 또는 '2026-11-16 14:30' 등")
    sales_amount: int = Field(ge=0)
    order_count: int = Field(default=0, ge=0)


class SalesIn(BaseModel):
    user_id: int
    rows: list[SalesRow] = Field(min_length=1, max_length=5000)


def parse_hour(value: str) -> str:
    """여러 날짜 형식 -> 한국시간 '%Y-%m-%dT%H'. 시간대가 붙은 ISO 문자열은 한국시간으로 바꾼다."""
    s = str(value).strip().replace("오전 ", "").strip()
    pm = "오후" in s
    s = s.replace("오후", "").strip()
    try:
        t = dt.datetime.fromisoformat(s)
        if t.tzinfo is not None:
            t = t.astimezone(KST)
    except ValueError:
        t = None
        for fmt in _TIME_FORMATS:
            try:
                t = dt.datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
        if t is None:
            raise ValueError(f"날짜/시간 형식을 알 수 없음: {value!r}")
    if pm and t.hour < 12:
        t = t.replace(hour=t.hour + 12)
    return t.strftime("%Y-%m-%dT%H")


def parse_int(value) -> int:
    s = re.sub(r"[,\s원₩]", "", str(value or ""))
    if s in ("", "-"):
        return 0
    f = float(s)
    if f < 0:
        raise ValueError("음수 금액")       # 환불 행은 POS 의 실매출 합계를 쓰도록 안내
    return int(round(f))


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise HTTPException(422, "파일 인코딩을 읽을 수 없습니다 (UTF-8 또는 CP949 CSV 로 저장해 주세요)")


def _pick(headers: list[str], names: set[str]) -> str | None:
    norm = {h: re.sub(r"\s+", "", h).lower() for h in headers}
    for h, n in norm.items():
        if n in {x.lower() for x in names}:
            return h
    return None


def aggregate_csv(text: str) -> tuple[dict[str, list[int]], list[str], int]:
    """CSV -> {hour_bucket: [매출, 주문수]}, 오류 목록, 읽은 행 수"""
    reader = csv.DictReader(io.StringIO(text))
    headers = [h for h in (reader.fieldnames or []) if h is not None]
    dt_col, d_col, t_col = _pick(headers, DATETIME_HEADERS), _pick(headers, DATE_HEADERS), _pick(headers, TIME_HEADERS)
    a_col, c_col = _pick(headers, AMOUNT_HEADERS), _pick(headers, COUNT_HEADERS)

    def when(row) -> str:
        if dt_col:
            return row.get(dt_col, "")
        if d_col and t_col:                       # 날짜 열 + 시간 열이 따로 있는 경우 ('2026-11-16' + '14' / '14:00')
            tm = (row.get(t_col) or "").strip()
            if re.fullmatch(r"\d{1,2}", tm):
                tm += ":00"
            return f"{(row.get(d_col) or '').strip()} {tm.split('~')[0].strip()}"
        return row.get(t_col or d_col, "")

    if not (dt_col or t_col) or not a_col:
        raise HTTPException(422, f"시간 열과 매출 열을 찾지 못했습니다. 첫 줄 제목 예: 시간,매출,주문수 (현재: {headers})")
    buckets: dict[str, list[int]] = {}
    errors: list[str] = []
    n = 0
    for line_no, row in enumerate(reader, start=2):
        if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
            continue   # 빈 줄
        n += 1
        try:
            hour = parse_hour(when(row))
            amount = parse_int(row.get(a_col))
            count = parse_int(row.get(c_col)) if c_col else 1
        except (ValueError, TypeError) as e:
            errors.append(f"{line_no}행: {e}")
            continue
        b = buckets.setdefault(hour, [0, 0])
        b[0] += amount
        b[1] += count
    return buckets, errors, n


def upsert(db: Session, user_id: int, buckets: dict[str, list[int]], source: str) -> tuple[int, int]:
    existing = {r.hour_bucket: r for r in db.scalars(select(SalesHourly).where(
        SalesHourly.user_id == user_id, SalesHourly.hour_bucket.in_(list(buckets)))).all()}
    inserted = updated = 0
    for hour, (amount, count) in buckets.items():
        row = existing.get(hour)
        if row:
            row.sales_amount, row.order_count, row.source = amount, count, source
            updated += 1
        else:
            db.add(SalesHourly(user_id=user_id, hour_bucket=hour, sales_amount=amount, order_count=count, source=source))
            inserted += 1
    db.commit()
    return inserted, updated


def _user(db: Session, user_id: int) -> User:
    if not db.get(User, user_id):
        raise HTTPException(404, "사용자를 찾을 수 없습니다")
    return db.get(User, user_id)


@router.post("/upload")
async def upload_csv(request: Request, user_id: int = Query(...), file: UploadFile = File(...),
                     db: Session = Depends(get_db)):
    ensure_owner(request, user_id)
    _user(db, user_id)
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "파일이 너무 큽니다 (최대 5MB)")
    if not raw.strip():
        raise HTTPException(422, "빈 파일입니다")
    buckets, errors, n = aggregate_csv(_decode(raw))
    if not buckets:
        raise HTTPException(422, {"message": "저장할 수 있는 행이 없습니다", "errors": errors[:MAX_ERRORS_SHOWN]})
    inserted, updated = upsert(db, user_id, buckets, "csv")
    return {"result": "success", "rows_read": n, "hours_saved": len(buckets), "inserted": inserted,
            "updated": updated, "error_count": len(errors), "errors": errors[:MAX_ERRORS_SHOWN],
            "hours": sorted(buckets)}


@router.post("")
def post_sales(data: SalesIn, request: Request, db: Session = Depends(get_db)):
    ensure_owner(request, data.user_id)
    _user(db, data.user_id)
    buckets: dict[str, list[int]] = {}
    for r in data.rows:
        try:
            hour = parse_hour(r.hour)
        except ValueError as e:
            raise HTTPException(422, str(e))
        b = buckets.setdefault(hour, [0, 0])
        b[0] += r.sales_amount
        b[1] += r.order_count
    inserted, updated = upsert(db, data.user_id, buckets, "api")
    return {"result": "success", "hours_saved": len(buckets), "inserted": inserted, "updated": updated}


@router.get("")
def get_sales(user_id: int, request: Request, date: dt.date | None = None, db: Session = Depends(get_db)):
    ensure_owner(request, user_id)
    _user(db, user_id)
    day = (date or dt.datetime.now(KST).date()).isoformat()
    rows = db.scalars(select(SalesHourly).where(SalesHourly.user_id == user_id,
                                                SalesHourly.hour_bucket.like(f"{day}T%"))
                      .order_by(SalesHourly.hour_bucket)).all()
    return {"user_id": user_id, "date": day,
            "hours": [{"hour": int(r.hour_bucket[-2:]), "label": r.hour_bucket, "sales_amount": r.sales_amount,
                       "order_count": r.order_count, "source": r.source} for r in rows],
            "total_sales": sum(r.sales_amount for r in rows), "total_orders": sum(r.order_count for r in rows)}
