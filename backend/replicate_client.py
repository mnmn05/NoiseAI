"""
T8. Replicate API (meta/musicgen) 통신 — httpx 비동기

  1) POST /predictions            -> prediction id 발급
  2) GET  /predictions/{id}       -> 3초마다 폴링 (succeeded / failed / canceled 이 될 때까지, 시간 제한 있음)
  3) output 에서 오디오 URL 꺼내기

주의: Replicate 가 준 결과 파일은 보통 1시간 뒤 삭제된다. 그래서 storage.py 가 완료 즉시 우리 서버로 내려받는다.
"""
import asyncio
import time

import httpx

from .settings import settings


class ReplicateError(Exception):
    pass


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.replicate_api_base,
        headers={"Authorization": f"Bearer {settings.replicate_api_token}"},
        timeout=httpx.Timeout(30.0),
    )


def _retry_after(resp: httpx.Response, default: float) -> float:
    try:
        return min(float(resp.headers.get("Retry-After", default)), 30.0)
    except ValueError:
        return default


async def create_prediction(client: httpx.AsyncClient, prompt: str) -> dict:
    """작업 생성. 요청이 이미 처리됐을 수 있어서(= 중복 과금) 429 와 '연결 자체 실패'일 때만 재시도한다."""
    if not settings.replicate_api_token:
        raise ReplicateError("REPLICATE_API_TOKEN 이 설정되지 않았습니다 (.env 또는 Render Environment 확인)")
    body = {
        "version": settings.replicate_model_version,
        "input": {
            "prompt": prompt,
            "duration": settings.track_duration,
            "output_format": settings.track_format,
        },
    }
    headers = {"Cancel-After": "10m"}   # 문제가 생겨도 10분 넘게 과금되지 않게 상한
    last = None
    for attempt in range(3):
        try:
            resp = await client.post("/predictions", json=body, headers=headers)
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            last = f"연결 실패: {e}"
            await asyncio.sleep(1 + attempt)
            continue
        if resp.status_code == 429:
            last = "요청 한도 초과(429)"
            await asyncio.sleep(_retry_after(resp, 2.0))
            continue
        if resp.status_code >= 400:
            raise ReplicateError(f"Replicate 요청 실패 {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if not data.get("id"):
            raise ReplicateError(f"Replicate 응답에 id 가 없음: {str(data)[:300]}")
        return data
    raise ReplicateError(f"Replicate 요청을 3번 시도했지만 실패: {last}")


async def _get_prediction(client: httpx.AsyncClient, prediction_id: str) -> dict:
    """상태 조회. 일시적인 네트워크 오류/5xx/429 는 몇 번 재시도한다 (조회는 여러 번 해도 안전)."""
    last = None
    for attempt in range(4):
        try:
            resp = await client.get(f"/predictions/{prediction_id}")
        except httpx.TransportError as e:
            last = f"네트워크 오류: {e}"
            await asyncio.sleep(1 + attempt)
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            last = f"HTTP {resp.status_code}"
            await asyncio.sleep(_retry_after(resp, 2.0))
            continue
        if resp.status_code >= 400:
            raise ReplicateError(f"Replicate 조회 실패 {resp.status_code}: {resp.text[:300]}")
        return resp.json()
    raise ReplicateError(f"Replicate 상태 조회를 반복 시도했지만 실패: {last}")


async def wait_for_prediction(client: httpx.AsyncClient, prediction_id: str) -> dict:
    deadline = time.monotonic() + settings.poll_timeout
    while True:
        data = await _get_prediction(client, prediction_id)
        status = data.get("status")
        if status == "succeeded":
            return data
        if status in ("failed", "canceled"):
            raise ReplicateError(f"Replicate 작업 {status}: {data.get('error')}")
        if time.monotonic() >= deadline:
            try:
                await client.post(f"/predictions/{prediction_id}/cancel")   # 더 과금되지 않게 취소
            except httpx.HTTPError:
                pass
            raise ReplicateError(f"Replicate 응답 대기 시간 초과 ({settings.poll_timeout:.0f}초)")
        await asyncio.sleep(settings.poll_interval)


def extract_output_url(data: dict) -> str:
    out = data.get("output")
    if isinstance(out, str) and out:
        return out
    if isinstance(out, list):
        for item in out:
            if isinstance(item, str) and item:
                return item
    if isinstance(out, dict):
        for item in out.values():
            if isinstance(item, str) and item.startswith("http"):
                return item
    raise ReplicateError("완료됐지만 output(오디오 URL)이 비어 있음 (생성 후 1시간이 지나 삭제됐을 수 있음)")
