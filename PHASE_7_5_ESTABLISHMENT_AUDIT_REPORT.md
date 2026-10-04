# Veriqoo Phase 7.5 — Atomic Establishment Review & Audit Trail Report

**Author**: Senior Systems & Security Engineer (Antigravity)  
**Date**: 2026-10-05  
**Status**: COMPLETED & VERIFIED (Unit/E2E Suite Passing; Staging Migration Ready for Human Application)

---

## 1. Migration Created & Ordering

### 1.1 Migration Identification & Sequencing
- **File Created**: [`supabase/migrations/20261016000000_t3_4_5_establishment_audit_and_rpc.sql`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/supabase/migrations/20261016000000_t3_4_5_establishment_audit_and_rpc.sql)
- **Timestamp Prefix**: `20261016000000`
- **Chronological Sequencing**:
  1. `20261006000000_t3_1_user_profiles.sql` — User profiles and roles
  2. `20261007000000_t3_2_saved_products.sql` — Saved products
  3. `20261008000000_t3_3_consumer_issues.sql` — Consumer issue reporting
  4. `20261009000000_t3_4_authority_workflow.sql` — Authority profiles and case management
  5. `20261010000000_t3_4_atomic_authority_rpc.sql` — Case assignment & status RPCs
  6. `20261010000001_t3_4_phase5_2_hardening.sql` — Service role grants and hardening
  7. `20261015000000_t3_4_1_establishment_registry.sql` — Retail establishment table, RLS, and constraints
  8. **`20261016000000_t3_4_5_establishment_audit_and_rpc.sql`** — **(New in Phase 7.5)** Atomic review RPC and dedicated establishment audit trail

*Note: The originally proposed timestamp `20261008000000` in the audit recommendation would have broken ordering by preceding the establishment registry table creation (`20261015000000`). The sequence was correctly ordered as `20261016000000`.*

### 1.2 Table Schema: `public.retail_establishment_audit_events`
- `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- `establishment_id UUID NOT NULL REFERENCES public.retail_establishments(id) ON DELETE CASCADE`
- `actor_id UUID NOT NULL` (enforced via validated session context)
- `actor_role TEXT NOT NULL DEFAULT 'authority'`
- `action TEXT NOT NULL` (`VERIFY`, `SUSPEND`, `REVOKE`)
- `event_type TEXT NOT NULL` (`ESTABLISHMENT_VERIFY`, `ESTABLISHMENT_SUSPEND`, `ESTABLISHMENT_REVOKE`)
- `previous_status TEXT NOT NULL`
- `new_status TEXT NOT NULL`
- `previous_is_active BOOLEAN NOT NULL`
- `new_is_active BOOLEAN NOT NULL`
- `notes TEXT` (or safe hash reference if sensitive)
- `provenance TEXT NOT NULL DEFAULT 'MANUAL'`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())`
- Indexes: `idx_est_audit_establishment_id` and `idx_est_audit_created_at`

### 1.3 Row Level Security (RLS) on Audit Events
- `ENABLE ROW LEVEL SECURITY` applied immediately.
- **Authority Read Policy**: Officers can select audit events for establishments within their jurisdiction:
  - Matching state (`p.state_code = re.state_code`)
  - Matching district (`p.jurisdiction_level = 'STATE' OR re.district_code = ANY(p.authorized_district_codes)`)
- **Direct Write Denied**: No insert/update/delete policies granted to `PUBLIC` or `authenticated`. All audit records are written strictly through the atomic PL/pgSQL RPC or service-role backend.

---

## 2. RPC Contract & Authorization Model

### 2.1 Function Signature
```sql
CREATE OR REPLACE FUNCTION public.authority_review_establishment(
    p_establishment_id UUID,
    p_actor_id UUID,
    p_action TEXT,
    p_expected_status TEXT,
    p_notes TEXT DEFAULT NULL,
    p_provenance TEXT DEFAULT 'MANUAL',
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp;
```

### 2.2 Row Locking and Concurrency Guarantees
1. **Explicit Row Lock**:
   ```sql
   SELECT * INTO v_est
   FROM public.retail_establishments
   WHERE id = p_establishment_id
   FOR UPDATE;
   ```
   Blocks concurrent review transactions until the active transaction completes.
2. **Mandatory Optimistic Concurrency Token**:
   - `p_expected_status` must not be null or empty; raises error code `42200` (`CONCURRENCY_TOKEN_REQUIRED`).
   - If `v_est.verification_status != UPPER(TRIM(p_expected_status))`, raises exception with SQLSTATE `40001` (`serialization_failure`) and message prefix `CONCURRENT_UPDATE_CONFLICT`.
3. **Terminal State Protection**:
   - If `v_est.verification_status = 'REVOKED'`, rejection exception is raised: `terminal status 'REVOKED' cannot be transitioned`.
4. **Lifecycle Transitions**:
   - `VERIFY`: Only allowed from `PENDING` or `SUSPENDED`.
   - `SUSPEND`: Only allowed from `VERIFIED`. `PENDING -> SUSPEND` rejected.
   - `REVOKE`: Allowed from `PENDING`, `VERIFIED`, or `SUSPENDED`.
5. **Verifier Identity Preservation**:
   - On `VERIFY`: `verification_authority_id` is updated to `p_actor_id`, and `verification_date` is stamped.
   - On `SUSPEND` or `REVOKE`: `verification_authority_id` is **preserved** (maintaining attribution of who originally certified the establishment). `updated_by` is stamped with `p_actor_id`.
6. **Atomic Audit Insertion & Transactional Rollback**:
   - If the audit event insertion fails, the entire transaction rolls back via PostgreSQL transaction semantics. No partial updates occur.

### 2.3 Privileges and Role Hardening
```sql
REVOKE ALL ON FUNCTION public.authority_review_establishment(...) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.authority_review_establishment(...) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.authority_review_establishment(...) TO service_role;
```
- Direct execution by end users or mobile clients over PostgREST is blocked (HTTP 401/403/404).
- The trusted backend invokes this function exclusively using service-role credentials.

---

## 3. Files Changed

| File | Change Nature | Description |
| :--- | :--- | :--- |
| [`supabase/migrations/20261016000000_t3_4_5_establishment_audit_and_rpc.sql`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/supabase/migrations/20261016000000_t3_4_5_establishment_audit_and_rpc.sql) | **NEW** | Migration for `retail_establishment_audit_events` and `authority_review_establishment` RPC with row locking and strict security privileges. |
| [`backend/app/services/establishment/errors.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/establishment/errors.py) | **MODIFIED** | Added `EstablishmentConcurrencyError` and `EstablishmentDatabaseError` alias. |
| [`backend/app/services/establishment/schemas.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/establishment/schemas.py) | **MODIFIED** | Added `expected_status` to `ReviewEstablishmentRequest`; added `created_by`, `updated_by` to `EstablishmentResponse`; added `EstablishmentAuditEventResponse` and `EstablishmentAuditTimelineResponse`. |
| [`backend/app/services/establishment/repository.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/establishment/repository.py) | **MODIFIED** | Added `review_establishment_atomic` and `get_audit_events` to abstract interface, `InMemoryEstablishmentRepository` (with rollback simulation), and `SupabaseEstablishmentRepository` (PostgREST RPC invocation). |
| [`backend/app/services/establishment/service.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/establishment/service.py) | **MODIFIED** | Enforced mandatory `expected_status` token, enforced jurisdiction boundaries, and delegated review to atomic repository method returning `(establishment, audit_event)`. |
| [`backend/app/api/v1/endpoints/authority.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/api/v1/endpoints/authority.py) | **MODIFIED** | Updated `review_establishment` to pass `expected_status`, map `EstablishmentConcurrencyError` to HTTP 409; added `GET /establishments/{establishment_id}/audit-timeline` with district-scoped authority authorization. |
| [`tests/test_t3_4_2_verification_api.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/tests/test_t3_4_2_verification_api.py) | **MODIFIED** | Added `expected_status` tokens to review calls in existing tests. |
| [`tests/test_t3_4_4_remediation.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/tests/test_t3_4_4_remediation.py) | **MODIFIED** | Unpacked `(updated_est, audit_event)` tuple and supplied `expected_status`. |
| [`tests/test_t3_4_staging_live.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/tests/test_t3_4_staging_live.py) | **MODIFIED** | Added staging tests `test_03_establishment_review_rpc_public_execution_revoked` and `test_04_establishment_review_rpc_contract`. |
| [`tests/test_t3_4_5_atomic_establishment_review.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/tests/test_t3_4_5_atomic_establishment_review.py) | **NEW** | Comprehensive unit & integration test suite (14 test cases) covering lifecycle, concurrency, token validation, audit retrieval, rollback, and cross-district boundary checks. |

---

## 4. Tests Run & Exact Results

### 4.1 Focused Phase 7.5 Atomic Review Tests
Command:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_t3_4_5_atomic_establishment_review.py -v
```
**Results**:
- `test_concurrent_review_conflict`: **PASSED**
- `test_consumer_review_rejected`: **PASSED**
- `test_cross_district_review_rejected`: **PASSED**
- `test_cross_district_timeline_access_rejected`: **PASSED**
- `test_database_error_mapping_to_500`: **PASSED**
- `test_existing_consumer_complaint_and_case_workflow_intact`: **PASSED**
- `test_inactive_officer_review_rejected`: **PASSED**
- `test_invalid_lifecycle_transition_rejected`: **PASSED**
- `test_missing_expected_status_token_rejected_with_422`: **PASSED**
- `test_rollback_when_audit_insertion_fails`: **PASSED**
- `test_stale_expected_status_token_rejected_with_409`: **PASSED**
- `test_successful_review_lifecycle_and_verifier_preservation`: **PASSED**
- `test_terminal_status_cannot_be_transitioned`: **PASSED**
- `test_unauthenticated_request_rejected`: **PASSED**

**Summary**: **14 passed, 0 failed** in 0.96s.

### 4.2 Complete T3-4 Establishment Suite
Command:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_t3_4_1_establishment_registry.py tests/test_t3_4_2_verification_api.py tests/test_t3_4_3_audit_gaps.py tests/test_t3_4_4_remediation.py tests/test_t3_4_5_atomic_establishment_review.py tests/test_t3_4_staging_live.py -v
```
**Summary**: **59 passed, 4 skipped (staging live tests), 0 failed** in 1.16s.

### 4.3 Full T3 Suite
Command:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_t3_1_user_profiles.py tests/test_t3_2_history_and_saved_products.py tests/test_t3_3_consumer_issue_reporting.py tests/test_t3_4_1_establishment_registry.py tests/test_t3_4_2_verification_api.py tests/test_t3_4_3_audit_gaps.py tests/test_t3_4_4_remediation.py tests/test_t3_4_5_atomic_establishment_review.py tests/test_t3_4_atomic_workflow.py tests/test_t3_4_authority_access_control.py tests/test_t3_4_authority_case_workflow.py tests/test_t3_4_staging_live.py tests/test_t3_4_trusted_jurisdiction.py -v
```
**Summary**: **177 passed, 4 skipped, 0 failed, 13 subtests passed** in 2.56s.

---

## 5. Unresolved Risks & Operational Notes

1. **Pending Migration Application**:
   Per strict constraints, migrations are not applied automatically to live databases. `supabase/migrations/20261016000000_t3_4_5_establishment_audit_and_rpc.sql` must be reviewed and executed in the staging Supabase project by an authorized operator.
2. **Actor Profile Validation in RPC**:
   The SQL RPC asserts that `p_actor_id` corresponds to an active authority profile in `public.authority_profiles` and matching `user_profiles.app_role = 'authority'`. When applying to staging/production, the database must contain provisioned authority profiles.
3. **No QR Code Functionality Added**:
   As required by Phase 7.5 constraints, QR code generation and verification functionality remains deferred to Phase 8.

---

## 6. Steps for Human Review & Staging Migration Application

1. **Open Supabase Staging Dashboard / CLI**:
   Ensure you have credentials for the isolated staging project (never production).
2. **Review the Migration Script**:
   Inspect [`supabase/migrations/20261016000000_t3_4_5_establishment_audit_and_rpc.sql`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/supabase/migrations/20261016000000_t3_4_5_establishment_audit_and_rpc.sql) ensuring:
   - Table `public.retail_establishment_audit_events` structure and RLS match documentation.
   - Function `public.authority_review_establishment` has row locking, preconditions, and `SET search_path = public, pg_temp`.
   - Execution is revoked from `PUBLIC` and `authenticated`, granted only to `service_role`.
3. **Apply the Migration via Supabase CLI**:
   ```bash
   supabase db push
   # OR apply specifically via psql
   psql "$STAGING_DATABASE_URL" -f supabase/migrations/20261016000000_t3_4_5_establishment_audit_and_rpc.sql
   ```
4. **Run Live PostgreSQL Integration Tests**:
   Set environment variables and run staging tests:
   ```bash
   export VERIQOO_STAGING_LIVE=true
   export STAGING_SUPABASE_URL="https://<staging-project>.supabase.co"
   export STAGING_SUPABASE_SERVICE_ROLE_KEY="<staging-service-role-key>"
   export STAGING_SUPABASE_ANON_KEY="<staging-anon-key>"

   pytest tests/test_t3_4_staging_live.py -v
   ```
   Verify all 4 staging tests pass, proving that public invocation of `authority_review_establishment` is blocked and service role invocation contract is satisfied.
