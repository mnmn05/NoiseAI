"""
DB 스키마 (T1)

  핵심 3테이블   users / tracks / status_log
  신규 3테이블   seat_events (키오스크 자리 선택·퇴석) / feedback (손님 키워드 요청) / sales_hourly (시간대별 매출)

기존 DB(Render 등)에 이미 테이블이 있으면 create_all 은 새 컬럼을 추가하지 않는다.
그래서 db.ensure_columns() 가 서버 시작 때 빠진 컬럼을 ALTER TABLE 로 채운다. 새 컬럼에는 server_default 를 꼭 달 것.
"""
import secrets
from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
                        false, text)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_public_id() -> str:
    """가게 공개 링크용 ID. user_id 를 그대로 노출하지 않으려고 따로 만든다."""
    return secrets.token_urlsafe(8)


class User(Base):
    """점주 계정 + 매장 정보 (T5 프롬프트의 재료)"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    store_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)       # 타겟 성별
    age_group: Mapped[str | None] = mapped_column(String(20), nullable=True)    # 타겟 연령대
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)     # 업종 (카페/주점/음식점)
    mood: Mapped[str | None] = mapped_column(String(30), nullable=True)         # 원하는 분위기
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # ---- (신규) ----
    noise_strategy: Mapped[str] = mapped_column(String(10), default="stable", server_default=text("'stable'"))  # stable(안정형) / lively(활기형)
    total_seats: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))       # 좌석 수 (점유율 분모)
    public_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True, default=new_public_id)
    guest_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)   # '전체 재구성' 요청 키워드 (영문, 콤마)
    guest_keywords_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Track(Base):
    """생성된 음원 (= 재생 대기열)"""
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    prompt: Mapped[str] = mapped_column(Text)                                    # 생성에 쓴 프롬프트
    audio_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)   # 완성 후 채워짐
    is_played: Mapped[bool] = mapped_column(Boolean, default=False)              # 재생 여부
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending/processing/succeeded/failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    prediction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Replicate 작업 ID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ---- (신규) ----
    source: Mapped[str] = mapped_column(String(10), default="auto", server_default=text("'auto'"))  # auto / request / quiet
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))   # 클수록 먼저 재생 (손님 요청곡)
    is_skipped: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())  # 재구성으로 대기열에서 빠짐
    noise_level: Mapped[str | None] = mapped_column(String(10), nullable=True)   # 생성 시점 소음 구간 (히스테리시스 기준)
    situation: Mapped[str | None] = mapped_column(String(20), nullable=True)     # 3요소 판정 결과
    feedback_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StatusLog(Base):
    """클라이언트가 3초마다 보내는 소음 기록"""
    __tablename__ = "status_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    noise_db: Mapped[float] = mapped_column(Float)
    # 리포트 GROUP BY 용. 한국시간 기준 '2026-10-16T14' 형태. DB 종류와 상관없이 같은 SQL로 집계하려고 미리 계산해 저장한다.
    hour_bucket: Mapped[str] = mapped_column(String(13))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    zone_id: Mapped[str | None] = mapped_column(String(30), nullable=True)   # (신규) 층/구역. 없으면 매장 전체

    __table_args__ = (Index("ix_status_log_user_hour", "user_id", "hour_bucket"),)


class SeatEvent(Base):
    """(신규) 키오스크에서 자리 선택(occupy) / 퇴석(release) 이벤트"""
    __tablename__ = "seat_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    seat_id: Mapped[str] = mapped_column(String(30))
    event: Mapped[str] = mapped_column(String(10))                 # occupy / release
    party_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_seat_events_user_time", "user_id", "created_at"),)


class Feedback(Base):
    """(신규) 손님 요청. mode: add_one(1곡 추가) / rebuild(전체 재구성) / quiet('조용했으면' 버튼)"""
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    mode: Mapped[str] = mapped_column(String(10))
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)   # 영문 키워드, 콤마 구분
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_feedback_user_time", "user_id", "created_at"),)


class SalesHourly(Base):
    """(신규) 시간대별 매출. 같은 매장·같은 시간은 1행 (업로드하면 덮어씀)"""
    __tablename__ = "sales_hourly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    hour_bucket: Mapped[str] = mapped_column(String(13))          # 한국시간 '2026-11-16T14'
    sales_amount: Mapped[int] = mapped_column(Integer, default=0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(10), default="csv")   # csv / api
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (UniqueConstraint("user_id", "hour_bucket", name="uq_sales_user_hour"),)
