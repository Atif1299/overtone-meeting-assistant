#!/usr/bin/env python3
"""
Run pre-meeting readiness checks for VoiceNav.

Examples:
  python3 scripts/rehearsal_checklist.py
  VOICENAV_DEV=1 python3 scripts/rehearsal_checklist.py --simulate
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _request(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
) -> tuple[int, str]:
    payload = None
    req_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode()
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, method=method, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.status, response.read().decode()


def _safe_check(name: str, fn) -> CheckResult:
    try:
        ok, detail = fn()
        return CheckResult(name=name, ok=ok, detail=detail)
    except urllib.error.HTTPError as exc:
        return CheckResult(name=name, ok=False, detail=f"HTTP {exc.code}: {exc.reason}")
    except Exception as exc:  # pragma: no cover - runtime/infra dependent
        return CheckResult(name=name, ok=False, detail=str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description="VoiceNav live rehearsal readiness checks")
    parser.add_argument("--backend-url", default=os.environ.get("BACKEND_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--frontend-url", default=os.environ.get("FRONTEND_URL", "http://127.0.0.1:5173"))
    parser.add_argument("--dashboard-url", default=os.environ.get("DASHBOARD_URL", "http://127.0.0.1:5174"))
    parser.add_argument("--simulate", action="store_true", help="Run dev transcript simulation")
    args = parser.parse_args()

    backend = args.backend_url.rstrip("/")
    frontend = args.frontend_url.rstrip("/")
    dashboard = args.dashboard_url.rstrip("/")

    admin_key = os.environ.get("ADMIN_API_KEY", "").strip()
    auth_headers = {"X-API-Key": admin_key} if admin_key else {}

    results: list[CheckResult] = []

    results.append(
        _safe_check(
            "Backend health",
            lambda: _check_health(backend),
        )
    )
    results.append(
        _safe_check(
            "Admin presentations API",
            lambda: _check_presentations(backend, auth_headers),
        )
    )
    results.append(
        _safe_check(
            "Frontend reachable",
            lambda: _check_url(frontend),
        )
    )
    results.append(
        _safe_check(
            "Dashboard reachable",
            lambda: _check_url(dashboard),
        )
    )

    if args.simulate:
        results.append(
            _safe_check(
                "Dev transcript simulation",
                lambda: _simulate_transcript_flow(backend, auth_headers),
            )
        )

    print("VoiceNav Rehearsal Checklist")
    print("=" * 32)
    for result in results:
        icon = "PASS" if result.ok else "FAIL"
        print(f"[{icon}] {result.name}: {result.detail}")

    failed = [r for r in results if not r.ok]
    if failed:
        print(f"\nReadiness: NOT READY ({len(failed)} failing checks)")
        return 1
    print("\nReadiness: READY")
    return 0


def _check_health(backend: str) -> tuple[bool, str]:
    status, body = _request(f"{backend}/health")
    payload = json.loads(body)
    ok = status == 200 and payload.get("status") == "ok"
    detail = (
        f"status={payload.get('status')} sessions={payload.get('active_sessions')} "
        f"queue={payload.get('transcript_queue_depth')}"
    )
    return ok, detail


def _check_presentations(backend: str, headers: dict[str, str]) -> tuple[bool, str]:
    status, body = _request(f"{backend}/api/presentations", headers=headers)
    payload = json.loads(body)
    if not isinstance(payload, list):
        return False, "Unexpected payload format"
    return status == 200, f"{len(payload)} presentation(s) available"


def _check_url(url: str) -> tuple[bool, str]:
    status, _ = _request(url)
    return status == 200, f"HTTP {status}"


def _simulate_transcript_flow(backend: str, headers: dict[str, str]) -> tuple[bool, str]:
    if os.environ.get("VOICENAV_DEV") != "1":
        return False, "VOICENAV_DEV must be 1 for simulation"
    status, body = _request(
        f"{backend}/api/dev/seed-session",
        method="POST",
        headers={**headers, "Content-Length": "0"},
    )
    if status != 200:
        return False, f"seed-session HTTP {status}"
    seed = json.loads(body)
    bot_id = seed["bot_id"]
    payload = {
        "event": "transcript.data",
        "data": {
            "bot": {"id": bot_id},
            "data": {"words": [{"text": "go"}, {"text": "to"}, {"text": "slide"}, {"text": "2"}]},
        },
    }
    status2, body2 = _request(
        f"{backend}/api/webhook/recall/transcript",
        method="POST",
        body=payload,
        headers=headers,
    )
    parsed = json.loads(body2)
    return status2 == 200 and parsed.get("status") in {"ok", "ignored"}, (
        f"seeded session={seed['session_id']} webhook={parsed.get('status')}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
