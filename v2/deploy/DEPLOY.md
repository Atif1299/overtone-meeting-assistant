# Deploy Overtone V2 (three Cloud Run services)

1. Deploy API (`cloudbuild.api.yaml`) first.
2. Set API env: `DATABASE_URL`, `GCS_BUCKET`, `GCS_PREFIX=v2`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `RECALL_API_KEY`, `ADMIN_API_KEY`, `BACKEND_URL`, `FRONTEND_URL` (V2 presenter URL), `CORS_ALLOWED_ORIGINS`.
3. Rebuild presenter/dashboard with `_VITE_API_BASE` / `_VITE_WS_BASE` pointing at the V2 API URL.
4. Keep `max-instances=1` on the API for sticky WebSockets until Redis fan-out lands.

V1 services stay untouched. Use `v2_` tables / `v2/` GCS prefix so catalogs do not collide.
