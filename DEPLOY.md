# Deploy Overtone backend to Google Cloud Run

The API is containerized in `backend/` (`backend/Dockerfile`). The process listens on **`PORT`** (Cloud Run sets it; default `8080` in the image).

---

## How CI/CD fits together

| Approach | Where you click “connect repo” | Secrets in GitHub? |
|----------|--------------------------------|--------------------|
| **A. Cloud Build trigger (recommended)** | **Google Cloud Console** — connect GitHub once (OAuth) | **No** GCP key in GitHub |
| **B. GitHub Actions** | GitHub runs the workflow | **Yes** — `GCP_SA_KEY` + Variables |

Cloud Run does **not** poll GitHub by itself. Either **Cloud Build** (Google pulls the repo) or **GitHub Actions** (GitHub pushes to GCP) runs the build. For fewer steps in GitHub Settings, use **A**.

---

## A. Connect the repo in GCP (no GitHub secrets)

1. Push this repository to GitHub (your account), e.g. `Atif1299/overtone-meeting-assistant`.
2. In **Google Cloud Console**: enable **Cloud Build API**, **Artifact Registry API**, **Cloud Run API**.
3. Create an **Artifact Registry** Docker repository (e.g. name `overtone`, same region you will use for Cloud Run).
4. **Cloud Build → Repositories → Connect repository** → choose **GitHub (Cloud Build GitHub App)** → authorize and select your repo.
5. **Cloud Build → Triggers → Create trigger**:
   - Event: Push to branch `main` (or your branch).
   - Build configuration: **Cloud Build configuration file** → path `cloudbuild.yaml`.
   - Substitution variables (optional): override `_REGION`, `_SERVICE`, `_AR_REPOSITORY`, `_IMAGE_NAME` to match your project (defaults are at the top of [cloudbuild.yaml](cloudbuild.yaml)).
6. Grant the **Cloud Build service account** permission to push images and deploy:
   - **Artifact Registry**: `Artifact Registry Writer` on the repo (or project).
   - **Cloud Run**: `Cloud Run Admin` and **Service Account User** on the Cloud Run runtime service account (so it can deploy new revisions).

On each push to the configured branch, Cloud Build runs `cloudbuild.yaml`: builds `./backend`, pushes the image to Artifact Registry, and deploys to Cloud Run.

**App secrets** (`OPENAI_API_KEY`, `DATABASE_URL`, etc.) are **not** in GitHub — set them once on the **Cloud Run service** (or **Secret Manager** + reference in Cloud Run). That is the same no matter which CI option you use.

---

## B. GitHub Actions (optional)

If you prefer the pipeline to run on GitHub’s runners, use `.github/workflows/deploy-backend-cloud-run.yml` and add:

- Secret: **`GCP_SA_KEY`** (JSON for a CI service account).
- Variables: `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_ARTIFACT_REPOSITORY`, `GCP_ARTIFACT_IMAGE_NAME`, `CLOUD_RUN_SERVICE`.

---

## Cloud Run environment (after first deploy)

Edit the service → **Variables & secrets** — align with `backend/.env.example`:

- `BACKEND_URL`, `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`
- Provider keys: `OPENAI_*`, `RECALL_*`, `AZURE_*`, `ANTHROPIC_*`, `ELEVENLABS_*`, etc.
- **`DATABASE_URL`** for production Postgres (e.g. Cloud SQL); avoid relying on SQLite on the container disk.
- **`REDIS_URL`** optional but useful for queues across instances.

Increase **request timeout** if long WebSocket sessions need it.

---

## Dashboard

Build with your public API URL:

```bash
cd dashboard
VITE_API_BASE=https://YOUR-CLOUD-RUN-URL npm run build
```

Host `dist/` wherever you like; set `VITE_ADMIN_API_KEY` at build time to match backend `ADMIN_API_KEY`.
