# Monorepo Setup

This repo combines the frontend (Next.js) and backend (Python/FastAPI) into a single repository, each deployed independently to GCP via Cloud Build.

## Structure

```
trackwinner.lol/
├── frontend/          # Next.js app → Cloud Run (bighack-berlin)
│   ├── Dockerfile
│   └── cloudbuild.yaml
├── backend/           # Python/FastAPI app → Cloud Run (hackathon)
│   ├── Dockerfile
│   └── cloudbuild.yaml
├── METHODOLOGY.md
└── SETUP.md
```

## Deployments

| Service | Platform | Cloud Run Service | Region |
|---|---|---|---|
| Frontend | Cloud Run | `bighack-berlin` | `europe-west1` |
| Backend | Cloud Run | `hackathon` | `europe-west1` |

Both services are deployed to Artifact Registry at:
`europe-west1-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/<service>`

## Cloud Build Triggers

Two triggers are configured in GCP Cloud Build, both watching the `main` branch:

| Trigger | Included Files | Config File |
|---|---|---|
| `deploy-frontend` | `frontend/**` | `frontend/cloudbuild.yaml` |
| `deploy-backend` | `backend/**` | `backend/cloudbuild.yaml` |

Pushes that only touch `frontend/` only trigger the frontend build, and vice versa.

## Frontend

- Next.js 15 with `output: "standalone"` for Docker/Cloud Run compatibility
- Multi-stage Dockerfile: deps → builder → runner (node:22-alpine)
- Serves on port 8080

## Backend

- Python/FastAPI with `uv` for dependency management
- Deployed via existing Dockerfile in `backend/`

## Syncing from source repos

To pull latest changes from the original repos into the monorepo:

**Frontend** (from [JonasBrilz/BigHack-Berlin-2026](https://github.com/JonasBrilz/BigHack-Berlin-2026)):
```bash
git clone https://github.com/JonasBrilz/BigHack-Berlin-2026 /tmp/bighack
cp frontend/cloudbuild.yaml /tmp/frontend-cloudbuild.yaml.bak
cp -r /tmp/bighack/. frontend/
cp /tmp/frontend-cloudbuild.yaml.bak frontend/cloudbuild.yaml
# Ensure next.config.mjs has output: "standalone"
```

**Backend** (from [JonasBrilz/hackathon](https://github.com/JonasBrilz/hackathon)):
```bash
git clone https://github.com/JonasBrilz/hackathon /tmp/hackathon
cp backend/cloudbuild.yaml /tmp/backend-cloudbuild.yaml.bak
cp -r /tmp/hackathon/. backend/
cp /tmp/backend-cloudbuild.yaml.bak backend/cloudbuild.yaml
rm -rf backend/.git
```
