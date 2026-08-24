# Overtone V2

Clean rebuild of the Overtone meeting presentation agent. V1 (`backend/`, `frontend/`, `dashboard/`) is the behavior reference only — do not mix imports.

## Stack

| Layer | Tech |
|-------|------|
| API | FastAPI |
| DB | Postgres + pgvector (`v2_*` tables) or SQLite locally |
| Objects | GCS prefix `v2/` |
| Voice | Gemini Live (preferred) / OpenAI Realtime |
| Indexing | Gemini or OpenAI Vision → OpenAI embeddings |
| Meetings | Recall.ai |
| Presenter | React (Recall output-media) |
| Dashboard | React operator studio |

## Quick start

```bash
# API (port 8001 — avoids V1 on 8000)
cd v2/api
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Presenter → http://127.0.0.1:5175
cd v2/presenter
npm i
npm run dev

# Dashboard → http://127.0.0.1:5176
cd v2/dashboard
npm i
npm run dev
```

**Windows note:** Do not append `# comments` on the same line as `npm run` in Command Prompt — cmd passes `#` to Vite and breaks the root/port. Use PowerShell comments on a separate line, or no trailing comment.

See [ARCHITECTURE.md](ARCHITECTURE.md) and [deploy/DEPLOY.md](deploy/DEPLOY.md).
