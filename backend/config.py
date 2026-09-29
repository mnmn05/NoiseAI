"""
튜닝용 상수 모음 (T1)
발표 직전에 매장 환경에 맞춰 조정할 때, 코드는 건드리지 말고 여기 숫자만 바꾼다.
"""
from datetime import timedelta, timezone
from pathlib import Path

# Render 서버는 UTC로 돌아가므로, 기록 시각은 한국시간(KST)으로 고정한다.
KST = timezone(timedelta(hours=9))

# ---- 제어 주기 ----
TICK_SEC = 3.0            # 계획서 요구사항: 연산 주기 3초

# ---- 소음 처리 (T4/T6) ----
MIC_TIMEOUT_SEC = 10.0    # 이 시간 동안 마이크 값이 없으면 더미 값으로 대체
NOISE_WINDOW = 5          # 순간 소음(그릇 깨짐 등) 제거용 중앙값 필터 크기
SMOOTHING_ALPHA = 0.4     # 지수 평활 계수 (0에 가까울수록 둔감, 1이면 평활 없음)

# ---- 더미 소음 (마이크 미연결 시 팀원 테스트용) ----
DUMMY_DB_MIN = 40.0
DUMMY_DB_MAX = 85.0
DUMMY_DB_STEP = 3.0       # 틱마다 흔들리는 폭 (랜덤워크)

# ---- 볼륨 페이드 (T6) ----
FADE_STEP = 8             # 1틱에 바꿀 수 있는 최대 볼륨 변화량 (팝핑 방지)

# ---- 혼잡도 임계치 (T6) ----
# 히스테리시스: 들어갈 때(in)와 빠져나올 때(out) 기준을 다르게 둬서 경계에서 안 흔들리게 한다.
TH = {
    "busy_in":   {"person": 10, "db": 70.0},   # 인원 >= 10 그리고 dB >= 70 이면 혼잡 진입
    "busy_out":  {"person": 8,  "db": 66.0},   # 인원 <= 8  그리고 dB <= 66 이어야 혼잡 해제
    "quiet_in":  {"person": 3,  "db": 50.0},   # 인원 <= 3  그리고 dB <= 50 이면 여유 진입
    "quiet_out": {"person": 5,  "db": 55.0},   # 인원 >= 5  또는  dB >= 55 이면 여유 해제
}

# ---- 분위기별 볼륨 / 음원 풀 (Suno 음원 파일명과 맞출 것) ----
PLAYLIST_POOL = {
    "busy":   {"volume": 25, "tracks": ["calm_ambient_01.mp3", "calm_ambient_02.mp3"]},
    "normal": {"volume": 40, "tracks": ["standard_bgm_01.mp3", "standard_bgm_02.mp3"]},
    "quiet":  {"volume": 60, "tracks": ["lounge_upbeat_01.mp3", "lounge_upbeat_02.mp3"]},
}

# ---- 이력 DB (T9) ----
DB_PATH = Path(__file__).with_name("store_history.db")
