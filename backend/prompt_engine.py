"""
T5. 소음 + 좌석 점유율 + 손님 피드백 + 매장 설정 -> 영문 키워드 -> MusicGen 프롬프트

1) 소음 구간 (히스테리시스)
   최근 3~5분 평균 dB 로 loud / normal / quiet 를 정한다. 직전 곡의 구간(prev_level)을 알면
   '들어갈 때'와 '빠져나올 때' 기준을 다르게 둬서 경계값 근처에서 곡 분위기가 흔들리지 않게 한다.

2) 3요소 판정 (situation)  — 우선순위: 손님 피드백 > 3요소 판정 > dB 기본
   quiet_request : 키오스크 '조용했으면' 버튼이 최근에 눌림 -> dB 와 무관하게 차분한 곡
   focus         : 점유율 높음 + dB 낮음 (카공족/1인 손님 집중) -> 집중용 BGM 유지, 절대 시끄럽게 안 함
   hold          : 점유율 낮음 + dB 높음 (소수 테이블 일시적 대화/기기 소음) -> 직전 분위기 유지
   loud / normal / quiet : 위에 해당 없으면 소음 구간 그대로

3) 소음 대응 전략 (점주가 가입/설정에서 고름)
   stable(안정형) : 시끄러울수록 일정한 리듬의 로파이·어쿠스틱·부드러운 재즈로 말소리를 덮음 (업종 장르를 대체)
   lively(활기형) : 시끄러울수록 빠르고 경쾌하고 리드미컬하게
   (예전 값 match = lively, calm = stable 로 그대로 받아준다)

4) 키워드 채택 : 우선순위가 높은 묶음부터 훑으며, 이미 채택된 키워드와 에너지가 반대인 키워드는 버린다.
   장르를 '대체'하는 묶음이 있으면 업종 장르는 쓰지 않는다. 장르가 하나도 안 남으면 업종별 안전 장르를 넣는다.

성별은 저장만 하고 프롬프트에는 쓰지 않는다 (성별로 음악 취향을 단정하는 근거가 약해서).
"""
import math
from dataclasses import dataclass, field

# ---------------------------------------------------------------- 소음 구간
LOUD_DB = 75.0     # 이 이상이면 '시끄러움' (진입 기준)
QUIET_DB = 50.0    # 이 이하이면 '조용함' (진입 기준)
LOUD_EXIT_DB = 71.0    # 시끄러움 상태에서 이 아래로 내려와야 해제
QUIET_EXIT_DB = 54.0   # 조용함 상태에서 이 위로 올라와야 해제

# ---------------------------------------------------------------- 점유율
OCC_HIGH = 0.7     # 이 이상이면 '사람 많음'
OCC_LOW = 0.3      # 이 이하이면 '사람 적음'

# ---------------------------------------------------------------- 입력 정규화 (한글/영문 모두 허용)
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
STRATEGY_ALIASES = {
    "안정형": "stable", "stable": "stable", "calm": "stable",
    "활기형": "lively", "lively": "lively", "match": "lively",
}
STRATEGY_LABEL_KO = {"stable": "안정형", "lively": "활기형"}

# 회원가입 화면의 선택지로 내려줄 값 (GET /api/options)
OPTIONS = {
    "category": ["카페", "주점", "음식점"],
    "age_group": ["10대", "20대", "30대", "40대", "50대 이상"],
    "mood": ["차분한", "활기찬", "아늑한", "고급스러운"],
    "gender": ["여성", "남성", "무관"],
    "noise_strategy": ["안정형", "활기형"],
}

# ---------------------------------------------------------------- 키워드 사전 : (키워드, 종류) 종류 = genre / energy / style
VENUE_NAME = {"cafe": "cafe", "bar": "bar", "restaurant": "restaurant"}

CATEGORY_KEYWORDS = {
    "cafe":       [("lofi beats", "genre"), ("acoustic piano", "genre"), ("chill", "energy")],
    "bar":        [("EDM", "genre"), ("heavy bass", "genre"), ("upbeat", "energy")],
    "restaurant": [("jazz", "genre"), ("light percussion", "genre"), ("easygoing", "energy")],
}
DEFAULT_CATEGORY_KEYWORDS = [("easy listening", "genre")]
# 업종 장르가 모순으로 다 빠졌을 때 넣는 장르 (예: 주점 + 차분한 -> EDM 대신 chill house)
SAFE_GENRE = {"cafe": "lofi beats", "bar": "chill house", "restaurant": "jazz"}
DEFAULT_SAFE_GENRE = "easy listening"

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

# 전략별 소음 규칙. 'genres' 가 있으면 업종 장르를 대체한다.
STRATEGY_RULES = {
    "lively": {
        "loud":   {"genres": [], "keywords": [("fast tempo", "energy"), ("energetic", "energy"), ("rhythmic", "energy")]},
        "normal": {"genres": [], "keywords": []},
        "quiet":  {"genres": [], "keywords": [("slow tempo", "energy"), ("calm", "energy")]},
    },
    "stable": {
        "loud":   {"genres": [("lofi beats", "genre"), ("acoustic guitar", "genre"), ("soft jazz", "genre")],
                   "keywords": [("steady rhythm", "energy"), ("slow tempo", "energy"), ("calm", "energy")]},
        "normal": {"genres": [], "keywords": [("steady rhythm", "energy")]},
        "quiet":  {"genres": [], "keywords": [("medium tempo", "energy"), ("warm", "style")]},
    },
}
# 전략과 무관한 특수 상황
SITUATION_RULES = {
    "quiet_request": {"genres": [("soft piano", "genre"), ("acoustic guitar", "genre")],
                      "keywords": [("slow tempo", "energy"), ("calm", "energy"), ("relaxing", "energy"), ("soft", "style")]},
    "focus":         {"genres": [("lofi beats", "genre"), ("ambient piano", "genre")],
                      "keywords": [("steady rhythm", "energy"), ("slow tempo", "energy"), ("calm", "energy"), ("minimal", "style")]},
}

# 손님이 키오스크에서 고르는 키워드 (한글 버튼 -> 영문 키워드)
GUEST_KEYWORDS = {
    "잔잔한": ("calm", "energy"), "편안한": ("relaxing", "energy"), "신나는": ("upbeat", "energy"),
    "경쾌한": ("bouncy", "energy"), "재즈": ("jazz", "genre"), "어쿠스틱": ("acoustic guitar", "genre"),
    "피아노": ("piano", "genre"), "로파이": ("lofi beats", "genre"), "시티팝": ("city pop", "genre"),
    "빈티지": ("vintage", "style"), "따뜻한": ("warm", "style"), "몽환적인": ("dreamy", "style"),
    "그루브": ("groovy", "style"),
}
_GUEST_BY_EN = {en: (en, kind) for en, kind in GUEST_KEYWORDS.values()}

# ---------------------------------------------------------------- 모순 키워드
LOW_ENERGY = {"slow tempo", "calm", "relaxing", "chill", "mellow", "easygoing", "soft", "minimal"}
HIGH_ENERGY = {"fast tempo", "energetic", "upbeat", "rhythmic", "bouncy", "EDM", "heavy bass"}


def _conflict(a: str, b: str) -> bool:
    return (a in LOW_ENERGY and b in HIGH_ENERGY) or (a in HIGH_ENERGY and b in LOW_ENERGY)


@dataclass(frozen=True)
class StoreProfile:
    category: str | None = None
    age_group: str | None = None
    gender: str | None = None     # 저장용. 프롬프트에는 반영하지 않음
    mood: str | None = None
    noise_strategy: str | None = None


@dataclass
class PromptResult:
    prompt: str
    keywords: list = field(default_factory=list)   # 채택된 키워드
    dropped: list = field(default_factory=list)    # 모순이라 버려진 키워드
    noise_level: str = "normal"                    # 소음 구간 loud / normal / quiet (히스테리시스 적용 후)
    situation: str = "normal"                      # quiet_request / focus / hold / loud / normal / quiet
    strategy: str = "lively"                       # stable / lively
    applied_level: str = "normal"                  # 실제로 키워드에 쓴 구간 (hold 면 직전 구간)


def _norm(value, aliases):
    if value is None:
        return None
    return aliases.get(str(value).strip().lower()) or aliases.get(str(value).strip())


def normalize_strategy(value, default: str = "stable") -> str:
    return _norm(value, STRATEGY_ALIASES) or default


def normalize_guest_keywords(values) -> list[str]:
    """한글 버튼 이름이나 영문 키워드를 영문 키워드 목록으로. 모르는 값은 버리고 순서/중복 정리."""
    out = []
    for v in values or []:
        s = str(v).strip()
        en = GUEST_KEYWORDS.get(s, (None,))[0] or (_GUEST_BY_EN.get(s, (None,))[0])
        if en and en not in out:
            out.append(en)
    return out


def _to_float(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def noise_level(noise_db, prev_level: str | None = None) -> str:
    """dB 를 loud / quiet / normal 로 분류. prev_level 이 있으면 히스테리시스 적용. 값이 없으면 prev 유지(없으면 normal)."""
    db = _to_float(noise_db)
    if db is None:
        return prev_level if prev_level in ("loud", "normal", "quiet") else "normal"
    if prev_level == "loud":
        return "loud" if db >= LOUD_EXIT_DB else ("quiet" if db <= QUIET_DB else "normal")
    if prev_level == "quiet":
        return "quiet" if db <= QUIET_EXIT_DB else ("loud" if db >= LOUD_DB else "normal")
    if db >= LOUD_DB:
        return "loud"
    if db <= QUIET_DB:
        return "quiet"
    return "normal"


def decide_situation(level: str, occupancy=None, quiet_requested: bool = False) -> str:
    """3요소 판정. 우선순위: 손님 피드백 > 점유율+소음 조합 > 소음 구간"""
    if quiet_requested:
        return "quiet_request"
    occ = _to_float(occupancy)
    if occ is not None:
        if occ >= OCC_HIGH and level == "quiet":
            return "focus"
        if occ <= OCC_LOW and level == "loud":
            return "hold"
    return level


def build_prompt_detail(noise_db, profile: StoreProfile, strategy: str | None = "match", *,
                        prev_level: str | None = None, occupancy=None, quiet_requested: bool = False,
                        guest_keywords=None) -> PromptResult:
    """
    noise_db        최근 3~5분 평균 dB (없으면 None)
    strategy        stable/lively (또는 예전 값 calm/match, 한글 안정형/활기형). None 이면 profile.noise_strategy
    prev_level      직전 곡의 소음 구간 (히스테리시스, hold 판정에 사용)
    occupancy       좌석 점유율 0~1 (모르면 None)
    quiet_requested 최근 '조용했으면' 버튼
    guest_keywords  손님이 고른 키워드 (한글 버튼명 또는 영문)
    """
    strat = normalize_strategy(strategy if strategy is not None else profile.noise_strategy, default="lively")
    level = noise_level(noise_db, prev_level)
    situation = decide_situation(level, occupancy, quiet_requested)

    if situation == "hold":
        applied = prev_level if prev_level in ("normal", "quiet") else "normal"
    elif situation in ("loud", "normal", "quiet"):
        applied = situation
    else:
        applied = level

    category = _norm(profile.category, CATEGORY_ALIASES)
    age = _norm(profile.age_group, AGE_ALIASES)
    mood = _norm(profile.mood, MOOD_ALIASES)
    guest = [_GUEST_BY_EN[k] for k in normalize_guest_keywords(guest_keywords)]

    # (키워드 묶음, 장르 대체 여부) — 우선순위 순서
    groups: list[tuple[list, bool]] = []
    if situation in SITUATION_RULES:                               # 1순위: '조용했으면' / 집중
        rule = SITUATION_RULES[situation]
        groups.append((rule["genres"] + rule["keywords"], bool(rule["genres"])))
    if guest:                                                      # 2순위: 손님 키워드 (장르를 고르면 업종 장르 대체)
        groups.append((guest, any(k == "genre" for _, k in guest)))
    if situation not in SITUATION_RULES:                           # 3순위: 전략별 소음 규칙
        rule = STRATEGY_RULES[strat][applied]
        groups.append((rule["genres"] + rule["keywords"], bool(rule["genres"])))
    groups.append((MOOD_KEYWORDS.get(mood, []), False))            # 4순위: 점주가 고른 분위기
    genre_replaced = any(rep for _, rep in groups)
    cat_kw = CATEGORY_KEYWORDS.get(category, DEFAULT_CATEGORY_KEYWORDS)
    if genre_replaced:                                             # 5순위: 업종 (장르 대체 시 장르는 빼고 에너지/스타일만)
        cat_kw = [(w, k) for w, k in cat_kw if k != "genre"]
    groups.append((cat_kw, False))
    groups.append((AGE_KEYWORDS.get(age, []), False))              # 6순위: 연령대

    accepted: list[tuple[str, str]] = []
    dropped: list[str] = []
    for group, _ in groups:
        for kw, kind in group:
            if any(kw == a for a, _ in accepted):
                continue
            if any(_conflict(kw, a) for a, _ in accepted):
                if kw not in dropped:
                    dropped.append(kw)
                continue
            accepted.append((kw, kind))

    if not any(kind == "genre" for _, kind in accepted):           # 장르가 하나도 없으면 안전 장르
        accepted.insert(0, (SAFE_GENRE.get(category, DEFAULT_SAFE_GENRE), "genre"))

    # 문장 안에서는 장르 -> 스타일 -> 에너지 순으로 읽히게 정렬 (같은 종류 안에서는 우선순위 순서 유지)
    order = {"genre": 0, "style": 1, "energy": 2}
    accepted.sort(key=lambda x: order[x[1]])
    keywords = [kw for kw, _ in accepted]

    venue = VENUE_NAME.get(category, "store")
    prompt = f"Instrumental background music for a {venue}: {', '.join(keywords)}. No vocals."
    return PromptResult(prompt=prompt, keywords=keywords, dropped=dropped, noise_level=level,
                        situation=situation, strategy=strat, applied_level=applied)


def build_prompt(noise_db, profile: StoreProfile, strategy: str | None = "match", **kwargs) -> str:
    return build_prompt_detail(noise_db, profile, strategy, **kwargs).prompt
