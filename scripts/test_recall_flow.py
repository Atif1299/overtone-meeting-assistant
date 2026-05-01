#!/usr/bin/env python3
"""
Exercise transcript + orchestrator path without Recall (requires VOICENAV_DEV=1).

Usage (from repo root):
  export VOICENAV_DEV=1
  export RECALL_SKIP_WEBHOOK_VERIFY=true
  # if backend ADMIN_API_KEY is set, export it in this shell too
  Start backend: cd backend && .venv/bin/uvicorn main:app --port 8000

  python3 scripts/test_recall_flow.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "").strip()


def _admin_headers() -> dict[str, str]:
    if not ADMIN_API_KEY:
        return {}
    return {"X-API-Key": ADMIN_API_KEY}


def main() -> int:
    if os.getenv("VOICENAV_DEV") != "1":
        print("Set VOICENAV_DEV=1 and start the backend with that env.", file=sys.stderr)
        return 1

    req = urllib.request.Request(
        f"{BACKEND}/api/dev/seed-session",
        data=b"",
        method="POST",
        headers={"Content-Length": "0", **_admin_headers()},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            seed = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(e.read().decode(), file=sys.stderr)
        return 1

    bot_id = seed["bot_id"]
    print("Seeded session:", seed)

    payload = {
        "event": "transcript.data",
        "data": {
            "bot": {"id": bot_id},
            "data": {
                "words": [{"text": "go"}, {"text": "to"}, {"text": "slide"}, {"text": "3"}],
            },
        },
    }
    body = json.dumps(payload).encode()
    wh = urllib.request.Request(
        f"{BACKEND}/api/webhook/recall/transcript",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", **_admin_headers()},
    )
    try:
        with urllib.request.urlopen(wh, timeout=30) as resp:
            print("Webhook:", resp.read().decode())
    except urllib.error.HTTPError as e:
        print(e.read().decode(), file=sys.stderr)
        return 1

    print("Open Presentation frontend with:", seed["session_id"])
    print(f"  {os.environ.get('FRONTEND_URL', 'http://127.0.0.1:5173')}/?session={seed['session_id']}&presentation=demo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
