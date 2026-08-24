#!/usr/bin/env bash
# Local development starter for Overtone.
# Starts backend (8001), presenter (5175), dashboard (5176).
# Press Ctrl+C to stop everything.

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/backend/.env"

PYTHON=""
if [ -x "$ROOT/backend/.venv/bin/python" ]; then
  PYTHON="$ROOT/backend/.venv/bin/python"
elif [ -x "$ROOT/backend/venv/bin/python" ]; then
  PYTHON="$ROOT/backend/venv/bin/python"
elif [ -x "$ROOT/backend/.venv/Scripts/python.exe" ]; then
  PYTHON="$ROOT/backend/.venv/Scripts/python.exe"
elif [ -x "$ROOT/backend/venv/Scripts/python.exe" ]; then
  PYTHON="$ROOT/backend/venv/Scripts/python.exe"
fi
if [ -z "$PYTHON" ]; then
  echo "ERROR: backend venv not found."
  exit 1
fi
if [ ! -d "$ROOT/presenter/node_modules" ]; then
  echo "ERROR: presenter/node_modules missing. Run: cd presenter && npm install"
  exit 1
fi
if [ ! -d "$ROOT/dashboard/node_modules" ]; then
  echo "ERROR: dashboard/node_modules missing. Run: cd dashboard && npm install"
  exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: backend/.env not found. Copy backend/.env.example to backend/.env"
  exit 1
fi

mkdir -p "$ROOT/logs"

cleanup() {
  echo ""
  echo "Stopping services..."
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting presenter -> http://127.0.0.1:5175"
(cd "$ROOT/presenter" && npm run dev) > "$ROOT/logs/presenter.log" 2>&1 &

echo "Starting dashboard -> http://127.0.0.1:5176"
(cd "$ROOT/dashboard" && npm run dev) > "$ROOT/logs/dashboard.log" 2>&1 &

echo "Starting backend   -> http://127.0.0.1:8001"
(cd "$ROOT/backend" && "$PYTHON" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001) > "$ROOT/logs/backend.log" 2>&1 &

echo "Press Ctrl+C to stop."
wait
