"""DB 연결 (T1) — SQLAlchemy 2.x. DATABASE_URL 만 바꾸면 SQLite / PostgreSQL / MySQL 어디든 동작."""
from sqlalchemy import create_engine, inspect, text, update
from sqlalchemy.orm import DeclarativeBase, sessionmaker

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
    ensure_columns()


def ensure_columns() -> list[str]:
    """이미 만들어진 테이블에 모델에는 있는데 DB 에는 없는 컬럼을 ALTER TABLE 로 추가한다.
    (create_all 은 새 테이블만 만들고 기존 테이블은 건드리지 않기 때문. Render 에 이미 배포된 DB 대응용)
    추가한 컬럼 이름 목록을 돌려준다."""
    from . import models
    added = []
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(engine.dialect)}'
                if col.server_default is not None:
                    arg = col.server_default.arg
                    default_sql = arg.text if hasattr(arg, "text") else str(arg.compile(dialect=engine.dialect))
                    ddl += f" DEFAULT {default_sql}"
                conn.execute(text(ddl))
                added.append(f"{table.name}.{col.name}")
        # 예전에 가입한 점주는 공개 링크 ID 가 없으니 채워 준다
        if "users.public_id" in added or "users" in existing_tables:
            rows = conn.execute(text("SELECT id FROM users WHERE public_id IS NULL")).fetchall()
            for (uid,) in rows:
                conn.execute(text("UPDATE users SET public_id = :p WHERE id = :i"),
                             {"p": models.new_public_id(), "i": uid})
    return added


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
