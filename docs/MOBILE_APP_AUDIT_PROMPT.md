# Role: Senior Client-Side Systems & API Auditor

# Objective
We are migrating our backend away from Supabase to a custom FastAPI REST backend. 
Your task is to perform an exhaustive audit of this entire mobile app codebase and extract **every single network call, Supabase database interaction, RPC function, Edge function, storage upload/download, and realtime subscription**.

# Scope of Search
Inspect all files across the project, including but not limited to:
- API clients, networking modules, and HTTP interceptors (`http`, `dio`, `fetch`, `axios`)
- Supabase client queries (`supabase.from(...)`, `.select()`, `.insert()`, `.update()`, `.upsert()`, `.delete()`)
- Supabase RPC invocations (`supabase.rpc(...)`)
- Supabase Edge Functions calls (`supabase.functions.invoke(...)`)
- Supabase Storage operations (`supabase.storage.from(...).upload()`, `.getPublicUrl()`, `.download()`, etc.)
- Realtime table/channel listeners (`supabase.channel(...)`, `.on('postgres_changes', ...)`)
- Auth flows (`supabase.auth.signInWithPassword`, `signUp`, `resetPasswordForEmail`, token refresh)
- Repositories, data sources, state management layers (BLoC, Cubit, Riverpod, Provider, GetX, ViewModel)
- Client-side data models and DTOs (classes with `fromJson`, `toJson`, `factory`, serialization)

# Output Deliverable
Generate a comprehensive, structured markdown document named `MOBILE_API_CONTRACT.md` organized by domain module:
1. **Authentication & Session** (Sign in, sign up, password recovery, token storage)
2. **User Profiles** (Customer, Provider, Handyman profile fetch and update)
3. **Services & Catalog** (Categories, subcategories, service listings, search, filtering)
4. **Bookings & Lifecycle** (Creation, listing, status transitions, OTP verification, extra charges, completion)
5. **Job Requests & Offers** (Custom job requests, provider bids, offer negotiations)
6. **Billing, Payments & Wallet** (Chapa / payment triggers, wallet transactions, balance, payout requests)
7. **Communication & Chat** (Inbox fetch, 1-on-1 messaging, read receipts, media messages)
8. **Reviews & Feedback** (Review submission, ratings fetch, bug/app feedback)
9. **Notifications & FCM** (Device token registration, push notification inbox, mark as read)
10. **Storage & Media** (Profile images, service images, proof of work images)
11. **App Configuration** (Banners, app settings, maintenance / force update check)

---

# Endpoint Specification Template
For **EVERY** call identified in the app, document the following standard specification:

---
### Endpoint: `[DOMAIN] - [ACTION_NAME]`
- **Call Type**: (`Supabase Table Query` | `Supabase RPC` | `Edge Function` | `REST HTTP` | `Storage` | `Realtime Listener`)
- **Target / Route**: (e.g., Supabase table `booked_service`, or RPC `attach_service_offer_booking`, or URL `/v1/bookings`)
- **Caller Context / Role**: (`Customer`, `Provider`, `Handyman`, or `Public/Unauthenticated`)
- **Trigger Location in Code**: `[File path and line numbers]`
- **Trigger Event / UI Screen**: (e.g., "Triggered when user clicks 'Confirm Booking' on CheckoutScreen")
- **Request Parameters / Payload**:
  - URL Query Parameters (e.g., `?category_id=...&limit=20`)
  - Headers / Auth requirement (e.g., Bearer Token required)
  - Body payload: Provide the exact fields, data types, nullability, and a sample JSON.
- **Client Model / Serialization**:
  - Show the client model class name (e.g., `BookingModel`, `CustomerDto`)
  - Include code snippet of `toJson()` or parameter map construction.
- **Filters, Order & Pagination Clauses**:
  - Detail exact query builder calls (e.g., `.eq('user_id', uid)`, `.order('created_at', ascending: false)`, `.range(0, 19)`)
- **Expected Response**:
  - Expected status codes (e.g., `200 OK`, `201 Created`)
  - Full response payload structure (nested objects, lists, types)
  - Show client model class name and snippet of `fromJson()` (pay special attention to camelCase vs snake_case keys like `bookingDate`, `paymentCompleted`, `serviceName`, etc.)
- **Error Handling**: How the mobile app handles errors (e.g., checks `res.error`, expects specific message/status code).
---

# Strict Instructions for the Agent
1. **Be 100% exhaustive**: Do not summarize or skip similar calls (e.g., if there are 8 distinct booking status update actions, document each one with its exact payload).
2. **Preserve exact field names**: Retain exact casing (e.g., `bookingDate`, `paymentCompleted`, `serviceName`, `taxList`). Do not assume snake_case if the client expects camelCase.
3. **Include edge cases**: List background syncs, FCM token registration calls, analytics triggers, and polling logic.

