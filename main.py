import random
import threading
import time
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# 매장 상태 관리 데이터 (DB 대용 메모리)
store_status = {
    "person_count": 0,       # 팀원 A(비전)가 업데이트할 인원수
    "noise_level_db": 45.0,  # 가상의 소음 데시벨 (마이크 대신 테스트용)
    "current_volume": 50,    # 최종 제어된 볼륨
    "current_track": "lounge_default.mp3"
}

class StatusUpdate(BaseModel):
    person_count: int

# 1. 팀원 A가 인원수를 보낼 때 받는 API
@app.post("/api/update-person")
def update_person(data: StatusUpdate):
    store_status["person_count"] = data.person_count
    return {"result": "success", "current_person": store_status["person_count"]}

# 2. 대시보드(팀원 C)가 전체 상태를 가져가는 API
@app.get("/api/status")
def get_status():
    return store_status

# 3. [팀원 B의 핵심 제어 로직] 가상의 소음과 인원수를 바탕으로 볼륨 자동 조절
def background_control_loop():
    while True:
        # 테스트를 위해 임의의 소음(dB) 수치 생성 (실제 마이크 대신 가상 시뮬레이션)
        # 나중에 원하시면 슬라이더나 수동 입력으로 바꿀 수 있습니다.
        simulated_db = round(random.uniform(40.0, 85.0), 1)
        store_status["noise_level_db"] = simulated_db
        
        person = store_status["person_count"]
        
        # --- 복합 제어 규칙 (Rule-based Engine) ---
        if person >= 10 and simulated_db > 70.0:
            store_status["current_volume"] = 25  # 사람이 많고 시끄러우면 볼륨 낮춤
            store_status["current_track"] = "calm_ambient_01.mp3"
        elif person <= 3:
            store_status["current_volume"] = 60  # 한가하면 적당한 볼륨
            store_status["current_track"] = "lounge_upbeat_02.mp3"
        else:
            store_status["current_volume"] = 40  # 기본 상태
            store_status["current_track"] = "standard_bgm.mp3"
            
        time.sleep(3) # 3초마다 상태 갱신

# 백그라운드에서 제어 루프 실행
threading.Thread(target=background_control_loop, daemon=True).start()


@app.get("/")
def read_root():
    return {"message": "NoiseAI Backend Server is Running!"}