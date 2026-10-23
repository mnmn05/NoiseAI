"""DB 스키마 (T1) — 3개 핵심 테이블: users / tracks / status_log"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


class Track(Base):
    """생성된 음원"""
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


class StatusLog(Base):
    """클라이언트가 3초마다 보내는 소음 기록"""
    __tablename__ = "status_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    noise_db: Mapped[float] = mapped_column(Float)
    # 리포트 GROUP BY 용. 한국시간 기준 '2026-10-16T14' 형태. DB 종류와 상관없이 같은 SQL로 집계하려고 미리 계산해 저장한다.
    hour_bucket: Mapped[str] = mapped_column(String(13))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    __table_args__ = (Index("ix_status_log_user_hour", "user_id", "hour_bucket"),)
