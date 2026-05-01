# Overtone — Developer Setup Guide

Step-by-step instructions to run the full system locally from a fresh clone.

---

## Prerequisites

Install these before starting:

| Tool | Install (macOS) | Purpose |
|------|----------------|---------|
| Python 3.11+ | `brew install python@3.11` | Backend runtime |
| Node.js 20+ | `brew install node` | Frontend + dashboard |
| LibreOffice | `brew install --cask libreoffice` | PPTX → PDF conversion |
| Poppler | `brew install poppler` | PDF → PNG rendering (`pdftoppm`) |
| cloudflared | `brew install cloudflared` | Public tunnels for Recall.ai |

Verify:
```bash
python3.11 --version   # 3.11.x or higher
node --version          # 20.x or higher
soffice --version       # LibreOffice 7.x+
pdftoppm -v             # poppler utils
cloudflared --version   # any recent version
```

---

## Step 1: Clone the repo

```bash
git clone https://github.com/abhanu1998/overtone.git
cd overtone
```

---

## Step 2: Install backend dependencies

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

---

## Step 3: Install frontend + dashboard dependencies

```bash
cd frontend && npm install && cd ..
cd dashboard && npm install && cd ..
```

---

## Step 4: Configure environment variables

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and fill in ALL of these keys:

### Required keys

| Key | Where to get it |
|-----|-----------------|
| `RECALL_API_KEY` | [Recall.ai dashboard](https://recall.ai) → API Keys |
| `OPENAI_API_KEY` | [OpenAI platform](https://platform.openai.com/api-keys) |
| `ANTHROPIC_API_KEY` | [Anthropic console](https://console.anthropic.com/settings/keys) |
| `AZURE_SEARCH_ENDPOINT` | Azure portal → your AI Search service → Overview → URL (e.g. `https://my-search.search.windows.net`) |
| `AZURE_SEARCH_KEY` | Azure portal → your AI Search service → Keys → Primary admin key |
| `AZURE_BLOB_ACCOUNT_URL` | Azure portal → your Storage account → Overview (e.g. `https://myaccount.blob.core.windows.net`) |
| `AZURE_BLOB_ACCOUNT_KEY` | Azure portal → your Storage account → Access keys → Key 1 |
| `ADMIN_API_KEY` | Generate any random string (e.g. `openssl rand -base64 32`). Used to authenticate dashboard → backend API calls. |

### Optional but recommended

| Key | Default | Notes |
|-----|---------|-------|
| `OPENAI_REALTIME_MODEL` | `gpt-4o-realtime-preview-2024-12-17` | Can use `gpt-realtime-1.5` for newer model |
| `OPENAI_REALTIME_VOICE` | `alloy` | Options: `alloy`, `coral`, `echo`, `shimmer` |
| `RECALL_SKIP_WEBHOOK_VERIFY` | `false` | Set `true` for local dev (skips webhook signature check) |
| `INDEXER_VISION_CONCURRENCY` | `3` | Parallel Claude Vision calls during indexing |

### Azure setup notes

**Azure AI Search:**
1. Create a resource in Azure portal (Free tier works for dev)
2. The index `overtone` is auto-created on first indexing run
3. You need the **admin key** (not query key) because the app creates/manages the index

**Azure Blob Storage:**
1. Create a Storage Account in Azure portal
2. Create a container named `presentations` (or set `AZURE_BLOB_CONTAINER_NAME` to your name)
3. CORS is auto-configured by `start-local.sh` on each run

---

## Step 5: Run everything

```bash
./start-local.sh
```

This script does everything automatically:
1. Starts two cloudflared tunnels (backend port 8000 + frontend port 5173)
2. Waits for tunnel URLs to resolve (~5-10 seconds)
3. Patches `backend/.env` with the live tunnel URLs and CORS origins
4. Updates Azure Blob Storage CORS rules for the new tunnel domains
5. Starts the backend (uvicorn on port 8000)
6. Starts the frontend (Vite on port 5173)
7. Starts the dashboard (Vite on port 5174)
8. Prints a summary table with all URLs

You should see output like:
```
┌─────────────────────────────────────────────────────────────────┐
│  Local                                                          │
│    API docs   http://127.0.0.1:8000/docs                        │
│    Frontend   http://127.0.0.1:5173                             │
│    Dashboard  http://127.0.0.1:5174                             │
│                                                                 │
│  Public (Recall webhooks)                                       │
│    Backend    https://xxxxx.trycloudflare.com                   │
│    Frontend   https://yyyyy.trycloudflare.com                   │
└─────────────────────────────────────────────────────────────────┘
```

**Important:** Tunnel URLs change on every restart. The script patches `.env` automatically.

---

## Step 6: Upload a presentation

1. Open the dashboard: **http://localhost:5174**
2. Go to the Presentations page
3. Upload a PDF or PPTX file
4. Wait for indexing to complete — this takes 1-3 minutes depending on page count:
   - PPTX → PDF conversion (LibreOffice)
   - PDF → PNG per page (pdftoppm at 150 DPI)
   - Claude Vision extracts metadata per page (3 pages concurrently)
   - OpenAI generates embeddings (3072-dim vectors)
   - Documents uploaded to Azure AI Search index `overtone`
5. Status changes from "indexing" → "ready"

---

## Step 7: Launch a bot into a meeting

1. Create a Google Meet / Zoom / Teams meeting
2. Copy the meeting URL
3. In the dashboard, go to the Launch page
4. Select:
   - **Agent**: choose a profile (or "default")
   - **Bot name**: anything (e.g. "Overtone Demo")
   - **Meeting URL**: paste the meeting link
   - **Presentation**: select the deck you uploaded
   - **Agent mode**: Realtime (primary)
   - **Auto-present first N slides**: set to e.g. `5` (or `0` for Q&A only)
5. Click **Connect bot**
6. The bot joins the meeting within 10-20 seconds with the presentation as its video feed

---

## Step 8: Interact with the bot

### Auto-present mode (N > 0):
- Bot opens with a pitch from slide 1, then narrates it
- **Say anything** (e.g. "next", "continue", "ok") → advances to slide 2
- Ask a question → bot searches the deck, navigates to the right slide, answers from content
- After slide N → transitions to Q&A mode

### Q&A mode (N = 0):
- Bot waits silently for questions
- Ask about any topic → bot finds the relevant slide, navigates, answers
- Follow-ups ("tell me more") stay on the current slide

---

## Running without tunnels (API-only testing)

If you don't need Recall.ai and just want to test the backend:

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend and dashboard separately:
```bash
cd frontend && npm run dev    # port 5173
cd dashboard && npm run dev   # port 5174
```

**Note:** Without tunnels, Recall bots won't be able to reach your backend or render the frontend.

---

## Troubleshooting

### "Network connection lost" in Google Meet
The cloudflared tunnels died or the backend restarted. Run `./start-local.sh` again and launch a new bot.

### Blank screen when bot joins
The frontend tunnel URL changed. The old bot session references dead URLs. Kill everything, run `./start-local.sh`, launch a new bot.

### Bot doesn't respond to speech
Check the backend logs: `tail -f /tmp/voicenav-backend.log`
- Look for `TOOL_CALL_RECEIVED` — confirms the bot heard you
- If no tool calls: check `OPENAI_API_KEY` is valid and `OPENAI_REALTIME_MODEL` exists

### Indexing fails
Check `tail -f /tmp/voicenav-backend.log` for errors.
- "ANTHROPIC_API_KEY" errors: key is missing or invalid
- LibreOffice errors: ensure `soffice` is in PATH
- pdftoppm errors: ensure `poppler` is installed

### Sessions lost after restart
Sessions are in-memory. Every backend restart clears all sessions. Re-launch the bot after restarting.

---

## Log locations

| Log | Path |
|-----|------|
| Backend | `/tmp/voicenav-backend.log` |
| Frontend | `/tmp/voicenav-frontend.log` |
| Dashboard | `/tmp/voicenav-dashboard.log` |

### Useful log grep patterns

```bash
# All timing markers
grep "⏱" /tmp/voicenav-backend.log

# Tool calls only
grep "TOOL_CALL_RECEIVED\|TOOL_EXEC_DONE\|TOOL_RESULT_SENT" /tmp/voicenav-backend.log

# Filler audio
grep "FILLER_AUDIO_SENT" /tmp/voicenav-backend.log

# Auto-advance
grep "AUTO_ADVANCE" /tmp/voicenav-backend.log

# RAG timing
grep "RAG embed_ms\|RAG azure_ms" /tmp/voicenav-backend.log

# Errors
grep "ERROR\|WARNING\|FAILED" /tmp/voicenav-backend.log
```

---

## API Reference

Swagger docs at http://localhost:8000/docs after starting the backend.

Key endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check + active session count |
| `/api/presentations` | GET | List all presentations |
| `/api/upload` | POST | Upload PDF/PPTX for indexing |
| `/api/launch-bot` | POST | Launch Recall bot into a meeting |
| `/api/agents` | GET | List agent profiles |
| `/api/session/{id}` | GET | Get session status |
| `/ws/realtime/{id}` | WS | Realtime audio relay (browser ↔ OpenAI) |
| `/ws/presentation/{id}` | WS | Presentation transport (navigate, filler, status) |
