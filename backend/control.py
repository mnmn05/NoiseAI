"""
제어 엔진
  T1  상태 저장소 + 백그라운드 루프
  T4  마이크 dB 입력 (값이 안 들어오면 더미 값으로 자동 대체)
  T5  소음 기반 복합 제어 규칙 (히스테리시스 / 중앙값 필터 / 지수평활 / 단계적 페이드)

※ 카메라 기반 인원수 감지는 법적 문제로 제외되었다.
   혼잡도는 마이크로 측정한 소음(dB)만으로 판정한다.
"""
import random
import statistics
import threading
import time
from datetime import datetime

from . import config

lock = threading.Lock()

# /api/status 로 그대로 나가는 값. 필드명은 팀원들과의 계약이라 함부로 바꾸지 말 것.
# (person_count 필드는 카메라 제외로 삭제됨 - 대시보드에서 더 이상 사용하지 않도록 공지 필요)
store_status = {
    "noise_level_db": 45.0,
    "crowd_level": "normal",          # quiet / normal / busy
    "current_volume": 40,             # 0~100
    "current_track": "standard_bgm_01.mp3",
    "auto_mode": True,
    "noise_source": "dummy",          # mic / dummy
    "updated_at": None,
}

# 내부 전용 값 (API로 나가지 않음)
_raw_noise_db = 45.0
_last_mic_time = None
_target_volume = 40
_noise_samples = []


# ------------------------------------------------------------ 입력 (T1 / T4 / T5)
def set_noise(db: float):
    """마이크 페이지가 보낸 소음(dB) 저장 (T4)"""
    global _raw_noise_db, _last_mic_time
    with lock:
        _raw_noise_db = db
        _last_mic_time = time.monotonic()


def set_mode(auto_mode: bool, manual_volume=None):
    """점주용 자동/수동 전환 (T5)"""
    global _target_volume
    with lock:
        store_status["auto_mode"] = auto_mode
        if not auto_mode and manual_volume is not None:
            store_status["current_volume"] = manual_volume
            _target_volume = manual_volume


def get_status() -> dict:
    with lock:
        return dict(store_status)


# ------------------------------------------------------------ 제어 로직
def _read_noise() -> float:
    """현재 소음값 결정. (반드시 lock을 잡은 상태에서 호출)"""
    global _raw_noise_db
    # 마이크 값이 최근에 들어왔으면 그 값을 사용
    if _last_mic_time is not None and time.monotonic() - _last_mic_time <= config.MIC_TIMEOUT_SEC:
        store_status["noise_source"] = "mic"
        return _raw_noise_db
    # 아니면 더미(랜덤워크) — 마이크 없이도 팀원들이 개발/시연 가능
    store_status["noise_source"] = "dummy"
    step = random.gauss(0, config.DUMMY_DB_STEP)
    _raw_noise_db = min(max(_raw_noise_db + step, config.DUMMY_DB_MIN), config.DUMMY_DB_MAX)
    return _raw_noise_db


def decide_crowd_level(db: float, prev: str) -> str:
    """소음(dB) 기준 혼잡도 판정. 히스테리시스: 이전 상태(prev)를 알아야 경계값에서 안 흔들린다."""
    th = config.TH
    if prev == "busy":
        return "normal" if db <= th["busy_out"]["db"] else "busy"
    if prev == "quiet":
        return "normal" if db >= th["quiet_out"]["db"] else "quiet"
    if db >= th["busy_in"]["db"]:
        return "busy"
    if db <= th["quiet_in"]["db"]:
        return "quiet"
    return "normal"


def control_tick() -> dict:
    """config.TICK_SEC 마다 한 번 실행되는 제어 한 스텝. 스냅샷(dict)을 반환."""
    global _target_volume
    with lock:
        raw = _read_noise()

        # 1) 순간 소음 제거(중앙값) -> 지수 평활
        _noise_samples.append(raw)
        del _noise_samples[:-config.NOISE_WINDOW]
        filtered = statistics.median(_noise_samples)
        smoothed = (config.SMOOTHING_ALPHA * filtered
                    + (1 - config.SMOOTHING_ALPHA) * store_status["noise_level_db"])
        store_status["noise_level_db"] = round(smoothed, 1)

        # 2) 혼잡도 판정 (히스테리시스)
        prev = store_status["crowd_level"]
        level = decide_crowd_level(store_status["noise_level_db"], prev)
        store_status["crowd_level"] = level

        # 3) 자동 모드일 때만 목표 볼륨/트랙 갱신 + 단계적 페이드
        if store_status["auto_mode"]:
            preset = config.PLAYLIST_POOL[level]
            _target_volume = preset["volume"]
            if level != prev:   # 상태가 바뀔 때만 곡 교체 (곡이 계속 끊기는 것 방지)
                store_status["current_track"] = random.choice(preset["tracks"])
            cur = store_status["current_volume"]
            if cur != _target_volume:
                step = min(config.FADE_STEP, abs(_target_volume - cur))
                store_status["current_volume"] = cur + step if _target_volume > cur else cur - step

        store_status["updated_at"] = datetime.now(config.KST).isoformat(timespec="seconds")
        return dict(store_status)


def background_loop(stop_event: threading.Event, on_tick=None):
    """백그라운드에서 TICK_SEC 마다 제어 실행. on_tick(snapshot)은 이력 저장 등에 사용(T8)."""
    while not stop_event.is_set():
        try:
            snapshot = control_tick()
            if on_tick:
                on_tick(snapshot)
        except Exception as e:  # 한 번 실패했다고 제어 루프 전체가 죽으면 안 됨
            print("[control] tick error:", e)
        stop_event.wait(config.TICK_SEC)