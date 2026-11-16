# NoiseAI ERD

`scripts/export_docs.py` 로 생성됨.

```mermaid
erDiagram
    users {
        integer id PK
        varchar email
        varchar password_hash
        varchar store_name
        varchar gender
        varchar age_group
        varchar category
        varchar mood
        timestamp_with_time_zone created_at
        varchar noise_strategy
        integer total_seats
        varchar public_id
        text guest_keywords
        timestamp_with_time_zone guest_keywords_until
    }
    feedback {
        integer id PK
        integer user_id FK
        varchar mode
        text keywords
        integer track_id
        timestamp_with_time_zone created_at
    }
    sales_hourly {
        integer id PK
        integer user_id FK
        varchar hour_bucket
        integer sales_amount
        integer order_count
        varchar source
        timestamp_with_time_zone updated_at
    }
    seat_events {
        integer id PK
        integer user_id FK
        varchar seat_id
        varchar event
        integer party_size
        timestamp_with_time_zone created_at
    }
    status_log {
        integer id PK
        integer user_id FK
        float noise_db
        varchar hour_bucket
        timestamp_with_time_zone created_at
        varchar zone_id
    }
    tracks {
        integer id PK
        integer user_id FK
        text prompt
        varchar audio_url
        boolean is_played
        varchar status
        text error
        varchar prediction_id
        timestamp_with_time_zone created_at
        timestamp_with_time_zone completed_at
        varchar source
        integer priority
        boolean is_skipped
        varchar noise_level
        varchar situation
        integer feedback_id
        timestamp_with_time_zone played_at
    }
    users ||--o{ feedback : "user_id"
    users ||--o{ sales_hourly : "user_id"
    users ||--o{ seat_events : "user_id"
    users ||--o{ status_log : "user_id"
    users ||--o{ tracks : "user_id"
```

| 테이블 | 설명 |
| --- | --- |
| `users` | 점주 계정 + 매장 설정 |
| `tracks` | AI 생성곡 = 재생 대기열 |
| `status_log` | 3초마다 소음 dB |
| `seat_events` | 키오스크 자리 선택/퇴석 |
| `feedback` | 손님 키워드 요청 |
| `sales_hourly` | 시간대별 매출 |
