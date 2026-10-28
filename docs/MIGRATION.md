# Migration plan — Zemen Service → dedicated backend

## Compatibility strategy

- Keep Supabase Auth, Postgres, Storage, and Realtime.
- New API validates existing Supabase access tokens (issuer, expiry, signature).
- Never trust `user_id` / role from request body alone.
- Released apps continue PostgREST; updated builds opt in via config/`API_BASE_URL`.
- Additive schema only; no destructive renames during coexistence.

## Workflow mapping (phase 0–1 focus)

| Workflow | Current | New endpoint | Compatibility | Status |
|----------|---------|--------------|---------------|--------|
| Health | n/a | `GET /api/v1/health` | — | done |
| Session whoami | Auth session + profile select | `GET /api/v1/auth/me` | JWT from Supabase | done |
| Categories | `category` / `sub_category` select | `GET /api/v1/catalog/categories` | PostgREST parallel | done |
| Service list/detail | `service` select | `GET /api/v1/catalog/services` | PostgREST parallel | done |
| Customer profile | `customer` by `user_id` | `GET /api/v1/customers/me` | PostgREST parallel | done |
| Provider profile | `provider` by `user_id` | `GET /api/v1/providers/me` | PostgREST parallel | done |
| Customer bookings | `booked_service` + realtime | `GET /api/v1/bookings` (customer) | Realtime stays on Supabase | done (list) |
| Provider bookings | same | `GET /api/v1/providers/me/bookings` | Realtime stays | done (list) |
| Create booking | client insert + payment edge | `POST /api/v1/bookings` | deferred phase 2 | pending |
| Accept / assign / complete | client update + edges | action endpoints | deferred; finance via edges | pending |
| Chapa verify / wallet | Edge Functions | `/api/v1/payments/*` | deferred phase 3 | pending |
| Chat / inbox | Realtime tables | later or keep Realtime | keep | pending |

## Cutover flags (client)

Suggested keys in `mobile_app_config` / dotenv:

- `use_backend_reads` (bool)
- `use_backend_bookings` (bool)
- `use_backend_payments` (bool)
- `api_base_url` (string)

Write path: **no silent fallback** after timeout — use idempotency keys + status reconciliation.

## Rollback

1. Turn feature flags off on clients.
2. Stop sending traffic to API (load balancer / DNS).
3. Data already written via API remains in shared Postgres — no undo migration needed for phase 0–1 reads.
4. For phase 2+ writes: document last good deploy; do not replay Edge + API for the same payment tx_ref.
