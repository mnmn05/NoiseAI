"""
기본 BGM 풀 (T2) — 로직

읽는 파일
  backend/data/bgm_metadata.json     곡별 메타데이터 (파일명, 구간, 태그, 프롬프트 ...)
  backend/data/bgm_tag_mapping.json  업종 / 분위기 / 연령대 -> 음악 스타일 키워드
  backend/assets/bgm/*.mp3           오디오 파일

DB 는 쓰지 않고 JSON 파일이 원본이다. (곡이 6개뿐이고 거의 안 바뀌어서)
"""
import json
from pathlib import Path

from .prompt_engine import AGE_ALIASES, CATEGORY_ALIASES, MOOD_ALIASES, _norm
from .settings import settings

DATA_DIR = Path(__file__).parent / "data"
AUDIO_DIR = Path(__file__).parent / "assets" / "bgm"


def load_metadata() -> list[dict]:
    return json.loads((DATA_DIR / "bgm_metadata.json").read_text(encoding="utf-8"))


def load_tag_mapping() -> dict:
    return json.loads((DATA_DIR / "bgm_tag_mapping.json").read_text(encoding="utf-8"))


def bgm_url(filename: str) -> str:
    # PUBLIC_BASE_URL 이 있으면 절대주소, 없으면 /bgm/... 상대경로
    return f"{settings.public_base_url}/bgm/{filename}"


def _wanted_keywords(category=None, mood=None, age_group=None) -> set[str]:
    """매장 설정(업종/분위기/연령대)을 매핑표로 바꿔 키워드 집합으로 만든다."""
    m = load_tag_mapping()
    cat = _norm(category, CATEGORY_ALIASES)
    mo = _norm(mood, MOOD_ALIASES)
    age = _norm(age_group, AGE_ALIASES)
    return (set(m["categories"].get(cat, {}).get("keywords", []))
            | set(m["moods"].get(mo, {}).get("keywords", []))
            | set(m["age_groups"].get(age, {}).get("keywords", [])))


def default_playlist(crowd_level=None, category=None, mood=None, age_group=None) -> list[dict]:
    """초기 큐(기본곡 재생 순서)를 만든다.

    정렬 기준 (앞에 있는 기준이 우선):
      1) 지금 혼잡도와 같은 구간의 곡
      2) 매장 키워드와 태그가 많이 겹치는 곡
      3) metadata.json 에 적힌 순서
    """
    want = _wanted_keywords(category, mood, age_group)
    items = load_metadata()
    order = sorted(
        range(len(items)),
        key=lambda i: (
            items[i]["crowd_level"] != crowd_level,    # 1) 같은 구간이면 False(=0) 이라 앞으로
            -len(want & set(items[i]["tags"])),         # 2) 겹치는 키워드가 많을수록 앞으로
            i,                                          # 3) 동점이면 파일 순서
        ),
    )
    return [
        {
            "filename": items[i]["filename"],
            "title": items[i]["title"],
            "crowd_level": items[i]["crowd_level"],
            "tags": items[i]["tags"],
            "bpm": items[i].get("bpm"),
            "duration_sec": items[i].get("duration_sec"),
            "url": bgm_url(items[i]["filename"]),
            "available": (AUDIO_DIR / items[i]["filename"]).exists(),   # mp3 가 아직 없으면 False
        }
        for i in order
    ]
