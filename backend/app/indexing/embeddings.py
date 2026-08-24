from __future__ import annotations

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
async def generate_embedding(text: str) -> list[float] | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        resp = await client.embeddings.create(
            model="text-embedding-3-large",
            input=text or " ",
        )
        return list(resp.data[0].embedding)
    finally:
        await client.close()
