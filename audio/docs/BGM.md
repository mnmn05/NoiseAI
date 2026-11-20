# BGM 태그 매핑표 (T2)

백엔드가 MusicGen 프롬프트를 만들 때 쓰는 기준입니다. 원본은 `backend/prompt_engine.py` 이고, 이 문서는 그 내용을 표로 푼 것입니다. 값을 바꾸려면 코드와 `backend/data/bgm_tag_mapping.json` 을 같이 바꿔야 합니다. (공유: 김민경)

## 1. 매장 설정 -> 키워드

| 업종 | 키워드 |
| --- | --- |
| 카페 | lofi beats, acoustic piano, chill |
| 주점 | EDM, heavy bass, upbeat |
| 음식점 | jazz, light percussion, easygoing |

| 분위기 | 키워드 |
| --- | --- |
| 차분한 | calm, relaxing |
| 활기찬 | upbeat, energetic |
| 아늑한 | warm, mellow |
| 고급스러운 | smooth, sophisticated |

| 연령대 | 키워드 |
| --- | --- |
| 10대 | trendy, energetic |
| 20대 | trendy, modern |
| 30대 | smooth, modern |
| 40대 | mellow, classic groove |
| 50대 이상 | classic, warm |

**성별은 프롬프트에 쓰지 않습니다.** (저장만 함. 성별로 음악 취향을 단정할 근거가 약해서) 예: '20대 여성 주점'과 '20대 남성 주점'은 같은 프롬프트가 나옵니다. 성별 열을 넣을지는 팀에서 정할 사항입니다.

## 2. 키워드 채택 규칙

1. 우선순위: **실시간 소음 > 분위기 > 업종 > 연령대** 순으로 후보 키워드를 훑습니다.
2. 이미 채택된 키워드와 에너지가 모순되면 버립니다. (느림 계열 `slow tempo, calm, relaxing, chill, mellow, easygoing` vs 빠름 계열 `fast tempo, energetic, upbeat`)
3. 남은 키워드를 `장르 -> 스타일 -> 에너지` 순으로 이어 붙여 `Instrumental background music for a {업종}: ..., ... No vocals.` 문장을 만듭니다. 업종을 모르면 `store`, 업종 키워드가 없으면 `easy listening` 을 씁니다.

소음 구간: `>= 75dB` 시끄러움 / `<= 50dB` 조용함 / 그 사이 보통. 소음 규칙은 `PROMPT_STRATEGY` 에 따라 다릅니다.

| 전략 | 시끄러울 때 | 조용할 때 | 보통일 때 |
| --- | --- | --- | --- |
| match | fast tempo, energetic | slow tempo, calm | (소음 키워드 없음) |
| calm | slow tempo, calm | medium tempo, warm | (소음 키워드 없음) |

`match`: 분위기를 맞춤 / `calm`: 시끄러우면 차분하게 (고객 피로 감소). 기본값은 `match`.

## 3. 조합 결과 예시 (보통 소음, 분위기 미선택)

| 업종 | 연령대 | 최종 키워드 |
| --- | --- | --- |
| 카페 | 10대 | lofi beats, acoustic piano, trendy, chill |
| 카페 | 20대 | lofi beats, acoustic piano, trendy, modern, chill |
| 카페 | 30대 | lofi beats, acoustic piano, smooth, modern, chill |
| 카페 | 40대 | lofi beats, acoustic piano, classic groove, chill, mellow |
| 카페 | 50대 이상 | lofi beats, acoustic piano, classic, warm, chill |
| 주점 | 10대 | EDM, heavy bass, trendy, upbeat, energetic |
| 주점 | 20대 | EDM, heavy bass, trendy, modern, upbeat |
| 주점 | 30대 | EDM, heavy bass, smooth, modern, upbeat |
| 주점 | 40대 | EDM, heavy bass, classic groove, upbeat |
| 주점 | 50대 이상 | EDM, heavy bass, classic, warm, upbeat |
| 음식점 | 10대 | jazz, light percussion, trendy, easygoing |
| 음식점 | 20대 | jazz, light percussion, trendy, modern, easygoing |
| 음식점 | 30대 | jazz, light percussion, smooth, modern, easygoing |
| 음식점 | 40대 | jazz, light percussion, classic groove, easygoing, mellow |
| 음식점 | 50대 이상 | jazz, light percussion, classic, warm, easygoing |

## 4. 소음/분위기에 따른 변화 예시 (20대 주점)

| 분위기 | 소음 | 전략 | 최종 키워드 | 버려진 키워드 |
| --- | --- | --- | --- | --- |
| (없음) | 시끄러움 | match | EDM, heavy bass, trendy, modern, fast tempo, energetic, upbeat | - |
| (없음) | 시끄러움 | calm | EDM, heavy bass, trendy, modern, slow tempo, calm | upbeat |
| (없음) | 보통 | match | EDM, heavy bass, trendy, modern, upbeat | - |
| (없음) | 조용함 | match | EDM, heavy bass, trendy, modern, slow tempo, calm | upbeat |
| (없음) | 조용함 | calm | EDM, heavy bass, warm, trendy, modern, medium tempo, upbeat | - |
| 활기찬 | 시끄러움 | match | EDM, heavy bass, trendy, modern, fast tempo, energetic, upbeat | - |
| 활기찬 | 시끄러움 | calm | EDM, heavy bass, trendy, modern, slow tempo, calm | upbeat, energetic |
| 활기찬 | 보통 | match | EDM, heavy bass, trendy, modern, upbeat, energetic | - |
| 활기찬 | 조용함 | match | EDM, heavy bass, trendy, modern, slow tempo, calm | upbeat, energetic |
| 활기찬 | 조용함 | calm | EDM, heavy bass, warm, trendy, modern, medium tempo, upbeat, energetic | - |
| 차분한 | 시끄러움 | match | EDM, heavy bass, trendy, modern, fast tempo, energetic, upbeat | calm, relaxing |
| 차분한 | 시끄러움 | calm | EDM, heavy bass, trendy, modern, slow tempo, calm, relaxing | upbeat |
| 차분한 | 보통 | match | EDM, heavy bass, trendy, modern, calm, relaxing | upbeat |
| 차분한 | 조용함 | match | EDM, heavy bass, trendy, modern, slow tempo, calm, relaxing | upbeat |
| 차분한 | 조용함 | calm | EDM, heavy bass, warm, trendy, modern, medium tempo, calm, relaxing | upbeat |

## 5. 기본 BGM 풀 (`backend/data/bgm_metadata.json`)

MusicGen 에는 아래 프롬프트를 **그대로** 넣어 생성합니다. (태그 = 프롬프트에 쓴 키워드). 파일명은 `config.PLAYLIST_POOL` 과 같아야 합니다.

| 파일 | 구간 | 프롬프트 |
| --- | --- | --- |
| `calm_ambient_01.mp3` | busy | Instrumental background music for a cafe: lofi beats, acoustic piano, slow tempo, calm, relaxing, chill. No vocals. |
| `calm_ambient_02.mp3` | busy | Instrumental background music for a restaurant: jazz, light percussion, smooth, sophisticated, slow tempo, calm, easygoing. No vocals. |
| `standard_bgm_01.mp3` | normal | Instrumental background music for a cafe: lofi beats, acoustic piano, warm, mellow, chill. No vocals. |
| `standard_bgm_02.mp3` | normal | Instrumental background music for a restaurant: jazz, light percussion, smooth, sophisticated, easygoing. No vocals. |
| `lounge_upbeat_01.mp3` | quiet | Instrumental background music for a bar: EDM, heavy bass, upbeat, energetic. No vocals. |
| `lounge_upbeat_02.mp3` | quiet | Instrumental background music for a cafe: lofi beats, acoustic piano, upbeat, energetic. No vocals. |

구간: busy(혼잡, 볼륨 25) / normal(보통, 40) / quiet(여유, 60). 생성 후 들어보고 `bpm` 을 채웁니다.

## 6. 초기 큐 API

`GET /api/bgm/playlist?user_id=1` (`user_id` 생략 가능)

서버가 켜져 있으면 언제든 기본곡 목록을 재생 순서대로 돌려줍니다. 첫 AI 곡이 `succeeded` 되기 전까지 클라이언트는 이 목록을 돌리면 됩니다.

```json
{"crowd_level": "normal",
 "tracks": [{"filename": "standard_bgm_01.mp3", "title": "Standard BGM 01", "crowd_level": "normal",
             "tags": ["lofi beats", "acoustic piano", "warm", "mellow", "chill"], "bpm": null, "duration_sec": 30,
             "url": "/bgm/standard_bgm_01.mp3", "available": true}]}
```

- 정렬: 지금 혼잡도(`/api/status` 의 `crowd_level`)와 같은 구간 곡 먼저 -> `user_id` 가 있으면 그 매장의 업종/분위기 키워드와 많이 겹치는 곡 먼저 -> 파일 순서.
- `url` 은 `PUBLIC_BASE_URL` 이 있으면 절대주소, 없으면 `/bgm/...` 상대경로.
- `available: false` 는 메타데이터에는 있지만 mp3 가 아직 `backend/assets/bgm/` 에 없는 곡입니다. 재생 목록에서 건너뛰세요.
- 없는 `user_id` 는 404.

프론트 흐름: 앱 시작 -> `/api/bgm/playlist` 로 큐 구성하고 바로 재생 -> `POST /api/tracks/generate` -> `GET /api/tracks/{id}` 3초 폴링 -> `succeeded` 면 현재 곡이 끝난 뒤 `audio_url` 재생 -> `POST /api/tracks/{id}/played`. 생성이 `failed` 거나 대기곡이 없으면(`/api/tracks/next` 404) 기본곡으로 복귀.
