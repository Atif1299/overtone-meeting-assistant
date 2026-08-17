#!/usr/bin/env bash
# Local development starter for VoiceNav / Overtone.
# Starts backend (8000), frontend (5173), dashboard (5174), and two cloudflared
# tunnels. Tunnel URLs are written back into backend/.env automatically so
# Recall.ai webhooks always point at the live tunnels.
# Press Ctrl+C to stop everything.

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/backend/.env"

# ── sanity checks ────────────────────────────────────────────────────────────
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
  echo "ERROR: backend venv not found. Run:"
  echo "  cd backend && python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "ERROR: frontend/node_modules missing. Run: cd frontend && npm install"
  exit 1
fi
if [ ! -d "$ROOT/dashboard/node_modules" ]; then
  echo "ERROR: dashboard/node_modules missing. Run: cd dashboard && npm install"
  exit 1
fi
if ! command -v cloudflared &>/dev/null; then
  echo "ERROR: cloudflared not found. Run: brew install cloudflared"
  exit 1
fi

# ── helpers ───────────────────────────────────────────────────────────────────
set_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

wait_for_tunnel_url() {
  local log="$1"
  for i in $(seq 1 30); do
    local url
    url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$log" 2>/dev/null | head -1)
    if [ -n "$url" ]; then echo "$url"; return 0; fi
    sleep 1
  done
  echo ""
}

# ── local data dirs (idempotent) ─────────────────────────────────────────────
mkdir -p "$ROOT/backend/data" "$ROOT/backend/presentations" "$ROOT/backend/generated_audio" "$ROOT/logs"

ALL_PIDS=()

cleanup() {
  echo ""
  echo "Stopping services…"
  kill "${ALL_PIDS[@]}" 2>/dev/null || true
  wait 2>/dev/null
  echo "Done."
}
trap cleanup INT TERM

# ── cloudflared tunnels ───────────────────────────────────────────────────────
echo "Starting tunnels…"
cloudflared tunnel --url http://localhost:8000 --no-autoupdate > /tmp/cf-backend.log 2>&1 &
ALL_PIDS+=($!)
cloudflared tunnel --url http://localhost:5173 --no-autoupdate > /tmp/cf-frontend.log 2>&1 &
ALL_PIDS+=($!)

# ── app services ─────────────────────────────────────────────────────────────
echo "Starting frontend → http://127.0.0.1:5173  (log: logs/frontend.log)"
cd "$ROOT/frontend" && npm run dev > "$ROOT/logs/frontend.log" 2>&1 &
ALL_PIDS+=($!)

echo "Starting dashboard→ http://127.0.0.1:5174  (log: logs/dashboard.log)"
cd "$ROOT/dashboard" && npm run dev > "$ROOT/logs/dashboard.log" 2>&1 &
ALL_PIDS+=($!)

# ── wait for tunnel URLs ──────────────────────────────────────────────────────
echo "Waiting for tunnel URLs…"
BACKEND_TUNNEL=$(wait_for_tunnel_url /tmp/cf-backend.log)
FRONTEND_TUNNEL=$(wait_for_tunnel_url /tmp/cf-frontend.log)

if [ -z "$BACKEND_TUNNEL" ] || [ -z "$FRONTEND_TUNNEL" ]; then
  echo "ERROR: Tunnels did not start in time. Check /tmp/cf-backend.log and /tmp/cf-frontend.log"
  cleanup; exit 1
fi

# ── patch .env with live tunnel URLs ─────────────────────────────────────────
echo "Patching backend/.env with tunnel URLs…"
set_env "BACKEND_URL"  "$BACKEND_TUNNEL"
set_env "FRONTEND_URL" "$FRONTEND_TUNNEL"
set_env "CORS_ALLOWED_ORIGINS" \
  "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174,${FRONTEND_TUNNEL}"

# ── update Azure Blob CORS with live origins ─────────────────────────────────
echo "Updating Azure Blob CORS rules…"
cd "$ROOT/backend"
"$PYTHON" "$ROOT/scripts/update_blob_cors.py"

# ── start backend (after env is patched) ─────────────────────────────────────
echo "Starting backend  → http://127.0.0.1:8000  (log: logs/backend.log)"
cd "$ROOT/backend"
"$PYTHON" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 > "$ROOT/logs/backend.log" 2>&1 &
ALL_PIDS+=($!)

# ── health check ─────────────────────────────────────────────────────────────
echo "Waiting for backend to be ready…"
for i in $(seq 1 15); do
  if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then break; fi
  sleep 1
done

if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
  echo "✓ Backend healthy"
else
  echo "⚠ Backend not yet responding — check logs/backend.log"
fi

# ── summary ───────────────────────────────────────────────────────────────────
echo ""
echo "┌─────────────────────────────────────────────────────────────────┐"
echo "│  Local                                                          │"
echo "│    API docs   http://127.0.0.1:8000/docs                        │"
echo "│    Frontend   http://127.0.0.1:5173                             │"
echo "│    Dashboard  http://127.0.0.1:5174                             │"
echo "│                                                                 │"
echo "│  Public (Recall webhooks)                                       │"
printf "│    Backend    %-52s│\n" "$BACKEND_TUNNEL"
printf "│    Frontend   %-52s│\n" "$FRONTEND_TUNNEL"
echo "│                                                                 │"
echo "│  Recall webhook URL (paste in Recall dashboard):               │"
printf "│    %-64s│\n" "${BACKEND_TUNNEL}/api/webhook/recall/bot-status"
echo "└─────────────────────────────────────────────────────────────────┘"
echo ""
echo "Press Ctrl+C to stop all services."

wait
