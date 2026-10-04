# Veriqoo U24-G Consistency Audit: Atomic Authoritative Revalidation Persistence

## Executive Summary
This audit addresses the persistence-consistency boundary for **Veriqoo U24-G: Authoritative Revalidation Result Persistence, History & Report Lifecycle**. It establishes how the authoritative `SERVER_REVALIDATED` state is durably persisted across relational and sync stores without exposing incomplete, corrupted, or phantom state through the in-memory `session_store` or public inspection/report APIs.

---

## 1. Audit Analysis & Questions Answered

### A. Which writes already share a PostgreSQL transaction?
- Within `SupabaseInspectionRepository.save_report()`, the report row in `inspection_reports` and the status update in `inspection_sessions` are executed via PostgREST HTTP operations.
- Within `inspection_requirement_results`, batch requirement rows are inserted together in a single request.
- Within `inspection_sync_operations`, each operation record is written as a single row with strict schema constraints.

### B. Which writes are currently independent?
In the initial U24-G implementation:
1. `sync_repo.save_operation()` (writes `reval-rep-{inspection_id}`)
2. `session_store` update (`session.report = ...`, `status = COMPLETED`)
3. `inspection_repo.save_report()` (writes to `inspection_reports`)
4. `inspection_repo.save_requirement_results()` (writes to `inspection_requirement_results`)

These four writes were previously independent and executed in a loose sequence where errors could be caught without halting downstream state exposure.

### C. Whether the Supabase/PostgreSQL client supports transactional execution through the existing architecture?
- The current application architecture interacts with Supabase primarily via the PostgREST HTTP interface (`requests.post/get/patch`) and in-memory repositories for testing.
- PostgREST exposes individual endpoint mutations per table; multi-table transactions across disparate tables (`inspection_reports`, `inspection_requirement_results`, and `inspection_sync_operations`) require either a single RPC/stored procedure or ordered durable execution with defensive rollbacks and failure barriers.
- Fabricating fake distributed 2PC (two-phase commit) is explicitly prohibited.

### D. Whether `session_store` is merely a cache/in-memory projection and can safely be updated only after durable persistence succeeds?
- **YES**: `session_store` is an in-memory runtime projection designed for fast request serving in the active application instance.
- **Critical Invariant**: The in-memory session store **MUST NOT** be updated until all durable persistence writes (relational report, requirement results, and sync operation record) succeed.
- If any durable persistence write fails:
  - `session_store` remains completely unmodified in its prior state.
  - The inspection is NOT marked `COMPLETED`.
  - No `SERVER_REVALIDATED` report is exposed.
  - A retryable persistence error is returned/raised so the caller does NOT receive a false 200 OK.

### E. What the smallest atomic persistence unit can be?
The smallest safe and consistent persistence unit is:
1. **In-Memory Pre-computation & Validation**: Compute complete revalidation results, verify all required fields and hashes, and construct both the `InspectionReport` and `DurableSyncOperationRecord`.
2. **Durable Relational Persistence**:
   - Persist authoritative report to `inspection_repo.save_report(inspection_id, reval_report)`.
   - Persist authoritative requirement results to `inspection_repo.save_requirement_results(inspection_id, verification_results)`.
   - If either fails, raise a persistence error immediately.
3. **Durable Sync Operation Persistence**:
   - Persist authoritative sync operation `reval-rep-{inspection_id}` with `UPSERT` semantics.
   - If this fails, raise a persistence error immediately.
4. **In-Memory Cache Projection**:
   - Only after all preceding durable writes have completed without exception, apply the state to `session_store` (`session.report = reval_report`, `session.inspection.status = InspectionStatus.COMPLETED`).
5. **Success Response**: Return the validated `ServerRevalidationResult`.

---

## 2. Failure & Recovery Matrix

| Failure Point | Durable State | In-Memory Session State | API Response | Recovery Action |
| :--- | :--- | :--- | :--- | :--- |
| **Computation Failure** | Unchanged | Unchanged | HTTP 500 / Error | Safe retry |
| **Relational Report Save Fails** | Unchanged | Unchanged | HTTP 500 / Persistence Error | Safe retry |
| **Requirement Results Save Fails** | Partial relational rolled back / dirty | Unchanged | HTTP 500 / Persistence Error | Safe retry (UPSERT heals) |
| **Sync Operation Save Fails** | Relational updated | Unchanged | HTTP 500 / Persistence Error | Safe retry (UPSERT heals) |
| **Response Dropped after Commit** | Durable & Authoritative | Updated in Session Store | Client Retries | Idempotent replay returns existing result |

---

## 3. Implementation Plan
1. Update `ServerRevalidationService.revalidate()` in `backend/app/services/offline_sync/revalidation.py`:
   - Enforce strict ordering: Relational writes -> Sync operation write -> Session store update.
   - Any failure in the durable persistence phase raises a `RuntimeError` / persistence exception, aborting the in-memory update.
2. Update `tests/test_phase24g_revalidation_persistence.py` to add tests explicitly proving:
   - Report persistence failure leaves session store untouched and raises error.
   - Requirement results failure leaves session store untouched and raises error.
   - Sync persistence failure leaves session store untouched and raises error.
   - Historical offline results and comparison metadata survive both failed and successful revalidation events.
3. Run full regression suite to ensure zero regressions.
