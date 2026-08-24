# Deploy Overtone (GCP Cloud Run)

Live services (project `x-saas-488416`, region `us-central1`):

| Service | Cloud Run name |
|---------|----------------|
| API | `overtone-v2-api` |
| Presenter | `overtone-v2-presenter` |
| Dashboard | `overtone-v2-dashboard` |

## Build + deploy

From repo root:

```bash
gcloud builds submit --config=deploy/cloudbuild.api.yaml --project=x-saas-488416 .
gcloud builds submit --config=deploy/cloudbuild.presenter.build.yaml --project=x-saas-488416 presenter
gcloud run deploy overtone-v2-presenter --region=us-central1 --image=us-central1-docker.pkg.dev/x-saas-488416/overtone/overtone-v2-presenter:latest

gcloud builds submit --config=deploy/cloudbuild.dashboard.build.yaml --project=x-saas-488416 dashboard
gcloud run deploy overtone-v2-dashboard --region=us-central1 --image=us-central1-docker.pkg.dev/x-saas-488416/overtone/overtone-v2-dashboard:latest
```

## API env (shared with legacy V1 infra)

Set on `overtone-v2-api`: `DATABASE_URL`, `GCS_BUCKET`, `GCS_PREFIX=v2`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `RECALL_API_KEY`, `ADMIN_API_KEY`, `BACKEND_URL`, `FRONTEND_URL` (presenter URL), `CORS_ALLOWED_ORIGINS`.

Uses same Cloud SQL + GCS bucket as V1 with `v2_` tables and `GCS_PREFIX=v2`.

## Live test script

```powershell
.\deploy\run_live_tests.ps1
```

Results written to `deploy/live-test-results.json`.
