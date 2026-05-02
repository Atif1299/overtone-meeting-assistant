# Deploy Overtone on Google Cloud (Cloud Run)

All parts can live in **one GCP project** and **one region**. You get **three Cloud Run services** (three URLs): **API**, **presenter frontend**, **admin dashboard**. Static UIs use **nginx** on `$PORT`; the API is [`backend/Dockerfile`](backend/Dockerfile).

---

## Architecture (GCP only)

| Service | Source | Dockerfile | Cloud Build config |
|---------|--------|------------|-------------------|
| API | [`backend/`](backend/) | [`backend/Dockerfile`](backend/Dockerfile) | [`cloudbuild.yaml`](cloudbuild.yaml) |
| Presenter UI | [`frontend/`](frontend/) | [`frontend/Dockerfile`](frontend/Dockerfile) | [`cloudbuild.frontend.yaml`](cloudbuild.frontend.yaml) |
| Dashboard | [`dashboard/`](dashboard/) | [`dashboard/Dockerfile`](dashboard/Dockerfile) | [`cloudbuild.dashboard.yaml`](cloudbuild.dashboard.yaml) |

Vite bakes **`VITE_*` at build time**. Deploy the **backend first**, copy its **HTTPS URL**, then set that URL in the frontend/dashboard build substitutions (and rebuild those services when the API URL changes).

---

## How CI/CD fits together

| Approach | Where you connect the repo | Secrets in GitHub? |
|----------|------------------------------|--------------------|
| **Cloud Build triggers (recommended)** | GCP Console — GitHub OAuth | **No** GCP key in GitHub |
| **GitHub Actions** | GitHub runs the workflow | **Yes** — `GCP_SA_KEY` + variables |

---

## A. Cloud Build: connect the repo (no GitHub secrets)

1. Enable **Cloud Build**, **Artifact Registry**, **Cloud Run** APIs; create an Artifact Registry **Docker** repository (e.g. `overtone`).
2. **Cloud Build → Connect repository** (GitHub Cloud Build app) → select your repo.
3. Create **three triggers** (same branch, e.g. `main`), each pointing to one config file:

   | Trigger | Configuration file |
   |---------|-------------------|
   | Backend | `cloudbuild.yaml` |
   | Frontend | `cloudbuild.frontend.yaml` |
   | Dashboard | `cloudbuild.dashboard.yaml` |

4. **Substitution variables** on each trigger: align `_REGION`, `_SERVICE`, `_AR_REPOSITORY`, `_IMAGE_NAME` with your project. Defaults in the YAML files use `europe-west1` and names like `overtone-frontend` — change if needed.

5. **Frontend trigger** must set (after the API is deployed):

   - `_VITE_API_BASE` — `https://YOUR-API-SERVICE-....run.app` (no trailing slash)
   - `_VITE_WS_BASE` — `wss://` + **same host** as the API (e.g. `wss://YOUR-API-SERVICE-....run.app`)

6. **Dashboard trigger** must set:

   - `_VITE_API_BASE` — same HTTPS API URL as above
   - `_VITE_ADMIN_API_KEY` — must match backend **`ADMIN_API_KEY`** (treat as a secret; substitutions are visible in build logs — for stricter handling, build locally with `docker build` and deploy the image manually, or use Secret Manager–backed builds).

7. Grant the **Cloud Build service account** **Artifact Registry Writer** and **Cloud Run Admin** (+ **Service Account User** on the runtime SA as needed).

---

## B. GitHub Actions (optional)

Backend-only workflow: [`.github/workflows/deploy-backend-cloud-run.yml`](.github/workflows/deploy-backend-cloud-run.yml). Frontend/dashboard can be built the same way with extra jobs, or rely on Cloud Build triggers above.

---

## Backend Cloud Run environment

Edit the **API** service → **Variables & secrets** — mirror [`backend/.env.example`](backend/.env.example):

- **`BACKEND_URL`** — this service’s public `https://....run.app` URL.
- **`FRONTEND_URL`** — presenter frontend Cloud Run URL (or your primary UI).
- **`CORS_ALLOWED_ORIGINS`** — comma-separated **origins** for both UIs, for example:
  - `https://overtone-frontend-....run.app`
  - `https://overtone-dashboard-....run.app`  
  Listing them explicitly is clearer than relying on regex alone.
- Provider keys: `OPENAI_*`, `RECALL_*`, `AZURE_*`, `ANTHROPIC_*`, `ELEVENLABS_*`, etc.
- **`DATABASE_URL`** for production Postgres (e.g. Cloud SQL); avoid relying on SQLite on the container disk.
- **`REDIS_URL`** optional but useful for queues across instances.

Raise **request timeout** if long WebSocket sessions need it.

---

## Local Docker build (without Cloud Build)

From the **repository root**:

**Frontend**

```bash
docker build -f frontend/Dockerfile frontend ^
  --build-arg VITE_API_BASE=https://YOUR-API.run.app ^
  --build-arg VITE_WS_BASE=wss://YOUR-API.run.app ^
  -t overtone-frontend:local
```

**Dashboard**

```bash
docker build -f dashboard/Dockerfile dashboard ^
  --build-arg VITE_API_BASE=https://YOUR-API.run.app ^
  --build-arg VITE_ADMIN_API_KEY=your-admin-key ^
  -t overtone-dashboard:local
```

(PowerShell: use backtick `` ` `` for line continuation instead of `^` if you prefer.)

---

## Operational checklist

| Step | Action |
|------|--------|
| 1 | Deploy **backend**; verify `GET /health` on the API URL |
| 2 | Set **`_VITE_*` substitutions** on frontend/dashboard triggers; run builds (or push to `main` if triggers fire on push) |
| 3 | Open both UI URLs; confirm pages load |
| 4 | Browser devtools: API calls hit the API host; **no CORS errors** |
| 5 | Recall/webhooks: **`BACKEND_URL`** matches the API URL |

---

## Files added for static UIs

- [`frontend/Dockerfile`](frontend/Dockerfile), [`frontend/nginx/templates/default.conf.template`](frontend/nginx/templates/default.conf.template), [`frontend/.dockerignore`](frontend/.dockerignore)
- [`dashboard/Dockerfile`](dashboard/Dockerfile), [`dashboard/nginx/templates/default.conf.template`](dashboard/nginx/templates/default.conf.template), [`dashboard/.dockerignore`](dashboard/.dockerignore)
- [`cloudbuild.frontend.yaml`](cloudbuild.frontend.yaml), [`cloudbuild.dashboard.yaml`](cloudbuild.dashboard.yaml)
