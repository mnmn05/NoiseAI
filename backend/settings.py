"""
환경변수 설정 (T1)
  - 로컬: 프로젝트 루트의 .env 파일
  - Render: 서비스의 Environment 탭에 같은 이름으로 등록 (이미 설정된 값이 .env 보다 우선)
"""
import os
from dataclasses import dataclass
from datetime import timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent      # backend/
PROJECT_DIR = BASE_DIR.parent                    # 프로젝트 루트

load_dotenv(PROJECT_DIR / ".env")                # 이미 있는 환경변수는 덮어쓰지 않음

KST = timezone(timedelta(hours=9))

# meta/musicgen 의 버전. 모델 페이지 > API 탭에서 최신 해시를 확인해 .env 로 바꿀 수 있다.
DEFAULT_MODEL_VERSION = "meta/musicgen:671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb"


def normalize_database_url(url: str) -> str:
    """Render/Neon 등이 주는 postgres:// 주소를 SQLAlchemy(psycopg3)가 읽는 형태로 바꾼다."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]
    return url


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    database_url: str
    replicate_api_token: str
    replicate_model_version: str
    replicate_api_base: str
    track_duration: int          # MusicGen 은 한 번에 최대 30초
    track_format: str            # mp3 / wav
    poll_interval: float         # Replicate 상태 확인 간격(초)
    poll_timeout: float          # 이 시간 안에 안 끝나면 포기(초)
    download_audio: bool         # True: 결과 음원을 우리 서버에 저장 (Replicate 링크는 1시간 뒤 삭제됨)
    media_dir: Path
    public_base_url: str         # 예: https://noiseai.onrender.com  (비우면 /media/... 상대경로)
    cors_origins: list
    prompt_strategy: str         # match: 시끄러우면 신나는 곡 / calm: 시끄러우면 차분한 곡 (매장 설정이 없을 때만 쓰는 기본값)
    jwt_secret: str = ""         # 로그인 토큰 서명 키. 비우면 서버 시작 때마다 임의 생성(재시작 시 재로그인 필요)
    auth_required: bool = False  # True: 점주 전용 API 에 로그인 토큰 필수 (배포 시 켜기)
    token_ttl_hours: float = 24.0

    @classmethod
    def from_env(cls) -> "Settings":
        db_url = os.getenv("DATABASE_URL") or f"sqlite:///{(PROJECT_DIR / 'noiseai.db').as_posix()}"
        fmt = os.getenv("TRACK_FORMAT", "mp3").strip().lower()
        strategy = os.getenv("PROMPT_STRATEGY", "match").strip().lower()
        media = Path(os.getenv("MEDIA_DIR", str(BASE_DIR / "media")))
        if not media.is_absolute():
            media = PROJECT_DIR / media
        origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
        return cls(
            database_url=normalize_database_url(db_url),
            replicate_api_token=os.getenv("REPLICATE_API_TOKEN", "").strip(),
            replicate_model_version=os.getenv("REPLICATE_MODEL_VERSION", DEFAULT_MODEL_VERSION).strip(),
            replicate_api_base=os.getenv("REPLICATE_API_BASE", "https://api.replicate.com/v1").rstrip("/"),
            track_duration=max(1, min(30, int(_env_float("TRACK_DURATION", 30)))),
            track_format=fmt if fmt in {"mp3", "wav"} else "mp3",
            poll_interval=_env_float("POLL_INTERVAL", 3.0),
            poll_timeout=_env_float("POLL_TIMEOUT", 240.0),
            download_audio=_env_bool("DOWNLOAD_AUDIO", True),
            media_dir=media,
            public_base_url=os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/"),
            cors_origins=origins or ["*"],
            prompt_strategy=strategy if strategy in {"match", "calm"} else "match",
            jwt_secret=os.getenv("JWT_SECRET", "").strip(),
            auth_required=_env_bool("AUTH_REQUIRED", False),
            token_ttl_hours=_env_float("TOKEN_TTL_HOURS", 24.0),
        )


settings = Settings.from_env()
