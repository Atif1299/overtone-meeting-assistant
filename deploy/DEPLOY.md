# Deploy DeckVoice (GCP Cloud Run)

1. Deploy API (`deploy/cloudbuild.api.yaml`) first from repo root. Service name: `deckvoice-v2-api`.
2. Set API env: `DATABASE_URL`, `GCS_BUCKET`, `GCS_PREFIX=v2`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `RECALL_API_KEY`, `ADMIN_API_KEY`, `BACKEND_URL`, `FRONTEND_URL` (presenter URL), `CORS_ALLOWED_ORIGINS`.
3. Rebuild presenter/dashboard/marketing (`deckvoice-v2-presenter`, `deckvoice-v2-dashboard`, `deckvoice-marketing`) with `_VITE_API_BASE` / `_VITE_WS_BASE` / `_VITE_DASHBOARD_URL` pointing at the new `deckvoice-*` URLs.
4. Keep `max-instances=1` on the API for sticky WebSockets until Redis fan-out lands.
5. Health-check the new URLs before deleting any `overtone-*` Cloud Run services.

Leave `GCS_BUCKET` as an env var. The live bucket `overtone-presentations-x-saas-488416` still holds decks; desired future name is `deckvoice-presentations-x-saas-488416` only after objects are copied. Do not delete the old bucket.

`deckvoice.com` is not owned yet. After purchase, map `deckvoice.com`/`www` → marketing, `app.deckvoice.com` → dashboard, `api.deckvoice.com` → API, `present.deckvoice.com` → presenter. See [../DEPLOY.md](../DEPLOY.md).

V1 Cloud Run services stay untouched. Uses `v2_` tables / `GCS_PREFIX=v2` so catalogs do not collide with legacy data.
