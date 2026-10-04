# Veriqoo Architectural Audit: Phase U24-E Partial Sync + Recovery

**Author**: Veriqoo Backend Architecture Team  
**Phase**: U24-E (Offline Inspection & Sync — Partial Sync + Recovery)  
**Date**: October 2026  
**Status**: COMPLETE / AUTHORITATIVE  

---

## 1. Executive Summary & Audit Context

Veriqoo is a legal-metrology compliance inspection platform operating under strict India Packaged Commodities Rules statutory standards. 

Phase U24-D established deterministic offline compliance evaluation against approved legal snapshot contexts. Phase U24-B and U24-C established the durable server-side sync operation ingestion foundation and authenticated sync endpoints (`POST /api/v1/inspections/sync/batch`, `GET /api/v1/inspections/{inspection_id}/sync-status`).

The objective of **Phase U24-E** is to guarantee **robust partial synchronization, dependency resolution, idempotent replay, and failure recovery** when mobile clients encounter partial batch failures, intermittent connectivity, network drops post-commit, or out-of-order retries.

---

## 2. Core Audit Findings (Questions A through Q)

### A. Are sync operations currently processed atomically or individually?
**Individually with granular per-operation state tracking.**  
In `SyncIngestionService.ingest_batch`, operations are topologically ordered by `sequence` and processed individually. Each operation receives an independent `SyncAcknowledgement` and persists its own `DurableSyncOperationRecord` state in the database. A batch is never treated as a single monolithic transaction that would roll back unrelated valid operations if one operation fails.

### B. What happens if operation N succeeds and operation N+1 fails?
**Partial success is preserved without rollback.**  
Operation $N$ is persisted with `status = ACKNOWLEDGED` and its side-effects are committed. When operation $N+1$ encounters a failure (e.g., transient error, pending dependency, or invalid entity structure), it is recorded as `RETRYABLE_FAILURE` or `REJECTED`. The client receives a `SyncBatchResponse` containing `ACKNOWLEDGED` for operation $N$ and `RETRYABLE_FAILURE`/`REJECTED` for operation $N+1$. Operation $N$ remains permanently acknowledged on the server.

### C. What happens if a dependency has RETRYABLE_FAILURE?
**Dependent operations are blocked deterministically.**  
When `SyncEntityValidator.check_dependencies` evaluates prerequisites, if any dependency has `status IN ('PENDING', 'PROCESSING', 'RETRYABLE_FAILURE')`, it returns `can_proceed = False, dep_err_code = 'SYNC_DEPENDENCY_PENDING'`. The dependent operation is marked as `RETRYABLE_FAILURE` and is NOT mutated or applied until the dependency resolves.

### D. What happens if a dependency is REJECTED?
**Dependent operations are rejected permanently.**  
If any prerequisite operation has `status = 'REJECTED'`, `check_dependencies` returns `can_proceed = False, dep_err_code = 'SYNC_DEPENDENCY_REJECTED'`. The dependent operation is permanently marked as `REJECTED` with `SyncAckStatus.REJECTED`.

### E. What happens if a dependency is missing?
**Treated as pending/unresolved.**  
If a prerequisite operation ID does not exist in the database or current batch, `check_dependencies` flags `SYNC_DEPENDENCY_PENDING`. The dependent operation is held in `RETRYABLE_FAILURE` until the missing prerequisite is supplied in a subsequent batch.

### F. What happens if a dependency belongs to another inspection?
**Cross-inspection dependencies are strictly invalid.**  
Sync operations are strictly scoped to a single `inspection_id`. If a dependency ID references an operation belonging to a different inspection, it violates inspection boundary isolation and is permanently rejected with `SYNC_CROSS_INSPECTION_DEPENDENCY` / `SYNC_INVALID_DEPENDENCY`.

### G. What happens when the same operation is replayed?
**Deterministic idempotent receipt (`ALREADY_APPLIED`).**  
When an operation is replayed with an identical `content_hash`:
- If existing status is `ACKNOWLEDGED` or `ALREADY_APPLIED`, the server returns `ALREADY_APPLIED` immediately without re-running any mutations.
- If existing status is `REJECTED`, the server returns `REJECTED` with the original diagnostic error code and message.
- If existing status is `RETRYABLE_FAILURE`, the server re-attempts evaluation (safe retry).

### H. What happens when the same operation_id is replayed with different content?
**Strict rejection (`SYNC_DUPLICATE_PAYLOAD_MISMATCH`).**  
If `existing_op.content_hash != operation.content_hash`, the server flags a payload conflict under the same identity and returns `SyncAckStatus.REJECTED` with error code `SYNC_DUPLICATE_PAYLOAD_MISMATCH`. No server state is modified.

### I. Are operation state transitions monotonic and deterministic?
**Yes.** Transitions follow a deterministic lifecycle:
```
                      ┌───────────────────┐
                      │      PENDING      │
                      └─────────┬─────────┘
                                │
                                ▼
                      ┌───────────────────┐
                      │    PROCESSING     │
                      └───┬───────────┬───┘
                          │           │
            ┌─────────────┴─────┐     └──────────────┐
            ▼                   ▼                    ▼
   ┌─────────────────┐ ┌─────────────────┐ ┌───────────────────┐
   │  ACKNOWLEDGED   │ │RETRYABLE_FAILURE│ │     REJECTED      │
   └────────┬────────┘ └────────┬────────┘ └───────────────────┘
            │                   │ (on retry)          ▲
            ▼                   └──────────►──────────┘
   ┌─────────────────┐
   │ ALREADY_APPLIED │ (Terminal Replay)
   └─────────────────┘
```
Terminal states (`ACKNOWLEDGED`, `ALREADY_APPLIED`, `REJECTED`) never regress or allow content mutations.

### J. Can a failed operation accidentally mutate inspection state?
**No.** All validations (content hash, entity structure, circular dependencies, prerequisite dependencies, and ownership authorization) execute prior to any inspection domain mutation. If any validation fails, the mutation is bypassed and the error state is recorded.

### K. Can an already-applied operation accidentally execute its mutation again?
**No.** Idempotency check occurs as step 1 in `ingest_operation`. Identical replays return `ALREADY_APPLIED` prior to entering any domain creation logic.

### L. Can two concurrent requests process the same operation simultaneously?
**Yes, safely handled via DB uniqueness and repository locking.**  
- `InMemorySyncOperationRepository` uses thread-safe `RLock`.
- `SupabaseSyncOperationRepository` uses PostgreSQL unique constraint `inspection_sync_operations_operation_id_unique`. If two concurrent requests race to create the same operation record, the second receives a conflict, catches `DuplicateOperationIdError`, and safely updates or returns the existing status.

### M. Does the current DB schema support safe recovery?
**Yes.** The `public.inspection_sync_operations` table contains all fields required for deterministic recovery: `operation_id`, `inspection_id`, `entity_type`, `entity_id`, `content_hash`, `dependency_ids`, `status`, `attempt_count`, `payload`, `error_code`, `error_message`, `created_at`, `received_at`, and `acknowledged_at`.

### N. Which operations are safe to retry? (`SAFE_TO_REPLAY`)
- Operations with status `RETRYABLE_FAILURE`.
- Operations waiting on prerequisite operations (`SYNC_DEPENDENCY_PENDING`).
- Operations encountering transient database connectivity errors.
- Replaying previously acknowledged operations (returns `ALREADY_APPLIED` safely).

### O. Which operations require rejection? (`MUST_REJECT`)
- Content hash mismatch (`SYNC_CONTENT_HASH_MISMATCH`).
- Conflicting payload under same operation ID (`SYNC_DUPLICATE_PAYLOAD_MISMATCH`).
- Circular dependency graphs (`SYNC_CIRCULAR_DEPENDENCY`).
- Dependencies that were permanently rejected (`SYNC_DEPENDENCY_REJECTED`).
- Cross-inspection dependency references (`SYNC_CROSS_INSPECTION_DEPENDENCY`).
- Unauthorized caller / ownership mismatch (`SYNC_NOT_OWNER`).
- Malformed entity schema or unsupported entity types (`SYNC_INVALID_ENTITY`, `SYNC_VALIDATION_ERROR`).

### P. Which operations require server revalidation? (`MUST_REVALIDATE`)
- Operations evaluated offline with a stale legal snapshot context.
- Operations where `evaluation_metadata.revalidation_required` is `True`.
- Operations where offline declarations conflict with server-side legal requirements.

### Q. Which operations should require human review? (`HUMAN_REVIEW_REQUIRED`)
- Contradictory OCR observations or candidate declarations.
- Ambiguous or unparsed evidence candidates.
- TriState `UNKNOWN` applicability outcomes.

---

## 3. Extension Plan for Phase U24-E

1. **Enhanced Cross-Inspection Dependency Validation**: Update `SyncEntityValidator.check_dependencies` to verify that all prerequisite operations belong to the same `inspection_id`.
2. **Deterministic Error Code Standardization**: Ensure `SYNC_CROSS_INSPECTION_DEPENDENCY` is emitted when cross-inspection dependencies are detected.
3. **Partial Batch Resilience & Replay Convergence**: Validate that partial batch retries and repeated entire-batch replays converge to a stable, idempotent state.
4. **Preservation of Server Revalidation & Offline Metadata**: Ensure offline evaluation metadata and legal snapshot IDs flow cleanly through the sync pipeline without invoking Gemini or altering compliance statuses.
5. **Comprehensive Test Suite**: Implement `tests/test_phase24e_sync_recovery.py` with 25+ targeted test scenarios covering all audit questions.
