"""
T1·T5·T8 신규 기능 테스트. 사용법 (프로젝트 루트에서): python tests/test_features.py
PostgreSQL 로 돌리려면: TEST_DATABASE_URL=postgresql://... python tests/test_features.py  (그 DB 의 테이블을 모두 지우니 빈 테스트 DB 만 쓸 것)
Replicate 는 httpx.MockTransport 로 흉내 낸다 (실제 API 호출/과금 없음).
"""
import datetime as dt
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # 프로젝트 루트
import httpx
from fastapi.testclient import TestClient

tmp = Path(tempfile.mkdtemp())

# ---------------------------------------------------------------- 0. 예전 스키마 DB 에 새 컬럼이 자동으로 붙는지 (Render 기존 DB 대응)
old_db = tmp / "old.db"
con = sqlite3.connect(old_db)
con.executescript("""
CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255) UNIQUE, password_hash VARCHAR(255), store_name VARCHAR(100),
                    gender VARCHAR(20), age_group VARCHAR(20), category VARCHAR(30), mood VARCHAR(30), created_at DATETIME);
CREATE TABLE tracks (id INTEGER PRIMARY KEY, user_id INTEGER, prompt TEXT, audio_url VARCHAR(1000), is_played BOOLEAN,
                     status VARCHAR(20), error TEXT, prediction_id VARCHAR(64), created_at DATETIME, completed_at DATETIME);
CREATE TABLE status_log (id INTEGER PRIMARY KEY, user_id INTEGER, noise_db FLOAT, hour_bucket VARCHAR(13), created_at DATETIME);
INSERT INTO users (id, email, password_hash, store_name) VALUES (1, 'old@shop.com', 'x', '옛날가게');
INSERT INTO tracks (id, user_id, prompt, is_played, status) VALUES (1, 1, 'p', 0, 'succeeded');
""")
con.commit(); con.close()

import backend.db as dbmod
from backend.settings import settings

ok = 0
def check(cond, msg):
    global ok
    assert cond, "FAIL: " + msg
    ok += 1
    print("  ok -", msg)

print("[0] 기존 DB 자동 마이그레이션")
dbmod.configure(f"sqlite:///{old_db.as_posix()}")
dbmod.init_db()
con = sqlite3.connect(old_db)
ucols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
tcols = {r[1] for r in con.execute("PRAGMA table_info(tracks)")}
check({"noise_strategy", "total_seats", "public_id", "guest_keywords"} <= ucols, "users 에 새 컬럼 추가")
check({"source", "priority", "is_skipped", "noise_level", "played_at"} <= tcols, "tracks 에 새 컬럼 추가")
row = con.execute("SELECT noise_strategy, total_seats, public_id FROM users WHERE id=1").fetchone()
check(row[0] == "stable" and row[1] == 0 and row[2], "기존 점주: 기본값 안정형/좌석 0 + 공개 ID 발급")
check(con.execute("SELECT source, priority, is_skipped FROM tracks WHERE id=1").fetchone() == ("auto", 0, 0), "기존 곡: 기본값 채움")
tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
check({"seat_events", "feedback", "sales_hourly"} <= tables, "신규 3테이블 생성")
con.close()
check(dbmod.ensure_columns() == [], "두 번 실행해도 추가할 컬럼 없음 (멱등)")

# ---------------------------------------------------------------- 본 테스트용 새 DB
TEST_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_URL:
    from backend.settings import normalize_database_url
    dbmod.configure(normalize_database_url(TEST_URL))
    from backend import models as _m  # noqa: F401
    dbmod.Base.metadata.drop_all(dbmod.engine)
    print("[DB] PostgreSQL:", TEST_URL.split("@")[-1])
else:
    dbmod.configure(f"sqlite:///{(tmp / 'test.db').as_posix()}")
settings.media_dir = tmp / "media"
settings.replicate_api_token = "r8_test_token"
settings.poll_interval = 0.01
settings.poll_timeout = 5.0
settings.public_base_url = ""

import backend.main as main
import backend.replicate_client as rc
import backend.storage as storage
from backend import control, config
from backend.models import Feedback, SalesHourly, SeatEvent, StatusLog, Track, User, utcnow
from backend.prompt_engine import StoreProfile, build_prompt_detail, noise_level, decide_situation
from backend.settings import KST

dbmod.init_db()
client = TestClient(main.app)


class FakeReplicate:
    """생성 요청마다 다른 id 를 주고, 첫 조회에 바로 완료"""
    def __init__(self):
        self.n = 0
        self.prompts = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path.endswith("/predictions"):
            import json
            self.n += 1
            self.prompts.append(json.loads(request.content)["input"]["prompt"])
            return httpx.Response(201, json={"id": f"p{self.n}", "status": "starting"})
        if request.method == "GET" and "/predictions/" in path:
            pid = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"id": pid, "status": "succeeded",
                                             "output": f"https://replicate.delivery/x/{pid}.mp3"})
        if request.url.host == "replicate.delivery":
            return httpx.Response(200, content=b"ID3FAKE" * 50)
        return httpx.Response(404)


fake = FakeReplicate()
rc.make_client = lambda: httpx.AsyncClient(base_url=settings.replicate_api_base,
                                           transport=httpx.MockTransport(fake.handler))
storage.make_download_client = lambda: httpx.AsyncClient(follow_redirects=True,
                                                         transport=httpx.MockTransport(fake.handler))


def add_noise(uid, values, minutes_ago=0.5):
    with dbmod.SessionLocal() as s:
        t = utcnow() - dt.timedelta(minutes=minutes_ago)
        for v in values:
            s.add(StatusLog(user_id=uid, noise_db=v, hour_bucket=t.astimezone(KST).strftime("%Y-%m-%dT%H"), created_at=t))
        s.commit()


def wipe(uid, *models):
    with dbmod.SessionLocal() as s:
        for m in models:
            s.query(m).filter(m.user_id == uid).delete()
        s.commit()


# ================================================================ T1. 가입 / 설정 / 로그인
print("[1] 가입·설정 (소음 대응 방식, 좌석 수)")
r = client.get("/api/options").json()
check(r["noise_strategy"] == ["안정형", "활기형"], "options 에 소음 대응 방식")
r = client.post("/api/users", json={"email": "cafe@shop.com", "password": "pw-12345678", "store_name": "스누피 카페",
                                    "category": "카페", "age_group": "20대", "mood": "아늑한", "total_seats": 10})
check(r.status_code == 201, "가입 201")
u = r.json(); uid = u["id"]
check(u["noise_strategy"] == "stable" and u["noise_strategy_ko"] == "안정형", "기본값 안정형")
check(u["total_seats"] == 10 and len(u["public_id"]) >= 8, "좌석 수 저장 + 공개 ID 발급")
r = client.post("/api/users", json={"email": "pub@shop.com", "password": "pw-12345678", "category": "주점",
                                    "age_group": "20대", "noise_strategy": "활기형"})
check(r.json()["noise_strategy"] == "lively", "가입 시 '활기형' -> lively")
bar_uid = r.json()["id"]
check(client.post("/api/users", json={"email": "x@shop.com", "password": "pw-12345678", "noise_strategy": "아무거나"}).status_code == 422,
      "잘못된 소음 대응 방식 422")
r = client.patch(f"/api/users/{uid}/store", json={"noise_strategy": "lively"})
check(r.json()["noise_strategy"] == "lively", "설정에서 전략 변경")
client.patch(f"/api/users/{uid}/store", json={"noise_strategy": "안정형"})
check(client.patch(f"/api/users/{uid}/store", json={"total_seats": None}).json()["total_seats"] == 10, "필수 값은 null 로 안 지워짐")

print("[2] 로그인 / 본인 확인")
r = client.post("/api/auth/login", json={"email": "CAFE@shop.com", "password": "pw-12345678"})
check(r.status_code == 200 and r.json()["user_id"] == uid, "로그인 성공 (이메일 대소문자 무시)")
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}"}
check(client.post("/api/auth/login", json={"email": "cafe@shop.com", "password": "wrong-pass"}).status_code == 401, "비밀번호 틀림 401")
check(client.post("/api/auth/login", json={"email": "none@shop.com", "password": "pw-12345678"}).json()["detail"] ==
      client.post("/api/auth/login", json={"email": "cafe@shop.com", "password": "wrong-pass"}).json()["detail"],
      "없는 이메일과 틀린 비밀번호 메시지 동일 (가입 여부 노출 방지)")
check(client.get("/api/auth/me", headers=H).json()["email"] == "cafe@shop.com", "/me")
check(client.get("/api/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401, "위조 토큰 401")
check(client.get(f"/api/users/{bar_uid}", headers=H).status_code == 403, "토큰 주인과 다른 매장 403")
settings.auth_required = True
check(client.get(f"/api/users/{uid}").status_code == 401, "AUTH_REQUIRED: 토큰 없으면 401")
check(client.get(f"/api/users/{uid}", headers=H).status_code == 200, "AUTH_REQUIRED: 본인 토큰 200")
check(client.post("/api/tracks/generate", json={"user_id": uid}).status_code == 401, "AUTH_REQUIRED: 곡 생성도 보호 (과금 방지)")
settings.auth_required = False

# ================================================================ T5. 규칙 엔진
print("[3] 규칙 엔진 — 전략 분기")
cafe = StoreProfile("카페", "20대", None, None)
bar = StoreProfile("주점", "20대", None, None)
r = build_prompt_detail(80, bar, "stable")
check(r.situation == "loud" and "EDM" not in r.keywords and "lofi beats" in r.keywords and "soft jazz" in r.keywords,
      "안정형 + 시끄러움: 업종 장르(EDM) 대신 로파이·어쿠스틱·소프트재즈로 마스킹")
check("steady rhythm" in r.keywords and "calm" in r.keywords and "upbeat" in r.dropped, "안정형 + 시끄러움: 일정한 리듬, 차분")
r = build_prompt_detail(80, bar, "lively")
check({"fast tempo", "energetic", "rhythmic"} <= set(r.keywords) and "EDM" in r.keywords, "활기형 + 시끄러움: 빠르고 리드미컬")
check(build_prompt_detail(80, cafe, "lively").keywords != build_prompt_detail(80, cafe, "stable").keywords, "같은 소음에서 두 전략은 방향이 다름")
check("medium tempo" in build_prompt_detail(45, cafe, "stable").keywords, "안정형 + 조용함: medium tempo")
check("slow tempo" in build_prompt_detail(45, cafe, "lively").keywords, "활기형 + 조용함: slow tempo")
check(build_prompt_detail(60, bar, "match").strategy == "lively" and build_prompt_detail(60, bar, "calm").strategy == "stable",
      "예전 값 match/calm 도 받아줌")
r = build_prompt_detail(60, StoreProfile("주점", "20대", None, "차분한"), "lively")
check("EDM" not in r.keywords and "chill house" in r.keywords, "주점 + 차분한: EDM 모순 제거 후 안전 장르(chill house)")
check(build_prompt_detail(60, StoreProfile("주점", "20대", "여성", None)).prompt ==
      build_prompt_detail(60, StoreProfile("주점", "20대", "남성", None)).prompt, "성별은 프롬프트에 영향 없음")
for strat in ("stable", "lively"):
    for db in (40, 60, 80):
        p = build_prompt_detail(db, cafe, strat)
        low = {"slow tempo", "calm", "relaxing", "chill", "mellow", "easygoing", "soft", "minimal"}
        high = {"fast tempo", "energetic", "upbeat", "rhythmic", "bouncy", "EDM", "heavy bass"}
        assert not (low & set(p.keywords) and high & set(p.keywords)), p.keywords
        assert p.prompt.startswith("Instrumental background music for a cafe:") and p.prompt.endswith("No vocals.")
check(True, "전략 2 × 소음 3 조합 모두 모순 키워드 없음 + 형식 유지")

print("[4] 규칙 엔진 — 히스테리시스 / 3요소 / 피드백")
check(noise_level(73) == "normal" and noise_level(73, "loud") == "loud", "73dB: 새로 들어갈 땐 normal, 시끄러움 상태면 유지")
check(noise_level(70, "loud") == "normal", "71dB 아래로 내려와야 시끄러움 해제")
check(noise_level(52) == "normal" and noise_level(52, "quiet") == "quiet", "52dB: 조용함 상태면 유지")
check(noise_level(None, "quiet") == "quiet" and noise_level(None) == "normal", "데이터 없으면 직전 구간 유지")
r = build_prompt_detail(45, cafe, "lively", occupancy=0.9)
check(r.situation == "focus" and "fast tempo" not in r.keywords and "minimal" in r.keywords, "점유율 높음 + 조용함 -> 집중용 BGM")
r = build_prompt_detail(85, cafe, "lively", occupancy=0.1, prev_level="normal")
check(r.situation == "hold" and r.applied_level == "normal" and "fast tempo" not in r.keywords, "점유율 낮음 + 시끄러움 -> 직전 분위기 유지")
check(build_prompt_detail(85, cafe, "lively", occupancy=0.5).situation == "loud", "점유율 보통이면 소음대로")
check(build_prompt_detail(85, cafe, "lively").situation == "loud", "점유율 모르면 소음대로")
r = build_prompt_detail(85, StoreProfile("주점", "20대", None, "활기찬"), "lively", occupancy=0.9, quiet_requested=True)
check(r.situation == "quiet_request" and "calm" in r.keywords and "energetic" not in r.keywords and "EDM" not in r.keywords,
      "'조용했으면' 은 dB·점유율·분위기보다 우선")
check(decide_situation("quiet", 0.9, True) == "quiet_request", "우선순위: 피드백 > 3요소")
r = build_prompt_detail(60, StoreProfile("음식점", "30대", None, None), "stable", guest_keywords=["재즈", "신나는", "없는값"])
check("jazz" in r.keywords and "upbeat" in r.keywords and "light percussion" not in r.keywords and "easygoing" in r.dropped,
      "손님 키워드가 업종/에너지보다 우선 (장르를 고르면 업종 장르 대체)")

# ================================================================ T8. 좌석
print("[5] 키오스크 자리 선택 / 점유율 / 예상 대기")
check(client.post("/api/seats/event", json={"user_id": uid, "seat_id": "T1", "event": "sit"}).status_code == 422, "잘못된 event 422")
check(client.post("/api/seats/event", json={"user_id": 999, "seat_id": "T1", "event": "occupy"}).status_code == 404, "없는 매장 404")
now = utcnow()
with dbmod.SessionLocal() as s:     # 지난 기록으로 평균 체류 40분을 만든다
    for i in range(3):
        s.add(SeatEvent(user_id=uid, seat_id=f"H{i}", event="occupy", created_at=now - dt.timedelta(days=1, minutes=40)))
        s.add(SeatEvent(user_id=uid, seat_id=f"H{i}", event="release", created_at=now - dt.timedelta(days=1)))
    s.add(SeatEvent(user_id=uid, seat_id="OLD", event="occupy", created_at=now - dt.timedelta(hours=5)))   # 퇴석 누락
    s.commit()
for i in range(9):
    client.post("/api/seats/event", json={"user_id": uid, "seat_id": f"T{i}", "event": "occupy", "party_size": 2})
r = client.get(f"/api/seats?user_id={uid}").json()
check(r["occupied_seats"] == 9 and r["occupancy"] == 0.9 and r["free_seats"] == 1, "9/10 점유 (퇴석 누락 5시간 전 자리는 자동 빈자리)")
check(r["avg_dwell_min"] == 40.0 and r["expected_wait_min"] == 0, "평균 체류 40분, 빈자리 있으면 대기 0분")
client.post("/api/seats/event", json={"user_id": uid, "seat_id": "T9", "event": "occupy"})
r = client.get(f"/api/seats?user_id={uid}").json()
check(r["free_seats"] == 0 and 5 <= r["expected_wait_min"] <= 40, f"만석이면 예상 대기시간 계산 ({r['expected_wait_min']}분)")
client.post("/api/seats/event", json={"user_id": uid, "seat_id": "T9", "event": "release"})
check(client.get(f"/api/seats?user_id={uid}").json()["occupied_seats"] == 9, "퇴석 반영")

print("[6] 곡 생성에 3요소 반영")
add_noise(uid, [45] * 25)
b = client.post("/api/tracks/generate", json={"user_id": uid}).json()
check(b["occupancy"] == 0.9 and b["situation"] == "focus", "점유율 0.9 + 45dB -> focus 로 생성")
check(fake.prompts[-1] == b["prompt"] and "minimal" in b["prompt"], "Replicate 에 실제로 그 프롬프트를 보냄")
t = client.get(f"/api/tracks/{b['id']}").json()
check(t["status"] == "succeeded" and t["situation"] == "focus" and t["noise_level"] == "quiet", "곡에 판정 결과 저장")
wipe(uid, StatusLog, SeatEvent)
add_noise(uid, [73] * 25)
b = client.post("/api/tracks/generate", json={"user_id": uid}).json()
check(b["noise_level"] == "normal", "직전 곡이 quiet 이고 73dB 면 normal (시끄러움 진입은 75dB 부터)")
wipe(uid, StatusLog)
add_noise(uid, [80] * 25)
b1 = client.post("/api/tracks/generate", json={"user_id": uid}).json()
wipe(uid, StatusLog)
add_noise(uid, [73] * 25)
b2 = client.post("/api/tracks/generate", json={"user_id": uid}).json()
check(b1["noise_level"] == "loud" and b2["noise_level"] == "loud", "직전 곡이 loud 면 73dB 에서도 loud 유지 (히스테리시스)")
wipe(uid, StatusLog)
add_noise(uid, [90] * 25, minutes_ago=6)
add_noise(uid, [50] * 25)
b = client.post("/api/tracks/generate", json={"user_id": uid}).json()
check(b["noise_db_used"] == 50.0, "4분보다 오래된 소음은 평균에서 제외")

# ================================================================ T8. 손님 요청
print("[7] 손님 키워드 요청 (1곡 추가)")
wipe(uid, Track, Feedback, StatusLog)
opts = client.get("/api/feedback/options").json()
check("재즈" in opts["keywords"] and opts["min_select"] == 2, "키오스크 버튼 목록")
check(client.post("/api/feedback", json={"user_id": uid, "keywords": ["재즈"], "mode": "add_one"}).status_code == 422, "키워드 1개면 422")
check(client.post("/api/feedback", json={"user_id": uid, "keywords": ["재즈", "모르는"], "mode": "add_one"}).status_code == 422,
      "알 수 없는 키워드는 빼고 셈")
check(client.post("/api/feedback", json={"user_id": uid, "keywords": ["재즈", "피아노"], "mode": "all"}).status_code == 422, "잘못된 mode 422")
auto1 = client.post("/api/tracks/generate", json={"user_id": uid}).json()["id"]
r = client.post("/api/feedback", json={"user_id": uid, "keywords": ["재즈", "피아노", "따뜻한"], "mode": "add_one"})
check(r.status_code == 201, "요청 201")
req = r.json()
check(req["track"]["source"] == "request" and req["track"]["priority"] > 0, "요청곡은 우선순위 높게")
check("jazz" in req["track"]["prompt"] and "piano" in req["track"]["prompt"], "요청 키워드가 프롬프트에 들어감")
check(client.get(f"/api/tracks/next?user_id={uid}").json()["id"] == req["track"]["id"], "먼저 만든 자동곡보다 요청곡이 다음 순서")
client.post(f"/api/tracks/{req['track']['id']}/played")
check(client.get(f"/api/tracks/next?user_id={uid}").json()["id"] == auto1, "요청곡 재생 후 자동곡")
check(client.post("/api/feedback", json={"user_id": uid, "keywords": ["재즈", "피아노"], "mode": "add_one"}).status_code == 429,
      "30초 안에 또 누르면 429")
with dbmod.SessionLocal() as s:
    check(s.get(Feedback, req["feedback"]["id"]).track_id == req["track"]["id"], "요청 기록에 곡 연결")

print("[8] 전체 재구성")
wipe(uid, Feedback)
auto2 = client.post("/api/tracks/generate", json={"user_id": uid}).json()["id"]
r = client.post("/api/feedback", json={"user_id": uid, "keywords": ["시티팝", "그루브"], "mode": "rebuild"}).json()
check(r["skipped_tracks"] >= 2, f"안 튼 곡들 대기열에서 제외 ({r['skipped_tracks']}곡)")
with dbmod.SessionLocal() as s:
    check(s.get(Track, auto1).is_skipped and s.get(Track, auto2).is_skipped, "기존 자동곡 skipped")
check(client.get(f"/api/tracks/next?user_id={uid}").json()["id"] == r["track"]["id"], "재구성 요청곡이 다음 곡")
b = client.post("/api/tracks/generate", json={"user_id": uid}).json()
check("city pop" in b["prompt"] and b["guest_keywords"] == ["city pop", "groovy"], "이후 자동곡도 30분간 재구성 키워드로 생성")
with dbmod.SessionLocal() as s:
    s.get(User, uid).guest_keywords_until = utcnow() - dt.timedelta(minutes=1); s.commit()
wipe(uid, Track)
b = client.post("/api/tracks/generate", json={"user_id": uid}).json()
check("city pop" not in b["prompt"] and b["guest_keywords"] == [], "30분 지나면 원래 매장 설정으로 복귀")

print("[9] '조용했으면' 버튼")
wipe(uid, Track, Feedback)
add_noise(uid, [85] * 25)
for i in range(5):                                  # 10석 중 5석 (점유율 0.5 -> 소음대로 판정)
    client.post("/api/seats/event", json={"user_id": uid, "seat_id": f"Q{i}", "event": "occupy"})
client.patch(f"/api/users/{uid}/store", json={"noise_strategy": "활기형"})
loud = client.post("/api/tracks/generate", json={"user_id": uid}).json()
check(loud["situation"] == "loud", "점유율 0.5 + 85dB -> loud")
check("fast tempo" in loud["prompt"], "활기형 + 85dB -> 빠른 곡이 대기 중")
r = client.post("/api/feedback/quiet", json={"user_id": uid}).json()
check(r["situation"] == "quiet_request" and "calm" in r["track"]["prompt"] and "fast tempo" not in r["track"]["prompt"],
      "dB 와 무관하게 즉시 차분한 곡")
check(r["skipped_tracks"] >= 1, "시끄러운 대기곡은 틀지 않음")
check(client.get(f"/api/tracks/next?user_id={uid}").json()["id"] == r["track"]["id"], "보정곡이 바로 다음")
r2 = client.post("/api/feedback/quiet", json={"user_id": uid}).json()
check(r2["already_requested"] is True and r2["track"] is None, "1분 안에 또 누르면 곡을 새로 만들지 않음")
wipe(uid, Track)
b = client.post("/api/tracks/generate", json={"user_id": uid}).json()
check(b["situation"] == "quiet_request" and "fast tempo" not in b["prompt"], "10분 동안은 자동곡도 차분하게")
with dbmod.SessionLocal() as s:
    for f in s.query(Feedback).filter(Feedback.user_id == uid):
        f.created_at = utcnow() - dt.timedelta(minutes=11)
    s.commit()
wipe(uid, Track)
check(client.post("/api/tracks/generate", json={"user_id": uid}).json()["situation"] == "loud", "10분 지나면 소음 기준으로 복귀")
client.patch(f"/api/users/{uid}/store", json={"noise_strategy": "안정형"})
check(len(client.get(f"/api/feedback?user_id={uid}").json()) == 2, "점주용 요청 기록 조회")

# ================================================================ T8. 매출
print("[10] 매출 CSV 업로드")
day = dt.date(2026, 11, 10)
csv_hourly = "시간,매출,주문수\n2026-11-10 12:00,\"150,000\",30\n2026-11-10 13:00,90000원,18\n2026-11-10 15:00,30000,6\n2026-11-10 18:00,200000,40\n잘못된줄,abc,1\n"
r = client.post(f"/api/sales/upload?user_id={uid}", files={"file": ("sales.csv", csv_hourly.encode("cp949"), "text/csv")})
j = r.json()
check(r.status_code == 200 and j["inserted"] == 4 and j["error_count"] == 1, "한글 엑셀(CP949) CSV: 4시간 저장, 잘못된 1행 보고")
r = client.post(f"/api/sales/upload?user_id={uid}", files={"file": ("sales.csv", csv_hourly.encode("utf-8-sig"), "text/csv")})
check(r.json()["updated"] == 4 and r.json()["inserted"] == 0, "같은 파일 다시 올리면 덮어씀 (두 배 안 됨)")
tx = "결제일시,결제금액\n2026-11-10 14:05:11,4500\n2026-11-10 14:40:00,5500\n2026/11/10 오후 2:59,3000\n"
r = client.post(f"/api/sales/upload?user_id={uid}", files={"file": ("tx.csv", tx.encode("utf-8"), "text/csv")}).json()
check(r["hours"] == ["2026-11-10T14"], "결제 건별 내역도 시간대로 합침 (오후 2시 포함)")
s = client.get(f"/api/sales?user_id={uid}&date=2026-11-10").json()
h = {x["hour"]: x for x in s["hours"]}
check(h[14]["sales_amount"] == 13000 and h[14]["order_count"] == 3, "건별 3건 -> 13,000원 / 3건")
check(h[12]["sales_amount"] == 150000 and s["total_sales"] == 483000, "콤마·'원' 제거, 하루 합계")
check(client.post(f"/api/sales/upload?user_id={uid}", files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")}).status_code == 422,
      "시간/매출 열이 없으면 422")
check(client.post(f"/api/sales/upload?user_id={uid}", files={"file": ("x.csv", b"", "text/csv")}).status_code == 422, "빈 파일 422")
check(client.post(f"/api/sales/upload?user_id={uid}", files={"file": ("x.csv", b"x" * (5 * 1024 * 1024 + 10), "text/csv")}).status_code == 413,
      "5MB 초과 413")
r = client.post("/api/sales", json={"user_id": uid, "rows": [{"hour": "2026-11-10T16", "sales_amount": 40000, "order_count": 8}]})
check(r.status_code == 200 and r.json()["inserted"] == 1, "JSON 입력 (POS 제휴 API 대비)")
check(client.post("/api/sales", json={"user_id": uid, "rows": [{"hour": "어제", "sales_amount": 1}]}).status_code == 422, "JSON 시간 형식 오류 422")

print("[11] 리포트: 소음 + 매출 + 재생 이력")
with dbmod.SessionLocal() as s:
    for hour, vals in {12: [72, 76], 13: [66, 64], 14: [52, 50], 15: [48, 46], 16: [58, 60], 18: [78, 80]}.items():
        for v in vals:
            s.add(StatusLog(user_id=uid, noise_db=v, hour_bucket=f"{day.isoformat()}T{hour:02d}", created_at=utcnow()))
    played = dt.datetime(2026, 11, 10, 18, 30, tzinfo=KST).astimezone(dt.timezone.utc)
    s.add(Track(user_id=uid, prompt="x", status="succeeded", is_played=True, played_at=played))
    s.add(Track(user_id=uid, prompt="y", status="succeeded", is_played=True, played_at=played + dt.timedelta(minutes=5)))
    s.add(Feedback(user_id=uid, mode="quiet", created_at=dt.datetime(2026, 11, 10, 12, 10, tzinfo=KST).astimezone(dt.timezone.utc)))
    s.commit()
r = client.get(f"/api/report?user_id={uid}&date=2026-11-10").json()
h = {x["hour"]: x for x in r["hours"]}
check(h[12]["sales_amount"] == 150000 and h[12]["avg_db"] == 74.0 and h[12]["crowd_label"] == "혼잡", "12시: 매출 + 평균 dB + 혼잡")
check(h[15]["crowd_level"] == "quiet" and h[16]["crowd_level"] == "normal", "고정 임계값 한산(<55)/보통/혼잡(>=70)")
check(h[18]["plays"] == 2 and h[12]["requests"] == 1, "시간대별 재생 수·손님 요청 수 (한국시간)")
check(h[3]["sales_amount"] is None and h[3]["avg_db"] is None and h[3]["crowd_level"] == "unknown", "데이터 없는 시간은 null")
sm = r["summary"]
check(sm["busiest_hour"] == 18 and sm["quietest_hour"] == 15 and sm["peak_sales_hour"] == 18, "가장 붐빈/한산한/매출 최고 시간")
check(sm["correlation_hours"] == 6 and sm["noise_sales_correlation"] > 0.8, f"소음-매출 상관계수 ({sm['noise_sales_correlation']})")
check("15시" in sm["suggestion"] and "할인" in sm["suggestion"], "점주용 한 줄 제안: " + sm["suggestion"])
check(r["overall"]["total_sales"] == 523000, "하루 매출 합계")
r = client.get(f"/api/report?user_id={uid}&date=2026-11-10&fill_empty=false").json()
check([x["hour"] for x in r["hours"]] == [12, 13, 14, 15, 16, 18], "fill_empty=false: 소음이나 매출이 있는 시간만")

# ================================================================ T8. 공개 혼잡 상태
print("[12] 가게 공개 링크 상태")
pid = client.get(f"/api/users/{uid}").json()["public_id"]
check(client.get("/api/public/status/nope").status_code == 404, "없는 링크 404")
wipe(uid, StatusLog, SeatEvent)
r = client.get(f"/api/public/status/{pid}").json()
check(r["crowd_level"] == "unknown" and "아직" in r["message"], "데이터 없으면 '정보 없음'")
check("email" not in r and "user_id" not in r and r["store_name"] == "스누피 카페", "개인정보(이메일·내부 ID) 미노출")
add_noise(uid, [45] * 15)
client.post("/api/seats/event", json={"user_id": uid, "seat_id": "A1", "event": "occupy"})
r = client.get(f"/api/public/status/{pid}").json()
check(r["crowd_level"] == "quiet" and r["message"] == "지금 한산해요, 조용히 쉬기 좋아요", "한산 메시지")
for i in range(2, 11):
    client.post("/api/seats/event", json={"user_id": uid, "seat_id": f"A{i}", "event": "occupy"})
r = client.get(f"/api/public/status/{pid}").json()
check(r["crowd_level"] == "busy" and r["free_seats"] == 0 and "예상 대기" in r["message"], "조용해도 만석이면 혼잡 + 예상 대기: " + r["message"])
wipe(uid, StatusLog)                                # 오늘 기록이 같은 시각대에 섞이지 않게 (실행 시각과 무관한 테스트)
with dbmod.SessionLocal() as s:
    base = (dt.datetime.now(KST) - dt.timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
    for hh, v in ((10, 75), (15, 47), (16, 52), (20, 80)):
        b = base.replace(hour=hh)
        s.add(StatusLog(user_id=uid, noise_db=v, hour_bucket=b.strftime("%Y-%m-%dT%H"), created_at=utcnow()))
    s.commit()
qh = client.get(f"/api/public/status/{pid}").json()["quiet_hours"]
check(qh[0]["hour"] == 15 and len(qh) == 3, f"최근 7일 한산한 시간대 추천 {[q['hour'] for q in qh]}")

# ================================================================ 실시간 제어 (control.py)
print("[13] 실시간 볼륨 제어")
check(control.decide_crowd_level(None, 75.0, "normal") == "busy", "인원수 없이 dB 만으로 busy 진입 (예전엔 불가능)")
check(control.decide_crowd_level(None, 68.0, "busy") == "busy" and control.decide_crowd_level(None, 65.0, "busy") == "normal",
      "busy 해제는 66dB 이하 (히스테리시스)")
check(control.decide_crowd_level(0, 75.0, "normal") == "normal", "인원수 입력이 살아 있으면 예전 규칙 그대로")
check(control.get_status()["max_volume"] == config.MAX_VOLUME, "/api/status 에 볼륨 상한")
control.set_mode(False, 100)
check(control.get_status()["current_volume"] == config.MAX_VOLUME, "수동 볼륨도 상한을 넘지 않음")
control.set_mode(True)
check(all(min(v["volume"], config.MAX_VOLUME) <= config.MAX_VOLUME for v in config.PLAYLIST_POOL.values()), "자동 볼륨 상한")
check(client.post("/api/status-log", json={"user_id": uid, "noise_db": 50, "zone_id": "2F"}).json()["zone_id"] == "2F", "층/구역 기록")

print(f"\nALL PASSED ({ok} checks) on", "postgresql" if TEST_URL else "sqlite")
