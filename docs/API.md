# NoiseAI 백엔드 API 명세

- 서버 주소: `https://<서비스명>.onrender.com` (로컬: `http://localhost:8000`)
- 자동 문서/테스트 화면: `<서버 주소>/docs`
- 모든 요청/응답은 JSON, 시각은 **한국시간(+09:00)** ISO 형식
- 필드명은 팀 간 계약입니다. 바꿔야 하면 팀 채팅에 먼저 공지하세요.
- 잘못된 값(범위 밖, 타입 오류)은 **422** 로 응답합니다.

## 한눈에 보기

| Method | Path | 호출자 | 설명 |
| --- | --- | --- | --- |
| POST | `/api/update-person` | 윤지우 (비전) | 인원수 전송 |
| POST | `/api/update-noise` | 마이크 페이지 (mic.html) | 소음 dB 전송 |
| GET | `/api/status` | 변정빈 (대시보드), 윤지우 (플레이어) | 현재 상태 전체 |
| POST | `/api/mode` | 변정빈 (대시보드) | 자동/수동 전환 |
| GET | `/api/history` | 변정빈 (그래프) | 최근 이력 (오래된 순) |
| GET | `/api/report/hourly` | 변정빈 (리포트) | 시간대별 집계 |
| GET | `/health` | Render | 서버 상태 확인 |

마이크 측정 페이지: `<서버 주소>/static/mic.html`

---

## POST `/api/update-person`

윤지우(비전) → 서버. **2초마다** 보내는 것을 권장합니다.

```json
// 요청
{"person_count": 12}          // 0 ~ 500 정수
// 응답
{"result": "success", "person_count": 12}
```

## POST `/api/update-noise`

마이크 페이지 → 서버. 1초마다 자동 전송됩니다. **10초 이상 값이 안 들어오면 서버가 더미 값으로 자동 전환**합니다.

```json
// 요청
{"noise_db": 68.4}            // 0 ~ 140 실수 (기기 보정 후의 상대값)
// 응답
{"result": "success", "noise_db": 68.4}
```

## GET `/api/status`

대시보드는 **1초마다**, 오디오 플레이어는 **1초마다** 폴링합니다.

```json
{
  "person_count": 12,
  "noise_level_db": 68.4,
  "crowd_level": "busy",
  "current_volume": 25,
  "current_track": "calm_ambient_01.mp3",
  "auto_mode": true,
  "noise_source": "mic",
  "updated_at": "2026-09-28T14:32:10+09:00"
}
```

| 필드 | 값 | 설명 |
| --- | --- | --- |
| `person_count` | 정수 | 마지막으로 받은 인원수 |
| `noise_level_db` | 실수 | 순간소음 제거·평활 처리된 소음 |
| `crowd_level` | `quiet` / `normal` / `busy` | 혼잡도 (여유 / 보통 / 혼잡) |
| `current_volume` | 0 ~ 100 | 지금 재생해야 할 볼륨. **목표값으로 단계적으로 이동**하므로 한 번에 점프하지 않음 |
| `current_track` | 파일명 | 지금 재생해야 할 음원. 혼잡도가 **바뀔 때만** 교체됨 |
| `auto_mode` | true / false | false면 점주가 수동으로 볼륨을 고정한 상태 |
| `noise_source` | `mic` / `dummy` | 소음이 실제 마이크 값인지 더미(테스트용) 값인지 |
| `updated_at` | ISO 시각 | 마지막 제어 계산 시각 (3초마다 갱신) |

### 혼잡도 기준 (현재 값, `backend/config.py`에서 조정)

| 상태 | 진입 | 해제 | 볼륨 | 음원 풀 |
| --- | --- | --- | --- | --- |
| busy | 인원 ≥ 10 그리고 소음 ≥ 70 | 인원 ≤ 8 그리고 소음 ≤ 66 | 25 | `calm_ambient_*.mp3` |
| normal | 그 외 | - | 40 | `standard_bgm_*.mp3` |
| quiet | 인원 ≤ 3 그리고 소음 ≤ 50 | 인원 ≥ 5 또는 소음 ≥ 55 | 60 | `lounge_upbeat_*.mp3` |

진입/해제 기준이 다른 이유: 경계값(9명↔10명)에서 볼륨이 계속 흔들리는 것을 막기 위함입니다.

### 음원 파일명 규칙 (윤지우 ↔ 백엔드 합의 사항)

`current_track` 값은 아래 파일명 중 하나입니다. **Suno로 만든 음원은 이 이름으로 저장**해야 플레이어가 그대로 재생할 수 있습니다.

```
calm_ambient_01.mp3    calm_ambient_02.mp3      # busy
standard_bgm_01.mp3    standard_bgm_02.mp3      # normal
lounge_upbeat_01.mp3   lounge_upbeat_02.mp3     # quiet
```

## POST `/api/mode`

점주가 자동/수동을 전환합니다.

```json
// 수동으로 전환하고 볼륨 33 고정
{"auto_mode": false, "manual_volume": 33}     // manual_volume: 0 ~ 100 (선택)
// 다시 자동으로
{"auto_mode": true}
// 응답
{"result": "success", "auto_mode": false}
```

수동 모드에서도 `crowd_level`, `noise_level_db` 는 계속 갱신되지만 볼륨과 트랙은 바뀌지 않습니다.

## GET `/api/history?limit=200`

`limit`: 1 ~ 5000 (기본 200). 최근 `limit`개를 **오래된 순서**로 반환하므로 그래프에 바로 쓸 수 있습니다. 3초마다 1행씩 쌓입니다.

```json
[
  {"ts": "2026-09-28T14:32:07+09:00", "person_count": 12, "noise_db": 67.9,
   "crowd_level": "busy", "volume": 25, "track": "calm_ambient_01.mp3"},
  ...
]
```

## GET `/api/report/hourly?hours=24`

`hours`: 1 ~ 168 (기본 24). 시간대별 집계를 오래된 순서로 반환합니다.

```json
[
  {"hour": "2026-09-28T14", "samples": 1200,
   "avg_noise_db": 61.3, "max_noise_db": 84.5,
   "avg_person": 7.2, "max_person": 14,
   "busy_pct": 22.5, "normal_pct": 60.0, "quiet_pct": 17.5}
]
```

`hour` 는 `YYYY-MM-DDTHH` (한국시간). 세 비율의 합은 약 100 입니다.

---

## 연동 예시

**윤지우 — 인원수 전송 (Python)**
```python
import requests
BASE = "https://<서비스명>.onrender.com"
requests.post(f"{BASE}/api/update-person", json={"person_count": count}, timeout=3)
```

**윤지우 — 플레이어가 상태 읽기 (Python)**
```python
s = requests.get(f"{BASE}/api/status", timeout=3).json()
volume, track = s["current_volume"], s["current_track"]   # 이 값 그대로 재생 / 페이드
```
볼륨을 얼마로 할지는 **백엔드가 결정**하고, 플레이어는 받은 값으로 부드럽게 페이드만 합니다.

**변정빈 — 대시보드 폴링 (JavaScript)**
```js
const BASE = "https://<서비스명>.onrender.com";
setInterval(async () => {
  const s = await (await fetch(`${BASE}/api/status`)).json();
  // s.person_count, s.noise_level_db, s.crowd_level, s.current_volume ...
}, 1000);
```

## 참고

- Render 무료 플랜은 일정 시간 요청이 없으면 서버가 잠듭니다. **첫 요청은 10~30초** 걸릴 수 있으니 시연 직전에 한 번 접속해 깨워두세요.
- Render 무료 플랜은 디스크가 영구 저장이 아니라서 재배포나 재시작 시 이력(`/api/history`)이 초기화될 수 있습니다.
- `noise_source` 가 `dummy` 이면 소음이 임의값입니다. 마이크 페이지(`/static/mic.html`)를 켜면 `mic` 으로 바뀝니다.

---

# 추가 API (DB · 음악 생성 · 리포트)

## 사용자 / 매장 설정
| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/options` | 회원가입 화면 선택지 `{category, age_group, mood, gender}` |
| POST | `/api/users` | 가입 `{email, password(8자+), store_name?, gender?, age_group?, category?, mood?}` → 201 / 이메일 중복 409 |
| GET | `/api/users/{id}` | 조회 (비밀번호 해시는 내려가지 않음) |
| PATCH | `/api/users/{id}/store` | 매장 설정 일부 수정 |

## 소음 기록
| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/api/status-log` | `{user_id, noise_db}` — **3초마다** 전송 |
| GET | `/api/status-log?user_id=1&limit=60` | 최근 기록 (오래된 순) |

## 음악 생성
| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/api/tracks/generate` | `{user_id, noise_db?}` → **202**. dB 를 생략하면 최근 30초 평균 사용. 이미 생성 중이면 200 + `already_generating: true` |
| GET | `/api/tracks/{id}` | `status`: pending → processing → succeeded / failed. 완료되면 `audio_url` |
| GET | `/api/tracks/next?user_id=1` | 아직 안 틀어준 가장 오래된 완성곡 (없으면 404) |
| POST | `/api/tracks/{id}/played` | 재생 완료 표시 |
| GET | `/api/tracks?user_id=1&status=succeeded` | 목록 |

프론트 흐름: `generate` 호출 → 응답의 `id` 를 3초마다 `GET /api/tracks/{id}` 로 확인 → `succeeded` 가 되면 `audio_url` 재생 → 끝나면 `played`.
생성에는 보통 수십 초가 걸립니다.

## 리포트
`GET /api/report?user_id=1&date=2026-10-16&start_hour=9&end_hour=22&fill_empty=true`
```json
{"user_id": 1, "date": "2026-10-16", "start_hour": 9, "end_hour": 22,
 "hours": [{"hour": 9, "label": "2026-10-16T09", "avg_db": 55.0, "max_db": 60.0, "min_db": 50.0, "samples": 1200},
           {"hour": 10, "label": "2026-10-16T10", "avg_db": null, "max_db": null, "min_db": null, "samples": 0}],
 "overall": {"avg_db": 70.0, "max_db": 90.0, "samples": 5}}
```
`date` 를 생략하면 오늘(한국시간). `fill_empty=true` 면 데이터 없는 시간도 `avg_db: null` 로 포함해 차트 X축이 끊기지 않습니다.
