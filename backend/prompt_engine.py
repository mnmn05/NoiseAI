"""
T5. 소음(dB) + 매장 설정 -> 영문 키워드 -> MusicGen 프롬프트

흐름
  1) 실시간 dB, 업종, 연령대, 분위기를 각각 '후보 키워드 묶음'으로 바꾼다 (우선순위: dB > 분위기 > 업종 > 연령대)
  2) 우선순위가 높은 묶음부터 훑으면서, 이미 채택된 키워드와 모순되는 키워드는 버린다 (예: calm 과 energetic)
  3) 남은 키워드를 하나의 영문 문장으로 이어붙인다
성별은 저장만 하고 프롬프트에는 쓰지 않는다 (성별로 음악 취향을 단정하는 근거가 약해서).
"""
import math
from dataclasses import dataclass, field

# ---- dB 구간 ----
LOUD_DB = 75.0     # 이 이상이면 '시끄러움'
QUIET_DB = 50.0    # 이 이하이면 '조용함'  (사이 구간은 매장 설정이 결정)

# ---- 입력 정규화 (한글/영문 모두 허용) ----
CATEGORY_ALIASES = {
    "카페": "cafe", "커피": "cafe", "cafe": "cafe", "coffee": "cafe",
    "주점": "bar", "술집": "bar", "펍": "bar", "bar": "bar", "pub": "bar",
    "음식점": "restaurant", "식당": "restaurant", "restaurant": "restaurant",
}
AGE_ALIASES = {
    "10대": "teens", "teens": "teens",
    "20대": "20s", "20s": "20s",
    "30대": "30s", "30s": "30s",
    "40대": "40s", "40s": "40s",
    "50대": "50plus", "50대 이상": "50plus", "60대": "50plus", "60대 이상": "50plus", "50plus": "50plus",
}
MOOD_ALIASES = {
    "차분한": "calm", "calm": "calm",
    "활기찬": "lively", "lively": "lively", "energetic": "lively",
    "아늑한": "cozy", "cozy": "cozy",
    "고급스러운": "elegant", "elegant": "elegant",
}

# 회원가입 화면의 선택지로 내려줄 값 (GET /api/options)
OPTIONS = {
    "category": ["카페", "주점", "음식점"],
    "age_group": ["10대", "20대", "30대", "40대", "50대 이상"],
    "mood": ["차분한", "활기찬", "아늑한", "고급스러운"],
    "gender": ["여성", "남성", "무관"],
}

# ---- 키워드 사전 : (키워드, 종류) 종류 = genre / energy / style ----
VENUE_NAME = {"cafe": "cafe", "bar": "bar", "restaurant": "restaurant"}

CATEGORY_KEYWORDS = {
    "cafe":       [("lofi beats", "genre"), ("acoustic piano", "genre"), ("chill", "energy")],
    "bar":        [("EDM", "genre"), ("heavy bass", "genre"), ("upbeat", "energy")],
    "restaurant": [("jazz", "genre"), ("light percussion", "genre"), ("easygoing", "energy")],
}
DEFAULT_CATEGORY_KEYWORDS = [("easy listening", "genre")]

MOOD_KEYWORDS = {
    "calm":    [("calm", "energy"), ("relaxing", "energy")],
    "lively":  [("upbeat", "energy"), ("energetic", "energy")],
    "cozy":    [("warm", "style"), ("mellow", "energy")],
    "elegant": [("smooth", "style"), ("sophisticated", "style")],
}

AGE_KEYWORDS = {
    "teens":  [("trendy", "style"), ("energetic", "energy")],
    "20s":    [("trendy", "style"), ("modern", "style")],
    "30s":    [("smooth", "style"), ("modern", "style")],
    "40s":    [("mellow", "energy"), ("classic groove", "style")],
    "50plus": [("classic", "style"), ("warm", "style")],
}

# dB 규칙. strategy 별로 시끄러울 때/조용할 때 어떤 키워드를 줄지 다르다.
#  match : 시끄러우면 빠르고 신나게, 조용하면 느리고 차분하게 (분위기를 맞춤)
#  calm  : 시끄러우면 느리고 차분하게 (고객 피로 줄이기), 조용하면 중간 템포로
DB_RULES = {
    "match": {
        "loud":  [("fast tempo", "energy"), ("energetic", "energy")],
        "quiet": [("slow tempo", "energy"), ("calm", "energy")],
    },
    "calm": {
        "loud":  [("slow tempo", "energy"), ("calm", "energy")],
        "quiet": [("medium tempo", "energy"), ("warm", "style")],
    },
}

# ---- 모순 키워드 ----
LOW_ENERGY = {"slow tempo", "calm", "relaxing", "chill", "mellow", "easygoing"}
HIGH_ENERGY = {"fast tempo", "energetic", "upbeat"}


def _conflict(a: str, b: str) -> bool:
    return (a in LOW_ENERGY and b in HIGH_ENERGY) or (a in HIGH_ENERGY and b in LOW_ENERGY)


@dataclass(frozen=True)
class StoreProfile:
    category: str | None = None
    age_group: str | None = None
    gender: str | None = None     # 저장용. 프롬프트에는 반영하지 않음
    mood: str | None = None


@dataclass
class PromptResult:
    prompt: str
    keywords: list = field(default_factory=list)   # 채택된 키워드
    dropped: list = field(default_factory=list)    # 모순이라 버려진 키워드
    noise_level: str = "normal"                    # loud / normal / quiet


def _norm(value, aliases):
    if value is None:
        return None
    return aliases.get(str(value).strip().lower()) or aliases.get(str(value).strip())


def noise_level(noise_db) -> str:
    """dB 를 loud / quiet / normal 로 분류. 값이 없거나 숫자가 아니면 normal."""
    try:
        db = float(noise_db)
    except (TypeError, ValueError):
        return "normal"
    if math.isnan(db):
        return "normal"
    if db >= LOUD_DB:
        return "loud"
    if db <= QUIET_DB:
        return "quiet"
    return "normal"


def build_prompt_detail(noise_db, profile: StoreProfile, strategy: str = "match") -> PromptResult:
    level = noise_level(noise_db)
    category = _norm(profile.category, CATEGORY_ALIASES)
    age = _norm(profile.age_group, AGE_ALIASES)
    mood = _norm(profile.mood, MOOD_ALIASES)
    rules = DB_RULES.get(strategy, DB_RULES["match"])

    # 우선순위 순서의 후보 묶음
    candidates = [
        rules.get(level, []),                                          # 1순위: 실시간 소음
        MOOD_KEYWORDS.get(mood, []),                                   # 2순위: 점주가 고른 분위기
        CATEGORY_KEYWORDS.get(category, DEFAULT_CATEGORY_KEYWORDS),    # 3순위: 업종
        AGE_KEYWORDS.get(age, []),                                     # 4순위: 연령대
    ]

    accepted: list[tuple[str, str]] = []
    dropped: list[str] = []
    for group in candidates:
        for kw, kind in group:
            if any(kw == a for a, _ in accepted):
                continue
            if any(_conflict(kw, a) for a, _ in accepted):
                dropped.append(kw)
                continue
            accepted.append((kw, kind))

    # 문장 안에서는 장르 -> 스타일 -> 에너지 순으로 읽히게 정렬 (우선순위 순서는 유지)
    order = {"genre": 0, "style": 1, "energy": 2}
    accepted.sort(key=lambda x: order[x[1]])
    keywords = [kw for kw, _ in accepted]

    venue = VENUE_NAME.get(category, "store")
    prompt = f"Instrumental background music for a {venue}: {', '.join(keywords)}. No vocals."
    return PromptResult(prompt=prompt, keywords=keywords, dropped=dropped, noise_level=level)


def build_prompt(noise_db, profile: StoreProfile, strategy: str = "match") -> str:
    return build_prompt_detail(noise_db, profile, strategy).prompt
