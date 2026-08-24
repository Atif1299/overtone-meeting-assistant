<p align="center">
  <img src="docs/assets/banner.svg" alt="Overtone — AI meeting presentation agent" width="800"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" alt="React"/>
  <img src="https://img.shields.io/badge/Gemini_Live-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini Live"/>
  <img src="https://img.shields.io/badge/Recall.ai-0066FF?style=for-the-badge&logo=googlemeet&logoColor=white" alt="Recall.ai"/>
  <img src="https://img.shields.io/badge/Cloud_Run-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white" alt="Cloud Run"/>
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
</p>

<p align="center"><strong>Upload a deck. Paste a meeting link. Overtone joins, presents, and answers questions live.</strong></p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#stack">Stack</a> ·
  <a href="#local-dev">Local dev</a> ·
  <a href="#deploy">Deploy</a> ·
  <a href="#live-gcp">Live</a>
</p>

---

## What is Overtone?

Overtone is an **AI meeting presentation agent**. Upload a PPTX or PDF, launch a bot with a Google Meet / Zoom / Teams link, and Overtone joins the call as a presenter — showing your slides as the bot camera and speaking through a realtime voice model.

It reads your **indexed deck**, navigates slides on demand, and answers audience questions **grounded in slide content** — not generic chat.

No separate presenter app in the meeting. Recall.ai carries the presenter webpage as output media; Gemini Live (default) or OpenAI Realtime handles speech-to-speech on the backend.

---

## Quick start

**Prerequisites:** Python 3.11+, Node 18+, Postgres with pgvector, and API keys for Recall.ai + Gemini (or OpenAI).

```bash
# API → http://127.0.0.1:8001
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Presenter → http://127.0.0.1:5175
cd presenter
npm i && npm run dev

# Dashboard → http://127.0.0.1:5176
cd dashboard
npm i && npm run dev
```

**Windows:** Do not append `# comments` on the same line as `npm run` in Command Prompt — cmd passes `#` to Vite and breaks the root/port.

Or use the helper scripts: [`start-local.ps1`](start-local.ps1) / [`start-local.sh`](start-local.sh).

---

## How it works

1. **Upload** — Dashboard ingests PPTX/PDF; Vision extracts per-slide metadata; pgvector stores searchable chunks.
2. **Launch** — Paste a meeting URL; Recall.ai joins and opens the presenter page as the bot camera.
3. **Present** — Presenter mic audio flows through the backend realtime relay → Gemini Live / OpenAI Realtime → spoken audio back into the meeting.
4. **Answer** — Tools (`navigate_to_slide`, `get_slide_details`, `search_and_answer`, …) run on the backend and stay grounded in indexed slide content.

---

## Stack

| Layer | Tech |
|-------|------|
| API | FastAPI, Postgres + pgvector, GCS |
| Voice | Gemini Live (preferred) / OpenAI Realtime |
| Indexing | Gemini or OpenAI Vision → OpenAI embeddings |
| Presenter | React (Recall output-media webpage) |
| Dashboard | React operator studio |

---

## Local dev

| Service | Port | Folder |
|---------|------|--------|
| API | 8001 | `backend/` |
| Presenter | 5175 | `presenter/` |
| Dashboard | 5176 | `dashboard/` |

Further reading: [ARCHITECTURE.md](ARCHITECTURE.md) · [TESTING.md](TESTING.md) · [deploy/DEPLOY.md](deploy/DEPLOY.md)

---

## Deploy

Cloud Build configs live under [`deploy/`](deploy/). Each service (API, presenter, dashboard) has its own `cloudbuild.*.yaml`.

See [deploy/DEPLOY.md](deploy/DEPLOY.md) for GCP project setup, secrets, and rollout steps.

---

## Live (GCP)

| Service | URL |
|---------|-----|
| API | https://overtone-v2-api-4idrhaffca-uc.a.run.app |
| Presenter | https://overtone-v2-presenter-4idrhaffca-uc.a.run.app |
| Dashboard | https://overtone-v2-dashboard-4idrhaffca-uc.a.run.app |

---

## Branches

- **`main`** — current product (V2 at repo root).
- **`archive/v1`** — preserved snapshot of the previous V1 layout before promotion.
