# Deploy DeckVoice (GCP Cloud Run)

Live services (project `x-saas-488416`, region `us-central1`):

| Service | Cloud Run name | Intended URL |
|---------|----------------|--------------|
| API | `deckvoice-v2-api` | https://deckvoice-v2-api-4idrhaffca-uc.a.run.app |
| Presenter | `deckvoice-v2-presenter` | https://deckvoice-v2-presenter-4idrhaffca-uc.a.run.app |
| Dashboard | `deckvoice-v2-dashboard` | https://deckvoice-v2-dashboard-4idrhaffca-uc.a.run.app |
| Marketing | `deckvoice-marketing` | https://deckvoice-marketing-4idrhaffca-uc.a.run.app |

Images still push to the existing Artifact Registry repo `overtone` (`us-central1-docker.pkg.dev/x-saas-488416/overtone/<image>`). Image names themselves are `deckvoice-*`.

## Build + deploy

From repo root. Deploy API first, then frontends so Vite bases point at the new API URL.

```bash
gcloud builds submit --config=deploy/cloudbuild.api.yaml --project=x-saas-488416 .

gcloud builds submit --config=deploy/cloudbuild.presenter.yaml --project=x-saas-488416 .

gcloud builds submit --config=deploy/cloudbuild.dashboard.yaml --project=x-saas-488416 .

gcloud builds submit --config=deploy/cloudbuild.marketing.yaml --project=x-saas-488416 .
```

Build-only (no deploy) configs remain in `deploy/cloudbuild.presenter.build.yaml` and `deploy/cloudbuild.dashboard.build.yaml`.

Do not delete `overtone-v2-*` / `overtone-marketing` until the new `deckvoice-*` services pass health checks.

## API env

Set on `deckvoice-v2-api`: `DATABASE_URL`, `GCS_BUCKET`, `GCS_PREFIX=v2`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `RECALL_API_KEY`, `ADMIN_API_KEY`, `BACKEND_URL`, `FRONTEND_URL` (presenter URL), `CORS_ALLOWED_ORIGINS`.

Copy those values from the previous `overtone-v2-api` service. Point `BACKEND_URL` / `FRONTEND_URL` / `CORS_ALLOWED_ORIGINS` at the new `deckvoice-*` run.app URLs (and later at custom domains).

Uses the same Cloud SQL instance as before, with `v2_` tables and `GCS_PREFIX=v2`.

## GCS buckets

Leave `GCS_BUCKET` as an environment variable. Do not rename or delete the live bucket; it still holds decks and indexes.

| Role | Current name (keep) | Desired name when you can copy objects |
|------|---------------------|----------------------------------------|
| Presentations / indexes | `overtone-presentations-x-saas-488416` | `deckvoice-presentations-x-saas-488416` |

Create the `deckvoice-*` bucket only when you can `gcloud storage cp --recursive` into it, then switch `GCS_BUCKET` on `deckvoice-v2-api`. Never delete the old bucket while it still holds data.

## Live test script

```powershell
.\deploy\run_live_tests.ps1
```

Results written to `deploy/live-test-results.json`.

## Custom domain (after deckvoice.com is purchased)

`deckvoice.com` is **not owned yet**. After it is bought, map hostnames to the new Cloud Run services — do not point them at the old `overtone-*` services.

| Hostname | Cloud Run service |
|----------|-------------------|
| `deckvoice.com` and `www.deckvoice.com` | `deckvoice-marketing` |
| `app.deckvoice.com` | `deckvoice-v2-dashboard` |
| `api.deckvoice.com` | `deckvoice-v2-api` |
| `present.deckvoice.com` | `deckvoice-v2-presenter` |

DNS + Cloud Run domain mapping (repeat per hostname):

1. In Cloud Run: **Manage custom domains** → Add mapping → select the service above → domain `deckvoice.com` (or subdomain).
2. At the registrar, create the records Cloud Run shows (typically `A`/`AAAA` for apex, `CNAME` for subdomains).
3. Wait for certificate provisioning.
4. Update API env: `BACKEND_URL=https://api.deckvoice.com`, `FRONTEND_URL=https://present.deckvoice.com`, `CORS_ALLOWED_ORIGINS` to include `https://app.deckvoice.com`, `https://present.deckvoice.com`, `https://deckvoice.com`, `https://www.deckvoice.com`.
5. Rebuild presenter/dashboard/marketing with `_VITE_API_BASE=https://api.deckvoice.com`, `_VITE_WS_BASE=wss://api.deckvoice.com`, `_VITE_DASHBOARD_URL=https://app.deckvoice.com`, `_VITE_MARKETING_URL=https://deckvoice.com`.
