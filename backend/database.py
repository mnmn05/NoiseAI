"""
상태 이력 저장 & 리포트 (T9)
SQLite 파일 하나(store_history.db)에 3초마다 스냅샷을 쌓고, 시간대별로 집계한다.
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
                person_count INTEGER,
                noise_db     REAL,
                crowd_level  TEXT,
                volume       INTEGER,
                track        TEXT
            )
        """)


def save_snapshot(snapshot: dict):
    """control.background_loop 가 틱마다 호출"""
    with closing(_connect()) as con, con:
        con.execute(
            "INSERT OR REPLACE INTO history VALUES (?,?,?,?,?,?)",
            (
                snapshot["updated_at"],
                snapshot["person_count"],
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
            "SELECT ts, person_count, noise_db, crowd_level, volume, track "
            "FROM history ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows][::-1]


def get_hourly_report(hours: int = 24) -> list[dict]:
    """시간대별 평균 소음/인원, 최대 인원, 혼잡도 비율(%)"""
    with closing(_connect()) as con:
        rows = con.execute(
            """
            SELECT substr(ts, 1, 13)                                   AS hour,
                   COUNT(*)                                            AS samples,
                   ROUND(AVG(noise_db), 1)                             AS avg_noise_db,
                   ROUND(MAX(noise_db), 1)                             AS max_noise_db,
                   ROUND(AVG(person_count), 1)                         AS avg_person,
                   MAX(person_count)                                   AS max_person,
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
