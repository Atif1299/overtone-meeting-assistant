import time
import logging
from config import Settings
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
async def generate_embedding(text: str, settings: Settings) -> list[float] | None:
    """Generate an embedding for the text using OpenAI text-embedding-3-large with retry logic."""
    if not settings.openai_api_key:
        return None
    
    t0 = time.monotonic()
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        resp = await client.embeddings.create(model="text-embedding-3-large", input=text or " ")
        logger.info("⏱ Embed success ms=%.1f text=%r", (time.monotonic() - t0) * 1000, text[:60])
        return resp.data[0].embedding
    except Exception as e:
        logger.warning("⏱ Embed attempt FAILED ms=%.1f error=%s", (time.monotonic() - t0) * 1000, e)
        raise e # Let tenacity handle it
    finally:
        await client.close()
