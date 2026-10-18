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

from . import control
from . import database
from .schemas import (
    HistoryItem,
    HourlyReportItem,
    ModeUpdate,
    ModeUpdateResponse,
    NoiseUpdate,
    NoiseUpdateResponse,
    StatusResponse,
)


# ------------------------------------------------------------ 앱
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버가 시작될 때 딱 한 번 실행 (--reload 로 여러 번 로드돼도 스레드 중복 방지)
    database.init_db()
    on_tick = database.save_snapshot   # 3초마다 스냅샷을 DB에 저장 (T8)
    stop_event = threading.Event()
    thread = threading.Thread(target=control.background_loop, args=(stop_event, on_tick), daemon=True)
    thread.start()

    yield  # 이 위: 서버 시작 시점 / 이 아래: 서버 종료 시점

    stop_event.set()


app = FastAPI(title="NoiseAI Backend", lifespan=lifespan)

# 대시보드/마이크 페이지가 다른 주소에서 호출해도 되도록 허용 (개발용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 마이크 측정 페이지: /static/mic.html  (Render가 HTTPS를 제공하므로 폰에서 마이크 권한이 뜸)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


# ------------------------------------------------------------ API
# ※ POST /api/update-person 은 카메라 인원수 감지 제외로 삭제됨


@app.get("/")
def read_root():
    return {"message": "NoiseAI Backend Server is Running!"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/update-noise", response_model=NoiseUpdateResponse, tags=["소음"])  # 마이크 페이지가 호출 (T4)
def update_noise(data: NoiseUpdate):
    control.set_noise(data.noise_db, voice_ratio)
    return {"result": "success", "noise_db": data.noise_db, "voice_ratio": data.voice_ratio}


@app.get("/api/status", response_model=StatusResponse, tags=["상태"])  # 변정빈(대시보드), 윤지우(플레이어)가 호출
def get_status():
    return control.get_status()


@app.post("/api/mode", response_model=ModeUpdateResponse, tags=["상태"])  # 점주용 자동/수동 전환 (T5)
def set_mode(data: ModeUpdate):
    control.set_mode(data.auto_mode, data.manual_volume)
    return {"result": "success", "auto_mode": data.auto_mode}


@app.get("/api/history", response_model=list[HistoryItem], tags=["리포트"])  # 그래프용 원본 이력 (T8)
def get_history(limit: int = Query(200, ge=1, le=5000)):
    return database.get_history(limit)


@app.get("/api/report/hourly", response_model=list[HourlyReportItem], tags=["리포트"])  # 시간대별 리포트 (T8)
def get_hourly_report(hours: int = Query(24, ge=1, le=168)):
    return database.get_hourly_report(hours)