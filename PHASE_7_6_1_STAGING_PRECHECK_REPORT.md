# PHASE 7.6.1: READ-ONLY STAGING PRECHECK & VERIFICATION REPORT

**Date:** 2026-10-05  
**Mode:** Read-Only Static Verification & Codebase Audit  
**Scope:** T3.1 through T3.4.5 Migrations, Staging Test Fixtures, Account Provisioning, and Flutter Client Configuration  
**Live DB Mutation Status:** **ZERO MUTATIONS PERFORMED (Paused awaiting user authorization)**

---

## 1. Executive Summary & Verification Findings

| Verification Category | Expected Invariant | Actual Repository Status | Audit Classification |
|---|---|---|---|
| **SQL Migrations 1–8** | Correct dependency ordering, table names, and RPC grants | 8 migrations reviewed; tables and security definers intact | **VERIFIED** |
| **Establishment Table Identity**| Exact table name in SQL & Python repository | SQL & backend repo use `retail_establishments` and `retail_establishment_audit_events` | **VERIFIED** |
| **Foundational DB Dependency** | `inspection_sessions` table required for FKs | Created in migration `20261004000000_phase8b_inspection_persistence.sql` | **VERIFIED** (Prerequisite identified) |
| **Staging Live Test Safety** | Non-destructive test execution against staging | Tests 01–04 perform zero data creation/mutation/deletion | **VERIFIED** |
| **Authority Account Provisioning**| Zero privilege escalation via public registration | Public `PATCH /users/me` disallows `app_role` modification; authority profiles require service-role provisioning | **VERIFIED** |
| **Flutter Staging Config** | Correct `--dart-define` keys for Supabase & FastAPI | `main.dart` requires `SUPABASE_URL`, `SUPABASE_KEY`; API client uses `VERIQOO_API_URL` | **VERIFIED** (Command parameters corrected) |

---

## 2. Migration Audit & Exact Database Contract

Inspection of the 8 migrations in `supabase/migrations/` confirms the following real database objects:

### Migration 1: `20261006000000_t3_1_user_profiles.sql`
- **Table Created:** `public.user_profiles`
- **Columns:** `id` (uuid pk), `user_id` (uuid unique, non-empty), `display_name` (text), `language_preference` (text in `en,hi,mr,ta,te,kn,gu,bn,pa`), `app_role` (text in `consumer,inspector,authority,admin`), `created_at`, `updated_at`.
- **Indexes:** `idx_user_profiles_user_id` (unique), `idx_user_profiles_app_role`.
- **Dependencies:** `auth.users`.

### Migration 2: `20261007000000_t3_2_saved_products.sql`
- **Table Created:** `public.saved_products`
- **Columns:** `id` (uuid pk), `user_id` (uuid), `inspection_id` (uuid REFERENCES `public.inspection_sessions(id)` ON DELETE CASCADE), `product_name`, `notes`, `created_at`, `updated_at`.
- **Constraints:** `UNIQUE (user_id, inspection_id)`.
- **Dependencies:** `public.inspection_sessions` (from `20261004000000_phase8b_inspection_persistence.sql`).

### Migration 3: `20261008000000_t3_3_consumer_issues.sql`
- **Table Created:** `public.consumer_issues`
- **Columns:** `id` (uuid pk), `user_id` (uuid), `inspection_id` (uuid REFERENCES `public.inspection_sessions(id)` ON DELETE SET NULL), `saved_product_id` (uuid REFERENCES `public.saved_products(id)` ON DELETE SET NULL), `issue_type` (check constraint), `title`, `description`, `status` (`SUBMITTED, UNDER_REVIEW, RESOLVED, REJECTED`), `resolution_notes`, `evidence_images` (jsonb array), `created_at`, `updated_at`.
- **RLS Policies:** `consumer_issues_select_own` (auth.uid = user_id), `consumer_issues_insert_own` (auth.uid = user_id, status = SUBMITTED), `consumer_issues_delete_own` (auth.uid = user_id, status = SUBMITTED).

### Migration 4: `20261009000000_t3_4_authority_workflow.sql`
- **Tables Created:**
  - `public.authority_profiles` (`user_id` unique, `department`, `designation`, `state_code`, `jurisdiction_level`, `authorized_district_codes` text[], `is_active`).
  - `public.consumer_issue_notes` (`issue_id` REFERENCES `consumer_issues`, `author_id`, `note_text`, `is_internal`).
  - `public.consumer_issue_audit_events` (`issue_id` REFERENCES `consumer_issues`, `actor_id`, `actor_role`, `event_type`, `previous_state`, `new_state`, `metadata`).
- **Altered Tables:** `public.consumer_issues` extended with `department`, `state_code`, `district_code`, `jurisdiction_verified`, `assigned_officer_id`, `assigned_at`, `assigned_by`.
- **RLS Policies:** Authority scoped SELECT on `consumer_issues`, `consumer_issue_notes`, `consumer_issue_audit_events`.

### Migration 5: `20261010000000_t3_4_atomic_authority_rpc.sql`
- **RPC Functions:** `public.authority_assign_case`, `public.authority_transition_status`.
- **Security:** `SECURITY DEFINER SET search_path = public, pg_temp; REVOKE ALL FROM PUBLIC, authenticated; GRANT EXECUTE TO service_role;`

### Migration 6: `20261010000001_t3_4_phase5_2_hardening.sql`
- **RPC Replacements:**
  - `public.authority_assign_case(uuid, uuid, uuid, uuid, boolean)`: Enforces self-assignment only and explicit `p_expect_unassigned`.
  - `public.authority_create_case_note(uuid, uuid, text, jsonb)`: Atomic note creation + `NOTE_ADDED` audit logging.
- **Grants:** `REVOKE ALL FROM PUBLIC, authenticated; GRANT EXECUTE TO service_role;`

### Migration 7: `20261015000000_t3_4_1_establishment_registry.sql`
- **Table Created:** `public.retail_establishments`
- **Columns:** `id` (uuid pk), `trade_name`, `legal_name`, `gstin` (varchar(15) unique), `lm_license_number`, `shop_establishment_number`, `state_code`, `district_code`, `pincode`, `physical_address`, `verification_status` (`PENDING, VERIFIED, SUSPENDED, REVOKED`), `verification_provenance` (`MANUAL, ESTABLISHMENT_QR, VERIFIED_GSTIN_INVOICE, ADMIN_TRIAGE_VERIFICATION, OFFICIAL_REGISTRY`), `verification_authority_id` (REFERENCES `authority_profiles(id)`), `verification_date`, `verification_notes`, `is_active`, `created_by`, `updated_by`, `created_at`, `updated_at`.
- **Altered Tables:** `public.consumer_issues` extended with `establishment_id` (REFERENCES `public.retail_establishments(id)` ON DELETE SET NULL), `jurisdiction_provenance`, `jurisdiction_verified_at`, `jurisdiction_verified_by`.
- **RPC Function:** `public.authority_verify_complaint_jurisdiction`.
- **Grants:** `GRANT EXECUTE TO service_role;`

### Migration 8: `20261016000000_t3_4_5_establishment_audit_and_rpc.sql`
- **Table Created:** `public.retail_establishment_audit_events`
- **Columns:** `id` (uuid pk), `establishment_id` (REFERENCES `public.retail_establishments(id)` ON DELETE CASCADE), `actor_id`, `actor_role`, `action` (`VERIFY, SUSPEND, REVOKE`), `event_type`, `previous_status`, `new_status`, `previous_is_active`, `new_is_active`, `notes`, `provenance`, `metadata`, `created_at`.
- **RLS Policy:** `retail_establishment_audit_events_select_authority` allows active officers matching territorial state/district to SELECT. Direct client write operations disallowed.
- **RPC Function:** `public.authority_review_establishment(uuid, text, uuid, text, text, text)` with `FOR UPDATE` lock, mandatory `expected_status` token, and atomic audit logging.
- **Grants:** `REVOKE ALL FROM PUBLIC, authenticated; GRANT EXECUTE TO service_role;`

---

## 3. Discrepancy Resolution: `retail_establishments` Table Naming

- **Finding:** Migration 7 and Migration 8 define the tables as:
  - `public.retail_establishments`
  - `public.retail_establishment_audit_events`
- **Backend Code Verification:**
  In `backend/app/services/establishment/repository.py`:
  - `SupabaseEstablishmentRepository` explicitly targets `"retail_establishments"` for all CRUD operations (lines 408, 417, 429, 444, 475).
  - `SupabaseEstablishmentRepository` explicitly targets `"retail_establishment_audit_events"` for audit queries (line 555).
- **Resolution:** The database schema and backend implementation are in **100% agreement**. No SQL objects or Python files require renaming. Checklists and deployment docs should always reference the canonical names `public.retail_establishments` and `public.retail_establishment_audit_events`.

---

## 4. Staging Live Test Safety Inspection (`tests/test_t3_4_staging_live.py`)

A detailed inspection of the 4 test cases in `tests/test_t3_4_staging_live.py` reveals:

1. **Environment Variables Required:**
   - `VERIQOO_STAGING_LIVE=true`
   - `STAGING_SUPABASE_URL` (or `SUPABASE_URL`)
   - `STAGING_SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_SERVICE_ROLE_KEY`)
   - `STAGING_SUPABASE_ANON_KEY` (or `SUPABASE_ANON_KEY`, optional for anon tests)
2. **Safety Fixture:**
   `setUpClass` validates that the URL does not contain `"prod"` without `"staging"`, immediately raising `RuntimeError("CRITICAL SAFETY HALT")` if a production target is detected.
3. **Behavior of Individual Tests:**
   - `test_01_public_rpc_execution_is_revoked`: Calls `POST /rest/v1/rpc/authority_assign_case` with anon key and `{}`. Asserts HTTP 401, 403, or 404 (non-mutating auth check).
   - `test_02_staging_health_and_version`: Calls `GET /rest/v1/` with service key. Asserts HTTP 200 (read-only health check).
   - `test_03_establishment_review_rpc_public_execution_revoked`: Calls `POST /rest/v1/rpc/authority_review_establishment` with anon key and `{}`. Asserts HTTP 401, 403, or 404 (non-mutating auth check).
   - `test_04_establishment_review_rpc_contract`: Calls `POST /rest/v1/rpc/authority_review_establishment` with service key and `{}`. Asserts HTTP 400/422/500 validation failure due to missing arguments (non-mutating schema probe).
4. **Data Mutation Assessment:**
   **Zero records are created, modified, or deleted.** The test suite is completely safe to execute against a dedicated staging environment.

---

## 5. Test Account Provisioning Workflow (Zero Public Privilege Escalation)

1. **Consumer Profile Provisioning:**
   - Flow: Standard Supabase Auth signup (`POST /auth/v1/signup`) -> User signs in -> FastAPI `GET /api/v1/users/me` automatically calls `UserProfileService.get_or_create_profile`, creating a record in `public.user_profiles` with `app_role: 'consumer'`.
   - Security Check: `PATCH /api/v1/users/me` only accepts `display_name` and `language_preference`. Any attempt to pass `app_role` is ignored/rejected by schema validation.
2. **Authority Profile Provisioning:**
   - Authority status requires two database records:
     1. `public.user_profiles` with `app_role = 'authority'`.
     2. `public.authority_profiles` with `department = 'LEGAL_METROLOGY'`, `state_code = 'Maharashtra'`, `authorized_district_codes = '{Pune}'`, `is_active = true`.
   - **Trusted Provisioning Mechanism:** Cannot be self-assigned by consumers. Must be provisioned either via direct administrative SQL script (service_role) or administrative onboarding script during staging initialization.

---

## 6. Flutter Staging Configuration & Corrected Commands

### Identified Discrepancies in Previous Run Command:
1. `lib/main.dart` enforces `const supabaseUrl = String.fromEnvironment('SUPABASE_URL')` and `const supabaseKey = String.fromEnvironment('SUPABASE_KEY')`. If either is empty, `main()` throws `StateError('Supabase is not configured')`.
2. `ConsumerIssueApiService` and `AuthorityApiService` look for `const String.fromEnvironment('VERIQOO_API_URL', defaultValue: 'http://localhost:8000/api/v1')`, NOT `API_BASE_URL`.

### Corrected Flutter Launch Command:
```powershell
C:\flutter\flutter\bin\flutter.bat run -d windows `
  --dart-define=SUPABASE_URL=https://<staging-project-ref>.supabase.co `
  --dart-define=SUPABASE_KEY=<staging-anon-key> `
  --dart-define=VERIQOO_API_URL=http://localhost:8000/api/v1
```

---

## 7. Migration Prerequisites for Clean Staging Database

If the target staging database is a completely fresh Supabase instance, all migrations up to `20261016000000` must be applied in chronological order. Specifically, migration `20261004000000_phase8b_inspection_persistence.sql` MUST be applied prior to `20261007000000_t3_2_saved_products.sql` to provide the `public.inspection_sessions` parent table.

### Full Staging Migration Order:
1. `20260829000000_enable_legal_rule_embeddings.sql`
2. `20260829000001_match_legal_rules.sql`
3. `20261002000000_legal_corpus_hierarchy.sql`
4. `20261002000001_legal_corpus_phase2.sql`
5. `20261002000002_phase3a_applicability.sql`
6. `20261003000000_phase4b_legal_embeddings.sql`
7. `20261003000001_phase4c_match_legal_corpus_embeddings.sql`
8. `20261004000000_phase8b_inspection_persistence.sql` *(Prerequisite for T3.2 & T3.3)*
9. `20261005000000_phase9e_telegram_account_links.sql`
10. `20261006000000_t3_1_user_profiles.sql`
11. `20261007000000_t3_2_saved_products.sql`
12. `20261008000000_t3_3_consumer_issues.sql`
13. `20261009000000_t3_4_authority_workflow.sql`
14. `20261010000000_t3_4_atomic_authority_rpc.sql`
15. `20261010000001_t3_4_phase5_2_hardening.sql`
16. `20261015000000_t3_4_1_establishment_registry.sql`
17. `20261016000000_t3_4_5_establishment_audit_and_rpc.sql`
