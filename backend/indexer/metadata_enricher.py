"""Vision per-page metadata extraction for presentation slides (OpenAI or Gemini)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from pathlib import Path

import json_repair

logger = logging.getLogger(__name__)

VISION_MODEL = "gpt-4o"
CLAUDE_MODEL = VISION_MODEL  # backward-compatible alias

SLIDE_EXTRACTION_PROMPT = """You are a presentation slide analyzer. You are looking at slide {page_number} of {total_pages} from the file "{filename}".

Analyze this slide image thoroughly. Extract ALL information visible on the slide — text, data in tables, chart values, diagram labels, image descriptions, everything.

Return a JSON object with this exact structure:

{{
  "page_number": {page_number},
  "title": "A clear, concise title for this slide (max 10 words). If the slide has a visible title, use it verbatim.",
  "description": "2-3 sentence description of what this slide communicates. Be specific — mention key points, not just 'This slide discusses X'.",
  "tag": "One of: overview | deep-dive | transition | appendix | cover. Choose the most appropriate tag.",
  "speaker_notes": "Write detailed, natural-language speaker notes for a presenter. 3-5 sentences. Include key numbers, trends, and talking points that support the slide content. The presenter should be able to speak confidently from these notes alone.",
  "layout": "Describe the slide layout, e.g.: kpi_grid_with_yoy | single_chart_full_width | two_column_comparison | bullet_list | image_with_caption | table | title_only | mixed",
  "data_points": {{
    "Key Metric Name": {{"value": "actual value", "yoy": "+/-X%", "direction": "up_good|up_bad|down_good|down_bad"}},
    "Simple Metric": "plain string value if no YoY context"
  }},
  "visuals": [
    {{
      "visual_id": "chart_p{page_number}_descriptive_name",
      "chart_type": "bar_chart | line_chart | pie_chart | waterfall_chart | scatter_plot | table | diagram | image",
      "description": "Detailed description of the visual: what it shows, key data points, trends, colors, labels.",
      "x_axis": {{"label": "axis label", "unit": "unit"}},
      "y_axis": {{"label": "axis label", "unit": "unit"}}
    }}
  ],
  "key_topics": ["topic1", "topic2", "topic3"],
  "entities": ["All named entities: company names, product names, people, technologies, specific numbers/metrics"],
  "content_text": "Complete text extraction of everything on the slide. Include ALL text — headings, bullet points, labels, footnotes, annotations. Preserve the logical structure with line breaks.",
  "has_table": false,
  "has_chart": false,
  "has_diagram": false,
  "searchable_content": "A single dense paragraph capturing ALL important information from this slide. Include: title, all key points, all data values, entity names, chart trends, table contents. A reader must understand the full slide content from this paragraph alone.",
  "questions_answered": ["List 4-6 specific questions that a presentation audience might ask that this slide directly answers. Match vocabulary an executive would use."]
}}

RULES:
- If there are NO data points with YoY context, set data_points to {{}} (empty object)
- If there are NO visuals/charts/diagrams, set visuals to [] (empty array)
- Extract EVERY piece of text visible on the slide, including small annotations and footnotes
- For charts, include actual data values and trends observed
- The searchable_content field is critical — it must be comprehensive
- Return ONLY valid JSON, no markdown code fences, no preamble"""


DOCUMENT_METADATA_PROMPT = """You are a presentation document analyzer. You have been given the extracted text content of each slide in a presentation.

Based on the slide contents below, generate document-level metadata.

Slides summary:
{slides_summary}

Return a JSON object with this exact structure:
{{
  "title": "Full descriptive title of the presentation",
  "account_name": "Company or organization name if identifiable, else null",
  "industry": "Industry category, e.g. 'B2B SaaS — Data Infrastructure', else null",
  "date_range": "Date range covered if apparent, e.g. 'Jan 1 – Jun 30, 2026', else null",
  "total_pages": {total_pages},
  "currency": "Currency used (e.g. USD, EUR) if financial data present, else null",
  "page_dimensions": {{
    "width": 1280,
    "height": 720,
    "aspect_ratio": "16:9",
    "format": "landscape_slide",
    "intended_use": "screen_sharing_presentation"
  }},
  "glossary": {{
    "TERM": "Definition — include all abbreviations and domain-specific terms found in the slides"
  }},
  "known_contradictions": [
    {{
      "summary": "Description of any apparent contradiction or tension between slides",
      "referenced_pages": [1, 2]
    }}
  ]
}}

RULES:
- If no glossary terms are found, set glossary to {{}}
- If no contradictions are apparent, set known_contradictions to []
- Return ONLY valid JSON, no markdown code fences, no preamble"""


def _read_image(path: str) -> str:
    """Synchronously read and encode image file to base64."""
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def _parse_json_response(text: str, context: str = "") -> dict:
    """Parse JSON from a Vision model response.

    Attempts in order:
    1. Direct parse after stripping code fences.
    2. json_repair — handles trailing commas, truncated strings, unescaped quotes.
    """
    ctx = f" for {context}" if context else ""

    # Strip markdown fences first
    clean = re.sub(r"^```(?:json)?\s*", "", text.strip())
    clean = re.sub(r"\s*```$", "", clean).strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Attempt repair before giving up
    logger.warning("JSON parse failed%s — attempting repair", ctx)
    repaired = json_repair.loads(clean)
    if isinstance(repaired, dict):
        return repaired

    raise json.JSONDecodeError(f"Unable to parse JSON response{ctx}", text, 0)


def _completion_text(response) -> str:
    if getattr(response, "choices", None):
        return str(response.choices[0].message.content or "")
    content = getattr(response, "content", None)
    if content:
        return str(content[0].text)
    return str(response)


async def extract_slide_metadata(
    *,
    image_path: str,
    page_number: int,
    total_pages: int,
    filename: str,
    client,
    model: str = VISION_MODEL,
) -> dict:
    """Send one slide image to OpenAI Vision and return structured metadata dict."""
    image_data = await asyncio.to_thread(_read_image, image_path)

    prompt = SLIDE_EXTRACTION_PROMPT.format(
        page_number=page_number,
        total_pages=total_pages,
        filename=filename,
    )

    response = await client.chat.completions.create(
        model=model,
        max_tokens=8192,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_data}",
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    return _parse_json_response(_completion_text(response), f"page {page_number}")


async def extract_document_metadata(
    *,
    page_metadatas: list[dict],
    total_pages: int,
    client,
    model: str = VISION_MODEL,
) -> dict:
    """Generate document-level metadata from already-extracted per-page metadata."""
    slides_summary = "\n\n".join(
        f"Slide {m.get('page_number', i+1)}: {m.get('title', '')} — {m.get('description', '')}\n"
        f"Content: {(m.get('content_text') or m.get('searchable_content') or '')[:500]}"
        for i, m in enumerate(page_metadatas)
    )

    prompt = DOCUMENT_METADATA_PROMPT.format(
        slides_summary=slides_summary,
        total_pages=total_pages,
    )

    response = await client.chat.completions.create(
        model=model,
        max_tokens=2048,
        messages=[
            {"role": "user", "content": prompt},
        ],
    )

    return _parse_json_response(_completion_text(response), "document metadata")


async def extract_all_pages(
    *,
    page_images: list[str],
    filename: str,
    client,
    concurrency: int = 3,
    on_progress=None,
    model: str = VISION_MODEL,
) -> list[dict]:
    """Extract metadata for all pages with a concurrency limit (OpenAI Vision)."""
    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict | None] = [None] * len(page_images)

    async def process_page(index: int, image_path: str) -> None:
        async with semaphore:
            max_attempts = 3
            last_error: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    metadata = await extract_slide_metadata(
                        image_path=image_path,
                        page_number=index + 1,
                        total_pages=len(page_images),
                        filename=filename,
                        client=client,
                        model=model,
                    )
                    results[index] = metadata
                    logger.info("Vision extracted page %d/%d", index + 1, len(page_images))
                    if on_progress:
                        await on_progress(
                            phase="enriching",
                            progress=(index + 1) / len(page_images),
                            current_page=index + 1,
                        )
                    return
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if attempt < max_attempts:
                        wait = 2 ** attempt
                        logger.warning(
                            "Page %d Vision attempt %d/%d failed (%s) — retrying in %ds",
                            index + 1, attempt, max_attempts, exc, wait,
                        )
                        await asyncio.sleep(wait)

            logger.error(
                "Page %d Vision failed after %d attempts: %s — inserting stub entry",
                index + 1, max_attempts, last_error,
            )
            results[index] = {
                "page_number": index + 1,
                "title": f"Slide {index + 1}",
                "description": "",
                "tag": "overview",
                "speaker_notes": "",
                "layout": "unknown",
                "data_points": {},
                "visuals": [],
                "key_topics": [],
                "entities": [],
                "content_text": "",
                "has_table": False,
                "has_chart": False,
                "has_diagram": False,
                "searchable_content": "",
                "questions_answered": [],
                "_extraction_failed": True,
            }

    await asyncio.gather(*[process_page(i, p) for i, p in enumerate(page_images)])
    return [r for r in results if r is not None]


async def extract_slide_metadata_gemini(
    *,
    image_path: str,
    page_number: int,
    total_pages: int,
    filename: str,
    client,
    model: str,
) -> dict:
    """Send one slide image to Gemini Vision and return structured metadata dict."""
    from google.genai import types

    image_bytes = await asyncio.to_thread(Path(image_path).read_bytes)
    prompt = SLIDE_EXTRACTION_PROMPT.format(
        page_number=page_number,
        total_pages=total_pages,
        filename=filename,
    )
    response = await client.aio.models.generate_content(
        model=model,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    types.Part.from_text(text=prompt),
                ],
            )
        ],
        config=types.GenerateContentConfig(max_output_tokens=8192),
    )
    text = getattr(response, "text", None) or ""
    if not text and getattr(response, "candidates", None):
        parts = response.candidates[0].content.parts or []
        text = "".join(str(getattr(p, "text", "") or "") for p in parts)
    return _parse_json_response(text, f"page {page_number}")


async def extract_document_metadata_gemini(
    *,
    page_metadatas: list[dict],
    total_pages: int,
    client,
    model: str,
) -> dict:
    """Generate document-level metadata via Gemini text model."""
    from google.genai import types

    slides_summary = "\n\n".join(
        f"Slide {m.get('page_number', i+1)}: {m.get('title', '')} — {m.get('description', '')}\n"
        f"Content: {(m.get('content_text') or m.get('searchable_content') or '')[:500]}"
        for i, m in enumerate(page_metadatas)
    )
    prompt = DOCUMENT_METADATA_PROMPT.format(
        slides_summary=slides_summary,
        total_pages=total_pages,
    )
    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=2048),
    )
    text = getattr(response, "text", None) or ""
    return _parse_json_response(text, "document metadata")


async def extract_all_pages_gemini(
    *,
    page_images: list[str],
    filename: str,
    client,
    concurrency: int = 3,
    on_progress=None,
    model: str,
) -> list[dict]:
    """Extract metadata for all pages via Gemini Vision with a concurrency limit."""
    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict | None] = [None] * len(page_images)

    async def process_page(index: int, image_path: str) -> None:
        async with semaphore:
            max_attempts = 3
            last_error: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    metadata = await extract_slide_metadata_gemini(
                        image_path=image_path,
                        page_number=index + 1,
                        total_pages=len(page_images),
                        filename=filename,
                        client=client,
                        model=model,
                    )
                    results[index] = metadata
                    logger.info("Gemini Vision extracted page %d/%d", index + 1, len(page_images))
                    if on_progress:
                        await on_progress(
                            phase="enriching",
                            progress=(index + 1) / len(page_images),
                            current_page=index + 1,
                        )
                    return
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if attempt < max_attempts:
                        wait = 2 ** attempt
                        logger.warning(
                            "Page %d Gemini Vision attempt %d/%d failed (%s) — retrying in %ds",
                            index + 1, attempt, max_attempts, exc, wait,
                        )
                        await asyncio.sleep(wait)

            logger.error(
                "Page %d Gemini Vision failed after %d attempts: %s — inserting stub entry",
                index + 1, max_attempts, last_error,
            )
            results[index] = {
                "page_number": index + 1,
                "title": f"Slide {index + 1}",
                "description": "",
                "tag": "overview",
                "speaker_notes": "",
                "layout": "unknown",
                "data_points": {},
                "visuals": [],
                "key_topics": [],
                "entities": [],
                "content_text": "",
                "has_table": False,
                "has_chart": False,
                "has_diagram": False,
                "searchable_content": "",
                "questions_answered": [],
                "_extraction_failed": True,
            }

    await asyncio.gather(*[process_page(i, p) for i, p in enumerate(page_images)])
    return [r for r in results if r is not None]
