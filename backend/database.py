"""
상태 이력 저장 & 리포트 (T8)
SQLite 파일 하나(store_history.db)에 3초마다 스냅샷을 쌓고, 시간대별로 집계한다.

※    예전 버전으로 만들어진 DB 파일이 있어도 init_db()가 알아서 정리한다.
"""
import sqlite3
from contextlib import closing

from . import config


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with closing(_connect()) as con, con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS history (
                ts           TEXT PRIMARY KEY,   -- 2026-09-21T14:32:10+09:00
                noise_db     REAL,
                crowd_level  TEXT,
                volume       INTEGER,
                track        TEXT
            )
        """)
        # 예전 DB(person_count 컬럼 있음)라면 컬럼 제거. 실패해도(구버전 SQLite)
        # 저장/조회는 컬럼 이름을 직접 지정하므로 정상 동작한다.
        cols = [r["name"] for r in con.execute("PRAGMA table_info(history)")]
        if "person_count" in cols:
            try:
                con.execute("ALTER TABLE history DROP COLUMN person_count")
            except sqlite3.OperationalError:
                pass


def save_snapshot(snapshot: dict):
    """control.background_loop 가 틱마다 호출"""
    with closing(_connect()) as con, con:
        con.execute(
            "INSERT OR REPLACE INTO history (ts, noise_db, crowd_level, volume, track) "
            "VALUES (?,?,?,?,?)",
            (
                snapshot["updated_at"],
                snapshot["noise_level_db"],
                snapshot["crowd_level"],
                snapshot["current_volume"],
                snapshot["current_track"],
            ),
        )


def get_history(limit: int = 200) -> list[dict]:
    """최근 limit개를 오래된 순서로 반환 (그래프 그리기 편하게)"""
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT ts, noise_db, crowd_level, volume, track "
            "FROM history ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows][::-1]


def get_hourly_report(hours: int = 24) -> list[dict]:
    """시간대별 평균/최대 소음, 혼잡도 비율(%)"""
    with closing(_connect()) as con:
        rows = con.execute(
            """
            SELECT substr(ts, 1, 13)                                   AS hour,
                   COUNT(*)                                            AS samples,
                   ROUND(AVG(noise_db), 1)                             AS avg_noise_db,
                   ROUND(MAX(noise_db), 1)                             AS max_noise_db,
                   ROUND(100.0 * SUM(crowd_level = 'busy')   / COUNT(*), 1) AS busy_pct,
                   ROUND(100.0 * SUM(crowd_level = 'normal') / COUNT(*), 1) AS normal_pct,
                   ROUND(100.0 * SUM(crowd_level = 'quiet')  / COUNT(*), 1) AS quiet_pct
            FROM history
            GROUP BY hour
            ORDER BY hour DESC
            LIMIT ?
            """,
            (hours,),
        ).fetchall()
    return [dict(r) for r in rows][::-1]