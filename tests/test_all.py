"""
전체 흐름 테스트. 사용법 (프로젝트 루트에서): python tests/test_all.py sqlite
(선택) 진짜 PostgreSQL 로 테스트: pip install pgserver 후 python tests/test_all.py postgres
Replicate 는 httpx.MockTransport 로 흉내 낸다 (실제 API 호출/과금 없음).
"""
import asyncio, sys, tempfile, os, json, datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # 프로젝트 루트
import httpx
from fastapi.testclient import TestClient

mode = sys.argv[1] if len(sys.argv) > 1 else "sqlite"
tmp = Path(tempfile.mkdtemp())

import backend.db as dbmod
import backend.settings as st
from backend.settings import settings, normalize_database_url

pg = None
if mode == "postgres":
    import pgserver
    pg = pgserver.get_server(tmp / "pgdata", cleanup_mode="stop")
    uri = pg.get_uri()                      # postgresql://postgres:@/postgres?host=/tmp/...
    print("postgres uri:", uri)
    url = normalize_database_url(uri)
else:
    url = f"sqlite:///{(tmp / 'test.db').as_posix()}"

dbmod.configure(url)
settings.media_dir = tmp / "media"
settings.replicate_api_token = "r8_test_token"
settings.poll_interval = 0.01
settings.poll_timeout = 5.0
settings.public_base_url = ""

import backend.main as main
import backend.replicate_client as rc
import backend.storage as storage
from backend.models import StatusLog, Track, User, utcnow

dbmod.init_db()
client = TestClient(main.app)

ok = 0
def check(cond, msg):
    global ok
    assert cond, "FAIL: " + msg
    ok += 1
    print("  ok -", msg)

# ---------------------------------------------------------------- Replicate 모의 서버
class FakeReplicate:
    def __init__(self, polls_before_done=2, final="succeeded", never_done=False, create_status=201):
        self.requests = []; self.polls = 0
        self.polls_before_done = polls_before_done; self.final = final
        self.never_done = never_done; self.create_status = create_status
        self.cancelled = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if request.method == "POST" and path.endswith("/predictions"):
            if self.create_status != 201:
                return httpx.Response(self.create_status, json={"detail": "boom"})
            return httpx.Response(201, json={"id": "pred123", "status": "starting"})
        if request.method == "POST" and path.endswith("/cancel"):
            self.cancelled = True
            return httpx.Response(200, json={"status": "canceled"})
        if request.method == "GET" and path.endswith("/predictions/pred123"):
            self.polls += 1
            if self.never_done or self.polls < self.polls_before_done:
                return httpx.Response(200, json={"id": "pred123", "status": "processing"})
            if self.final == "succeeded":
                return httpx.Response(200, json={"id": "pred123", "status": "succeeded",
                                                 "output": "https://replicate.delivery/x/out.mp3"})
            return httpx.Response(200, json={"id": "pred123", "status": self.final, "error": "model exploded"})
        if request.url.host == "replicate.delivery":
            return httpx.Response(200, content=b"ID3FAKE-MP3-BYTES" * 100)
        return httpx.Response(404)

def install(fake):
    rc.make_client = lambda: httpx.AsyncClient(
        base_url=settings.replicate_api_base,
        headers={"Authorization": f"Bearer {settings.replicate_api_token}"},
        transport=httpx.MockTransport(fake.handler))
    storage.make_download_client = lambda: httpx.AsyncClient(
        follow_redirects=True, transport=httpx.MockTransport(fake.handler))

def wipe_tracks():
    with dbmod.SessionLocal() as s:
        s.query(Track).delete(); s.commit()

# ================================================================ 1. 사용자
print("[1] users")
r = client.get("/api/options"); check(r.status_code == 200 and "카페" in r.json()["category"], "options 목록")
r = client.post("/api/users", json={"email": "Owner@Cafe.com", "password": "pw-12345678", "store_name": "스누피 카페",
                                    "gender": "여성", "age_group": "20대", "category": "카페", "mood": "아늑한"})
check(r.status_code == 201, "가입 201"); uid = r.json()["id"]
check(r.json()["email"] == "owner@cafe.com" and "password_hash" not in r.json(), "이메일 소문자화, 해시 비노출")
check(client.post("/api/users", json={"email": "owner@cafe.com", "password": "pw-12345678"}).status_code == 409, "중복 이메일 409")
check(client.post("/api/users", json={"email": "bad", "password": "pw-12345678"}).status_code == 422, "잘못된 이메일 422")
check(client.post("/api/users", json={"email": "a@b.co", "password": "short"}).status_code == 422, "짧은 비밀번호 422")
with dbmod.SessionLocal() as s:
    from backend.security import verify_password
    check(verify_password("pw-12345678", s.get(User, uid).password_hash), "저장된 해시로 비밀번호 검증 가능")
check(client.get(f"/api/users/{uid}").json()["category"] == "카페", "조회")
check(client.get("/api/users/9999").status_code == 404, "없는 사용자 404")
r = client.patch(f"/api/users/{uid}/store", json={"mood": "차분한"})
check(r.json()["mood"] == "차분한" and r.json()["category"] == "카페", "일부 필드만 수정")

# ================================================================ 2. Status_Log
print("[2] status-log")
check(client.post("/api/status-log", json={"user_id": uid, "noise_db": 55.46}).status_code == 201, "기록 201")
check(client.post("/api/status-log", json={"user_id": uid, "noise_db": 200}).status_code == 422, "범위 밖 dB 422")
check(client.post("/api/status-log", json={"user_id": 9999, "noise_db": 50}).status_code == 404, "없는 사용자 404")
lst = client.get(f"/api/status-log?user_id={uid}").json()
check(len(lst) == 1 and lst[0]["noise_db"] == 55.5, "목록 조회, 소수 1자리 반올림")

# ================================================================ 3. 리포트 (시간대 GROUP BY)
print("[3] report")
day = dt.date(2026, 3, 5)
with dbmod.SessionLocal() as s:
    for hour, vals in {9: [50, 60], 14: [70, 80, 90]}.items():
        for v in vals:
            s.add(StatusLog(user_id=uid, noise_db=v, hour_bucket=f"{day.isoformat()}T{hour:02d}",
                            created_at=utcnow()))
    s.add(StatusLog(user_id=uid, noise_db=99, hour_bucket="2026-03-06T09", created_at=utcnow()))   # 다른 날짜
    s.commit()
r = client.get(f"/api/report?user_id={uid}&date=2026-03-05").json()
h = {x["hour"]: x for x in r["hours"]}
check(len(r["hours"]) == 24, "fill_empty 기본: 24시간 전부 포함")
check(h[9]["avg_db"] == 55.0 and h[9]["samples"] == 2, "9시 평균 55.0 / 2건")
check(h[14]["avg_db"] == 80.0 and h[14]["max_db"] == 90.0 and h[14]["min_db"] == 70.0, "14시 평균/최대/최소")
check(h[0]["avg_db"] is None and h[0]["samples"] == 0, "데이터 없는 시간은 null")
check(r["overall"]["samples"] == 5 and r["overall"]["avg_db"] == 70.0, "하루 전체 집계 (다른 날짜 제외)")
r = client.get(f"/api/report?user_id={uid}&date=2026-03-05&fill_empty=false&start_hour=10&end_hour=23").json()
check([x["hour"] for x in r["hours"]] == [14], "fill_empty=false + 시간 범위")
check(client.get(f"/api/report?user_id={uid}&date=2026-03-05&start_hour=20&end_hour=5").status_code == 422, "start>end 422")
check(client.get(f"/api/report?user_id={uid}&date=not-a-date").status_code == 422, "날짜 형식 오류 422")
check(client.get("/api/report?user_id=9999").status_code == 404, "없는 사용자 404")
today = client.get(f"/api/report?user_id={uid}").json()
check(today["date"] == dt.datetime.now(st.KST).date().isoformat(), "date 생략 시 오늘(KST)")

# ================================================================ 4. 음악 생성 (Replicate 모의)
print("[4] generate - 성공 경로")
wipe_tracks()
fake = FakeReplicate(polls_before_done=3); install(fake)
r = client.post("/api/tracks/generate", json={"user_id": uid, "noise_db": 80})
check(r.status_code == 202, "generate 는 즉시 202")
body = r.json(); tid = body["id"]
check("fast tempo" in body["prompt"] or "calm" in body["prompt"], "프롬프트 생성됨: " + body["prompt"])
check(body["noise_level"] == "loud" and body["noise_db_used"] == 80.0, "dB 80 -> loud")
# TestClient 는 백그라운드 작업이 끝난 뒤 반환 -> 이미 완료 상태여야 함
t = client.get(f"/api/tracks/{tid}").json()
check(t["status"] == "succeeded", "백그라운드 완료 후 status=succeeded")
check(t["audio_url"] == f"/media/track_{tid}.mp3", "audio_url 은 우리 서버 주소")
saved = settings.media_dir / f"track_{tid}.mp3"
check(saved.exists() and saved.stat().st_size == len(b"ID3FAKE-MP3-BYTES" * 100), "음원 파일이 디스크에 저장됨")
check(client.get(t["audio_url"]).content.startswith(b"ID3FAKE"), "/media 로 실제 파일 서빙")
check(not list(settings.media_dir.glob("*.part")), ".part 임시파일 남지 않음")
check(fake.polls == 3, f"폴링 {fake.polls}회 후 완료")
post_req = [x for x in fake.requests if x.method == "POST"][0]
sent = json.loads(post_req.content)
check(post_req.headers["authorization"] == "Bearer r8_test_token", "Authorization 헤더")
check(sent["version"] == settings.replicate_model_version, "version 전송")
check(sent["input"] == {"prompt": t["prompt"], "duration": 30, "output_format": "mp3"}, "input 필드 (prompt/duration/output_format)")
check(post_req.headers["cancel-after"] == "10m", "Cancel-After 상한 헤더")
dl = [x for x in fake.requests if x.url.host == "replicate.delivery"][0]
check(dl.headers.get("authorization") == "Bearer r8_test_token", "replicate.delivery 다운로드에는 토큰 포함")
with dbmod.SessionLocal() as s:
    check(s.get(Track, tid).prediction_id == "pred123", "prediction_id 저장")

print("[4b] 재생 대기열")
check(client.get(f"/api/tracks/next?user_id={uid}").json()["id"] == tid, "next = 안 틀어준 곡")
check(client.post(f"/api/tracks/{tid}/played").json()["is_played"] is True, "played 표시")
check(client.get(f"/api/tracks/next?user_id={uid}").status_code == 404, "다 틀었으면 next 404")
check(len(client.get(f"/api/tracks?user_id={uid}").json()) == 1, "목록 조회")
check(client.get("/api/tracks/9999").status_code == 404, "없는 곡 404")

print("[5] generate - dB 생략 시 최근 평균 사용")
wipe_tracks()
with dbmod.SessionLocal() as s:
    s.query(StatusLog).delete(); s.commit()
for v in (40, 44, 46):
    client.post("/api/status-log", json={"user_id": uid, "noise_db": v})
fake = FakeReplicate(polls_before_done=1); install(fake)
b = client.post("/api/tracks/generate", json={"user_id": uid}).json()
check(b["noise_db_used"] == 43.3 and b["noise_level"] == "quiet", "최근 평균 43.3dB -> quiet")
check("slow tempo" in b["prompt"], "조용하면 slow tempo 포함: " + b["prompt"])
check("calm" in b["prompt"] and "energetic" not in b["prompt"], "calm 과 energetic 이 같이 들어가지 않음")

print("[6] 중복 생성 방지")
wipe_tracks()
with dbmod.SessionLocal() as s:
    s.add(Track(user_id=uid, prompt="x", status="processing")); s.commit()
r = client.post("/api/tracks/generate", json={"user_id": uid, "noise_db": 60})
check(r.status_code == 200 and r.json()["already_generating"] is True, "생성 중이면 새로 안 만들고 200 + already_generating")
with dbmod.SessionLocal() as s:
    check(s.query(Track).count() == 1, "Track 이 늘어나지 않음 (과금 방지)")
check(client.post("/api/tracks/generate", json={"user_id": 9999}).status_code == 404, "없는 사용자 404")
check(client.post("/api/tracks/generate", json={"user_id": uid, "noise_db": 500}).status_code == 422, "dB 범위 검증")

print("[7] 서버 재시작 복구")
n = dbmod.recover_stale_tracks()
check(n == 1, "중단된 processing 곡 1개를 failed 처리")
with dbmod.SessionLocal() as s:
    t0 = s.query(Track).first()
    check(t0.status == "failed" and "재시작" in t0.error, "에러 사유 기록")

print("[8] 실패 경로")
wipe_tracks()
fake = FakeReplicate(polls_before_done=1, final="failed"); install(fake)
tid = client.post("/api/tracks/generate", json={"user_id": uid, "noise_db": 60}).json()["id"]
t = client.get(f"/api/tracks/{tid}").json()
check(t["status"] == "failed" and "model exploded" in t["error"] and t["audio_url"] is None, "Replicate failed -> Track failed + 사유")

wipe_tracks()
fake = FakeReplicate(create_status=422); install(fake)
tid = client.post("/api/tracks/generate", json={"user_id": uid, "noise_db": 60}).json()["id"]
t = client.get(f"/api/tracks/{tid}").json()
check(t["status"] == "failed" and "422" in t["error"], "생성 요청 거절 -> failed")

wipe_tracks()
settings.poll_timeout = 0.15
fake = FakeReplicate(never_done=True); install(fake)
tid = client.post("/api/tracks/generate", json={"user_id": uid, "noise_db": 60}).json()["id"]
t = client.get(f"/api/tracks/{tid}").json()
check(t["status"] == "failed" and "시간 초과" in t["error"], "시간 초과 -> failed")
check(fake.cancelled, "시간 초과 시 Replicate 작업 취소 요청")
settings.poll_timeout = 5.0

wipe_tracks()
settings.replicate_api_token = ""
fake = FakeReplicate(); install(fake)
tid = client.post("/api/tracks/generate", json={"user_id": uid, "noise_db": 60}).json()["id"]
t = client.get(f"/api/tracks/{tid}").json()
check(t["status"] == "failed" and "REPLICATE_API_TOKEN" in t["error"], "토큰 없으면 친절한 에러")
check(len(fake.requests) == 0, "토큰 없으면 외부 요청 자체를 안 보냄")
settings.replicate_api_token = "r8_test_token"

print("[9] DOWNLOAD_AUDIO=false 이면 Replicate URL 그대로 저장")
wipe_tracks()
settings.download_audio = False
fake = FakeReplicate(polls_before_done=1); install(fake)
tid = client.post("/api/tracks/generate", json={"user_id": uid, "noise_db": 60}).json()["id"]
t = client.get(f"/api/tracks/{tid}").json()
check(t["status"] == "succeeded" and t["audio_url"] == "https://replicate.delivery/x/out.mp3", "원본 URL 저장")
settings.download_audio = True

print("[10] 설정/유틸")
check(normalize_database_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db", "postgres:// 변환")
check(normalize_database_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db", "postgresql:// 변환")
check(normalize_database_url("mysql://u:p@h/db") == "mysql+pymysql://u:p@h/db", "mysql:// 변환")
check(normalize_database_url("sqlite:///x.db") == "sqlite:///x.db", "sqlite 는 그대로")
check(rc.extract_output_url({"output": ["https://a/b.mp3"]}) == "https://a/b.mp3", "output 이 리스트여도 처리")
try:
    rc.extract_output_url({"output": None}); check(False, "output None 이면 에러")
except rc.ReplicateError:
    check(True, "output None 이면 ReplicateError")

print(f"\nALL PASSED ({ok} checks) on {mode}")
if pg:
    pg.cleanup()
