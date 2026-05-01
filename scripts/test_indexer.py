#!/usr/bin/env python3
"""Quick local check for indexing and retrieval."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


async def main() -> int:
    try:
        from indexer.pipeline import run_index_job
        from orchestrator.rag_retriever import search_presentation
        from services import storage as storage_mod
    except ModuleNotFoundError as exc:
        print(
            "Missing backend dependencies. Run from backend virtualenv, e.g.: "
            "cd backend && source .venv/bin/activate && cd .. && python3 scripts/test_indexer.py",
            file=sys.stderr,
        )
        print(f"Import error: {exc}", file=sys.stderr)
        return 1

    fixture_path = BACKEND / "presentations" / "fixture-index.txt"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(
        "VoiceNav overview. Slide 1 covers architecture. "
        "Slide 2 covers integration testing and webhooks."
    )

    summary = storage_mod.save_upload("fixture-index.txt", fixture_path.read_bytes())
    await run_index_job(summary.presentation_id)
    hits = await search_presentation("integration testing webhooks", summary.presentation_id)
    print(json.dumps({"presentation_id": summary.presentation_id, "hits": hits[:2]}, indent=2))
    return 0 if hits else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
