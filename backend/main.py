"""
FastAPI 엔드포인트만 담당 (T1). 실제 로직은 control.py / database.py 에 있다.

실행 (항상 프로젝트 루트에서):
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import control
from . import database            # (기존) SQLite 이력 — 새 Status_Log/리포트로 대체되면 삭제해도 됨
from . import db as sqldb                 # (신규) SQLAlchemy — users / tracks / status_log
from .routers import report, status_log, tracks, users
from .settings import settings


# ------------------------------------------------------------ 요청 스키마
class PersonUpdate(BaseModel):
    person_count: int = Field(ge=0, le=500)


class NoiseUpdate(BaseModel):
    noise_db: float = Field(ge=0.0, le=140.0)


class ModeUpdate(BaseModel):
    auto_mode: bool
    manual_volume: int | None = Field(default=None, ge=0, le=100)


# ------------------------------------------------------------ 앱
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버가 시작될 때 딱 한 번 실행 (--reload 로 여러 번 로드돼도 스레드 중복 방지)
    on_tick = None
    database.init_db()
    sqldb.init_db()                       # users / tracks / status_log 테이블 생성 (이미 있으면 그대로 둠)
    sqldb.recover_stale_tracks()          # 재시작으로 끊긴 '생성 중' 곡을 실패 처리
    on_tick = database.save_snapshot   # 3초마다 스냅샷을 DB에 저장 (T9)
    stop_event = threading.Event()
    thread = threading.Thread(target=control.background_loop, args=(stop_event, on_tick), daemon=True)
    thread.start()

    yield  # 이 위: 서버 시작 시점 / 이 아래: 서버 종료 시점

    stop_event.set()


app = FastAPI(title="NoiseAI Backend", lifespan=lifespan)

# 대시보드/마이크 페이지가 다른 주소에서 호출해도 되도록 허용 (개발용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 마이크 측정 페이지: /static/mic.html  (Render가 HTTPS를 제공하므로 폰에서 마이크 권한이 뜸)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# 생성된 음원 파일: /media/track_<id>.mp3  (T8)
settings.media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")

# 신규 라우터 (T1 users/status-log, T5·T8 tracks, T8 report)
app.include_router(users.router)
app.include_router(status_log.router)
app.include_router(tracks.router)
app.include_router(report.router)


# ------------------------------------------------------------ API
@app.get("/")
def read_root():
    return {"message": "NoiseAI Backend Server is Running!"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/update-person")          # 윤지우(비전)가 호출
def update_person(data: PersonUpdate):
    control.set_person(data.person_count)
    return {"result": "success", "person_count": data.person_count}


@app.post("/api/update-noise")           # 마이크 페이지가 호출 (T4)
def update_noise(data: NoiseUpdate):
    control.set_noise(data.noise_db)
    return {"result": "success", "noise_db": data.noise_db}


@app.get("/api/status")                  # 변정빈(대시보드), 윤지우(플레이어)가 호출
def get_status():
    return control.get_status()


@app.post("/api/mode")                   # 점주용 자동/수동 전환 (T6)
def set_mode(data: ModeUpdate):
    control.set_mode(data.auto_mode, data.manual_volume)
    return {"result": "success", "auto_mode": data.auto_mode}


@app.get("/api/history")                 # 그래프용 원본 이력 (T9)
def get_history(limit: int = Query(200, ge=1, le=5000)):
    return database.get_history(limit)


@app.get("/api/report/hourly")           # 시간대별 리포트 (T9)
def get_hourly_report(hours: int = Query(24, ge=1, le=168)):
    return database.get_hourly_report(hours)
