"""
NoiseAI - 팀원 B(김민경) 백엔드 뼈대
지금 단계: 더미 모드(임의 dB 생성)로 API 구조와 제어 로직만 먼저 완성.
나중에 T4(실제 마이크 dB)와 T9(이력 저장)는 여기에 추가로 얹으면 됨.

실행:
    uvicorn main:app --host 0.0.0.0 --port 8000
"""
from contextlib import asynccontextmanager
import random
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------- 설정값
TICK_SEC = 3.0        # 계획서 요구사항: 연산 주기 3초

# 혼잡도 판정 임계치 (히스테리시스: 진입/해제 값을 다르게 둬서 경계에서 안 흔들리게 함)
TH = {
    "busy_in":  {"person": 10, "db": 70.0},
    "busy_out": {"person": 8,  "db": 66.0},
    "quiet_in": {"person": 3,  "db": 50.0},
    "quiet_out": {"person": 5, "db": 55.0},
}

# 분위기별 볼륨/트랙 프리셋 (윤지우 씨가 Suno로 만들 음원 풀 이름과 맞춰야 함)
PLAYLIST_POOL = {
    "busy":   {"volume": 25, "track": "calm_ambient_01.mp3"},
    "normal": {"volume": 40, "track": "standard_bgm_01.mp3"},
    "quiet":  {"volume": 60, "track": "lounge_upbeat_01.mp3"},
}

# ---------------------------------------------------------------- 공유 상태
_lock = threading.Lock()

store_status = {
    "person_count": 0,
    "noise_level_db": 45.0,
    "crowd_level": "normal",       # quiet / normal / busy
    "current_volume": 40,
    "current_track": "standard_bgm_01.mp3",
    "auto_mode": True,
}


class PersonUpdate(BaseModel):
    person_count: int = Field(ge=0, le=500)


class NoiseUpdate(BaseModel):
    noise_db: float = Field(ge=0.0, le=140.0)


# ---------------------------------------------------------------- 제어 로직
def decide_crowd_level(person: int, db: float, prev: str) -> str:
    """히스테리시스 적용: 이전 상태를 알아야 경계값에서 안 흔들림."""
    if prev == "busy":
        if person <= TH["busy_out"]["person"] and db <= TH["busy_out"]["db"]:
            return "normal"
        return "busy"
    if prev == "quiet":
        if person >= TH["quiet_out"]["person"] or db >= TH["quiet_out"]["db"]:
            return "normal"
        return "quiet"
    if person >= TH["busy_in"]["person"] and db >= TH["busy_in"]["db"]:
        return "busy"
    if person <= TH["quiet_in"]["person"] and db <= TH["quiet_in"]["db"]:
        return "quiet"
    return "normal"


def control_tick():
    """3초마다 한 번 실행되는 제어 로직 한 스텝."""
    with _lock:
        # TODO(T4): 지금은 임의 값. 실제 마이크 dB로 교체 예정.
        store_status["noise_level_db"] = round(random.uniform(40.0, 85.0), 1)

        level = decide_crowd_level(
            store_status["person_count"],
            store_status["noise_level_db"],
            store_status["crowd_level"],
        )
        store_status["crowd_level"] = level

        if store_status["auto_mode"]:
            preset = PLAYLIST_POOL[level]
            store_status["current_volume"] = preset["volume"]
            store_status["current_track"] = preset["track"]

        # TODO(T9): 여기서 SQLite에 스냅샷 저장 예정.


def background_control_loop(stop_event: threading.Event):
    while not stop_event.is_set():
        control_tick()
        stop_event.wait(TICK_SEC)


# ---------------------------------------------------------------- 앱 & lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버가 시작될 때 딱 한 번 실행 (--reload로 여러 번 로드돼도 스레드 중복 방지)
    stop_event = threading.Event()
    thread = threading.Thread(target=background_control_loop, args=(stop_event,), daemon=True)
    thread.start()

    yield  # 이 위: 서버 시작 시점 / 이 아래: 서버 종료 시점

    stop_event.set()  # 서버 꺼질 때 백그라운드 스레드 정리


app = FastAPI(title="NoiseAI Backend", lifespan=lifespan)

# CORS: 대시보드(변정빈)와 마이크 페이지가 다른 origin에서 호출하므로 필수
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 개발용. 나중에 실제 주소로 좁혀도 됨
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- API
@app.post("/api/update-person")   # 윤지우(비전)가 호출
def update_person(data: PersonUpdate):
    with _lock:
        store_status["person_count"] = data.person_count
    return {"result": "success", "person_count": data.person_count}


@app.post("/api/update-noise")    # 마이크 페이지가 호출 (T4에서 연결)
def update_noise(data: NoiseUpdate):
    with _lock:
        store_status["noise_level_db"] = data.noise_db
    return {"result": "success", "noise_db": data.noise_db}


@app.get("/api/status")           # 변정빈(대시보드), 윤지우(플레이어)가 호출
def get_status():
    with _lock:
        return dict(store_status)


@app.get("/")
def read_root():
    return {"message": "NoiseAI Backend Server is Running!"}