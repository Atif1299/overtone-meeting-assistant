# Overtone

**Upload a deck. Paste a meeting link. Overtone joins, presents, and answers questions live.**

Overtone is an AI meeting presentation agent. It joins Google Meet / Zoom / Teams via Recall.ai, shows your slides as the bot camera, and speaks through a realtime speech-to-speech model (Gemini Live by default, OpenAI Realtime as fallback).

## Product stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, Postgres + pgvector, GCS |
| Voice | Gemini Live (`REALTIME_PROVIDER=auto`) or OpenAI Realtime |
| Indexing | Gemini Vision or OpenAI Vision → embeddings (`text-embedding-3-large`) |
| Presenter | React (Recall output-media webpage) |
| Dashboard | React (upload + launch) |

## Quick start (local)

1. Copy [`backend/.env.example`](backend/.env.example) → `backend/.env` and fill keys (`GEMINI_API_KEY` and/or `OPENAI_API_KEY`, `RECALL_API_KEY`).
2. Backend: `cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000`
3. Presenter: `cd frontend && npm i && npm run dev`
4. Dashboard: `cd dashboard && npm i && npm run dev`

Full setup: [docs/setup-guide.md](docs/setup-guide.md) · Deploy: [DEPLOY.md](DEPLOY.md)

## How a session works

1. Upload PPTX/PDF in the dashboard → Vision extracts per-slide metadata → pgvector index.
2. Launch bot with a Meet URL → Recall opens the presenter page as camera.
3. Presenter mic audio → backend realtime relay → Gemini Live / OpenAI Realtime → spoken audio back into the meeting.
4. Tools (`navigate_to_slide`, `get_slide_details`, `search_and_answer`, …) run on the backend and stay grounded in indexed slide content.

## Branches

- `main` — current product (Gemini Live + Vision, SQL catalog, GCS, empty-slide fix).
- `client-v1` — preserved client snapshot of the earlier `main` (no product updates from this line).

## Docs

- [Setup](docs/setup-guide.md)
- [Deploy](DEPLOY.md)
- [Technical summary](docs/project-summary.md)
