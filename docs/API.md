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
| GET | `/api/status` | 변정빈 (대시보드), 윤지우 (플레이어) | 현재 상태 전체 (`max_volume`: 플레이어 볼륨 상한) |
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

# 추가 API (DB · 음악 생성 · 손님 요청 · 매출 · 리포트 · 공개 상태)

전체 스키마/요청 예시는 서버의 `/docs` (Swagger) 또는 `docs/openapi.json` (Postman > Import). DB 구조는 `docs/ERD.md`, `docs/schema.sql`.
세 파일은 `python scripts/export_docs.py` 로 코드에서 다시 만들 수 있습니다.

## 로그인 (T7 연동)
| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/api/auth/login` | `{email, password}` → `{access_token, token_type: "bearer", user_id, expires_in}` / 틀리면 401 |
| GET | `/api/auth/me` | 헤더 `Authorization: Bearer <토큰>` → `{user_id, email, store_name}` |

- 환경변수 `AUTH_REQUIRED=true` (배포 권장) 이면 **점주 전용 API** 는 토큰이 필수이고 토큰 주인 = `user_id` 여야 합니다 (아니면 401/403).
  점주 전용: `GET /api/users/{id}`, `PATCH /api/users/{id}/store`, `POST /api/tracks/generate`, `/api/sales*`, `GET /api/report`
- `AUTH_REQUIRED=false` (기본, 개발용) 이면 토큰 없이도 동작합니다. 토큰을 보내면 주인 검사는 합니다.
- `JWT_SECRET` 을 비우면 서버가 켜질 때마다 새 키를 만들어서 재시작 후 다시 로그인해야 합니다. 배포 때는 꼭 설정하세요.

## 사용자 / 매장 설정
| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/options` | 가입 화면 선택지 `{category, age_group, mood, gender, noise_strategy: ["안정형","활기형"]}` |
| POST | `/api/users` | 가입 `{email, password(8자+), store_name?, gender?, age_group?, category?, mood?, noise_strategy?, total_seats?}` → 201 |
| GET | `/api/users/{id}` | 조회. 응답에 `noise_strategy`(stable/lively), `noise_strategy_ko`, `total_seats`, `public_id`(가게 공개 링크용) |
| PATCH | `/api/users/{id}/store` | 매장 설정 일부 수정 (소음 대응 방식, 좌석 수 포함) |

`noise_strategy` 는 `안정형`/`활기형`/`stable`/`lively` 모두 받습니다. 비우면 안정형.

## 소음 기록
| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/api/status-log` | `{user_id, noise_db, zone_id?}` — **3초마다**. `zone_id` 는 층/구역 (예: `"1F"`) |
| GET | `/api/status-log?user_id=1&limit=60` | 최근 기록 (오래된 순) |

마이크 페이지를 `/static/mic.html?user_id=1&zone=1F` 로 열면 3초마다 자동으로 저장합니다.

## 음악 생성 / 재생 대기열
| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/api/tracks/generate` | `{user_id, noise_db?}` → **202**. 곡 재생이 시작될 때 호출. dB 를 생략하면 **최근 4분 평균** (샘플 20개 미만이면 직전 구간 유지). 생성 중인 자동곡이 있으면 200 + `already_generating: true` |
| GET | `/api/tracks/{id}` | `status`: pending → processing → succeeded / failed |
| GET | `/api/tracks/next?user_id=1` | 다음에 틀 곡. **'조용했으면' 보정곡 → 손님 요청곡 → 오래된 자동곡** 순. 재구성으로 빠진 곡 제외. 없으면 404 (기본 BGM 으로) |
| POST | `/api/tracks/{id}/played` | 재생 완료 표시 (`played_at` 기록 → 리포트의 시간대별 재생 수) |
| GET | `/api/tracks?user_id=1&status=succeeded` | 목록 |

`generate` 응답에는 판정 근거가 같이 옵니다:
```json
{"id": 12, "status": "pending", "prompt": "Instrumental background music for a cafe: ...", "source": "auto", "priority": 0,
 "noise_db_used": 72.4, "noise_level": "loud", "situation": "loud", "strategy": "stable", "occupancy": 0.6,
 "guest_keywords": [], "keywords": ["lofi beats", "..."], "dropped_keywords": ["upbeat"]}
```
- `situation`: `quiet_request`('조용했으면') / `focus`(사람 많고 조용함) / `hold`(사람 적고 시끄러움 → 직전 분위기 유지) / `loud` / `normal` / `quiet`
- `source`: `auto` / `request`(손님 키워드) / `quiet`('조용했으면')

플레이어 흐름: 앱 시작 → 기본곡 큐 재생 → 곡이 시작될 때마다 `generate` → 곡이 끝나기 전에 `GET /api/tracks/next` → 있으면 그 곡, 404 면 기본곡 → 끝나면 `played`.

## 손님 요청 (키오스크 버튼)
| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/feedback/options` | 키워드 버튼 목록 `{keywords: ["잔잔한","재즈",...], min_select: 2, max_select: 5, modes}` |
| POST | `/api/feedback` | `{user_id, keywords: ["재즈","피아노"], mode: "add_one" \| "rebuild"}` → 201 |
| POST | `/api/feedback/quiet` | `{user_id}` → 201. '조용했으면' 버튼 |
| GET | `/api/feedback?user_id=1` | 최근 요청 기록 (점주 대시보드) |

- `add_one`: 선택 키워드로 1곡을 만들어 **다음 곡**으로 끼워 넣습니다.
- `rebuild`: 아직 안 튼 곡을 대기열에서 빼고(`skipped_tracks`), 30분 동안 자동곡도 이 키워드로 만듭니다.
- `quiet`: 대기열을 비우고 차분한 곡을 가장 먼저 틀며, 10분 동안 자동곡도 차분하게 만듭니다. 1분 안에 다시 누르면 곡을 새로 만들지 않습니다(`already_requested: true`).
- 키워드 2개 미만 422, 같은 매장 30초 안 재요청 429, 요청곡이 2곡 이상 생성 중이면 429.

## 키오스크 자리 / 공개 혼잡 상태
| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/api/seats/event` | `{user_id, seat_id: "T3", event: "occupy" \| "release", party_size?}` — 자리 선택 후 주문 = occupy, 결제 완료·정리 = release |
| GET | `/api/seats?user_id=1` | `{total_seats, occupied_seats, free_seats, occupancy, avg_dwell_min, expected_wait_min, occupied: [...]}` |
| GET | `/api/public/status/{public_id}` | **로그인 없음.** 가게 링크용 (아래) |

```json
{"store_name": "스누피 카페", "crowd_level": "quiet", "crowd_label": "한산", "message": "지금 한산해요, 조용히 쉬기 좋아요",
 "avg_db": 47.2, "occupancy": 0.2, "free_seats": 8, "expected_wait_min": 0,
 "quiet_hours": [{"hour": 15, "avg_db": 46.5, "crowd_level": "quiet"}], "updated_at": "2026-11-16T15:02:11+09:00"}
```
- 퇴석 기록이 없어도 3시간이 지나면 빈자리로 봅니다. 좌석 수(`total_seats`)가 0 이거나 최근 7일 키오스크 기록이 없으면 점유율은 `null`.
- 예상 대기 = 최근 7일 평균 체류시간 − 가장 오래 앉아 있는 자리의 경과 시간 (최소 5분). 빈자리가 있으면 0.
- 혼잡도: 좌석 정보가 있으면 점유율(≥85% 혼잡, <40% 한산), 없으면 최근 5분 평균 dB(≥70 혼잡, <55 한산).
- `quiet_hours`: 최근 7일 시간대별 평균 dB 가 낮은 3개 시간 — 조용한 곳을 찾는 손님이 시간을 골라 올 수 있게.
- 이메일·내부 user_id 는 내보내지 않습니다.

## 매출 (POS)
| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/api/sales/upload?user_id=1` | `multipart/form-data`, 필드명 `file` (CSV, 최대 5MB) |
| POST | `/api/sales` | `{user_id, rows: [{hour: "2026-11-16T14", sales_amount, order_count}]}` — POS 제휴 API 가 생기면 이 주소로 |
| GET | `/api/sales?user_id=1&date=2026-11-16` | 하루치 시간대별 매출 |

CSV 는 **시간대별 합계**(`시간,매출,주문수`)와 **결제 건별 내역**(`결제일시,결제금액` — 주문수 열이 없으면 행 수를 셈) 둘 다 받고,
날짜·시간 열이 따로 있어도(`날짜,시간,매출`) 됩니다. 한글 엑셀 CSV(CP949)·UTF-8 모두 읽고, `"150,000"`·`90000원` 같은 표기도 처리합니다.
같은 시간은 덮어쓰므로 같은 파일을 두 번 올려도 두 배가 되지 않습니다. 읽지 못한 행은 `errors` 로 알려 줍니다.

## 리포트 (소음 + 매출 한 차트)
`GET /api/report?user_id=1&date=2026-11-10&start_hour=9&end_hour=22&fill_empty=true`
```json
{"hours": [{"hour": 12, "label": "2026-11-10T12", "avg_db": 74.0, "max_db": 76.0, "min_db": 72.0, "samples": 1200,
            "crowd_level": "busy", "crowd_label": "혼잡", "sales_amount": 150000, "order_count": 30, "plays": 9, "requests": 1}],
 "overall": {"avg_db": 62.2, "max_db": 80.0, "samples": 7200, "total_sales": 523000, "total_orders": 105},
 "summary": {"busiest_hour": 18, "quietest_hour": 15, "peak_sales_hour": 18, "noise_sales_correlation": 0.96,
             "correlation_hours": 6,
             "suggestion": "18시가 가장 붐볐고 15시가 가장 한산했어요. 15시 매출은 18시의 15% 예요. 15시에 할인·이벤트를 해 보면 빈 시간대를 채울 수 있어요."}}
```
- 차트: X축 `hour`, 막대 `sales_amount`, 선 `avg_db` (이중 축). 값이 없으면 `null`.
- 혼잡도 고정 임계값: 평균 dB <55 한산 / 55~70 보통 / ≥70 혼잡.
- `noise_sales_correlation` 은 소음과 매출이 둘 다 있는 시간이 3개 이상일 때만 계산합니다 (−1~1, 1 에 가까울수록 시끄러운 시간에 매출도 높음).
