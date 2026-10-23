"""
생성된 음원을 우리 서버(media 폴더)에 저장하고 /media/... 주소를 돌려준다.

왜 필요한가: Replicate 결과 파일은 생성 후 약 1시간 뒤 삭제된다. URL 만 DB 에 넣으면 나중에 재생이 안 된다.
주의: Render 무료 웹서비스의 디스크는 재배포/재시작 때 초기화된다. 오래 보관하려면 S3/Cloudflare R2/Supabase Storage 같은
      외부 저장소로 바꿔야 한다 (그때는 이 파일의 save_remote_audio 만 교체하면 됨).
"""
from urllib.parse import urlparse

import httpx

from .settings import settings


def make_download_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True)


def media_url(filename: str) -> str:
    return f"{settings.public_base_url}/media/{filename}"


async def save_remote_audio(url: str, track_id: int) -> str:
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    filename = f"track_{track_id}.{settings.track_format}"
    dest = settings.media_dir / filename
    tmp = dest.with_name(dest.name + ".part")

    host = urlparse(url).hostname or ""
    headers = {}
    if host.endswith("replicate.com") or host.endswith("replicate.delivery"):
        headers["Authorization"] = f"Bearer {settings.replicate_api_token}"

    try:
        async with make_download_client() as client:
            async with client.stream("GET", url, headers=headers) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
        if tmp.stat().st_size == 0:
            raise RuntimeError("내려받은 오디오 파일이 비어 있음")
        tmp.replace(dest)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return media_url(filename)
