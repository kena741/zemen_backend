# Zemen Service Backend

Dedicated FastAPI API for **Zemen Service** (merged customer + provider Flutter app).

- Shares the existing Supabase project **betegna** (`rffptyqhqvzrpmyxlwwu`) Postgres + Auth.
- Validates Supabase access tokens; does not re-register users.
- Released mobile builds can keep using PostgREST while this API rolls out.

See `docs/ARCHITECTURE.md` and `docs/MIGRATION.md`.

## Quick start

```bash
cp .env.example .env
# Set DATABASE_URL (Supabase pooler) and SUPABASE_JWT_SECRET from the dashboard / secret manager.

uv sync
uv run uvicorn app.main:app --reload --port 8000
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

## Structure (iCareMC-inspired)

```
app/
  api/v1/{routers,schemas}
  core/{security,services}
  persistence/sqlalchemy/{models,repository_imp}
  jobs/
```
# zemen_backend
