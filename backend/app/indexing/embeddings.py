from __future__ import annotations

import time

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

_client: AsyncOpenAI | None = None
_client_key: str | None = None
last_embed_ms: int | None = None


def openai_client() -> AsyncOpenAI:
    global _client, _client_key
    settings = get_settings()
    key = settings.openai_api_key
    if _client is None or _client_key != key:
        _client = AsyncOpenAI(api_key=key)
        _client_key = key
    return _client


async def generate_embedding(text: str, *, hot: bool = False) -> list[float] | None:
    global last_embed_ms
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    wait = wait_exponential(min=0.05, max=0.4) if hot else wait_exponential(min=1, max=10)
    timeout = 0.8 if hot else 30.0
    started = time.perf_counter()

    @retry(stop=stop_after_attempt(3), wait=wait, reraise=True)
    async def _run() -> list[float]:
        api = openai_client().with_options(timeout=timeout)
        resp = await api.embeddings.create(
            model="text-embedding-3-large",
            input=text or " ",
        )
        return list(resp.data[0].embedding)

    try:
        return await _run()
    except Exception:
        if hot:
            return None
        raise
    finally:
        last_embed_ms = int(round((time.perf_counter() - started) * 1000))
