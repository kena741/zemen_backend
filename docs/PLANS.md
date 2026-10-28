# Zemen migration plans (execute in order)

**Supabase project:** betegna `rffptyqhqvzrpmyxlwwu`  
**REST (legacy clients):** `https://rffptyqhqvzrpmyxlwwu.supabase.co/rest/v1/<table>`  
**New API:** `https://<api-host>/api/v1/...`  
**Client focus:** `zemen_service` (customer + provider merged). Admin/lolelink later.

Inventory source: Supabase MCP (`list_tables`, `execute_sql`, `generate_typescript_types`, Realtime publication, RLS). See `docs/generated/schema_inventory.json`.

---

## Plan 0 — Foundation ✅

| Item | Status |
|------|--------|
| FastAPI scaffold (iCareMC-style layout) | done |
| Map core ORM models to live columns | done (core) |
| Validate Supabase JWT (HS256 / JWKS) | done |
| Health + OpenAPI tags | done |
| Read: catalog, auth/me, customers/me, providers/me, bookings | done |

**Rollback:** stop API; clients stay on REST.

---

## Plan 1 — Low-risk reads (config, social proof, inbox lists) ✅

Replace PostgREST **SELECT** only. Realtime subscriptions stay on Supabase.

| Domain | REST table(s) | Backend route | Auth |
|--------|---------------|---------------|------|
| Banners | `banner` | `GET /api/v1/config/banners` | public |
| Taxes | `country_tax` | `GET /api/v1/config/taxes` | public |
| Coupons | `coupon` | `GET /api/v1/config/coupons` | public |
| App settings | `app_settings` | `GET /api/v1/config/settings/{id}` | public |
| Mobile config | `mobile_app_config` | `GET /api/v1/config/mobile/{app_key}` | public |
| Reviews | `review_customer` | `GET /api/v1/reviews?serviceId=` | public |
| Notifications | `notification` | `GET /api/v1/notifications` | owner |
| Offers (list) | `service_offer` | `GET /api/v1/offers` | customer/provider |
| Job requests (list) | `job_request` | `GET /api/v1/jobs` | customer/provider |
| Wallet ledger (read) | `wallet_transaction` | `GET /api/v1/wallet/transactions` | owner |
| Handymen (provider) | `handyman` | `GET /api/v1/providers/me/handymen` | provider |
| Currency | `currencies` | `GET /api/v1/config/currency` (active or `null`), `GET /api/v1/config/currencies` | public |
| Languages | `languages` | `GET /api/v1/config/languages` | public |
| Document types | `documents` | `GET /api/v1/catalog/documents` | public |
| Required documents | `sub_category_documents` + `documents` | `GET /api/v1/catalog/sub-categories/{id}/documents?requiredOnly=` | public |

App wiring (behind `USE_BACKEND_READS`, PostgREST fallback on error): customer `getCurrency`, splash
`getCurrentCurrency`, `getLanguage`; provider `getCurrency`, `getLanguage`, `getDocuments`,
`getDocumentsBySubCategoryId`, `getRequiredDocumentsBySubCategoryId`. Parity checked on betegna: same rows as the
app's two-step PostgREST lookup (0 mismatches). `GET /config/settings/{id}` strips secret fields (Chapa `secretKey`).

**Do:** implement routes + models + authz.  
**Don't:** wallet credits, payment verify, booking status writes.  
**Rollback:** feature-flag `use_backend_reads=false`.

---

## Plan 2 — Profile & service management writes ✅

| Action | Legacy | Backend | Status |
|--------|--------|---------|--------|
| Update customer profile | `customer` upsert | `PATCH /api/v1/customers/me` | done |
| Update provider profile | `provider` upsert | `PATCH /api/v1/providers/me` | done |
| Provider services CRUD | `service` upsert/delete | `/api/v1/providers/me/services` | done |
| Handyman CRUD | `handyman` upsert/delete | `/api/v1/providers/me/handymen` | done |
| Auth email/phone via Edge | `update-provider-profile-auth` | keep Edge for now | deferred |
| Create customer profile | `customer` upsert (signup) | `POST /api/v1/customers/me` (wallet=0; 409 if exists) | done |
| Create provider profile | `provider` upsert (signup) | `POST /api/v1/providers/me` (wallet=0, not activated) | done |
| Archive profile | client/Edge delete | `DELETE /customers/me`, `DELETE /providers/me` (soft `archived_at`; auth delete stays on Edge) | done |
| Company profile | `companies` upsert | `GET/PUT /api/v1/providers/me/company` | done |
| Verify docs metadata | `verify_documents` | `GET/PUT/DELETE /api/v1/providers/me/documents` (`isVerify` forced false; Storage keys unchanged) | done |
| Payout methods | `provider_payment_methods` | `/api/v1/providers/me/payment-methods` (`providerID` from JWT) | done |
| Service likes | `service.likedUser` overwrite | `PUT/DELETE /api/v1/catalog/services/{id}/like` (caller id only) | done |
| Saved service drafts | `customers_service` + `customer_service_details` | `GET/PUT/DELETE /api/v1/customers/me/service-details` | done |

App wiring behind `USE_BACKEND_WRITES` / `USE_BACKEND_READS` (PostgREST fallback): customer `updateUser` (PATCH then POST), likes, saved service details; provider `updateProvider` (PATCH then POST), company, verify documents, bank/payment methods.

Still deferred: `update-provider-profile-auth` (Supabase Auth email/phone), Storage object delete (apps keep calling Storage), account-auth wipe (`delete-customer` Edge).

**Guards:** patches cannot set `wallet_*`, `activation_*`, `service_tier_*`, or `approved`/`feature` via create. New services start `approved=false`.

Preserve Storage object keys. Keep Realtime on `service`, `verify_documents`.

---

## Plan 3 — Booking lifecycle (non-finance first) ✅

Workflow actions (not free-form status patches). No wallet / payment writes.

| Action | Endpoint | Status |
|--------|----------|--------|
| Accept | `POST /api/v1/bookings/{id}/accept` | done |
| Reject (status only) | `POST /api/v1/bookings/{id}/reject` | done — refunds stay on Edge |
| Assign handyman | `POST /api/v1/bookings/{id}/assign-handyman` | done |
| Status transition | `POST /api/v1/bookings/{id}/status` | done (allowlisted) |
| Customer create booking | `POST /api/v1/bookings` | done (unpaid pending only) |
| Customer cancel | `POST /api/v1/bookings/{id}/cancel` | done — status + pending offers only; refund stays Edge/`applyCancelRefundIfPaid` |
| Job create / patch / close / bid | `POST/PATCH /jobs`, `POST /jobs/{id}/close`, `POST /jobs/{id}/bid` | done (`is_paid` ignored; close = enum `rejected`; bid does not assign `providerId`) |
| Offer create / accept / reject / cancel / attach | `POST /offers`, `POST /offers/{id}/accept\|reject\|cancel\|attach-booking` | done (replaces `attach_service_offer_booking` RPC) |
| Notification read / delete / clear | `POST /notifications/read`, `DELETE /notifications/{id}`, `DELETE /notifications` | done (own rows only; no client `setNotification`) |
| Complete + commission | Edge `complete-booking` | keep until Plan 4 |
| Extra-charge / payment-completed flags | PostgREST `setOrder` | keep until Plan 4 |

App wiring: `USE_BACKEND_BOOKINGS` for cancel / jobs / offers / provider accept-reject-assign-status-bid; `USE_BACKEND_WRITES` for notification read/delete. PostgREST fallback on error. `setNotification` and `send-push-notification` stay on the current path.

Idempotency keys on create. Dual-client: old REST + new API must see same `booked_service` rows (Realtime stays).

---

## Plan 4 — Payments, wallet, recurring (high risk) ✅ writers exist, **gated off**

**Hard rule:** one live writer. Edge Functions remain that writer until cutover.  
Server `PAYMENTS_WRITES_ENABLED` defaults **false** (HTTP 503).  
Client `USE_BACKEND_PAYMENTS` stays **false**. Chapa secret is read from **env only**, never `app_settings`.

| Legacy | Backend | Gate |
|--------|---------|------|
| status probe | `GET /api/v1/payments/status` | live (reports `enabled: false`) |
| `verify-payment` wallet / booking / activation | `POST /api/v1/payments/chapa/verify` | 503 until server flag |
| complete + commission | `POST /api/v1/payments/bookings/{id}/complete` | 503; numeric `adminCommission` or `app_settings.admin_commission` |
| cancel / decline refund | `POST /api/v1/payments/bookings/{id}/refund` | 503; rejects `completed`; amount from `payments` / booking |
| withdrawal request | `POST /api/v1/wallet/withdrawals` | 503; pending only, bank from owned method |
| cancel pending withdrawal | `POST /api/v1/wallet/withdrawals/{id}/cancel` | 503 |
| `notify-recurring-cycle-due` | `app/jobs/recurring.py` | SELECT-only list of due cycles |
| tier / featured / job verify | same verify `purpose` | 501 — Edge stays |

Guards vs live Edge bugs: ledger + balance after `FOR UPDATE`; idempotent on `(transactionId, type, note, isCredit)`; booking verify compares Chapa amount to booking total and consumes `tx_ref`; refunds refuse completed bookings; no client-supplied amount or user id for credits.

App helpers are wired behind `USE_BACKEND_PAYMENTS` (booking verify, wallet top-up, cancel refund, provider withdrawal) with Edge/PostgREST fallback. Do not flip the flag until finance clears the 7 duplicate credit groups and the unique index can be applied.

Still owner-only / not applied: anon money-guard migration; Chapa key rotation; unique ledger indexes.

### 4a — Read-only audit (2026-10-27, betegna) ✅

Ledger model: a wallet balance = credits − debits in `wallet_transaction`
(provider withdrawals are provider-type debits). 464/469 provider balances and
392/399 customer balances satisfy this exactly, so the ledger is the source of truth.

Backend: `GET /api/v1/admin/finance/reconciliation` (`finance:read`, SELECT-only)
reports duplicate credits, balance drift per account, and ledger health.

Baseline at audit time (must not grow once the backend owns money writes):

| Check | Value |
|-------|-------|
| Duplicate credit groups (same tx, type, amount, note) | 7 groups, 73.61 excess |
| Provider balance ≠ ledger | 5 accounts, 1,107.08 abs drift |
| Customer balance ≠ ledger | 6 accounts, 15,206.21 abs drift |
| Provider-typed rows matching no provider | 116 |
| Untyped ledger rows | 3 |

`complete-booking` Edge Function findings (live code not changed; the backend replacement must fix these):

1. **Commission logic is dead code (latent, no loss observed).** It only uses `booked_service.adminCommission` when it
   is an object (the column is `numeric`) and falls back to a `settings` table that does not exist (error ignored), so
   this function would credit the full gross. The real rule lives in `app_settings` (`id`, `data` jsonb). All 35
   recorded "completed (payout after admin commission)" credits did deduct commission, so those payouts most likely
   come from another writer with the same note (e.g. the lolelink/Next payout route). Which writer is live must be
   confirmed before the backend takes over.
2. **Double payout possible.** It checks for an existing credit, then inserts, with no unique constraint and without
   checking that the conditional `pending_approval → completed` update matched a row. The check uses `maybeSingle()`,
   which returns no row when two already exist, so a booking that already has duplicates is paid again on every retry.
   Observed: 3 bookings paid out twice; cancel/decline refunds written 2–10× within seconds.
3. **Lost wallet updates.** `provider.walletAmount` (text) is read, added to and written back without a lock.
4. **Partial failure returns `ok: true`.** Ledger insert and balance update are separate, non-transactional steps.
5. Ownership check compares `booking.customer_id` to the auth uid; correct only where `customer.id = user_id`.

Backend design requirements derived from this:

- Ledger insert + balance update + status transition in **one DB transaction**, provider row `FOR UPDATE`.
- Idempotency enforced by the database: a partial unique index on
  `wallet_transaction("transactionId", type, note-kind)` for payout/refund kinds. It cannot be created until the
  7 existing duplicate groups are resolved by finance, so it ships as a reviewed migration, not an automatic fix.
- Status transition must check rows affected; zero rows means "already processed", not success-with-credit.
- Commission: use the per-booking `adminCommission` amount captured at booking time; fall back to `app_settings.data`
  for `admin_commission`. Match whichever live writer produced the existing correct payouts.

#### Critical: money tables are writable by any client (verified from catalog, no write test performed)

| Table | Policy / grant for `anon` and `authenticated` |
|-------|------------------------------------------------|
| `provider` | `ALL using true` (PUBLIC); UPDATE on `walletAmount` |
| `customer` | `ALL using true` (anon, authenticated); UPDATE on `wallet_amount` |
| `withdrawal_history` | `ALL using true` (PUBLIC); UPDATE on `paymentStatus`, `accountNumber` |
| `wallet_transaction` | public SELECT (everyone's history) + public INSERT |
| `payments` | RLS **off**, full table grants |
| `booked_service` | `ALL using true` (anon, authenticated) |

No triggers guard these columns. With only the public anon key a caller can set any wallet balance, insert ledger
rows, approve a withdrawal or change its destination account, and read every user's transactions and bank details.

This cannot be closed by RLS alone today: the released apps depend on it.

- Customer app `applyCancelRefundIfPaid` inserts the refund row, then `updateUserWallet("+x")` read-modify-writes `customer.wallet_amount`.
- Provider app decline refund (`refundCustomerWalletOnBookingCancel`) credits another user's wallet (`updateOtherUserWallet`).
- Provider `updateUserWallet` / `updateProviderWalletAmount` write `provider.walletAmount`; `setWithdrawRequest` upserts `withdrawal_history`.

The client-side check-then-insert in these flows is the source of the 2–10× duplicate refunds above.

Lowest-risk containment (needs owner decision, staging first): a `BEFORE UPDATE` trigger on `provider`/`customer`
that rejects wallet-column changes and on `withdrawal_history` that rejects `paymentStatus`/account changes when
`auth.role()` is `anon`; then the same for `authenticated` once the apps call backend/Edge endpoints for refunds and
withdrawals. Step 1 is ready but **not applied anywhere**:
`supabase/migrations/20261027200000_guard_money_writes_from_anon.sql`, verified by
`supabase/tests/guard_money_writes_from_anon.sql` (single transaction, rolled back). In a throwaway Postgres 17
it blocks anon wallet changes, non-zero-wallet signups, and any anon write to `withdrawal_history` /
`wallet_transaction`; it allows zero-wallet signups and all `authenticated` writes; re-applying is a no-op. Every
betegna account without ledger activity has wallet `0`/`0.0`/`0.00`/null, so signups pass. The staging project
(`cdmgxbepfixfeumytkag`) is not reachable from this Supabase connection and betegna has no branches, so the staging
run is pending; production waits for explicit approval.

lolelink-admin already drafted cancel-refund unique indexes
(`scripts/sql/add-wallet-transaction-cancel-idempotency-indexes.sql`, not applied; blocked by existing duplicates).

#### Critical: live Chapa secret key is public

- `app_settings` has RLS **off** and full `anon`/`authenticated` grants. Row `payment` holds `data.chapa.secretKey`,
  a **live** key (`CHASECK-` prefix; the `isSandbox: true` flag is misleading). Anyone with the anon key can read it,
  and can also overwrite it or any other setting (`admin_commission`, policies, contact info).
- Released apps depend on this: the customer app (`dashboard_screen_controller.dart` `_finalizePendingServicePayment`,
  `finalizePendingWalletTopup`) and provider app (`bank_detail_screen_controller.dart`) download the secret key and call
  Chapa from the device. Wallet top-ups and booking payments are therefore verified **on the device**, and the
  device then writes the wallet/ledger itself.
- Overwriting `secretKey` with an attacker's own Chapa key would make server-side verification (`verify-payment`
  loads the key from this row before the `CHAPA_SECRET_KEY` env var) accept the attacker's own transactions.
- Needs owner action: review Chapa dashboard activity (transfers/payouts), restrict the key if Chapa allows, and plan
  rotation together with an app release that stops reading the key (rotating now while the apps still read it from
  the table only replaces one exposed key with another). Edge Functions should read `CHAPA_SECRET_KEY` from env only.

`verify-payment` (auth OK via `verifyAuth`; one entry point for wallet / booking / activation / tier / featured):

- Booking: marks `paymentCompleted` for any successful Chapa `tx_ref` **without comparing the paid amount to the
  booking total** and without recording that the `tx_ref` was consumed; one small payment can mark any number of the
  caller's bookings paid.
- `nextCycle`: once a booking is already paid, the same old `tx_ref` passes again and the recurring period advances,
  with `billingInterval` taken from the request body (pay a week, advance a year).
- Wallet: credit = Chapa amount minus fee, idempotent only on `wallet_transaction.transactionId = tx_ref` via
  `maybeSingle()`; no check that the `tx_ref` belongs to the caller or was meant as a top-up (a booking `tx_ref`
  can be redeemed again as wallet credit); ledger insert then non-atomic balance update.

#### Other Edge Functions

- `refund-customer-booking-decline` (verify_jwt on; caller must be the booking's provider). Does **not** check booking
  status, so a provider can refund any paid booking, including one already completed and paid out to them; the
  booking is not moved to a refunded/rejected state. Wallet is updated **before** the ledger insert; if the insert
  fails the balance is credited with no ledger row and a retry credits again (customer drift source). Error responses
  include raw DB errors / `String(e)`.
- `refund-rejected` (provider restores rejected withdrawals). Auth and amount derivation are sound (amount = recorded
  debit). Idempotency is a scan of existing `withdrawal-refund:<id>` rows, so concurrent calls can double-restore;
  ledger insert precedes the wallet update, so a failed update leaves ledger > balance. No duplicates observed.

Remaining audit: `chapa-payment`, activation / tier / featured verify, `job_request_payment`,
`notify-recurring-cycle-due`; and the lolelink payout writer (`src/lib/booking-completion-payout.ts`, read-only).

---

## Plan 5 — Chat / Realtime coexistence ✅

Keep Supabase Realtime for `chat`, `chat_inbox`, `booked_service`. HTTP writes the same tables so streams keep working. Inserting `chat` fires `manage_chat_inbox` (two directional inbox rows: `sender_receiver` and `receiver_sender`).

| Action | Endpoint | Notes |
|--------|----------|--------|
| List inbox | `GET /api/v1/chats/inbox` | caller identities only |
| List messages | `GET /api/v1/chats/{peerId}/messages` | snapshot; live UI stays on Realtime |
| Send | `POST /api/v1/chats/{peerId}/messages` | `senderId` must be a JWT-linked identity; empty body rejected |
| Mark seen | `POST /api/v1/chats/{peerId}/seen` | inbound rows + matching inbox |
| Delete one | `DELETE /api/v1/chats/{peerId}/messages/{chatID}` | participant only; inbox resynced |
| Clear thread | `DELETE /api/v1/chats/{peerId}` | both directions + inbox variants |

App wiring behind `USE_BACKEND_CHAT` (default off). PostgREST fallback. Push (`SendNotification`) stays on the current path. Storage uploads stay on Supabase.

---

---

## Plan 6 — Admin / lolelink

Audit (2026-10-27, betegna `rffptyqhqvzrpmyxlwwu`):

- 65 Next.js route handlers under `src/app/api`. Every non-webhook route is gated by `requireAdminPermission` / `requireAdminSession` (`admin.user_id = auth.uid()`, `is_active`, `admin_role.permissions`). All 3 Chapa webhooks verify signatures. Service-role key is server-only.
- ~20 Redux slices (`src/features/*`, plus `admin/bookings`, `admin/dashboard`, `admin/verify-documents` pages) query PostgREST **from the browser** with the admin's JWT. Their writes only work because the tables carry `ALL using=true` policies, which also let any mobile/anon user perform them.
- Browser writes: `category`, `sub_category`, `sub_category_documents`, `coupon`, `country_tax`, `handyman`, `notification`, `service` (approve/feature/edit/soft-delete), `verify_documents` (+ `provider.verified_subcategory_ids`). (`customerSlice.addCustomer` and `paymentsSlice.updatePayment` exist but are never dispatched — customer creation goes through the `add_customer` Edge Function; no browser booking/payment deletes.)
- No `.rpc`, `functions.invoke` or `storage.from` calls from the browser; `auth.admin.*` only on the server.

Phases (each behind `NEXT_PUBLIC_USE_ADMIN_BACKEND_*`, PostgREST fallback for reads only):

Status:

- [x] 6a `RequireAdmin` / `require_admin_permission` (`app/core/security/admin_deps.py`, grammar in `admin_permissions.py`), `admin_activity_log` written in the same transaction (`admin_audit.py`), `GET /admin/me`.
- [x] 6b service approval + featured decisions, provider document verification (single, reject, approve-pending, reapprove-rejected). Wired in lolelink-admin `approveServicesSlice.ts` / `verifyDocumentsSlice.ts` behind `NEXT_PUBLIC_USE_ADMIN_BACKEND`.
- [x] 6b backend endpoints for catalog (`category`, `sub_category` + `sub_category_documents` atomically), `coupon`, `country_tax`, `handyman`, admin `notification` inbox, service create/edit/archive (`app/api/v1/routers/admin_catalog.py`). FK-blocked deletes return 409.
- [ ] 6b lolelink-admin wiring for the endpoints above (catalog, coupon, tax, handyman, notification, edit/add/delete service slices). Not started — admin repo untouched by design.
- Dropped from 6b: `booked_service` payment-status override. `paymentsSlice.updatePayment` is unused and writes `paid_at`/`escrow_released_at`, which do not exist on `booked_service`. Revisit only inside Plan 4. No booking/payment deletes happen from the browser (the earlier match was `URLSearchParams.delete`).
- [x] 6c backend reads (`app/api/v1/routers/admin_reads.py`): `GET /admin/dashboard/summary` (sections gated per permission), `/admin/customers`, `/admin/providers[/{id}]`, `/admin/services` (provider name + featured-payment match), `/admin/bookings[/{id}]`, `/admin/withdrawals[/{id}]` (with active payout methods). Paginated, searchable, enums validated (422) before hitting Postgres.
- [ ] 6c lolelink-admin wiring for the reads. Not started — admin repo untouched by design.
- [ ] Staging smoke test with an admin account, then enable per environment.

Cross-cutting fix found during 6c: Postgres enum columns (`booked_service.status`, `booked_service.payment_status`, `payments.status`, `job_request.status`, `service.feature_requested_status`, `provider.provider_type`, `provider.company_verification_status`) were mapped as `Text`. asyncpg binds those as `$n::VARCHAR`, which Postgres rejects (`operator does not exist: payment_status_enum = character varying`), so booking create/accept/reject/status (Plan 3) would have failed on first real call. All now use `app/persistence/sqlalchemy/enums.py`; every mapped column was diffed against `information_schema` with zero mismatches; `tests/test_enum_binds.py` guards it.

- **6a Admin auth in backend.** `RequireAdmin(permission)` dependency: Supabase JWT → `admin` row (`is_active`) → `admin_role.permissions`, same permission strings as `lib/admin-permissions.ts`. Every write appends `admin_activity_log`. `GET /api/v1/admin/me`.
- **6b Browser-direct writes → backend** (the actual security win). `/api/v1/admin/{categories,subcategories,subcategory-documents,coupons,taxes,handymen,notifications,services(approve|feature|reject),verify-documents,providers}`. Payment-status edits on `booked_service` go to a dedicated audited endpoint requiring `finance:write`; booking/payment deletes become soft-delete (`is_archived`).
- **6c Browser-direct reads → backend.** Dashboard aggregates, bookings list, customers/providers lists, wallet/withdrawal lists — paginated, server-side.
- **6d Existing Next routes.** Keep as-is (already server-side and guarded). Port non-finance ones (marketing tracker, blog, banners, roles/admins, documents, mobile-app-config, settings) opportunistically; no urgency.
- **6e Finance stays put.** `payout/*`, `admin/bookings/payment*`, `provider/activate-payment*`, Chapa webhooks and `auth.admin.*` user creation/deletion remain in Next/Edge until Plan 4 is done. No dual execution.
- **6f RLS tightening (Plan 7 dependency).** After 6b ships and mobile apps stop writing these tables directly, replace `ALL using=true` with read-only public policies on catalog tables, and admin-only writes via backend (service role). Staging first, one table per migration.

---

## Plan 7 — Deprecate PostgREST paths

Only after adoption metrics + parity. Then tighten RLS (today many `Enable all access` policies; 5 tables have RLS **off** — fix carefully with policies, don't enable blind).

---

## Execution checklist (this sprint)

1. [x] MCP schema inspect + inventory JSON  
2. [x] Plan 1 routes implemented  
3. [x] Tests for ownership filters (booking authz)  
4. [x] Document REST → API map in COMPATIBILITY / PLANS  
5. [x] Plan 2 profile/service/handyman writes  
6. [ ] Client flag wiring (follow-up in `zemen_service`)  
7. [x] Plan 3 booking create + lifecycle + jobs/offers/notification writes (finance still Edge)  
8. [x] Client API stub + feature flags in `zemen_service` + provider package  
9. [x] Wire high-traffic reads/writes behind flags (catalog, profile, bookings)  
10. [ ] Staging cutover smoke (`API_BASE_URL` + `USE_BACKEND_READS=true`)  
11. [x] Plan 4 payment writers implemented and gated off (`PAYMENTS_WRITES_ENABLED=false`)
12. [x] Plan 5 chat send/seen/delete (Realtime stays)
