# Deploy Overtone (GCP Cloud Run)

1. Deploy API (`deploy/cloudbuild.api.yaml`) first from repo root.
2. Set API env: `DATABASE_URL`, `GCS_BUCKET`, `GCS_PREFIX=v2`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `RECALL_API_KEY`, `ADMIN_API_KEY`, `BACKEND_URL`, `FRONTEND_URL` (presenter URL), `CORS_ALLOWED_ORIGINS`.
3. Rebuild presenter/dashboard with `_VITE_API_BASE` / `_VITE_WS_BASE` pointing at the API URL.
4. Keep `max-instances=1` on the API for sticky WebSockets until Redis fan-out lands.

V1 Cloud Run services stay untouched. Uses `v2_` tables / `GCS_PREFIX=v2` so catalogs do not collide with legacy data.

See [../DEPLOY.md](../DEPLOY.md) for command examples.
