"""
기본 BGM 초기 큐 API (T2)

  GET /api/bgm/playlist?user_id=1     (user_id 는 생략 가능)
  -> 첫 AI 곡이 만들어지기 전까지 돌릴 기본곡 목록을 재생 순서대로 돌려준다.

-------------------------------------------------------------------
적용 방법: backend/main.py 에 2줄만 추가하면 된다.

  1) import 모음, `from .routers import report, status_log, tracks, users` 바로 아래
       from .routers import bgm as bgm_router    # T2 기본 BGM 라우터 (초기 재생 큐)

  2) `app.include_router(report.router)` 바로 아래
       bgm_router.install(app)    # T2: /api/bgm/playlist 등록 + 기본곡 mp3 를 /bgm/<파일명> 으로 제공

(선택) 기본곡 mp3 를 git 에 올리려면 .gitignore 맨 아래에 한 줄 추가
       !backend/assets/bgm/*.mp3
-------------------------------------------------------------------
"""
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .. import bgm_pool, control
from ..db import get_db
from ..models import User

router = APIRouter(prefix="/api/bgm", tags=["bgm"])


@router.get("/playlist")
def default_playlist(user_id: int | None = None, db: Session = Depends(get_db)):
    # user_id 가 있으면 그 매장의 업종/분위기/연령대에 맞는 곡을 앞에 둔다
    category = mood = age_group = None
    if user_id is not None:
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(404, "사용자를 찾을 수 없습니다")
        category, mood, age_group = user.category, user.mood, user.age_group

    level = control.get_status()["crowd_level"]    # 지금 혼잡도 (quiet / normal / busy)
    return {"crowd_level": level, "tracks": bgm_pool.default_playlist(level, category, mood, age_group)}


def install(app: FastAPI) -> None:
    """main.py 에서 호출 — 라우터 등록 + 기본곡 오디오 폴더를 /bgm 으로 공개"""
    bgm_pool.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/bgm", StaticFiles(directory=bgm_pool.AUDIO_DIR), name="bgm")
    app.include_router(router)
