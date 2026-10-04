# Veriqoo Phase 7.4.3 — Security, Database Contract & Integration Audit Report

**Date:** 2026-10-05  
**Audit Scope:** Phase 7.4.1 (Establishment Registry Foundation) and Phase 7.4.2 (Verification API & Lifecycle Workflow)  
**Security Boundary:** FastAPI REST Endpoints, Supabase PostgREST, Row Level Security (RLS), and Atomic PL/pgSQL RPC Functions  
**Status:** Complete — Ready for Review (No database migrations or code mutations applied)

---

## 1. Actual Files and Functions Inspected

The following source files, database migrations, and functions were systematically inspected line-by-line:

| File Path | Component / Layer | Primary Functions / Symbols Inspected |
|---|---|---|
| `backend/app/api/v1/endpoints/authority.py` | API Routing & Presentation | `list_authority_cases`, `get_case_details`, `assign_case_officer`, `list_case_notes`, `add_case_note`, `transition_case_status`, `get_case_audit_timeline`, `verify_case_jurisdiction`, `create_establishment`, `review_establishment`, `get_establishment`, `list_establishments`, `_map_establishment_response` |
| `backend/app/services/establishment/service.py` | Establishment Business Logic | `EstablishmentService.__init__`, `_enforce_active_authority`, `create_establishment`, `review_establishment`, `get_establishment`, `list_establishments` |
| `backend/app/services/establishment/schemas.py` | Pydantic Request/Response Models | `CreateEstablishmentRequest`, `ReviewEstablishmentRequest`, `EstablishmentResponse`, `PaginatedEstablishmentsResponse` |
| `backend/app/services/establishment/repository.py` | Establishment Persistence | `EstablishmentRepository` (ABC), `InMemoryEstablishmentRepository` (`save_establishment`, `get_by_id`, `get_by_gstin`, `list_by_jurisdiction`), `SupabaseEstablishmentRepository` (`_headers`, `_request`, `_map_row`, `save_establishment`, `get_by_id`, `get_by_gstin`, `list_by_jurisdiction`) |
| `backend/app/services/establishment/models.py` | Domain Models & Enums | `EstablishmentVerificationStatus`, `EstablishmentVerificationProvenance`, `RetailEstablishment` |
| `backend/app/services/establishment/errors.py` | Exception Definitions | `EstablishmentError`, `EstablishmentNotFoundError`, `EstablishmentInactiveError`, `EstablishmentUnverifiedError`, `InvalidEstablishmentDataError` |
| `backend/app/services/authority/dependencies.py` | Security Dependencies | `require_authority_user`, `AUTHORIZED_AUTHORITY_ROLES` |
| `backend/app/services/authority/case_service.py` | Case Workflow Business Logic | `AuthorityCaseService.__init__`, `_enforce_authority_case_access`, `list_cases`, `get_case_details`, `assign_officer`, `add_investigation_note`, `list_investigation_notes`, `transition_status`, `list_audit_events`, `verify_case_jurisdiction` |
| `backend/app/services/authority/case_repository.py` | Case & RPC Persistence | `AuthorityCaseRepository` (ABC), `InMemoryAuthorityCaseRepository`, `SupabaseAuthorityCaseRepository` (`_request`, `_map_case_row`, `_map_note_row`, `_map_audit_row`, `_rpc`, `atomic_assign_officer`, `atomic_transition_status`, `atomic_create_note`, `atomic_verify_jurisdiction`, `save_case`) |
| `backend/app/services/authority/schemas.py` | Authority Schemas | `CaseSummaryResponse`, `CaseDetailResponse`, `CaseAssignRequest`, `CaseAssignResponse`, `CreateCaseNoteRequest`, `CaseNoteResponse`, `CaseStatusTransitionRequest`, `CaseStatusTransitionResponse`, `AuditEventResponse`, `VerifyCaseJurisdictionRequest`, `VerifyCaseJurisdictionResponse` |
| `backend/app/api/dependencies.py` | Dependency Injection | `get_user_profile_service`, `get_authority_service`, `get_authority_case_service`, `get_establishment_service`, `get_consumer_issue_service`, `get_trusted_jurisdiction_resolver` |
| `backend/app/api/v1/endpoints/consumer_issues.py` | Consumer Reporting Endpoints | `_serialize_issue`, `submit_consumer_issue`, `list_consumer_issues`, `get_consumer_issue` |
| `backend/app/services/consumer_issues/jurisdiction.py` | Trusted Jurisdiction Resolver | `validate_canonical_jurisdiction`, `ServerVerifiedLocationRegistry`, `DefaultTrustedJurisdictionResolver.resolve_jurisdiction` |
| `supabase/migrations/20261015000000_t3_4_1_establishment_registry.sql` | Phase 7.4.1 DDL Migration | Table `retail_establishments`, alterations on `consumer_issues`, RLS policies, RPC `authority_verify_complaint_jurisdiction`, security grants |
| `supabase/migrations/20261010000001_t3_4_phase5_2_hardening.sql` | Phase 5.2 Hardening Migration | RPCs `authority_assign_case`, `authority_create_case_note` |
| `supabase/migrations/20261010000000_t3_4_atomic_authority_rpc.sql` | Phase 5 Atomic RPCs | RPC `authority_transition_status` |
| `supabase/migrations/20261009000000_t3_4_authority_workflow.sql` | Phase 4 DDL Migration | Table `authority_profiles`, `consumer_issue_notes`, `consumer_issue_audit_events`, RLS policies |
| `supabase/migrations/20261006000000_t3_1_user_profiles.sql` | Phase 1 DDL Migration | Table `user_profiles`, constraints, indexes |

---

## 2. Endpoint-by-Endpoint Authorization Matrix

All authority and establishment endpoints are mounted under `/api/v1/authority`.

| Endpoint | HTTP Method | Authentication Dependency | Required Role | Active Profile Enforcement | Department Isolation | State & District Scope Enforcement | Concurrency Token / Lock | Audit Logging Behavior | Error Status Codes |
|---|---|---|---|---|---|---|---|---|---|
| `/authority/cases` | GET | `require_authority_user` | `authority`, `admin` | Checked (`ap.is_active is True`) | Scoped strictly to `officer.department` | Scoped strictly to `state_code` and `authorized_district_codes` | Read-only | None (Read) | 401, 403, 500 |
| `/authority/cases/{case_id}` | GET | `require_authority_user` | `authority`, `admin` | Checked (`ap.is_active is True`) | Checked (`officer.department == case.department`) | Checked (`officer.state == case.state` & `case.district in officer.districts`); **Fails closed if unverified** | Read-only | None (Read) | 401, 403, 404, 500 |
| `/authority/cases/{case_id}/assign` | POST | `require_authority_user` | `authority`, `admin` | Checked | Checked (Officer and Case match) | Checked (Case in officer jurisdiction) | `expected_assigned_officer_id` or `expect_unassigned=true` (FOR UPDATE row lock in SQL RPC) | Atomic insert to `consumer_issue_audit_events` (`CASE_ASSIGNED` / `CASE_REASSIGNED`) | 401, 403, 404, 409, 422, 500 |
| `/authority/cases/{case_id}/notes` | GET | `require_authority_user` | `authority`, `admin` | Checked | Checked | Checked; fails closed if unverified | Read-only | None (Read) | 401, 403, 404, 500 |
| `/authority/cases/{case_id}/notes` | POST | `require_authority_user` | `authority`, `admin` | Checked | Checked | Checked | FOR UPDATE row lock in SQL RPC | Atomic insert to `consumer_issue_notes` and `consumer_issue_audit_events` (`NOTE_ADDED`) | 401, 403, 404, 422, 500 |
| `/authority/cases/{case_id}/status` | PATCH | `require_authority_user` | `authority`, `admin` | Checked | Checked | Checked | `expected_status` token mandatory (FOR UPDATE row lock in SQL RPC) | Atomic update and insert to `consumer_issue_audit_events` (`STATUS_CHANGED`) | 401, 403, 404, 409, 422, 500 |
| `/authority/cases/{case_id}/audit-timeline` | GET | `require_authority_user` | `authority`, `admin` | Checked | Checked | Checked | Read-only | None (Read) | 401, 403, 404, 500 |
| `/authority/cases/{case_id}/verify-jurisdiction` | POST | `require_authority_user` | `authority`, `admin` | Checked | Checked (`case.department == officer.department`) | Checked (`officer.state == est.state` & `est.district in officer.districts`) | FOR UPDATE row lock on both `consumer_issues` and `retail_establishments` in SQL RPC | Atomic update to `consumer_issues` and insert to `consumer_issue_audit_events` (`JURISDICTION_VERIFIED`) | 401, 403, 404, 422, 500 |
| `/authority/establishments` | POST | `require_authority_user` | `authority`, `admin` | Checked | N/A (Commercial physical premises) | Checked (`officer.state == can_state` & `can_district in officer.districts`) | None | **None** (No audit record created) | 401, 403, 422, 500 |
| `/authority/establishments/{id}/review` | POST | `require_authority_user` | `authority`, `admin` | Checked | N/A | Checked (`officer.state == est.state` & `est.district in officer.districts`) | **None** (Application-level mutation; no row lock) | **None** (No audit record; overwrites table row) | 401, 403, 404, 422, 500 |
| `/authority/establishments/{id}` | GET | `require_authority_user` | `authority`, `admin` | Checked | N/A | Allowed if within officer jurisdiction OR if establishment is active & verified | Read-only | None (Read) | 401, 403, 404, 500 |
| `/authority/establishments` | GET | `require_authority_user` | `authority`, `admin` | Checked | N/A | Filtered strictly to officer state and authorized districts | Read-only | None (Read) | 401, 403, 500 |

---

## 3. Confirmed Vulnerabilities and Severity

### Critical Severity

#### C-1: `SupabaseEstablishmentRepository.save_establishment` executes HTTP `POST` without upsert headers, causing live review updates to crash (HTTP 409)
- **Component:** `backend/app/services/establishment/repository.py:212-220`
- **Description:** When an officer reviews an establishment via `review_establishment`, the establishment entity already exists in PostgreSQL. `save_establishment` issues an HTTP `POST` to PostgREST `retail_establishments` with header `Prefer: return=representation`. In PostgREST, a plain `POST` with an existing primary key is an `INSERT`, which raises PostgreSQL error code `23505` (`duplicate key value violates unique constraint "retail_establishments_pkey"`), returning HTTP 409 Conflict.
- **Proof:** Confirmed in `tests/test_t3_4_3_audit_gaps.py::test_gap_5_supabase_establishment_repo_save_lacks_upsert_header`. Live staging calls to review establishments will fail on Supabase.
- **Remediation:** Configure `Prefer: resolution=merge-duplicates,return=representation` on upsert or switch to HTTP `PATCH` by ID.

---

### High Severity

#### H-1: Missing Database Atomic RPC, Row Locking, and Concurrency Guards for Establishment Lifecycle
- **Component:** `supabase/migrations/20261015000000_t3_4_1_establishment_registry.sql` and `backend/app/services/establishment/service.py:105-156`
- **Description:** Migration `20261015000000_t3_4_1_establishment_registry.sql` created the atomic complaint jurisdiction RPC (`authority_verify_complaint_jurisdiction`), but **did not define any atomic database RPC for establishment creation or review**. Establishment review is implemented as a multi-step Python process: `get_by_id`, in-memory mutation, and un-locked save. If two officers concurrently review the same establishment (e.g. one verifying, one suspending), there is no `FOR UPDATE` lock or optimistic concurrency token (`expected_status`), leading to race conditions and lost updates.
- **Remediation:** Introduce an atomic `authority_review_establishment` RPC in a subsequent migration with row locking (`FOR UPDATE`) and explicit transition checks.

#### H-2: Missing Audit Trail for Establishment Lifecycle & Reviewer Identity Overwrite
- **Component:** `supabase/migrations/20261015000000_t3_4_1_establishment_registry.sql` and `backend/app/services/establishment/service.py:140-147`
- **Description:**
  1. No audit event table exists for establishments (unlike `consumer_issue_audit_events`). Any review action (VERIFY, SUSPEND, REVOKE) overwrites existing columns in-place on `retail_establishments`.
  2. When an establishment is suspended or revoked (`action == 'SUSPEND'` or `'REVOKE'`), the service sets `verification_status = 'SUSPENDED'` and `is_active = false`, but **leaves `verification_authority_id` pointing to the original verifying officer** and `verification_date` set to the original verification date.
  3. Consequently, there is no permanent or queryable record of which officer suspended/revoked the establishment, when the action occurred, or what the prior status was.
- **Proof:** Confirmed in `tests/test_t3_4_3_audit_gaps.py::test_gap_4_suspend_revoke_leaves_original_verifier_id`.
- **Remediation:** Create a `retail_establishment_audit_events` table (or dedicated `suspension_authority_id` / `suspension_date` tracking) and record all review transitions immutably.

---

### Medium Severity

#### M-1: `_serialize_issue` in `consumer_issues.py` omits establishment binding and provenance fields
- **Component:** `backend/app/api/v1/endpoints/consumer_issues.py:30-49`
- **Description:** `ConsumerIssueResponse` defines `establishment_id`, `jurisdiction_provenance`, `jurisdiction_verified_at`, and `jurisdiction_verified_by`. However, `_serialize_issue()` does not pass these fields when constructing the response.
- **Impact:** Consumers and API clients querying `/api/v1/consumer-issues` or `/api/v1/consumer-issues/{id}` always receive `establishment_id: null` and `jurisdiction_provenance: "UNVERIFIED"`, even after an authority officer has successfully verified the jurisdiction and bound the complaint to a registered establishment.
- **Proof:** Confirmed in `tests/test_t3_4_3_audit_gaps.py::test_gap_1_consumer_issue_serialization_omits_establishment_provenance`.
- **Remediation:** Add the missing fields to `_serialize_issue()` in `consumer_issues.py`.

#### M-2: `CaseDetailResponse` and `CaseSummaryResponse` omit establishment binding fields
- **Component:** `backend/app/services/authority/schemas.py:10-51` and `backend/app/api/v1/endpoints/authority.py:165-185`
- **Description:** The authority response schemas (`CaseDetailResponse` and `CaseSummaryResponse`) do not contain `establishment_id`, `jurisdiction_provenance`, `jurisdiction_verified_at`, or `jurisdiction_verified_by`.
- **Impact:** When investigating officers view case details via `GET /authority/cases/{case_id}`, they cannot see which establishment premises was bound to the case or what verification provenance was used.
- **Proof:** Confirmed in `tests/test_t3_4_3_audit_gaps.py::test_gap_2_case_detail_response_schema_omits_establishment_id`.
- **Remediation:** Add optional establishment metadata fields to `CaseDetailResponse` and map them in `endpoints/authority.py`.

#### M-3: Missing GSTIN and Pincode format validation in `CreateEstablishmentRequest`
- **Component:** `backend/app/services/establishment/schemas.py:10-21`
- **Description:** `CreateEstablishmentRequest` defines `gstin: str | None = Field(default=None, max_length=15)` without a `min_length` or regex constraint, and `pincode` without a numeric check.
- **Impact:** Malformed identifiers like `gstin="123"` pass Pydantic validation and are stored in PostgreSQL.
- **Proof:** Confirmed in `tests/test_t3_4_3_audit_gaps.py::test_gap_6_gstin_validation_allows_short_invalid_strings`.
- **Remediation:** Add regex pattern `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$` and `^\d{6}$` validation in Pydantic.

---

### Low Severity

#### L-1: `ReviewEstablishmentRequest` notes alias `verification_notes` is shadowed in endpoint
- **Component:** `backend/app/api/v1/endpoints/authority.py:657` and `backend/app/services/establishment/schemas.py:23-32`
- **Description:** `ReviewEstablishmentRequest` accepts both `notes` and `verification_notes` (with helper `get_notes()`). However, `authority.py` passes `payload.notes` directly to `establishment_service.review_establishment()`. If a client sends `{"action": "VERIFY", "verification_notes": "..."}`, the note is dropped.
- **Proof:** Confirmed in `tests/test_t3_4_3_audit_gaps.py::test_gap_3_review_establishment_request_notes_alias_contract`.
- **Remediation:** Pass `payload.get_notes()` instead of `payload.notes`.

#### L-2: Unhandled Database Exception Mapping on Duplicate GSTIN Collision
- **Component:** `backend/app/services/establishment/service.py:80-86` and `repository.py:155-158`
- **Description:** If two concurrent requests attempt to onboard the same GSTIN, the application-level pre-check passes concurrently. PostgreSQL raises a unique violation on `retail_establishments_gstin_key`, which `SupabaseEstablishmentRepository` raises as an unhandled `HTTPError`, resulting in a generic 500 Internal Server Error instead of a 409 Conflict.
- **Remediation:** Catch unique violation responses and raise `InvalidEstablishmentDataError` or `DuplicateEstablishmentError` with HTTP 409.

---

## 4. Database Contract Mismatches

| Subject | Database (PostgreSQL / SQL DDL) | Application Layer (Python / Pydantic) | Status / Analysis |
|---|---|---|---|
| `authority_verify_complaint_jurisdiction` Arguments | `p_case_id uuid, p_establishment_id uuid, p_actor_id uuid, p_provenance text, p_verification_notes text DEFAULT NULL` | `payload = {"p_case_id": ..., "p_establishment_id": ..., "p_actor_id": ..., "p_provenance": ..., "p_verification_notes": ...}` | **Matched**: Names, types, and defaults align perfectly. |
| `authority_verify_complaint_jurisdiction` Returns | `jsonb_build_object('case', ..., 'establishment', ..., 'audit_event', ...)` | `res["case"]`, `res["audit_event"]` | **Matched**: Required entities extracted safely. |
| `retail_establishments.verification_provenance` Allowed Values | `CHECK (verification_provenance IN ('MANUAL', 'ESTABLISHMENT_QR', 'VERIFIED_GSTIN_INVOICE', 'ADMIN_TRIAGE_VERIFICATION', 'OFFICIAL_REGISTRY'))` | `EstablishmentVerificationProvenance`: `MANUAL`, `ESTABLISHMENT_QR`, `VERIFIED_GSTIN_INVOICE`, `ADMIN_TRIAGE_VERIFICATION`, `OFFICIAL_REGISTRY` | **Matched**: Enum values match DDL check constraints. |
| `consumer_issues.jurisdiction_provenance` Allowed Values | `CHECK (jurisdiction_provenance IN ('UNVERIFIED', 'ESTABLISHMENT_QR', 'VERIFIED_GSTIN_INVOICE', 'ADMIN_TRIAGE_VERIFICATION'))` | `VerifyCaseJurisdictionRequest`: `ADMIN_TRIAGE_VERIFICATION`, `VERIFIED_GSTIN_INVOICE`, `ESTABLISHMENT_QR` | **Matched**: `MANUAL` is disallowed for case verification, which is correct and intentional. |
| PostgREST Persistence Header for `retail_establishments` | Requires `Prefer: resolution=merge-duplicates` for updates via POST to prevent unique key violation | `headers=self._headers(prefer="return=representation")` without merge-duplicates | **Mismatch (Critical C-1)**: Updates via PostgREST will fail with HTTP 409 on live database. |
| Establishment Review RPC | No RPC function in migration DDL | Service calls repository update without DB lock or RPC | **Mismatch (High H-1)**: Missing atomic RPC layer. |
| Establishment Audit Events Table | No table exists in migrations | No audit events recorded in service | **Mismatch (High H-2)**: No audit trail for establishment lifecycle. |
| Consumer Issue Response Serialization | `establishment_id`, `jurisdiction_provenance`, `jurisdiction_verified_at`, `jurisdiction_verified_by` exist on `consumer_issues` | `_serialize_issue` omits all 4 fields | **Mismatch (Medium M-1)**: Fields dropped before returning to client. |
| Authority Case Detail Response | `establishment_id`, `jurisdiction_provenance` exist on `consumer_issues` | `CaseDetailResponse` has no fields for establishment binding | **Mismatch (Medium M-2)**: Officers cannot inspect linked establishment in case detail view. |

---

## 5. Tests Run and Exact Results

All tests were executed against the Python 3.12 virtual environment (`.venv`):

### 1. Focused Phase 7.4.1 and Phase 7.4.2 Test Suite
**Command:**
```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest -v tests/test_t3_4_1_establishment_registry.py tests/test_t3_4_2_verification_api.py
```
**Result:** **26 passed** in 1.40s (100% pass rate).
- Validated atomic jurisdiction verification, terminal case rejection, department mismatch rejection, cross-district rejection, inactive establishment rejection, and role-based access denial.

### 2. Full T3 Integration Test Suite (Phases 1 through 7.4.2)
**Command:**
```powershell
$files = Get-ChildItem tests/test_t3_*.py | ForEach-Object { $_.FullName }
$env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest -v $files
```
**Result:** **144 passed, 2 skipped** in 2.56s.
- `test_t3_1_user_profiles.py`: Passed
- `test_t3_2_history_and_saved_products.py`: Passed
- `test_t3_3_consumer_issue_reporting.py`: Passed
- `test_t3_4_authority_access_control.py`: Passed
- `test_t3_4_authority_case_workflow.py`: Passed
- `test_t3_4_atomic_workflow.py`: Passed
- `test_t3_4_trusted_jurisdiction.py`: Passed
- `test_t3_4_1_establishment_registry.py`: Passed
- `test_t3_4_2_verification_api.py`: Passed
- `test_t3_4_staging_live.py`: Skipped (Requires live staging environment credentials).

### 3. Gap Verification Test Suite (`test_t3_4_3_audit_gaps.py`)
**Command:**
```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest -v tests/test_t3_4_3_audit_gaps.py
```
**Result:** **6 passed** in 0.57s.
- Confirmed serialization omission in `consumer_issues.py`
- Confirmed `CaseDetailResponse` missing `establishment_id`
- Confirmed `ReviewEstablishmentRequest` notes alias behavior
- Confirmed reviewer identity persistence omission during SUSPEND
- Confirmed `SupabaseEstablishmentRepository` missing upsert header
- Confirmed GSTIN validation allowing short strings

---

## 6. Items Requiring Live Staging Verification

The following items cannot be fully verified offline in unit mocks and must be validated against a live staging Supabase instance (`VERIQOO_STAGING_LIVE=true`):

1. **RPC Security Grants against PostgREST Anonymous and Authenticated Roles:**
   - Verify that HTTP calls to `POST /rest/v1/rpc/authority_verify_complaint_jurisdiction` using the `anon` key return `401 Unauthorized` or `404 Not Found`.
   - Verify that HTTP calls using an `authenticated` consumer JWT return `403 Forbidden` / function execute permission denied.
   - Verify that execution is granted **only** when using `service_role`.

2. **Row-Level Security (RLS) on `retail_establishments`:**
   - Verify that authenticated consumers querying `/rest/v1/retail_establishments` can only see rows where `verification_status = 'VERIFIED' AND is_active = true`.
   - Verify that direct `INSERT`, `UPDATE`, or `DELETE` requests on `/rest/v1/retail_establishments` from client tokens are rejected with RLS policy violations.

3. **Live PostgREST Upsert Behavior (`C-1`):**
   - Confirm that updating an existing establishment via `SupabaseEstablishmentRepository` without `resolution=merge-duplicates` produces HTTP 409 on PostgreSQL, and that adding `resolution=merge-duplicates` resolves the error.

4. **Foreign Key Deletion Constraint (`ON DELETE SET NULL`):**
   - Verify that if a verified establishment record is deleted in PostgreSQL, any linked `consumer_issues.establishment_id` is set to `NULL` while the historical audit event row in `consumer_issue_audit_events` retains the complete JSON snapshot of the establishment metadata.

---

## 7. Recommended Fixes Ordered by Priority

### Priority 1: Immediate Bugfixes (Safe & Non-Breaking)
1. **Fix `SupabaseEstablishmentRepository.save_establishment` PostgREST Header (`C-1`):**
   - Add `resolution=merge-duplicates` to the `Prefer` header in `save_establishment`:
     ```python
     headers = self._headers(prefer="resolution=merge-duplicates,return=representation")
     ```
2. **Propagate Establishment & Provenance Fields in `consumer_issues.py` (`M-1`):**
   - In `_serialize_issue`, pass `establishment_id`, `jurisdiction_provenance`, `jurisdiction_verified_at`, and `jurisdiction_verified_by`.
3. **Resolve Notes Alias in `endpoints/authority.py` (`L-1`):**
   - In `review_establishment`, pass `payload.get_notes()` instead of `payload.notes`.
4. **Expose Establishment Metadata in Authority `CaseDetailResponse` (`M-2`):**
   - Add `establishment_id`, `jurisdiction_provenance`, `jurisdiction_verified_at`, and `jurisdiction_verified_by` to `CaseDetailResponse` and populate them in `get_case_details`.

### Priority 2: Data Integrity & Validation Hardening
5. **Harden GSTIN & Pincode Validation in `CreateEstablishmentRequest` (`M-3`):**
   - Add regex pattern matching: GSTIN (`^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`) and Pincode (`^\d{6}$`).
6. **Graceful Error Handling for Duplicate GSTIN (`L-2`):**
   - Map database unique constraint violation (`23505`) to `InvalidEstablishmentDataError` (HTTP 409 Conflict).

### Priority 3: Architecture & Schema Enhancements (Requires Next Migration)
7. **Introduce Atomic Establishment Review RPC & Audit History Table (`H-1`, `H-2`):**
   - In a future migration (e.g. `20261016000000_t3_4_2_establishment_lifecycle.sql`):
     - Create table `public.retail_establishment_audit_events` tracking `establishment_id`, `actor_id`, `event_type` (`ONBOARDED`, `VERIFIED`, `SUSPENDED`, `REVOKED`), `previous_status`, `new_status`, `metadata`, `created_at`.
     - Create atomic RPC `public.authority_review_establishment` with row locking (`FOR UPDATE`), optimistic status check, and atomic audit logging.
     - Add explicit `suspension_authority_id` and `suspension_date` columns or rely on the audit events table.
