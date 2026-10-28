# Compatibility — Zemen Service clients ↔ backend

## Auth

| Concern | Behavior |
|---------|----------|
| Login / refresh / logout / reset | Remain on **Supabase Auth** (and existing Edge Functions for phone reset) |
| API calls | `Authorization: Bearer <supabase_access_token>` |
| User ids | `auth.users.id` ↔ `customer.user_id` / `provider.user_id` — unchanged |
| Roles | Derived from profile rows (customer and/or provider can both exist on one user) |

## Read parity (Plans 0–1)

Legacy REST base: `https://rffptyqhqvzrpmyxlwwu.supabase.co/rest/v1/<table>`

| Mobile / PostgREST | Backend |
|--------------------|---------|
| `category` | `GET /api/v1/catalog/categories` |
| `sub_category` | `GET /api/v1/catalog/sub-categories` |
| `service` (approved) | `GET /api/v1/catalog/services` |
| `banner` | `GET /api/v1/config/banners` |
| `country_tax` | `GET /api/v1/config/taxes` |
| `coupon` | `GET /api/v1/config/coupons` |
| `app_settings` | `GET /api/v1/config/settings/{id}` |
| `mobile_app_config` | `GET /api/v1/config/mobile/{app_key}` |
| `customer` by `user_id` | `GET /api/v1/customers/me` |
| `provider` by `user_id` | `GET /api/v1/providers/me` |
| `handyman` by provider | `GET /api/v1/providers/me/handymen` |
| `booked_service` by customer | `GET /api/v1/bookings` |
| `booked_service` by provider | `GET /api/v1/providers/me/bookings` |
| `booked_service` by id | `GET /api/v1/bookings/{id}` |
| `job_request` | `GET /api/v1/jobs?as=customer\|provider` |
| `service_offer` | `GET /api/v1/offers?as=customer\|provider` |
| `review_customer` | `GET /api/v1/reviews?serviceId=` |
| `notification` | `GET /api/v1/notifications` |
| `wallet_transaction` | `GET /api/v1/wallet/transactions` |
| `withdrawal_history` | `GET /api/v1/wallet/withdrawals` |

### Write parity (Plan 2)

| Mobile / PostgREST | Backend |
|--------------------|---------|
| `customer` upsert (profile) | `PATCH /api/v1/customers/me` |
| `provider` upsert (profile) | `PATCH /api/v1/providers/me` |
| `service` select by provider | `GET /api/v1/providers/me/services` |
| `service` upsert | `POST` / `PATCH /api/v1/providers/me/services` |
| `service` delete | `DELETE /api/v1/providers/me/services/{id}` |
| `handyman` upsert/delete | `POST` / `PATCH` / `DELETE /api/v1/providers/me/handymen` |
| booking create (`setOrder` unpaid) | `POST /api/v1/bookings` |
| booking accept/reject/status upsert | `POST /api/v1/bookings/{id}/accept\|reject\|status\|assign-handyman` |
| `review_customer` insert | `POST /api/v1/reviews` |
| FCM token update | `PUT /api/v1/customers/me/fcm-token` / `providers/me/fcm-token` |

### Client flags (`zemen_service` dotenv)

| Key | Effect |
|-----|--------|
| `API_BASE_URL` | Backend origin (required for any backend path) |
| `USE_BACKEND_READS` | Catalog/config/profile reads via API |
| `USE_BACKEND_WRITES` | Profile/service/handyman writes |
| `USE_BACKEND_BOOKINGS` | Booking create/actions |
| `USE_BACKEND_PAYMENTS` | **Keep false** until Plan 4 |

### Wired Flutter call sites (flagged, PostgREST fallback)

**Customer (`zemen_service`)**
- reads: `getCategory`, `getServiceData`, `getUserProfile` (self), `getBookingData`, `getCustomerBookingsOnce`
- writes: `updateUser` (`USE_BACKEND_WRITES`)
- bookings: unpaid `setOrder` → `POST /bookings` (`USE_BACKEND_BOOKINGS`)

**Provider package**
- reads: `getCategory`, `getBookingList`, `getBooking`, `getServiceDetailsByProviderId` (own)
- writes: `updateProvider` (`USE_BACKEND_WRITES`)
- bookings: `updateBooking` accept/reject → action endpoints (`USE_BACKEND_BOOKINGS`)

Realtime streams (`getBookingsStreamForCustomer`, chat) remain on Supabase.

Response JSON uses camelCase aliases for fields the Flutter models already expect (`serviceName`, `bookingDate`, `paymentCompleted`, …).

**Note:** Reject sets status only. Paid-booking refunds still use Edge `refund-customer-booking-decline` until Plan 4.

## Still on Supabase (do not cut over yet)

- Realtime streams on `booked_service`, `job_request`, `chat`, `chat_inbox`
- Storage uploads (`betegnabucket`, …)
- All Chapa / wallet / refund / tier Edge Functions
- Booking status transitions that credit wallets or commissions
- `lolelink-admin` admin mutations not listed below

## lolelink-admin (Plan 6)

Flags (browser, per Supabase target selected in the env switcher):

| Env | Meaning |
|-----|---------|
| `NEXT_PUBLIC_USE_ADMIN_BACKEND` | `true` routes the wired thunks to the API |
| `NEXT_PUBLIC_ZEMEN_API_URL` | API base for the prod target |
| `NEXT_PUBLIC_ZEMEN_API_URL_STAGING` | API base for the staging target; unset keeps staging on PostgREST |

Wired call sites (no fallback once the API path is chosen):

| Thunk | Was | Now |
|-------|-----|-----|
| `approveServiceById` | `service.update({approved})` | `POST /admin/services/{id}/approve` (`services:write`) |
| `approveServicesByProvider` | select + `service.update` | `POST /admin/providers/{id}/services/approve` |
| `approve/reject/unfeatureServiceById` | `service.update({feature, feature_requested_status})` | `POST /admin/services/{id}/feature` `{decision}` |
| `verifyDocument` | `verify_documents` + `provider.verified_subcategory_ids` with manual undo | `POST /admin/verify-documents/{id}/verify` (`providers:verify`, one transaction) |
| `rejectDocument` | same | `POST /admin/verify-documents/{id}/reject` `{reason}`; push still via `/api/admin/push/notify` |
| `approveAllDocuments` / `reapproveAllRejectedDocuments` | bulk update | `POST /admin/providers/{id}/verify-documents/approve-pending` / `reapprove-rejected` |

Activity log rows written by the API carry `metadata.source = "zemen_backend"`.

Backend-ready, not yet wired in lolelink-admin:

| Slice / thunk | Endpoint | Permission |
|---------------|----------|------------|
| `categorySlice` add/update/delete | `POST /admin/categories`, `PATCH`/`DELETE /admin/categories/{id}` | `catalog:write` |
| `subcategorySlice` add/update/delete (+ `documentIds`) | `POST /admin/subcategories`, `GET`/`PATCH`/`DELETE /admin/subcategories/{id}` | `catalog:write` |
| `couponSlice` | `GET`/`POST /admin/coupons`, `PATCH`/`DELETE /admin/coupons/{id}` | `catalog:read` / `catalog:write` |
| `taxSlice` (`isFix` derived from `type`) | `GET`/`POST /admin/taxes`, `PATCH`/`DELETE /admin/taxes/{id}` | `finance:read` / `finance:write` |
| `handymanSlice` | `GET`/`POST /admin/handymen`, `PATCH`/`DELETE /admin/handymen/{id}` | `providers:read` / `providers:write` |
| `notificationSlice` mark read / mark all / delete | `GET /admin/notifications`, `POST /admin/notifications/read` `{ids?}`, `POST /admin/notifications/delete` `{ids}` | `notifications:*` |
| `addServiceSlice` / `editServiceSlice` / `deleteServiceSlice` | `POST /admin/services`, `PATCH /admin/services/{id}`, `POST /admin/services/{id}/archive` | `services:write` |

Reads (6c), replacing browser full-table selects:

| Browser source | Endpoint | Permission |
|----------------|----------|------------|
| `customerSlice` (`customer` + booking counts + provider flag) | `GET /admin/customers?search&includeArchived&limit&offset` | `customers:read` |
| `providerSlice` list / by id | `GET /admin/providers?search&active&includeArchived`, `GET /admin/providers/{id}` | `providers:read` |
| `approveServicesSlice.fetchServices`, `providerSlice` services | `GET /admin/services?providerId&includeArchived&approved&featureStatus&search` | `services:read` |
| `bookedServiceSlice`, `paymentsSlice.fetchPayments`, bookings page | `GET /admin/bookings?status=..&paymentStatus=..&providerId&customerId&from&to`, `GET /admin/bookings/{id}` | `bookings:read` |
| `payoutSlice` (+ `provider_payment_methods`) | `GET /admin/withdrawals?status&providerId`, `GET /admin/withdrawals/{id}` | `finance:read` |
| (new, no legacy equivalent) | `GET /admin/finance/reconciliation?limit` — duplicate credits, wallet vs ledger drift (SELECT-only) | `finance:read` |
| `admin/dashboard/page.tsx` counts | `GET /admin/dashboard/summary` | any admin; sections need their read permission |

Behavior differences vs. the browser path:

- Notification bulk ops only touch `recipient_role = 'admin'` rows (browser "mark all read" updates every unread row in the table).
- Sub-category document links are replaced in the same transaction as the sub-category update.
- Deletes blocked by foreign keys (category used by services, handyman on bookings) return 409 instead of a raw Postgres error.
- Storage uploads/removals for service images and videos stay client-side; the API stores URLs only.

## Retirement conditions

A PostgREST table path may be deprecated only when:

1. Updated `zemen_service` builds use the API for that domain in production,
2. Parity tests pass for old+new clients on the same rows,
3. Realtime/storage side effects still fire from API writes,
4. Adoption metrics show released builds below the agreed threshold.

## PostgREST (`/rest/v1/`) gap list — 2026-10-27

Source: betegna `public` schema catalog (everything PostgREST exposes) cross-checked with every `.from()`, `.rpc()`
and `functions.invoke()` call in `zemen_service` (customer app) and `packages/zemen_provider` (provider app).
`C` = customer app, `P` = provider app.

### Used by the apps, no backend endpoint yet

| Table / call | App usage | Needed backend endpoint | Plan |
|--------------|-----------|-------------------------|------|
| `booked_service` extra-charge flags | customer `setOrder` (C) | keep PostgREST until payment cutover | 4 leftover |
| Edge `send-push-notification` | invoke (C, P) | server-side side effect of the action that triggers it | 3 leftover |
| Edge `update-provider-profile-auth` | invoke (P) | `PATCH /providers/me` (auth email/phone part) | 2 |
| `service_tier_payment` / featured / job verify | insert, select (P) | `purpose=tier\|featured\|job` returns 501; Edge stays | 4 leftover |
| Chapa verify on device (apps still read `app_settings` secret) | C booking + wallet; P banks | backend verify exists but `USE_BACKEND_PAYMENTS` stays false | 4 leftover |

Already covered: `app_settings` (`GET /config/settings/{id}`, secret fields now stripped), `currencies`
(`/config/currency`), `languages`, `documents` + `sub_category_documents` (Plan 1, wired in both apps), `banner`, `category`,
`sub_category`, `country_tax`, `coupon`, `review_customer`, `handyman` (provider CRUD), `service` (catalog + provider
CRUD), `booked_service` reads/create/accept/reject/assign/status/cancel, `job_request` reads + create/patch/close/bid,
`service_offer` reads + create/accept/reject/cancel/attach-booking, `notification` list + mark-read/delete/clear (no
client create), wallet and withdrawal reads, `customer`/`provider` `me` + FCM token + create/archive,
company, verify-document metadata, payment methods, service likes, saved service details (Plan 2), `chat` /
`chat_inbox` send/seen/delete/inbox list (Plan 5; Realtime streams stay on Supabase), Plan 4 money writers
(`POST /payments/chapa/verify`, booking complete/refund, wallet withdrawals) — **HTTP 503 until
`PAYMENTS_WRITES_ENABLED`**. Extra-charge flags and on-device Chapa stay until cutover.

App references to tables that do not exist (legacy fallbacks, always fail): `settings`, `tax`, `walletTransaction`.

### Exposed by PostgREST, not used by either app

All have anon read **and** write (RLS `using true` or RLS off). Used by lolelink-admin / web or unused; they need RLS
review rather than mobile endpoints: `admin`, `admin_role`, `admin_activity_log`, `admin_documents`, `activities`,
`bank_details`, `blog_post`, `blog_comment`, `blog_like`, `contact_messages`, `document_deliveries`, `feedback`,
`marketing_tracker_{sheet,column,row}`, `mobile_app_config`, `notifications`, `opportunities`,
`opportunity_stage_history`, `page_views`, `provider_analytics`, `provider_availability_weekly`,
`provider_blocked_dates`, `provider_customer`, `subscriptions`. RLS **off**: `app_settings`, `payments`,
`notification`, `customer_service_details`, `customers_service`.
RPCs exposed to anon: `acknowledge_document_delivery`, `add_blog_comment`, `attach_service_offer_booking`,
`current_provider_profile_id`, `get_deletable_storage_paths`, `get_my_document_delivery_path`, `has_blog_like`,
`increment_blog_view`, `list_my_document_deliveries`, `toggle_blog_like`.
