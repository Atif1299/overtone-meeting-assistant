# Deploy Overtone backend to Google Cloud Run

This repository includes a Docker image for the FastAPI app in `backend/` (see `backend/Dockerfile`). The container listens on **`PORT`** (Cloud Run sets this; default `8080`).

## 1. Push this project to your GitHub repo

From your machine (replace paths if needed):

```bash
cd /path/to/overtone
git remote add myrepo https://github.com/Atif1299/overtone-meeting-assistant.git
git fetch myrepo
git push -u myrepo HEAD:main
```

If `main` already exists on the remote with different history, use `--force-with-lease` only if you intend to overwrite it.

Authenticate with GitHub using **HTTPS + personal access token**, **SSH keys**, or **GitHub CLI** (`gh auth login`).

## 2. Google Cloud setup (once per project)

1. Create or pick a **GCP project** and enable billing.
2. Enable APIs: **Artifact Registry**, **Cloud Run**, **Cloud Build** (optional if you only use GitHub Actions to build).
3. Create an **Artifact Registry** repository (Docker), e.g. name `overtone`, region `us-central1`.
4. Create a **service account** for CI with roles, for example:
   - `roles/run.admin`
   - `roles/artifactregistry.writer`
   - `roles/iam.serviceAccountUser` (on the Cloud Run runtime SA if needed)
5. Create a **JSON key** for that service account (or use Workload Identity Federation for production). In GitHub: **Settings → Secrets and variables → Actions**, add secret **`GCP_SA_KEY`** with the full JSON file contents.

## 3. GitHub Actions variables

In the same repository: **Settings → Secrets and variables → Actions → Variables**, add:

| Variable | Example |
|----------|---------|
| `GCP_PROJECT_ID` | `my-project-123` |
| `GCP_REGION` | `us-central1` |
| `GCP_ARTIFACT_REPOSITORY` | `overtone` |
| `GCP_ARTIFACT_IMAGE_NAME` | `overtone-backend` |
| `CLOUD_RUN_SERVICE` | `overtone-backend` |

Workflow file: `.github/workflows/deploy-backend-cloud-run.yml` (runs on push to `main` when `backend/` changes, or **Run workflow** manually).

## 4. Cloud Run service configuration

After the first deploy, open **Cloud Run → your service → Edit & deploy new revision** and set environment variables and secrets (or use **Secret Manager** references). At minimum align with `backend/.env.example`:

- `BACKEND_URL` — HTTPS URL of this Cloud Run service.
- `FRONTEND_URL` — your dashboard URL.
- `CORS_ALLOWED_ORIGINS` — include that dashboard origin (regex already allows `*.a.run.app` for typical Cloud Run URLs).
- API keys: `OPENAI_API_KEY`, `RECALL_*`, `AZURE_*`, `ANTHROPIC_API_KEY`, etc.
- **`DATABASE_URL`** — use **Cloud SQL (Postgres)** or another managed Postgres for production; SQLite on the container disk is not durable across restarts.
- **`REDIS_URL`** — optional but recommended for the transcript queue across instances (e.g. **Memorystore**).

Increase **request timeout** if long-lived WebSockets need it (Cloud Run supports up to 60 minutes).

## 5. Dashboard

Build the dashboard with your API URL:

```bash
cd dashboard
VITE_API_BASE=https://YOUR-CLOUD-RUN-URL npm run build
```

Host `dist/` on Cloud Storage + CDN, another Cloud Run static host, or any static host; set `VITE_ADMIN_API_KEY` at build time to match `ADMIN_API_KEY` on the backend.

## 6. Connect GitHub to GCP (summary)

- **GitHub** holds code; **Actions** builds the Docker image and deploys to **Cloud Run** using **`GCP_SA_KEY`** and the **Variables** above.
- You do not “connect Cloud Run to GitHub” inside the GCP console for this flow: the workflow uses the gcloud API with the service account key.

If the workflow fails, check: Artifact Registry path matches variables, APIs enabled, and the service account has the roles listed above.
