# Veriqoo — Phase 7.4.4 Remediation Report
**Audit Remediation, Contract Alignment & Concurrency Protection Design**  
*Document Version: 1.0.0*  
*Date: 2026-10-05*  
*Target Environment: Offline Test Suite & Local Virtualenv (`.venv`)*  

---

## 1. Executive Summary

In accordance with [`PHASE_7_4_3_SECURITY_INTEGRATION_AUDIT.md`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/PHASE_7_4_3_SECURITY_INTEGRATION_AUDIT.md), Phase 7.4.4 remediates confirmed implementation defects, contract omissions, and data persistence bugs identified in Phase 7.4.2 without mutating the live database, without modifying unrelated modules, and without weakening existing authorization, fail-closed boundaries, or RLS guarantees.

All confirmed bugs across establishment persistence, consumer complaint serialization, review notes alias handling, authority case details binding, and input schema validation have been resolved with regression coverage. For high-severity architectural findings **H-1** (lack of atomic concurrency token on establishment reviews) and **H-2** (insufficient establishment review audit history and verifier attribution confusion), a complete database migration and PL/pgSQL RPC design specification has been authored for immediate deployment in Phase 7.5.

---

## 2. Files Changed

| File Path | Description of Changes |
| :--- | :--- |
| [`backend/app/services/establishment/errors.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/establishment/errors.py) | Added `DuplicateEstablishmentError` and `EstablishmentRepositoryError` domain exceptions inheriting from `EstablishmentError`. |
| [`backend/app/services/establishment/service.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/establishment/service.py) | Imported `DuplicateEstablishmentError` and raised it upon duplicate GSTIN check on establishment onboarding instead of generic `ValueError`. |
| [`backend/app/services/establishment/repository.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/establishment/repository.py) | **1.** Added duplicate GSTIN cross-record check and `simulate_db_error` toggle to `InMemoryEstablishmentRepository`.<br>**2.** In `SupabaseEstablishmentRepository._request`: caught HTTP 409, `retail_establishments_gstin_key`, and Postgres code `23505` to raise `DuplicateEstablishmentError`; caught 500s/network errors to raise `EstablishmentRepositoryError`.<br>**3.** In `save_establishment`: distinguished creation (`POST` with no merge-duplicates) from updates (`PATCH` targeting `id=eq.{id}`), preventing duplicate constraint bypass or blind overwrites. |
| [`backend/app/services/establishment/schemas.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/establishment/schemas.py) | **1.** Added regex validators for GSTIN (`^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`) and Indian pincode (`^[1-9][0-9]{5}$`).<br>**2.** Normalized GSTIN to uppercase.<br>**3.** Documented that format validation is purely structural syntax checking, not tax authority verification.<br>**4.** Added `@model_validator(mode="after")` to `ReviewEstablishmentRequest` ensuring `notes` and `verification_notes` aliases stay strictly synchronized. |
| [`backend/app/services/authority/schemas.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/authority/schemas.py) | Added `establishment_id`, `jurisdiction_provenance`, `jurisdiction_verified_at`, and `jurisdiction_verified_by` to `CaseSummaryResponse` and `CaseDetailResponse`. |
| [`backend/app/api/v1/endpoints/authority.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/api/v1/endpoints/authority.py) | **1.** Mapped `establishment_id`, `jurisdiction_provenance`, `jurisdiction_verified_at`, and `jurisdiction_verified_by` in `list_authority_cases` and `_map_case_detail_response`.<br>**2.** Caught `DuplicateEstablishmentError` and returned HTTP 409 with structured error `{"code": "DUPLICATE_ESTABLISHMENT", ...}`.<br>**3.** Passed `payload.get_notes()` in `review_establishment` to guarantee alias parity. |
| [`backend/app/api/v1/endpoints/consumer_issues.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/api/v1/endpoints/consumer_issues.py) | In `_serialize_issue`, mapped actual persisted fields `establishment_id`, `jurisdiction_provenance`, `jurisdiction_verified_at`, and `jurisdiction_verified_by` from `ConsumerIssue` domain model to `ConsumerIssueResponse`. |
| [`tests/test_t3_4_2_verification_api.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/tests/test_t3_4_2_verification_api.py) | Updated test assertion for duplicate GSTIN onboarding from HTTP 422 to HTTP 409 with error code `DUPLICATE_ESTABLISHMENT`. |
| [`tests/test_t3_4_3_audit_gaps.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/tests/test_t3_4_3_audit_gaps.py) | Updated gap verification suite to assert that identified contract omissions and validation gaps are now closed and remediated. |
| [`tests/test_t3_4_4_remediation.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/tests/test_t3_4_4_remediation.py) | New comprehensive regression test suite containing 13 focused test cases covering all Phase 7.4.4 tasks. |

---

## 2. Bugs Remediated

### Task 1: Establishment Persistence & Conflict Handling
- **Issue:** `SupabaseEstablishmentRepository.save_establishment` previously sent HTTP `POST` without `Prefer: resolution=merge-duplicates`, causing any subsequent update (e.g. status review) to fail on duplicate primary key. Blindly adding `resolution=merge-duplicates` would risk silent overwrites or unique GSTIN constraint masking. Duplicate GSTIN was previously handled as a generic `ValueError` returning HTTP 422.
- **Fix:** Distinguish create from update by checking `existing = self.get_by_id(establishment.id)`. New records issue HTTP `POST` without merge-duplicates so standard PostgreSQL unique constraints (`retail_establishments_gstin_key`) are strictly enforced. Updates issue HTTP `PATCH` scoped with `params={"id": f"eq.{establishment.id}"}`. When a duplicate GSTIN conflict occurs (Postgres 23505 / HTTP 409), `DuplicateEstablishmentError` is raised and translated to HTTP 409 Conflict with `"code": "DUPLICATE_ESTABLISHMENT"`. Repository or network errors raise `EstablishmentRepositoryError` and safely return HTTP 500 without leaking connection internals.

### Task 2: Consumer Complaint Serialization
- **Issue:** In [`backend/app/api/v1/endpoints/consumer_issues.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/api/v1/endpoints/consumer_issues.py), `_serialize_issue` omitted `establishment_id`, `jurisdiction_provenance`, `jurisdiction_verified_at`, and `jurisdiction_verified_by`, causing verified consumer issues to always return `null` establishment bindings and default `UNVERIFIED` provenance.
- **Fix:** `_serialize_issue` now propagates `issue.establishment_id`, `issue.jurisdiction_provenance or "UNVERIFIED"`, `issue.jurisdiction_verified_at`, and `issue.jurisdiction_verified_by`. Owner-only RLS and fail-closed state/district filtering remain intact.

### Task 3: Review Notes Alias Parity
- **Issue:** `ReviewEstablishmentRequest` had a `.notes` field and a `.verification_notes` alias, but the endpoint passed `payload.notes` directly to `establishment_service.review_establishment`, causing notes sent under `verification_notes` to be lost and persisted as `None`.
- **Fix:** Added a Pydantic `model_validator(mode="after")` that synchronizes `notes` and `verification_notes`. Both field accessors and `payload.get_notes()` now return the exact same persisted note. The endpoint was updated to use `payload.get_notes()`.

### Task 4: Authority Case Details Establishment Binding
- **Issue:** `CaseDetailResponse` and `CaseSummaryResponse` lacked fields for establishment bindings, meaning officers reviewing statutory cases could not see bound establishment IDs or provenance metadata.
- **Fix:** Added `establishment_id: str | None`, `jurisdiction_provenance: str = "UNVERIFIED"`, `jurisdiction_verified_at: datetime | None`, and `jurisdiction_verified_by: str | None` to `CaseDetailResponse` and `CaseSummaryResponse`. Mapped in `list_authority_cases` and extracted clean helper `_map_case_detail_response`. Confidential consumer personal data is preserved from exposure.

### Task 5: Request Validation (GSTIN & Pincode)
- **Issue:** `CreateEstablishmentRequest` only enforced `max_length=15` on GSTIN and had no validation on Indian postal codes, allowing arbitrary strings (such as `"123"`) to be onboarded.
- **Fix:** Added regex validator enforcing standard 15-character GSTIN format (`^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`) and normalizing lowercase input to uppercase. Added 6-digit Indian PIN code validator (`^[1-9][0-9]{5}$`). Explicitly documented in schema docstrings that regex checks validate syntactic format only and do NOT certify business authenticity or active GST registration.

---

## 4. Regression Tests Added

The new test suite [`tests/test_t3_4_4_remediation.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/tests/test_t3_4_4_remediation.py) includes 13 regression tests across 5 test classes:

1. `Task1EstablishmentPersistenceTestCase.test_establishment_creation_and_update`: Confirms establishment creation persists a new record and subsequent review updates the existing record via `PATCH` rather than conflicting on insert.
2. `Task1EstablishmentPersistenceTestCase.test_duplicate_gstin_raises_duplicate_establishment_error`: Confirms duplicate GSTIN in `EstablishmentService` raises `DuplicateEstablishmentError`.
3. `Task1EstablishmentPersistenceTestCase.test_in_memory_repository_duplicate_gstin_on_save`: Confirms `InMemoryEstablishmentRepository` enforces cross-record GSTIN uniqueness on save.
4. `Task1EstablishmentPersistenceTestCase.test_repository_simulated_db_error`: Confirms simulated database errors raise `EstablishmentRepositoryError`.
5. `Task1EstablishmentPersistenceTestCase.test_supabase_repo_distinguishes_post_and_patch`: Confirms `SupabaseEstablishmentRepository` uses HTTP `POST` for new records and targeted `PATCH` with `?id=eq.{id}` for existing records without `merge-duplicates`.
6. `Task2ConsumerComplaintSerializationTestCase.test_verified_complaint_serialization`: Confirms verified consumer complaints serialize `establishment_id`, `jurisdiction_provenance`, `jurisdiction_verified_at`, and `jurisdiction_verified_by`.
7. `Task2ConsumerComplaintSerializationTestCase.test_unverified_complaint_serialization`: Confirms unverified complaints serialize `None` and `"UNVERIFIED"` without leakage.
8. `Task3ReviewNotesAliasTestCase.test_notes_alias_parity`: Confirms `notes` and `verification_notes` behave identically across `.notes`, `.verification_notes`, and `get_notes()`.
9. `Task4AuthorityCaseDetailsTestCase.test_case_detail_with_establishment_binding`: Confirms `_map_case_detail_response` exposes establishment binding and provenance on bound cases.
10. `Task4AuthorityCaseDetailsTestCase.test_case_detail_without_establishment_binding`: Confirms unbound cases safely default without error.
11. `Task5RequestValidationTestCase.test_valid_gstin_and_pincode`: Confirms valid GSTIN and pincode pass, and lowercase GSTIN is normalized to uppercase.
12. `Task5RequestValidationTestCase.test_invalid_gstin_rejected`: Confirms invalid GSTIN lengths, invalid state codes, missing characters, and malformed structures are rejected with Pydantic `ValidationError`.
13. `Task5RequestValidationTestCase.test_invalid_pincode_rejected`: Confirms invalid pincodes (leading zeros, 4-digit, 5-digit, 7-digit, alphanumeric, whitespace) are rejected with `ValidationError`.

---

## 5. Exact Test Results

Execution command:
```powershell
$files = (Get-ChildItem tests/test_t3_*.py | Select-Object -ExpandProperty FullName); & .\.venv\Scripts\python.exe -m pytest $files
```

### Output Summary
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\omnik\Downloads\Prince\CraftVerse\Veriqoo
plugins: anyio-4.15.1
collected 165 items

tests\test_t3_1_user_profiles.py ...........                             [  6%]
tests\test_t3_2_history_and_saved_products.py ..............             [ 15%]
tests\test_t3_3_consumer_issue_reporting.py .......................      [ 29%]
tests\test_t3_4_1_establishment_registry.py .............                [ 36%]
tests\test_t3_4_2_verification_api.py .............                      [ 44%]
tests\test_t3_4_3_audit_gaps.py ......                                   [ 48%]
tests\test_t3_4_4_remediation.py .............                           [ 56%]
tests\test_t3_4_atomic_workflow.py ........................              [ 70%]
tests\test_t3_4_authority_access_control.py ......................       [ 84%]
tests\test_t3_4_authority_case_workflow.py ..............                [ 92%]
tests\test_t3_4_staging_live.py ss                                       [ 93%]
tests\test_t3_4_trusted_jurisdiction.py ..........                       [100%]

======================= 163 passed, 2 skipped in 2.52s ========================
```
- **Total Tests:** 165
- **Passed:** 163
- **Failed:** 0
- **Skipped:** 2 (`test_t3_4_staging_live.py` correctly skips offline when live Supabase credentials are not supplied)
- **Exit Code:** 0

---

## 6. Architecture Design for Concurrency & Audit Trail (H-1 & H-2)

As required by Task 6, no live database mutations or SQL migrations were executed in this phase. The full technical specification for Phase 7.5 DDL and RPC implementation is detailed below:

### 6.1 Database Schema Additions
```sql
-- Migration: 20261008000000_t3_4_establishment_audit_and_rpc.sql

-- 1. Create dedicated audit event log for retail establishments
CREATE TABLE IF NOT EXISTS public.retail_establishment_audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    establishment_id UUID NOT NULL REFERENCES public.retail_establishments(id) ON DELETE CASCADE,
    actor_id UUID NOT NULL REFERENCES auth.users(id),
    action TEXT NOT NULL CHECK (action IN ('VERIFY', 'SUSPEND', 'REVOKE')),
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    notes TEXT,
    provenance TEXT NOT NULL DEFAULT 'MANUAL',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Index for timeline queries
CREATE INDEX IF NOT EXISTS idx_establishment_audit_est_id_created 
    ON public.retail_establishment_audit_events(establishment_id, created_at DESC);

-- Enable RLS
ALTER TABLE public.retail_establishment_audit_events ENABLE ROW LEVEL SECURITY;

-- Authority RLS: Officers can inspect audit history in their jurisdiction
CREATE POLICY "Authority read establishment audit events"
    ON public.retail_establishment_audit_events
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.authority_profiles ap
            JOIN public.retail_establishments re ON re.id = retail_establishment_audit_events.establishment_id
            WHERE ap.user_id = auth.uid()
              AND ap.is_active = TRUE
              AND ap.state_code = re.state_code
              AND (ap.level = 'STATE' OR re.district_code = ANY(ap.authorized_districts))
        )
    );
```

### 6.2 Atomic Concurrency RPC Specification
```sql
-- 2. Atomic review RPC with row-level locking, optimistic concurrency token, and transactional audit logging
CREATE OR REPLACE FUNCTION public.authority_review_establishment(
    p_establishment_id UUID,
    p_action TEXT,
    p_expected_status TEXT,
    p_notes TEXT DEFAULT NULL,
    p_provenance TEXT DEFAULT 'MANUAL'
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_actor_id UUID;
    v_profile RECORD;
    v_est RECORD;
    v_new_status TEXT;
    v_is_active BOOLEAN;
BEGIN
    v_actor_id := auth.uid();
    IF v_actor_id IS NULL THEN
        RAISE EXCEPTION 'Unauthorized: authenticated session required' USING ERRCODE = '42501';
    END IF;

    -- Verify active authority profile
    SELECT * INTO v_profile
    FROM public.authority_profiles
    WHERE user_id = v_actor_id AND is_active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Forbidden: active authority profile required' USING ERRCODE = '42501';
    END IF;

    -- Row-level exclusive lock on establishment
    SELECT * INTO v_est
    FROM public.retail_establishments
    WHERE id = p_establishment_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Establishment % not found', p_establishment_id USING ERRCODE = 'P0002';
    END IF;

    -- Verify territorial jurisdiction
    IF v_profile.state_code <> v_est.state_code OR
       (v_profile.level = 'DISTRICT' AND NOT (v_est.district_code = ANY(v_profile.authorized_districts))) THEN
        RAISE EXCEPTION 'Forbidden: cross-jurisdiction review prohibited' USING ERRCODE = '42501';
    END IF;

    -- Precondition check: Optimistic concurrency token
    IF p_expected_status IS NOT NULL AND v_est.verification_status <> p_expected_status THEN
        RAISE EXCEPTION 'Concurrency conflict: expected status %, found %', p_expected_status, v_est.verification_status
            USING ERRCODE = '40001';
    END IF;

    -- Validate transition & determine new state
    IF p_action = 'VERIFY' THEN
        v_new_status := 'VERIFIED';
        v_is_active := TRUE;
    ELSIF p_action = 'SUSPEND' THEN
        v_new_status := 'SUSPENDED';
        v_is_active := FALSE;
    ELSIF p_action = 'REVOKE' THEN
        v_new_status := 'REVOKED';
        v_is_active := FALSE;
    ELSE
        RAISE EXCEPTION 'Invalid review action: %', p_action USING ERRCODE = '22023';
    END IF;

    -- Update establishment
    UPDATE public.retail_establishments
    SET verification_status = v_new_status,
        is_active = v_is_active,
        verification_provenance = p_provenance,
        verification_notes = p_notes,
        verification_authority_id = CASE WHEN p_action = 'VERIFY' THEN v_actor_id ELSE verification_authority_id END,
        verification_date = CASE WHEN p_action = 'VERIFY' THEN timezone('utc'::text, now()) ELSE verification_date END,
        updated_by = v_actor_id,
        updated_at = timezone('utc'::text, now())
    WHERE id = p_establishment_id;

    -- Insert audit event entry atomically in same transaction
    INSERT INTO public.retail_establishment_audit_events (
        establishment_id,
        actor_id,
        action,
        previous_status,
        new_status,
        notes,
        provenance,
        created_at
    ) VALUES (
        p_establishment_id,
        v_actor_id,
        p_action,
        v_est.verification_status,
        v_new_status,
        p_notes,
        p_provenance,
        timezone('utc'::text, now())
    );

    RETURN jsonb_build_object(
        'establishment_id', p_establishment_id,
        'action', p_action,
        'previous_status', v_est.verification_status,
        'new_status', v_new_status,
        'actor_id', v_actor_id
    );
END;
$$;

-- Restrict execution
REVOKE ALL ON FUNCTION public.authority_review_establishment FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.authority_review_establishment TO authenticated, service_role;
```

---

## 7. Items Requiring Live Staging Verification

Because live database mutations were prohibited in Phase 7.4.4, the following items require execution against a real Supabase staging instance with valid service keys:

1. **Unique Constraint Race Tests:** Concurrently executing onboarding requests with the identical GSTIN against Supabase to verify that Postgres returns 23505 and the backend maps it to HTTP 409 `DUPLICATE_ESTABLISHMENT`.
2. **PostgREST PATCH vs POST Execution:** Verifying that `SupabaseEstablishmentRepository.save_establishment` executes `PATCH /rest/v1/retail_establishments?id=eq.{id}` successfully against real Postgres tables and does not overwrite existing rows.
3. **Execution of `test_t3_4_staging_live.py`:** Un-skipping and running live staging tests using `SUPABASE_TEST_URL` and `SUPABASE_TEST_SERVICE_ROLE_KEY`.

---

## 8. Highest-Priority Remaining Task

**Phase 7.5: Apply Establishment Concurrency & Audit Migration (`20261008000000_t3_4_establishment_audit_and_rpc.sql`)**  
Implement the `retail_establishment_audit_events` table and the `authority_review_establishment` RPC in Supabase, update the Python service layer to invoke this RPC with optimistic concurrency preconditions, and verify atomic state transitions before adding QR-based establishment verification.
