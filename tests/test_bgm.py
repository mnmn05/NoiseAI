"""기본 BGM (T2) 테스트. 사용법 (프로젝트 루트에서): python tests/test_bgm.py"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient

tmp = Path(tempfile.mkdtemp())
import backend.db as dbmod
dbmod.configure(f"sqlite:///{(tmp / 'bgm.db').as_posix()}")
from backend.settings import settings
settings.media_dir = tmp / "media"
settings.public_base_url = ""

import backend.bgm_pool as bgm
from fastapi import FastAPI
from backend.routers import bgm as bgm_router, users as users_router
from backend import config
from backend.prompt_engine import (AGE_KEYWORDS, CATEGORY_KEYWORDS, MOOD_KEYWORDS, StoreProfile,
                                   build_prompt_detail, CATEGORY_ALIASES, MOOD_ALIASES, AGE_ALIASES)

ok = 0
def check(cond, msg):
    global ok
    assert cond, "FAIL: " + msg
    ok += 1
    print("  ok -", msg)

meta, mapping = bgm.load_metadata(), bgm.load_tag_mapping()

# ---- 데이터 파일 정합성
pool = {f for v in config.PLAYLIST_POOL.values() for f in v["tracks"]}
check({m["filename"] for m in meta} == pool, "메타데이터 파일명 == config.PLAYLIST_POOL (누락/초과 없음)")
check(all(m["crowd_level"] == lvl for lvl, v in config.PLAYLIST_POOL.items() for m in meta if m["filename"] in v["tracks"]), "곡의 구간이 PLAYLIST_POOL 과 일치")
check(5 <= len(meta) <= 10, "기본곡 5~10곡")
check(all(all(t in m["prompt"] for t in m["tags"]) for m in meta), "tags 는 모두 prompt 에 들어 있음")
check(all(m["prompt"].startswith("Instrumental background music") and m["prompt"].endswith("No vocals.") for m in meta), "프롬프트 형식")

# ---- 매핑표가 prompt_engine 과 같은지 (드리프트 방지)
for name, src in (("categories", CATEGORY_KEYWORDS), ("moods", MOOD_KEYWORDS), ("age_groups", AGE_KEYWORDS)):
    check(set(mapping[name]) == set(src), f"{name} 키 == prompt_engine")
    check(all(mapping[name][k]["keywords"] == [w for w, _ in src[k]] for k in src), f"{name} 키워드 == prompt_engine")
check(set(CATEGORY_ALIASES.values()) == set(mapping["categories"]), "가입 화면 업종 값이 모두 매핑표에 있음")
check(set(MOOD_ALIASES.values()) == set(mapping["moods"]), "가입 화면 분위기 값이 모두 매핑표에 있음")
check(set(AGE_ALIASES.values()) == set(mapping["age_groups"]), "가입 화면 연령대 값이 모두 매핑표에 있음")

# ---- 프롬프트가 정말 이 조합에서 나오는지 (docs/BGM.md 예시 신뢰성)
r = build_prompt_detail(60, StoreProfile("bar", "20s", None, None))
check(r.keywords == ["EDM", "heavy bass", "trendy", "modern", "upbeat"], "20대 주점(보통 소음) 키워드 == 문서 예시")
check(build_prompt_detail(60, StoreProfile("bar", "20s", "여성", None)).prompt == build_prompt_detail(60, StoreProfile("bar", "20s", "남성", None)).prompt, "성별은 프롬프트에 영향 없음")

# ---- 초기 큐
pl = bgm.default_playlist()
check(len(pl) == len(meta) and len({t["filename"] for t in pl}) == len(meta), "큐에 전곡이 한 번씩")
check(bgm.default_playlist("quiet")[0]["crowd_level"] == "quiet", "지금 구간 곡이 먼저")
check(all(t["crowd_level"] == "busy" for t in bgm.default_playlist("busy")[:2]), "busy 구간 2곡이 앞에")
first = bgm.default_playlist("normal", "restaurant", "elegant", "30대")[0]
check(first["filename"] == "standard_bgm_02.mp3", "normal + 음식점/고급스러운 -> standard_bgm_02 가 먼저")
first = bgm.default_playlist("quiet", "카페", "활기찬")[0]
check(first["filename"] == "lounge_upbeat_02.mp3", "quiet + 카페/활기찬 -> lounge_upbeat_02 가 먼저")
check(bgm.default_playlist("???", "???", "???", "???")[0]["filename"] == meta[0]["filename"], "알 수 없는 값은 파일 순서")

# ---- 엔드포인트 + 정적 파일
dbmod.init_db()
app = FastAPI()                      # main.py 를 건드리지 않으므로, install() 만 붙인 작은 앱으로 시험
app.include_router(users_router.router)
bgm_router.install(app)
(bgm.AUDIO_DIR / "standard_bgm_01.mp3").write_bytes(b"ID3test")
try:
    with TestClient(app) as c:
        r = c.get("/api/bgm/playlist"); j = r.json()
        check(r.status_code == 200 and len(j["tracks"]) == len(meta), "GET /api/bgm/playlist 200")
        check(j["crowd_level"] in {"quiet", "normal", "busy"}, "현재 혼잡도 포함")
        by = {t["filename"]: t for t in j["tracks"]}
        check(by["standard_bgm_01.mp3"]["available"] is True and by["calm_ambient_01.mp3"]["available"] is False, "파일 유무가 available 에 반영")
        check(by["standard_bgm_01.mp3"]["url"] == "/bgm/standard_bgm_01.mp3", "url 은 PUBLIC_BASE_URL 이 없으면 상대경로")
        settings.public_base_url = "https://x.onrender.com"
        check(c.get("/api/bgm/playlist").json()["tracks"][0]["url"].startswith("https://x.onrender.com/bgm/"), "PUBLIC_BASE_URL 이 있으면 절대주소")
        settings.public_base_url = ""
        check(c.get("/bgm/standard_bgm_01.mp3").content == b"ID3test", "/bgm/<파일> 정적 제공")
        u = c.post("/api/users", json={"email": "a@b.co", "password": "password1", "category": "주점", "mood": "활기찬", "age_group": "20대"}).json()
        r = c.get(f"/api/bgm/playlist?user_id={u['id']}")
        check(r.status_code == 200, "user_id 로 조회")
        check(c.get("/api/bgm/playlist?user_id=9999").status_code == 404, "없는 user_id -> 404")
finally:
    (bgm.AUDIO_DIR / "standard_bgm_01.mp3").unlink(missing_ok=True)

print(f"\nALL PASSED ({ok} checks)")
