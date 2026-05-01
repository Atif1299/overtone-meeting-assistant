from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def client() -> TestClient:
    test_agents_db = ROOT / ".pytest_agents.db"
    if test_agents_db.exists():
        test_agents_db.unlink()
    os.environ["RECALL_SKIP_WEBHOOK_VERIFY"] = "true"
    os.environ["RECALL_WEBHOOK_SECRET"] = ""
    os.environ["RECALL_API_KEY"] = ""
    os.environ["VOICENAV_DEV"] = "0"
    os.environ["AGENTS_DB_PATH"] = str(test_agents_db)
    os.environ["ANTHROPIC_API_KEY"] = ""
    os.environ["AZURE_BLOB_ACCOUNT_URL"] = ""
    os.environ["AZURE_BLOB_ACCOUNT_KEY"] = ""

    from config import get_settings

    get_settings.cache_clear()

    from main import app

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_runtime_state() -> None:
    from services.agent_store import agent_store
    from config import get_settings
    from orchestrator.engine import clear_queue
    from services.event_dedupe import event_deduper
    from services.index_jobs import reset_index_jobs_for_tests
    from services.session_store import store

    get_settings().admin_api_key = ""
    reset_index_jobs_for_tests()
    asyncio.run(store.clear())
    asyncio.run(event_deduper.clear())
    asyncio.run(clear_queue())
    agent_store.reset_for_tests()
