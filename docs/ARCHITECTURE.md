# Zemen Service — Architecture & Migration Audit

**Scope:** merged Flutter app `zemen_service` (customer + provider package) against shared Supabase project **betegna** (`rffptyqhqvzrpmyxlwwu`).  
**Out of scope for this phase:** standalone `zemen_provider` cutover (same DB; code paths mirrored in `packages/zemen_provider`), deep `lolelink-admin` rewrite (shares DB; keep PostgREST until admin phase).

## 1. Current architecture map

```
┌─────────────────────────┐     ┌──────────────────────────┐
│ zemen_service (Flutter) │     │ lolelink-admin (Next)    │
│  customer shell         │     │  admin / ops             │
│  + packages/zemen_      │     └────────────┬─────────────┘
│    provider             │                  │
└───────────┬─────────────┘                  │
            │ supabase_flutter / supabase-js │
            ▼                                ▼
┌──────────────────────────────────────────────────────────┐
│ Supabase project "betegna"  rffptyqhqvzrpmyxlwwu         │
│  Auth · PostgREST · Realtime · Storage · Edge Functions  │
│  Postgres public schema (customer, provider, bookings…)  │
└──────────────────────────────────────────────────────────┘

Staging URL (service): cdmgxbepfixfeumytkag.supabase.co
```

**Target (phase 1+):**

```
Clients ──Bearer Supabase JWT──▶ FastAPI /api/v1/* ──▶ same Postgres
Released clients may still hit PostgREST/Realtime/Storage directly.
```

## 2. Repository inventory

| Path | Role |
|------|------|
| `~/Desktop/zulu/zemen_service` | **Primary client** — customer app + embedded provider package |
| `~/Desktop/zulu/zemen_service/packages/zemen_provider` | Provider/handyman UI & data access (merged) |
| `~/Desktop/zulu/zemen_provider` | Older standalone provider (same betegna DB; reference only) |
| `~/Desktop/zulu/zemen-web` | Marketing/web customer+provider surfaces |
| `~/Desktop/zulu/lolelink-admin` | Admin dashboard on same Supabase |
| `~/Desktop/zulu/zemen_backend` | **This API** (new) |

Reference structure only: `~/Desktop/ICareMC/icaremc_backend` (layout conventions — not entities/rules).

## 3. Supabase dependency inventory (zemen_service)

### Client bootstrap
- `lib/bootstrap.dart`, `packages/zemen_provider/lib/bootstrap.dart` — `Supabase.initialize`
- Env: `SUPABASE_URL`, `SUPABASE_ANON` (`.env` / `.env.staging` / `.env.production`)
- Prod + default → `https://rffptyqhqvzrpmyxlwwu.supabase.co`
- Staging → `https://cdmgxbepfixfeumytkag.supabase.co`

### Data access hubs
- `lib/utils/supabase_utils.dart` — customer workflows
- `packages/zemen_provider/lib/utils/supabase_utils.dart` — provider workflows
- Table names via `lib/constant/collection_name.dart` / provider package twin

### Highest-traffic tables (utils usage)
`booked_service`, `customer`, `provider`, `service`, `service_offer`, `chat` / `chat_inbox`, `notification`, `wallet_transaction`, `job_request`, `handyman`, `review_customer`, `payments`, `provider_payment_methods`, `app_settings`, `category` / `sub_category`, `verify_documents`, `service_tier_payment`

### Realtime (keep initially)
- `booked_service` streams (customer bookings / detail)
- `job_request` streams
- `chat` / `chat_inbox` streams
- Provider notification/offer streams

### Storage
- Bucket `betegnabucket` (public) — profile/service media
- `admin-documents`, `public-assets` (private), `feedback`

### Edge Functions (deployed on betegna; sample)
Auth/profile: `signup-customer`, `login-customer`, `delete-customer`, `reset-password-by-phone`, `reset-password-by-phone-provider`, `update-provider-profile-auth`  
Payments: `chapa-payment`, `verify-payment`, `verify-chapa-activation`, `verify-provider-activation`, `verify-featured-request-payment`, `verify-service-tier-payment`, `job_request_payment`, `complete-booking`, `refund-customer-booking-decline`, `refund-rejected`  
Ops: `send-push-notification`, `notify-recurring-cycle-due`, `manage-handyman(s)`, `handle-sms`, `add_customer`, `admin-create-user`

### Local function folders in repo
- Service: `delete-customer`, `login-customer`, `reset-password-by-phone`
- Standalone provider repo also has tier/refund/push/recurring sources

## 4. Entity & relationship map (canonical DB names)

```
auth.users
   │ user_id
   ├─▶ customer (id, wallet_amount, …)
   ├─▶ provider (id, activation_*, service_tier_*, …)
   └─▶ handyman (id, provider_id, …)
          │
category ─┬─▶ sub_category ─┬─▶ service ──▶ booked_service
          │                 │                 │
          │                 └─ documents /     ├─ payments
          │                    verify_documents├─ review_customer
          │                                    ├─ notification
          │                                    └─ service_proof JSON
          │
job_request (customerId, providerId, serviceId, bidList)
service_offer (service/customer/provider ids as text historically)
wallet_transaction (customer_id | provider_id)
```

### Enums (preserve exactly)
- `status`: pending, accepted, rejected, on_the_way, in_progress, hold, completed, pending_extra_payment, pending_approval, admin_paid
- `payment_status_enum`: pending_payment, payment_approved_by_admin, payment_rejected_by_admin, payment_completed, payment_cancelled
- `provider_type`: individual, company
- `company_verification_status`: not_submitted, pending, approved, rejected
- `feature_request_status_enum`: none, pending, rejected, accepted

### Naming quirks (API must preserve / document)
- Mixed snake_case and camelCase columns (`firstName` vs `first_name`)
- `service_offer` / `service_tier_payment` store some FKs as **text**, not uuid
- Customer package `CollectionName.customers = "customers"` is unused; live queries use `customer`

## 5. Proposed backend folder structure

Mirrors iCareMC layout, Zemen domains:

```
zemen_backend/
  app/
    api/v1/routers|schemas
    core/security|services|domain
    persistence/sqlalchemy/{models,repository_imp,migrations}
    jobs/
  docs/
  scripts/
  tests/
```

API prefix: `/api/v1` with domain tags: Auth, Catalog, Customers, Providers, Handymen, Bookings, Offers, Jobs, Payments, Wallet, Reviews, Notifications, Uploads, Admin.

## 6. Migration phases & rollback boundaries

| Phase | Move | Rollback boundary |
|-------|------|-------------------|
| **0** | Ship API scaffold; validate Supabase JWTs; read-only catalog/profiles/bookings | Disable clients’ `API_BASE_URL`; no DB writes from API |
| **1** | Profile + service CRUD via API (feature flag) | Flag off; PostgREST writes resume |
| **2** | Booking lifecycle actions (accept/assign/complete) | Flag off; keep Edge Functions as source of truth for finance |
| **3** | Payments/wallet/recurring — after parity tests only | Never dual-write; flag off to Edge/`verify-*` |
| **4** | Admin/lolelink migration | Separate program |
| **5** | Deprecate direct table access after adoption metrics | Reverse only if clients still on old build |

**Hard rule:** keep Auth + Postgres + Storage + Realtime on Supabase through phase 3. No password-hash export; sessions stay Supabase.

## 7. Compatibility matrix

| Client | Today | During migration | Done |
|--------|-------|------------------|------|
| Released `zemen_service` | PostgREST + Edge + Realtime | Unchanged | Unchanged until store update |
| Updated `zemen_service` | — | Feature-flagged API for reads → writes | API primary; Realtime/Storage may remain |
| `lolelink-admin` | PostgREST / Edge | Unchanged in phase 0–3 | Later |
| Staging | `cdmgxbep…` | Point staging API at staging DB | Prod flip last |

## 8. Risks & open questions

1. **RLS quality:** several tables use `Enable all access for all users`; `payments`, `notification`, `app_settings`, `customer_service_details`, `customers_service` have **RLS disabled**. Backend must enforce ownership regardless; fix RLS as a parallel hardening track (do not enable without policies).
2. **Shared project name “betegna”** — confirm no cross-product tables collide with Zemen ops (marketing_tracker_*, companies CRM, etc.).
3. **Staging vs prod** — two project refs; confirm schema parity before dual deploy.
4. **Financial Edge Functions** remain source of truth until phase 3 parity.
5. **Realtime:** backend writes must still land in published tables so existing streams work; avoid duplicate push from overlapping paths.
6. Unresolved: preferred JWT verify method in prod (legacy `JWT_SECRET` HS256 vs asymmetric JWKS)? Support both in config.
7. Unresolved: production `DATABASE_URL` (pooler) for the API service account — set via secrets, never chat.

## 9. Security note (advisory)

Do **not** blindly run `ENABLE ROW LEVEL SECURITY` on tables that currently lack it without adding policies first — that would break released apps. Coordinate hardening with admin.
