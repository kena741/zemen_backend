# Role: Senior Frontend Architect & API Contract Auditor

# Objective
We are migrating our backend away from Supabase to a custom FastAPI REST backend.
Your task is to perform an exhaustive audit of this admin dashboard codebase and extract **every single data access point, Supabase call, API request, storage operation, and permission check**.

# Scope of Search
Scan all directories across the admin dashboard codebase, including:
- API route handlers, client services, query hooks (React Query / SWR / RTK Query / custom fetchers)
- Supabase queries (`supabase.from(...)`, `.select()`, `.insert()`, `.update()`, `.delete()`)
- Supabase RPC invocations (`supabase.rpc(...)`)
- Supabase Edge Functions (`supabase.functions.invoke(...)`)
- Supabase Storage access (`supabase.storage.from(...)`)
- Auth hooks, session management, and admin token handling
- Role / Permission gating (e.g., `admin_role`, `permissions.ts`, permission guards on routes/components)
- TypeScript interfaces, types, and Zod/Yup/Joi validation schemas

# Output Deliverable
Generate a comprehensive, structured markdown document named `ADMIN_API_CONTRACT.md` organized by admin module:
1. **Admin Authentication & RBAC** (Login, session validation, role switching, permissions check)
2. **Providers & Verification Management** (List providers, verify documents, status changes, tier updates)
3. **Customer Management** (Customer list, details, address view, wallet balance adjustments)
4. **Service & Catalog Management** (Categories, subcategories, service approval, service edit/delete)
5. **Bookings & Operations Management** (All bookings view, manual status transitions, dispute handling)
6. **Finance, Payouts & Commission** (Payments view, withdrawal requests approval/rejection, bank details)
7. **Document Management & Deliveries** (Upload legal/compliance PDFs, dispatch to providers, receipt tracking)
8. **CRM & Opportunities** (Lead pipeline, opportunity stages, activity logs)
9. **Content & Blog** (Post creation, comment moderation, banners)
10. **Marketing Tracker** (Sheets, columns, row updates)
11. **Platform Configuration** (App settings, mobile version update rules, maintenance mode, taxes, coupons)
12. **Audit & Activity Logs** (Admin actions log, filtering by admin user/resource)

---

# Operation Specification Template
For **EVERY** admin operation identified, document the following standard specification:

---
### Admin Operation: `[MODULE] - [ACTION_NAME]`
- **Call Type**: (`REST HTTP` | `Supabase Table Query` | `Supabase RPC` | `Edge Function` | `Storage`)
- **Target Route / Resource**: (e.g., table `admin_activity_log`, or `provider_payment_methods`, or RPC `acknowledge_document_delivery`, or route `/v1/admin/providers`)
- **Required Admin Permission**: (e.g., `providers:verify`, `services:write`, `finance:read`, `settings:write`, `*`)
- **Source Code Location**: `[File path and line numbers]`
- **UI Screen / Component**: (e.g., `ProviderVerificationModal.tsx`, `BookingDetailDrawer.tsx`)
- **HTTP Method / SQL Action**: (`GET`/`SELECT`, `POST`/`INSERT`, `PATCH`/`UPDATE`, `DELETE`)
- **Request Parameters / Payload**:
  - Query parameters (search terms, status filters, date range filters, pagination limit/offset)
  - Request body (JSON structure with TypeScript types and nullability)
- **Filters & Clauses Applied**:
  - Exact query builder clauses (e.g., `.eq('is_active', true)`, `.order('created_at', { ascending: false })`, `.range(0, 49)`)
- **Expected Response**:
  - Full TypeScript `interface` or `type` definition matching the response
  - Count & pagination format (e.g., `{ data: [...], count: number }`)
- **Side Effects**:
  - Side effects triggered (e.g., logs entry in `admin_activity_log`, invalidates cache key, downloads PDF)
---

# Strict Instructions for the Agent
1. **Zero omissions**: Every table read, update, batch action, document download, and settings toggle must be listed.
2. **Capture exact TypeScript types**: Provide the actual TS `interface` or `type` matching requests and responses.
3. **Capture exact filters**: Detail how the dashboard filters data (e.g., status enums, date strings, search syntax).

