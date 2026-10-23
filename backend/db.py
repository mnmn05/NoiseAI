"""DB 연결 (T1) — SQLAlchemy 2.x. DATABASE_URL 만 바꾸면 SQLite / PostgreSQL / MySQL 어디든 동작."""
from sqlalchemy import update
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine

from .settings import settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    kwargs = {"pool_pre_ping": True}          # 오래 놀던 연결이 끊겨 있어도 자동 복구
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def configure(url: str):
    """엔진 교체 (테스트용)"""
    global engine, SessionLocal
    engine.dispose()
    engine = _make_engine(url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI 의존성: 요청마다 세션을 열고 끝나면 닫는다."""
    with SessionLocal() as session:
        yield session


def init_db():
    from . import models  # noqa: F401  (모델을 import 해야 테이블이 등록됨)
    Base.metadata.create_all(engine)


def recover_stale_tracks() -> int:
    """서버가 재시작되면 생성 중이던 작업(BackgroundTask)이 사라진다. 그 곡들을 실패 처리해서 영구 '생성 중'을 막는다."""
    from .models import Track, utcnow
    with SessionLocal() as s:
        res = s.execute(
            update(Track)
            .where(Track.status.in_(("pending", "processing")))
            .values(status="failed", error="서버가 재시작되어 생성이 중단됨", completed_at=utcnow())
        )
        s.commit()
        return res.rowcount or 0
