# Veriqoo Phase 7.4.1 — Persistent Establishment Registry & Jurisdiction Foundation Report

## 1. Executive Summary

Phase 7.4.1 implements the database foundation, repository layer, and atomic verification RPC for trusted retail commercial establishments and consumer complaint jurisdiction verification, following the architecture approved in [PHASE_7_4_TRUSTED_JURISDICTION_DESIGN.md](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/PHASE_7_4_TRUSTED_JURISDICTION_DESIGN.md).

Key achievements in this phase:
1. **Migration Authoring (`public.retail_establishments`):** Designed and authored `supabase/migrations/20261015000000_t3_4_1_establishment_registry.sql`, providing persistent establishment storage, official business identifiers (GSTIN, LM License, Shop & Establishment Number), canonical ISO/LGD jurisdiction fields, verification lifecycle states, and update triggers.
2. **Complaint Schema Extensions (`public.consumer_issues`):** Extended complaints with `establishment_id`, `jurisdiction_provenance`, `jurisdiction_verified_at`, and `jurisdiction_verified_by`.
3. **Strict Authorization Policies:** Configured Row Level Security (RLS) restricting public and authenticated access to verified establishments only, while granting officers access strictly within their authorized departmental and geographic boundaries. Direct client manipulation is completely disabled.
4. **Atomic Verification RPC (`public.authority_verify_complaint_jurisdiction`):** Authored an audited PostgreSQL `SECURITY DEFINER` function with row-level locks on both complaint and establishment rows, strict actor jurisdiction enforcement, provenance validation, and atomic audit logging. Executable only by the backend `service_role`.
5. **Backend & Domain Models:** Implemented `RetailEstablishment` dataclasses, `EstablishmentRepository` interfaces (`InMemoryEstablishmentRepository` and `SupabaseEstablishmentRepository`), updated complaint domain models and schemas, and wired repository dependency providers.
6. **Zero-Regression Test Suite:** Added 13 new unit and static audit tests in `tests/test_t3_4_1_establishment_registry.py` (total 133 backend tests passing, 0 failures, 0 regressions).

---

## 2. Migration Details & DDL Specification

Migration file: [`supabase/migrations/20261015000000_t3_4_1_establishment_registry.sql`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/supabase/migrations/20261015000000_t3_4_1_establishment_registry.sql)

### 2.1 Table: `public.retail_establishments`
```sql
CREATE TABLE IF NOT EXISTS public.retail_establishments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_name text NOT NULL,
    legal_name text,
    gstin varchar(15) UNIQUE,
    lm_license_number text,
    shop_establishment_number text,
    state_code text NOT NULL,
    district_code text NOT NULL,
    pincode varchar(6),
    physical_address text,
    verification_status varchar(30) NOT NULL DEFAULT 'PENDING',
    verification_provenance varchar(50) NOT NULL DEFAULT 'MANUAL',
    verification_authority_id uuid REFERENCES public.authority_profiles(id) ON DELETE SET NULL,
    verification_date timestamptz,
    verification_notes text,
    is_active boolean NOT NULL DEFAULT true,
    created_by uuid,
    updated_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT retail_establishments_trade_name_nonempty
        CHECK (length(trim(trade_name)) > 0),
    CONSTRAINT retail_establishments_state_code_nonempty
        CHECK (length(trim(state_code)) > 0),
    CONSTRAINT retail_establishments_district_code_nonempty
        CHECK (length(trim(district_code)) > 0),
    CONSTRAINT retail_establishments_verification_status_check
        CHECK (verification_status IN ('PENDING', 'VERIFIED', 'SUSPENDED', 'REVOKED')),
    CONSTRAINT retail_establishments_verification_provenance_check
        CHECK (verification_provenance IN ('MANUAL', 'ESTABLISHMENT_QR', 'VERIFIED_GSTIN_INVOICE', 'ADMIN_TRIAGE_VERIFICATION', 'OFFICIAL_REGISTRY'))
);
```

### 2.2 Table Alteration: `public.consumer_issues`
```sql
ALTER TABLE public.consumer_issues
    ADD COLUMN IF NOT EXISTS establishment_id uuid REFERENCES public.retail_establishments(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS jurisdiction_provenance varchar(50) NOT NULL DEFAULT 'UNVERIFIED',
    ADD COLUMN IF NOT EXISTS jurisdiction_verified_at timestamptz,
    ADD COLUMN IF NOT EXISTS jurisdiction_verified_by uuid REFERENCES public.authority_profiles(id) ON DELETE SET NULL;

ALTER TABLE public.consumer_issues
    DROP CONSTRAINT IF EXISTS consumer_issues_provenance_check;
ALTER TABLE public.consumer_issues
    ADD CONSTRAINT consumer_issues_provenance_check
        CHECK (jurisdiction_provenance IN ('UNVERIFIED', 'ESTABLISHMENT_QR', 'VERIFIED_GSTIN_INVOICE', 'ADMIN_TRIAGE_VERIFICATION'));
```

### 2.3 Indexes & Performance Optimizations
- `idx_retail_establishments_jurisdiction` on `(state_code, district_code)` for localized inspector queries.
- `idx_retail_establishments_gstin` on `(gstin)` where `gstin IS NOT NULL` for instant invoice cross-referencing.
- `idx_retail_establishments_verification` on `(verification_status, is_active)` for active registry lookups.
- `idx_consumer_issues_establishment` on `(establishment_id)` where `establishment_id IS NOT NULL`.
- `idx_consumer_issues_provenance` on `(jurisdiction_provenance)` for triage dashboard filtering.

---

## 3. Authorization & Row Level Security (RLS)

### 3.1 Establishment Visibility Policies
1. **Public/Consumer Read Policy (`retail_establishments_select_verified`):**
   - Authenticated users (consumers) can query establishments if and only if:
     `verification_status = 'VERIFIED' AND is_active = true`
   - Unverified (`PENDING`), suspended, or revoked establishments are concealed from general users.
2. **Authority Officer Read Policy (`retail_establishments_select_authority`):**
   - Active officers can inspect all establishments in their jurisdiction:
     `retail_establishments.state_code = ap.state_code AND retail_establishments.district_code = ANY(ap.authorized_district_codes)`
3. **Disallowed Direct PostgREST Modifications:**
   - No `INSERT`, `UPDATE`, or `DELETE` policies exist for `authenticated` users on `retail_establishments`. All onboarding and status transitions must execute via backend service-role workflows or verified administrative procedures.

### 3.2 Atomic Verification RPC (`public.authority_verify_complaint_jurisdiction`)
The RPC enforces strict statutory boundary checks:
- **Actor Authentication:** Rejects null actors; if called within an authenticated session, verifies `p_actor_id == auth.uid()`.
- **Role Verification:** Validates caller's `app_role IN ('authority', 'admin')` from `public.user_profiles`.
- **Concurrent Row Locking:** Locks both `public.consumer_issues` and `public.retail_establishments` using `FOR UPDATE`.
- **Terminal Case Guard:** Rejects verification of cases in terminal states (`RESOLVED`, `REJECTED`).
- **Department Isolation:** Asserts `v_actor_profile.department == v_case.department`.
- **Establishment State:** Rejects missing establishments, inactive establishments (`is_active IS NOT TRUE`), and unverified establishments (`verification_status != 'VERIFIED'`).
- **Strict Jurisdiction Bound:**
  ```sql
  IF v_actor_profile.state_code != v_est.state_code
     OR NOT (v_est.district_code = ANY(v_actor_profile.authorized_district_codes)) THEN
      RAISE EXCEPTION 'ACTOR_JURISDICTION_DENIED: Actor % is not authorized for establishment jurisdiction (% / %)',
          p_actor_id, v_est.state_code, v_est.district_code USING ERRCODE = '42501';
  END IF;
  ```
  *An officer is strictly forbidden from verifying complaints outside their authorized state and district scope.*
- **Atomic Audit Record:** Writes `event_type = 'JURISDICTION_VERIFIED'` into `public.consumer_issue_audit_events` in the same transaction.
- **Grants:** `REVOKE ALL ... FROM PUBLIC, authenticated;` and `GRANT EXECUTE ... TO service_role;`.

---

## 4. Test Results & Verification Analysis

### 4.1 Test Suite Breakdown
Test Suite: [`tests/test_t3_4_1_establishment_registry.py`](file:///c:/Users/omnik\Downloads\Prince\CraftVerse\Veriqoo\tests\test_t3_4_1_establishment_registry.py)

| Test Identifier | Test Target & Contract | Execution Mode | Result |
|---|---|---|---|
| `test_default_unverified_state_for_new_complaint` | Unverified defaults (`jurisdiction_verified=False`, `establishment_id=None`, `provenance='UNVERIFIED'`) | In-Memory Domain | **PASSED** |
| `test_consumer_can_read_unverified_complaint` | Submitting consumer maintains full read access to unverified complaints | In-Memory Domain | **PASSED** |
| `test_unverified_complaint_excluded_from_authority_queues` | District officer docket (`list_cases`) excludes unverified complaints | In-Memory Domain | **PASSED** |
| `test_valid_atomic_jurisdiction_verification` | Verification updates case, writes audit event, and activates case in target officer queue | In-Memory RPC Mock | **PASSED** |
| `test_inactive_establishment_rejection` | Inactive establishment rejected (`EstablishmentInactiveError`), case unchanged | In-Memory Domain | **PASSED** |
| `test_unverified_establishment_rejection` | Establishment with status `PENDING` rejected (`EstablishmentUnverifiedError`) | In-Memory Domain | **PASSED** |
| `test_cross_jurisdiction_verification_rejection` | Officer in Pune attempting to verify Mumbai establishment rejected (`AuthorityJurisdictionDeniedError`) | In-Memory Domain | **PASSED** |
| `test_department_mismatch_verification_rejection` | Food Safety officer attempting to verify Legal Metrology complaint rejected | In-Memory Domain | **PASSED** |
| `test_inactive_officer_verification_rejection` | Suspended/inactive officer account rejected (`AuthorityInactiveError`) | In-Memory Domain | **PASSED** |
| `test_consumer_role_cannot_verify_complaint` | Consumer role attempting verification rejected (`AuthorityRoleDeniedError`) | In-Memory Domain | **PASSED** |
| `test_terminal_case_cannot_be_verified` | Resolved/Rejected cases cannot be verified (`InvalidStatusTransitionError`) | In-Memory Domain | **PASSED** |
| `test_atomic_rollback_on_audit_failure` | Simulated audit event insertion failure rolls back all case updates | In-Memory RPC Mock | **PASSED** |
| `test_migration_ddl_static_security_checks` | Migration DDL static audit (search_path, SECURITY DEFINER, RLS, grants) | Static AST / File Inspection | **PASSED** |

### 4.2 Full T3 Regression Test Run
Command:
```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_t3_*.py"
```
Output:
```
Ran 133 tests in 1.339s
OK (skipped=2)
```
*Note: The 2 skipped tests are live Supabase staging tests in `test_t3_4_staging_live.py` that intentionally skip when live credentials are unconfigured.*

---

## 5. Backward Compatibility & System Integrity

1. **Existing Complaints Preserved:**
   - Existing complaints in the database and repositories remain untouched. Their newly added columns (`establishment_id`, `jurisdiction_verified_at`, `jurisdiction_verified_by`) default safely to `NULL`, and `jurisdiction_provenance` defaults to `'UNVERIFIED'`.
2. **Authority Queue Invariance:**
   - Unverified complaints remain strictly excluded from district officer queues (`list_cases`), preserving the fail-closed invariant established in Phase 7.1.
3. **Consumer Read Access:**
   - Consumers can query and view all complaints they submitted regardless of whether an establishment has been verified.
4. **No Premature Status Mutation:**
   - Verification of jurisdiction does *not* prematurely transition `status` (e.g. `SUBMITTED` stays `SUBMITTED`), ensuring the authority workflow and assignment preconditions remain intact.

---

## 6. Execution Constraints & Operational Blockers

### 6.1 Compliance with Constraints
- **Production/Staging Safety:** No live database connections were made, and no migrations were applied to a live database.
- **No Spoofed Verification:** All test fixtures in unit tests are explicitly marked as test-only (e.g., `trade_name="Test Retailer Pune (Test-Only)"`).
- **No Premature UI/QR Code Implementation:** In accordance with instructions, QR generation, QR scanning, and consumer UI changes were deferred to future phases (Phase 7.4.4).

### 6.2 Remaining Blockers for Production Deployment
1. **Staging Database Application:** Migration `20261015000000_t3_4_1_establishment_registry.sql` must be applied to the Supabase staging database once migration approval is granted.
2. **Phase 7.4.2 (Administrative Triage API):** Endpoints exposing `authority_verify_complaint_jurisdiction` to authorized State Nodal Officers must be implemented in FastAPI.
3. **External Merchant Verification Registry:** While manual and admin verification are fully modeled, live GST API integration or State Legal Metrology dealer registration data feeds require official API credentials.
