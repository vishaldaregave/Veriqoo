# Veriqoo Phase 7.4.2 — Secure Jurisdiction Verification API and Establishment Onboarding Report

## Executive Summary

Phase 7.4.2 connects the persistent commercial establishment registry and atomic jurisdiction-verification database RPC (established in Phase 7.4.1) to an authorized, end-to-end FastAPI backend workflow. It introduces protected authority endpoints for complaint jurisdiction verification and controlled commercial establishment onboarding and lifecycle review.

In compliance with project directives:
- **No QR code scanning or consumer mobile UI changes** were implemented in this phase.
- **Actor derivation is strictly authenticated**: The acting user ID is derived solely from the validated JWT authentication context (`require_authority_user`), never from an untrusted request body field.
- **Service-role credentials remain confidential**: Direct access to the database RPC is revoked from `PUBLIC` and `authenticated` roles in PostgreSQL and restricted to `service_role`. The FastAPI backend safely executes the RPC using backend credentials after verifying the officer's active credentials, role, department, and jurisdiction scope.
- **Establishments start as PENDING and unverified**: No synthetic demo data was marked as verified, and no external GSTIN gateway integrations were fabricated.
- **All 146 backend tests pass** with zero errors or regressions.

---

## 1. Pre-Implementation Audit & Architecture Decisions

### 1.1 Existing Assets Inspected
- [`supabase/migrations/20261015000000_t3_4_1_establishment_registry.sql`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/supabase/migrations/20261015000000_t3_4_1_establishment_registry.sql): Schema definition for `retail_establishments`, consumer issue extensions (`establishment_id`, `jurisdiction_provenance`, `jurisdiction_verified_at`, `jurisdiction_verified_by`), and atomic RPC `public.authority_verify_complaint_jurisdiction`.
- [`backend/app/services/establishment/`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/establishment/): Domain models (`RetailEstablishment`), provenance enums, error hierarchy, and repository interfaces (`EstablishmentRepository`, `InMemoryEstablishmentRepository`, `SupabaseEstablishmentRepository`).
- [`backend/app/services/authority/case_repository.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/authority/case_repository.py): `atomic_verify_jurisdiction()` implementation for both in-memory unit tests and Supabase REST/RPC execution.
- [`backend/app/services/authority/case_service.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/authority/case_service.py): Business logic coordination for queues, assignment, investigation notes, and status lifecycle.
- [`backend/app/api/v1/endpoints/authority.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/api/v1/endpoints/authority.py): FastAPI endpoints for authority operations.
- [`backend/app/api/dependencies.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/api/dependencies.py): Dependency injection graph for repositories and service coordinators.

### 1.2 Identified Gaps Before Phase 7.4.2
1. **Missing Service Layer for Establishments**: While the repository and domain model existed, there was no `EstablishmentService` coordinating business validation (LGD jurisdiction checks, duplicate GSTIN checks, onboarding lifecycle, and state/district authorization boundaries).
2. **Missing Endpoint for Jurisdiction Verification**: No HTTP endpoint existed for an authorized officer to bind a complaint to a verified establishment.
3. **Missing Establishment Onboarding & Review Endpoints**: Authorities lacked REST endpoints to onboard new commercial premises or transition establishment verification status (`VERIFY`, `SUSPEND`, `REVOKE`).
4. **Dependency Injection Gap**: `get_authority_case_service` did not inject `EstablishmentRepository`, preventing pre-validation of establishment records prior to RPC dispatch.

---

## 2. Authorized Jurisdiction Verification Implementation

### 2.1 Endpoint Specification
- **Path**: `POST /api/v1/authority/cases/{case_id}/verify-jurisdiction`
- **Authentication**: Bearer JWT validated via `require_authority_user` (roles: `authority` or `admin`).
- **Request Schema**: [`VerifyCaseJurisdictionRequest`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/authority/schemas.py)
  ```json
  {
    "establishment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "provenance": "ADMIN_TRIAGE_VERIFICATION",
    "verification_notes": "Premises inspected and matched with municipal trade records."
  }
  ```
- **Response Schema**: [`VerifyCaseJurisdictionResponse`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/authority/schemas.py)
  ```json
  {
    "case_id": "c8e9c005-1ad0-4547-9066-ccaa7caae2ec",
    "establishment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "state_code": "MH",
    "district_code": "PUNE",
    "jurisdiction_verified": true,
    "jurisdiction_provenance": "ADMIN_TRIAGE_VERIFICATION",
    "verified_at": "2026-10-05T01:45:00Z",
    "verified_by": "33330000-0000-0000-0000-000000000003",
    "audit_event_id": "e81d432e-b6a3-4b68-9642-e19efc212211"
  }
  ```

### 2.2 Security & Authorization Guardrails
1. **Actor Derivation**: `principal.user_id` is obtained strictly from the verified JWT payload. Untrusted actor IDs in request bodies are neither accepted nor allowed.
2. **Profile & Status Validation**: The authority user must have an active `UserProfile` with role `authority` or `admin`, and an active `AuthorityProfile`.
3. **Department Isolation**: Case department (`case.department`) must strictly match the officer's assigned department (`principal.department`). Cross-department attempts fail with HTTP 403 (`DEPARTMENT_MISMATCH`).
4. **Establishment Integrity**: The target establishment must exist (`EstablishmentNotFoundError` -> 404), be active (`EstablishmentInactiveError` -> 422), and be verified (`EstablishmentUnverifiedError` -> 422).
5. **Jurisdiction Boundary Enforcement**:
   - `establishment.state_code` must match `principal.jurisdiction.state_code`.
   - `establishment.district_code` must be an element of `principal.jurisdiction.authorized_district_codes`.
   - Violations fail immediately with HTTP 403 (`AuthorityJurisdictionDeniedError`).
6. **Case Lifecycle Protection**: Complaints in terminal statuses (`RESOLVED`, `REJECTED`) cannot be verified (HTTP 422 `InvalidStatusTransitionError`).
7. **Atomic Transaction Boundary**: The operation delegates to `AuthorityCaseRepository.atomic_verify_jurisdiction()`, which executes the database function `public.authority_verify_complaint_jurisdiction`. If audit event insertion or case update fails, all changes are rolled back within the single database transaction.
8. **Queue Activation**: Prior to verification, complaints have `jurisdiction_verified = False` and are completely excluded from authority queues. Upon verification, the complaint activates in the authorized district officer's queue and remains excluded from other districts.

---

## 3. Controlled Establishment Onboarding & Review

### 3.1 Workflow Architecture
Commercial establishments represent physical or registered merchant premises. To prevent untrusted data poisoning:
- **Default State**: Newly registered establishments start in status `PENDING`, `is_active = True`, and `verification_provenance = MANUAL`.
- **Jurisdiction Validation**: States and districts are validated against canonical Indian LGD codes (`validate_canonical_jurisdiction`). Invalid codes are rejected with HTTP 422.
- **Onboarding Boundary**: An officer can only onboard establishments located within their authorized state and districts. Cross-district or cross-state onboarding attempts fail with HTTP 403.
- **GSTIN Conflict Protection**: Attempting to onboard an establishment with a pre-existing GSTIN fails closed with HTTP 422.
- **No Fabricated Registries**: Verification provenance is explicitly set to `MANUAL`, `ADMIN_TRIAGE_VERIFICATION`, or `OFFICIAL_REGISTRY` (when an authoritative external source is configured). No live GSTIN verification is claimed without real portal credentials.

### 3.2 Reviewer Authorization Model
- **Endpoint**: `POST /api/v1/authority/establishments/{establishment_id}/review`
- **Supported Actions**:
  - `VERIFY`: Updates status to `VERIFIED`, captures reviewer identity (`verification_authority_id`), timestamp (`verification_date`), provenance, and audited notes.
  - `SUSPEND`: Updates status to `SUSPENDED` and sets `is_active = False` without deleting historical records.
  - `REVOKE`: Updates status to `REVOKED` and sets `is_active = False`.
- **Jurisdiction Boundary on Review**: Officers can only review establishments within their authorized state and districts. Cross-district review attempts fail with HTTP 403.
- **Documented Authorization Limitation**: The current system relies on district/state jurisdiction matching for reviews. A dedicated statewide registrar or central licensing authority role is recommended before opening merchant self-registration.

### 3.3 Establishment Listing & Inspection Endpoints
- `GET /api/v1/authority/establishments/{establishment_id}`: Retrieves establishment details. Accessible if within officer's jurisdiction, or if verified and active.
- `GET /api/v1/authority/establishments`: Paginated listing filtered by canonical state and authorized district codes. Querying districts outside the officer's scope fails with HTTP 403.

---

## 4. Summary of Code & File Changes

| File | Change Type | Description |
|---|---|---|
| [`backend/app/services/establishment/schemas.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/establishment/schemas.py) | Created | Pydantic request/response schemas for establishment onboarding, review, detail, and paginated listing. |
| [`backend/app/services/establishment/service.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/establishment/service.py) | Created | `EstablishmentService` coordinating canonical validation, GSTIN uniqueness, onboarding, review transitions, and scoped lookups. |
| [`backend/app/services/establishment/__init__.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/establishment/__init__.py) | Modified | Re-exported schemas, errors, models, repositories, and service. |
| [`backend/app/services/authority/schemas.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/authority/schemas.py) | Modified | Added `VerifyCaseJurisdictionRequest` and `VerifyCaseJurisdictionResponse`. |
| [`backend/app/services/authority/case_service.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/services/authority/case_service.py) | Modified | Injected `establishment_repository` into `AuthorityCaseService` and implemented `verify_case_jurisdiction()`. |
| [`backend/app/api/dependencies.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/api/dependencies.py) | Modified | Added `get_establishment_service` provider and wired `establishment_repository` into `get_authority_case_service`. |
| [`backend/app/api/v1/endpoints/authority.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/backend/app/api/v1/endpoints/authority.py) | Modified | Added `POST /cases/{case_id}/verify-jurisdiction`, `POST /establishments`, `POST /establishments/{establishment_id}/review`, `GET /establishments/{id}`, and `GET /establishments`. |
| [`tests/test_t3_4_2_verification_api.py`](file:///c:/Users/omnik/Downloads/Prince/CraftVerse/Veriqoo/tests/test_t3_4_2_verification_api.py) | Created | 13 comprehensive tests for verification API, role gating, jurisdiction bounds, establishment lifecycle, atomicity rollback, and queue activation. |

---

## 5. Verification Test Suite Results

### 5.1 New Tests: `tests/test_t3_4_2_verification_api.py`
Execution command:
```powershell
.venv\Scripts\python.exe -m unittest tests/test_t3_4_2_verification_api.py
```
Results:
```
Ran 13 tests in 0.209s
OK
```

#### Detailed Test Coverage Matrix:
1. `test_unauthenticated_requests_fail_401`: Verifies that calls without an `Authorization` header to verification and establishment endpoints return HTTP 401.
2. `test_consumer_and_inspector_roles_denied_403`: Verifies that users with `consumer` and `inspector` roles are rejected with HTTP 403 on all authority verification and establishment onboarding routes.
3. `test_inactive_and_unprovisioned_authority_denied_403`: Verifies that deactivated officers (`is_active = False`) and unprovisioned users lacking an `AuthorityProfile` return HTTP 403.
4. `test_cross_district_verification_denied_403`: Verifies that a Pune officer attempting to verify against a Satara establishment receives HTTP 403.
5. `test_cross_department_verification_denied_403`: Verifies that a Food Safety officer attempting to verify a Legal Metrology complaint receives HTTP 403 (`DEPARTMENT_MISMATCH`).
6. `test_unverified_establishment_rejected`: Verifies that attempting verification against a `PENDING` establishment returns HTTP 422.
7. `test_inactive_establishment_rejected`: Verifies that attempting verification against an inactive establishment returns HTTP 422.
8. `test_nonexistent_establishment_returns_404`: Verifies that a non-existent establishment ID returns HTTP 404.
9. `test_terminal_case_verification_rejected`: Verifies that cases in terminal states (`RESOLVED`, `REJECTED`) cannot be verified (HTTP 422).
10. `test_successful_jurisdiction_verification_and_queue_activation`: Verifies end-to-end verification, state binding, provenance setting, audit event emission, and activation in the Pune queue while remaining excluded from the Satara queue.
11. `test_verification_failure_atomicity_rollback`: Verifies that simulated audit event insertion failure rolls back all case modifications to the unverified state.
12. `test_establishment_onboarding_lifecycle`: Verifies initial `PENDING` status, cross-district rejection, duplicate GSTIN rejection, cross-officer review denial, approval to `VERIFIED`, and suspension to `SUSPENDED` with `is_active = False`.
13. `test_list_and_get_establishments_jurisdiction_scoping`: Verifies that establishment lookups and paginated queries are strictly scoped to the officer's authorized state and districts.

### 5.2 Full Regression Test Suite Execution
Execution command:
```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_t3_*.py"
```
Results:
```
Ran 146 tests in 1.337s
OK (skipped=2)
```
*(The 2 skipped tests are staging tests in `test_t3_4_staging_live.py`, which intentionally skip when live Supabase credentials are absent).*

### 5.3 Distinction Between Mocked and Live Database Tests
- **In-Memory Mock Tests**: The 13 tests in `test_t3_4_2_verification_api.py` and the existing unit suites execute against in-memory repository doubles. They prove endpoint routing, authentication parsing, role authorization, domain logic, error schemas, and atomicity rollback semantics.
- **Live Supabase / PostgreSQL RPC Tests**: Real execution of migration `20261015000000_t3_4_1_establishment_registry.sql` against PostgreSQL requires staging credentials (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`). Staging deployment and live execution are reserved for authorized staging test windows.

---

## 6. Known Limitations & Staging Acceptance Criteria

### 6.1 Known Limitations
1. **No QR Scanning (By Design)**: QR code generation and consumer camera scanning workflows are intentionally deferred to Phase 7.5.
2. **No Live GSTIN Validation Gateway**: Establishment GSTINs are formatted and validated syntactically; verification relies on officer audit provenance (`MANUAL`, `ADMIN_TRIAGE_VERIFICATION`). Integration with the national GST API requires live government gateway API credentials.
3. **Establishment Reviewer Hierarchy**: Any active authority officer can currently verify or suspend establishments within their assigned district. Future revisions should consider adding a designated `state_admin` or `licensing_officer` sub-role.

### 6.2 Staging Acceptance Criteria
Before applying migration `20261015000000_t3_4_1_establishment_registry.sql` to staging:
1. Verify `public.retail_establishments` table creation and foreign key constraint `fk_consumer_issues_establishment` on `public.consumer_issues`.
2. Verify `public.authority_verify_complaint_jurisdiction` RPC permissions (`REVOKE ALL FROM PUBLIC, authenticated; GRANT EXECUTE TO service_role`).
3. Confirm that direct client invocations using user JWTs fail with `42501` permission denied, while backend calls with `service_role` succeed.
4. Execute `python -m unittest tests/test_t3_4_staging_live.py` with staging credentials to validate live PostgreSQL row locking and atomic event creation.
