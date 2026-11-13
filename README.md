# Zemen Service Backend

Dedicated FastAPI API for **Zemen Service** (merged customer + provider Flutter app).

- Shares the existing Supabase project **betegna** (`rffptyqhqvzrpmyxlwwu`) Postgres + Auth.
- Validates Supabase access tokens; does not re-register users.
- Released mobile builds can keep using PostgREST while this API rolls out.

See `docs/ARCHITECTURE.md` and `docs/MIGRATION.md`.

## Quick start

### Option A: Local Python / uv
```bash
cp .env.example .env
# Set DATABASE_URL (or leave blank in dev to use DEV_DATABASE_URL) and SUPABASE_JWT_SECRET.

uv sync
uv run alembic -c app/persistence/sqlalchemy/alembic.ini upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

### Option B: Docker Compose (App + Postgres + Alembic)
```bash
docker compose up -d
```
This spins up PostgreSQL (`db`) and starts the FastAPI server (`app`) on port 8000.

### Alembic Migrations
```bash
# Using Docker Compose (pattern from zuludine-backend)
docker compose run --rm alembic upgrade head
docker compose run --rm alembic revision --autogenerate -m "describe_changes"
docker compose run --rm alembic current
docker compose run --rm alembic history

# Or locally with Python / uv
uv run alembic -c app/persistence/sqlalchemy/alembic.ini upgrade head
uv run alembic -c app/persistence/sqlalchemy/alembic.ini revision --autogenerate -m "describe_changes"
uv run alembic -c app/persistence/sqlalchemy/alembic.ini current
```

OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs)

```bash
uv run python scripts/self_check.py
uv run pytest
```

## Phase 0 routes

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/health` | public |
| GET | `/api/v1/auth/me` | Bearer Supabase JWT |
| GET | `/api/v1/catalog/categories` | public |
| GET | `/api/v1/catalog/sub-categories` | public |
| GET | `/api/v1/catalog/services` | public |
| GET | `/api/v1/catalog/services/{id}` | public |
| GET | `/api/v1/customers/me` | customer profile |
| GET | `/api/v1/providers/me` | provider profile |
| GET | `/api/v1/providers/me/bookings` | provider profile |
| GET | `/api/v1/bookings` | customer profile |
| GET | `/api/v1/bookings/{id}` | customer or provider owner |

## Deployment (Cloud Build & Cloud Run)

Automated deployment pipelines following the `zuludine-backend` pattern:

* **Staging Pipeline:** [`cloudbuild-staging.yaml`](file:///home/daniel/zulu-tech/zemen_backend/cloudbuild-staging.yaml)
  * Triggers on staging branch/tag.
  * Runs tests and self-check.
  * Builds and pushes image to Artifact Registry (`backend-staging`).
  * Deploys to Cloud Run service `zemen-service-backend-staging` with `ENVIRONMENT=staging` and `STAGING_DATABASE_URL` from Secret Manager.

* **Production Pipeline:** [`cloudbuild-production.yaml`](file:///home/daniel/zulu-tech/zemen_backend/cloudbuild-production.yaml)
  * Triggers on `main` branch or release tag.
  * Runs tests and self-check.
  * Builds and pushes image to Artifact Registry (`backend-prod`).
  * Deploys to Cloud Run service `zemen-service-backend-prod` with `ENVIRONMENT=production` and `PRODUCTION_DATABASE_URL` from Secret Manager.

## Structure (iCareMC-inspired)

```
app/
  api/v1/{routers,schemas}
  core/{security,services}
  persistence/sqlalchemy/{models,repository_imp}
  jobs/
```
# zemen_backend
