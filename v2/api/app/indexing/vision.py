from __future__ import annotations

import asyncio
import base64
import json
import re
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

SLIDE_PROMPT = """Extract structured metadata from this presentation slide image.
Return ONLY valid JSON with keys:
page_number (int), title (str), description (str), content (str), speaker_notes (str),
data_points (list of str), section_label (str), has_table (bool), has_chart (bool), has_diagram (bool).
page_number should be {page_number} of {total_pages}. Filename: {filename}.
Be thorough — put all readable text into content/searchable fields."""


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        from json_repair import loads as repair_loads

        return repair_loads(text)


def _stub(page_number: int, err: str) -> dict:
    return {
        "page_number": page_number,
        "title": f"Slide {page_number}",
        "description": "",
        "content": "",
        "speaker_notes": "",
        "data_points": [],
        "section_label": "overview",
        "_extraction_failed": True,
        "_error": err,
    }


def is_stub_page(page: dict) -> bool:
    if page.get("_extraction_failed"):
        return True
    title = (page.get("title") or "").strip()
    content = (page.get("content") or page.get("searchable_content") or "").strip()
    if re.fullmatch(r"Slide\s+\d+", title, flags=re.I) and len(content) < 20:
        return True
    return len(content) < 8 and len(title) < 3


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
async def _openai_page(image_path: Path, page_number: int, total_pages: int, filename: str) -> dict:
    from openai import AsyncOpenAI

    settings = get_settings()
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        resp = await client.chat.completions.create(
            model=settings.indexer_llm_model or "gpt-4o",
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        {
                            "type": "text",
                            "text": SLIDE_PROMPT.format(
                                page_number=page_number, total_pages=total_pages, filename=filename
                            ),
                        },
                    ],
                }
            ],
        )
        data = _parse_json(resp.choices[0].message.content or "{}")
        data["page_number"] = page_number
        return data
    finally:
        await client.close()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
async def _gemini_page(image_path: Path, page_number: int, total_pages: int, filename: str) -> dict:
    from google import genai
    from google.genai import types

    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = SLIDE_PROMPT.format(page_number=page_number, total_pages=total_pages, filename=filename)
    resp = await client.aio.models.generate_content(
        model=settings.gemini_vision_model,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_bytes(data=image_path.read_bytes(), mime_type="image/png"),
                    types.Part.from_text(text=prompt),
                ]
            )
        ],
        config=types.GenerateContentConfig(max_output_tokens=8192),
    )
    text = getattr(resp, "text", None) or ""
    data = _parse_json(text)
    data["page_number"] = page_number
    return data


async def extract_all_pages(
    *,
    page_images: list[Path],
    filename: str,
    provider: str,
) -> list[dict]:
    settings = get_settings()
    sem = asyncio.Semaphore(settings.indexer_vision_concurrency)
    total = len(page_images)

    async def one(i: int, path: Path) -> dict:
        async with sem:
            try:
                if provider == "gemini":
                    return await _gemini_page(path, i, total, filename)
                return await _openai_page(path, i, total, filename)
            except Exception as exc:  # noqa: BLE001
                return _stub(i, str(exc))

    return list(await asyncio.gather(*[one(i, p) for i, p in enumerate(page_images, start=1)]))
