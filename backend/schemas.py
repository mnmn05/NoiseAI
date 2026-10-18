"""
팀 공용 API 계약 (T1)
- 요청/응답 형식을 한 곳에 모아 둔다. 정빈(대시보드/로그인 UI)·지우(플레이어)는 이 파일과
  서버의 /docs 페이지를 기준으로 작업한다.
- 필드 이름·값을 바꿀 때는 이 파일을 먼저 고치고 팀에 공지할 것.

[아직 엔드포인트가 없는 초안] SignUpRequest / LoginRequest / TokenResponse /
UserProfile / TrackOut 은 로그인·음원 API 구현 전에 형식만 먼저 합의하기 위한 모델이다.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ------------------------------------------------------------ 공용 값 (Literal)
CrowdLevel = Literal["quiet", "normal", "busy"]        # 제어 엔진이 판정하는 혼잡도
NoiseSource = Literal["mic", "dummy"]                  # 소음값 출처
Mood = Literal["calm", "standard", "upbeat"]           # 음원 분위기 (quiet→calm, normal→standard, busy→upbeat)
StoreCategory = Literal["cafe", "pub", "restaurant", "retail", "etc"]
TargetGender = Literal["male", "female", "mixed"]      # 매장 '주 고객층' 기준 (점주 본인 성별 아님)
TargetAge = Literal["teens", "20s", "30s", "40s", "50plus", "mixed"]


# ------------------------------------------------------------ 소음 / 상태 / 모드
class NoiseUpdate(BaseModel):
    """POST /api/update-noise 요청 (mic.html → 서버)"""
    noise_db: float = Field(ge=0.0, le=140.0)
    voice_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class NoiseUpdateResponse(BaseModel):
    result: Literal["success"]
    noise_db: float
    voice_ratio: float | None = None


class ModeUpdate(BaseModel):
    """POST /api/mode 요청 (점주 화면 → 서버)"""
    auto_mode: bool
    manual_volume: int | None = Field(default=None, ge=0, le=100)


class ModeUpdateResponse(BaseModel):
    result: Literal["success"]
    auto_mode: bool


class StatusResponse(BaseModel):
    """GET /api/status 응답 (대시보드, 플레이어가 사용)"""
    noise_level_db: float
    crowd_level: CrowdLevel
    current_volume: int = Field(ge=0, le=100)
    current_track: str
    auto_mode: bool
    noise_source: NoiseSource
    updated_at: str | None = None      # ISO8601(KST). 서버 시작 직후 첫 판단 전에는 null


# ------------------------------------------------------------ 이력 / 리포트
class HistoryItem(BaseModel):
    """GET /api/history 응답의 항목 (오래된 순)"""
    ts: str
    noise_db: float
    crowd_level: CrowdLevel
    volume: int
    track: str


class HourlyReportItem(BaseModel):
    """GET /api/report/hourly 응답의 항목 (오래된 순)"""
    hour: str                          # 예: 2026-10-06T14  (KST, 시 단위)
    samples: int
    avg_noise_db: float
    max_noise_db: float
    busy_pct: float
    normal_pct: float
    quiet_pct: float


# ------------------------------------------------------------ [초안] 회원 / 로그인
class SignUpRequest(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=8)
    store_category: StoreCategory
    target_gender: TargetGender | None = None     # 선택 항목
    target_age: TargetAge | None = None           # 선택 항목
    privacy_consent: bool                         # 개인정보 수집·이용 동의 (True 필수)

    @field_validator("email", mode="before")
    @classmethod
    def _clean_email(cls, v):
        # 형식 검사(pattern) 전에 공백 제거·소문자 변환 (mode="before")
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("password")
    @classmethod
    def _bcrypt_limit(cls, v: str) -> str:
        # bcrypt는 72바이트까지만 해시하므로 한글 등 멀티바이트도 바이트 기준으로 제한
        if len(v.encode("utf-8")) > 72:
            raise ValueError("비밀번호가 너무 깁니다 (최대 72바이트)")
        return v

    @field_validator("privacy_consent")
    @classmethod
    def _consent_required(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("개인정보 수집·이용에 동의해야 가입할 수 있습니다")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def _clean_email(cls, v):
        return v.strip().lower() if isinstance(v, str) else v


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UserProfile(BaseModel):
    email: str
    store_category: StoreCategory
    target_gender: TargetGender | None = None
    target_age: TargetAge | None = None


# ------------------------------------------------------------ [초안] 음원 트랙
class TrackOut(BaseModel):
    """음원 풀 한 곡의 메타데이터. 지우의 metadata.json 필드 이름과 동일하게 맞출 것."""
    id: int
    title: str
    mood: Mood
    category: StoreCategory | None = None
    age: TargetAge | None = None
    file_url: str
    duration_sec: int = Field(ge=1)