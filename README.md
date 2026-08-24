# Overtone

**Upload a deck. Paste a meeting link. Overtone joins, presents, and answers questions live.**

Overtone is an AI meeting presentation agent. It joins Google Meet / Zoom / Teams via Recall.ai, shows your slides as the bot camera, and speaks through a realtime speech-to-speech model (Gemini Live by default, OpenAI Realtime as fallback).

## Stack

| Layer | Tech |
|-------|------|
| API | FastAPI, Postgres + pgvector, GCS |
| Voice | Gemini Live (preferred) / OpenAI Realtime |
| Indexing | Gemini or OpenAI Vision → OpenAI embeddings |
| Presenter | React (Recall output-media webpage) |
| Dashboard | React operator studio |

## Quick start (local)

```bash
# API → http://127.0.0.1:8001
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Presenter → http://127.0.0.1:5175
cd presenter
npm i
npm run dev

# Dashboard → http://127.0.0.1:5176
cd dashboard
npm i
npm run dev
```

**Windows note:** Do not append `# comments` on the same line as `npm run` in Command Prompt — cmd passes `#` to Vite and breaks the root/port.

See [ARCHITECTURE.md](ARCHITECTURE.md), [TESTING.md](TESTING.md), and [deploy/DEPLOY.md](deploy/DEPLOY.md).

## How a session works

1. Upload PPTX/PDF in the dashboard → Vision extracts per-slide metadata → pgvector index.
2. Launch bot with a Meet URL → Recall opens the presenter page as camera.
3. Presenter mic audio → backend realtime relay → Gemini Live / OpenAI Realtime → spoken audio back into the meeting.
4. Tools (`navigate_to_slide`, `get_slide_details`, `search_and_answer`, …) run on the backend and stay grounded in indexed slide content.

## Branches

- `main` — current product (V2 promoted to repo root).
- `archive/v1` — preserved snapshot of the previous V1 layout before promotion.

## Live (GCP)

| Service | URL |
|---------|-----|
| API | https://overtone-v2-api-4idrhaffca-uc.a.run.app |
| Presenter | https://overtone-v2-presenter-4idrhaffca-uc.a.run.app |
| Dashboard | https://overtone-v2-dashboard-4idrhaffca-uc.a.run.app |

Deploy with configs under [`deploy/`](deploy/).
