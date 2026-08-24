# V2 testing notes (full matrix later)

## Smoke (done in rebuild)

- `GET /health`
- Admin auth + agents list
- Quality gate unit tests
- Import `app.main:app`

## Full pass (later)

1. Upload PDF/PPTX → status `ready` (Vision + embeddings + pgvector when `DATABASE_URL` set)
2. Launch Meet → Recall join → presenter slides
3. Ask grounded question → navigate + speak
4. Mute / unmute / leave
5. Customer API key create → launch with customer key
6. Cloud Run deploy of three V2 services
