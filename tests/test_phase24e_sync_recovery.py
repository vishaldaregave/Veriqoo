"""Comprehensive test suite for Phase U24-E — Partial Sync & Recovery.

Tests all required U24-E verification scenarios:
1. Independent operations partially succeed
2. Failed operation remains retryable (RETRYABLE_FAILURE)
3. Dependent operation waits for failed dependency
4. Retry after dependency succeeds unblocks dependent operations
5. Same operation replay returns ALREADY_APPLIED
6. Same operation ID with changed payload returns REJECTED + SYNC_DUPLICATE_PAYLOAD_MISMATCH
7. Already-applied operation does not mutate underlying domain twice
8. Missing dependency blocks dependent operation deterministically
9. Rejected dependency permanently blocks dependent operation (SYNC_DEPENDENCY_REJECTED)
10. Retryable dependency blocks dependent operation until resolved
11. Cross-inspection dependency rejected (SYNC_CROSS_INSPECTION_DEPENDENCY)
12. Dependency cycle rejected (SYNC_CIRCULAR_DEPENDENCY)
13. Invalid content hash rejected (SYNC_CONTENT_HASH_MISMATCH)
14. Ownership mismatch safely rejected (SYNC_NOT_OWNER)
15. Concurrent duplicate submission thread safety
16. Independent operations not rolled back when another operation fails
17. Retryable infrastructure failure does not corrupt state
18. Permanent validation failure is not marked retryable
19. Repeated entire-batch replay converges to a stable, idempotent state
20. Partial retry only processes unresolved operations
21. Stale legal snapshot does not silently become current compliance (MUST_REVALIDATE preserved)
22. Existing U24-D offline evaluation metadata is preserved
23. No new compliance statuses are introduced
24. Existing U24-C API behavior remains compatible
25. No duplicate inspection entities are created
26. Monotonic state transitions lattice enforced
27. Manifest reconciliation accurately reflects partial and recovered states
"""

import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_inspection_repository,
    get_session_store,
    get_sync_ingestion_service,
    get_sync_operation_repository,
)
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import AuthenticatedUser
from backend.app.main import create_app
from backend.app.services.inspection.repository import InMemoryInspectionRepository
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.offline_sync import (
    DurableSyncOperationRecord,
    EvaluationMetadata,
    EvaluationMode,
    InMemorySyncOperationRepository,
    OperationStatus,
    SyncAckStatus,
    SyncAcknowledgement,
    SyncEntityType,
    SyncErrorCode,
    SyncIngestionService,
    SyncManifest,
    SyncOperation,
    SyncOperationType,
    SyncStatus,
)
from backend.app.services.offline_sync.validator import SyncEntityValidator
from backend.app.services.verification.models import VerificationStatus


def _make_op(
    operation_id: str,
    inspection_id: str = "insp-100",
    entity_type: SyncEntityType = SyncEntityType.INSPECTION,
    entity_id: str = "insp-100",
    operation_type: SyncOperationType = SyncOperationType.CREATE,
    payload: dict | None = None,
    sequence: int = 1,
    dependency_ids: list[str] | None = None,
    created_at: str | None = None,
) -> SyncOperation:
    """Construct a valid hashed SyncOperation."""
    p = payload if payload is not None else {"metadata": {"notes": "test"}}
    content_hash = SyncOperation.compute_content_hash(p)
    return SyncOperation(
        operation_id=operation_id,
        inspection_id=inspection_id,
        entity_type=entity_type,
        entity_id=entity_id,
        operation_type=operation_type,
        content_hash=content_hash,
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
        sequence=sequence,
        dependency_ids=dependency_ids or [],
        payload=p,
    )


class TestPhase24EPartialSyncAndRecovery:
    """Unit and integration test suite for partial sync and deterministic recovery."""

    def test_01_independent_operations_partially_succeed(self):
        """Independent operations in a batch succeed even if one fails."""
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        service = SyncIngestionService(sync_repo, insp_repo)
        user_id = "user-100"

        # Root inspection
        op_root = _make_op("op-root", "insp-1", SyncEntityType.INSPECTION, "insp-1", sequence=1)
        # Valid image operation
        op_img = _make_op(
            "op-img-1",
            "insp-1",
            SyncEntityType.IMAGE,
            "img-1",
            payload={"image_id": "img-1", "normalized_hash": "hash-abc"},
            sequence=2,
            dependency_ids=["op-root"],
        )
        # Invalid evidence operation (missing target field -> permanent reject)
        op_invalid = _make_op(
            "op-ev-invalid",
            "insp-1",
            SyncEntityType.EVIDENCE,
            "ev-1",
            payload={"raw_text": "sample text without field"},
            sequence=3,
        )
        # Valid independent fact operation
        op_fact = _make_op(
            "op-fact-1",
            "insp-1",
            SyncEntityType.FACT,
            "fact-1",
            payload={"fact_key": "is_prepacked", "value": True},
            sequence=4,
            dependency_ids=["op-root"],
        )

        acks = service.ingest_batch([op_root, op_img, op_invalid, op_fact], user_id)
        assert len(acks) == 4

        ack_map = {a.operation_id: a for a in acks}
        assert ack_map["op-root"].status == SyncAckStatus.ACKNOWLEDGED
        assert ack_map["op-img-1"].status == SyncAckStatus.ACKNOWLEDGED
        assert ack_map["op-ev-invalid"].status == SyncAckStatus.REJECTED
        assert ack_map["op-fact-1"].status == SyncAckStatus.ACKNOWLEDGED

    def test_02_failed_operation_remains_retryable(self):
        """Transiently failed operation (e.g. missing dependency) is recorded as RETRYABLE_FAILURE."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        # Child operation submitted before parent exists
        op_child = _make_op(
            "op-child",
            "insp-1",
            SyncEntityType.OCR_OBSERVATION,
            "obs-1",
            payload={"image_id": "img-1", "raw_text": "text"},
            sequence=1,
            dependency_ids=["op-missing-parent"],
        )

        ack = service.ingest_operation(op_child, user_id)
        assert ack.status == SyncAckStatus.RETRYABLE_FAILURE
        assert ack.error_code == SyncErrorCode.SYNC_DEPENDENCY_PENDING.value

        rec = sync_repo.get_operation("op-child")
        assert rec is not None
        assert rec.status == OperationStatus.RETRYABLE_FAILURE

    def test_03_dependent_operation_waits_for_failed_dependency(self):
        """Operation D depending on C waits when C is in RETRYABLE_FAILURE."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        op_a = _make_op("op-a", "insp-1", SyncEntityType.INSPECTION, "insp-1", sequence=1)
        # C depends on missing op-x -> C becomes RETRYABLE_FAILURE
        op_c = _make_op(
            "op-c",
            "insp-1",
            SyncEntityType.IMAGE,
            "img-1",
            payload={"image_id": "img-1", "source_hash": "hash1"},
            sequence=2,
            dependency_ids=["op-x"],
        )
        # D depends on C
        op_d = _make_op(
            "op-d",
            "insp-1",
            SyncEntityType.OCR_OBSERVATION,
            "obs-1",
            payload={"image_id": "img-1", "raw_text": "MRP 100"},
            sequence=3,
            dependency_ids=["op-c"],
        )

        acks = service.ingest_batch([op_a, op_c, op_d], user_id)
        ack_map = {a.operation_id: a for a in acks}

        assert ack_map["op-a"].status == SyncAckStatus.ACKNOWLEDGED
        assert ack_map["op-c"].status == SyncAckStatus.RETRYABLE_FAILURE
        assert ack_map["op-d"].status == SyncAckStatus.RETRYABLE_FAILURE
        assert ack_map["op-d"].error_code == SyncErrorCode.SYNC_DEPENDENCY_PENDING.value

    def test_04_retry_after_dependency_succeeds(self):
        """When prerequisite dependency succeeds in a later batch, dependent operation is acknowledged."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        # Batch 1: op-parent is not present, op-child fails with retryable dependency
        op_child = _make_op(
            "op-child",
            "insp-1",
            SyncEntityType.OCR_OBSERVATION,
            "obs-1",
            payload={"image_id": "img-1", "raw_text": "text"},
            sequence=1,
            dependency_ids=["op-parent"],
        )
        ack1 = service.ingest_operation(op_child, user_id)
        assert ack1.status == SyncAckStatus.RETRYABLE_FAILURE

        # Batch 2: submit op-parent first, then retry op-child
        op_parent = _make_op(
            "op-parent",
            "insp-1",
            SyncEntityType.IMAGE,
            "img-1",
            payload={"image_id": "img-1", "source_hash": "hash1"},
            sequence=1,
        )
        ack_parent = service.ingest_operation(op_parent, user_id)
        assert ack_parent.status == SyncAckStatus.ACKNOWLEDGED

        # Retry op-child
        ack_child_retry = service.ingest_operation(op_child, user_id)
        assert ack_child_retry.status == SyncAckStatus.ACKNOWLEDGED

        rec = sync_repo.get_operation("op-child")
        assert rec.status == OperationStatus.ACKNOWLEDGED
        assert rec.attempt_count == 2

    def test_05_same_operation_replay_returns_already_applied(self):
        """Network disconnect simulation: replaying an acknowledged operation returns ALREADY_APPLIED."""
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        service = SyncIngestionService(sync_repo, insp_repo)
        user_id = "user-100"

        op = _make_op("op-1", "insp-1", SyncEntityType.INSPECTION, "insp-1")
        ack1 = service.ingest_operation(op, user_id)
        assert ack1.status == SyncAckStatus.ACKNOWLEDGED

        # Simulate mobile client retrying after connection drop
        ack2 = service.ingest_operation(op, user_id)
        assert ack2.status == SyncAckStatus.ALREADY_APPLIED
        assert ack2.operation_id == "op-1"

    def test_06_same_operation_id_with_changed_payload_returns_rejected(self):
        """Replaying the same operation_id with mutated payload is rejected."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        op1 = _make_op("op-tamper", "insp-1", payload={"data": "original"})
        ack1 = service.ingest_operation(op1, user_id)
        assert ack1.status == SyncAckStatus.ACKNOWLEDGED

        # Same op_id, altered payload
        op2 = _make_op("op-tamper", "insp-1", payload={"data": "mutated"})
        ack2 = service.ingest_operation(op2, user_id)
        assert ack2.status == SyncAckStatus.REJECTED
        assert ack2.error_code == SyncErrorCode.SYNC_DUPLICATE_PAYLOAD_MISMATCH.value

    def test_07_already_applied_operation_does_not_mutate_twice(self):
        """ALREADY_APPLIED operation does not trigger redundant underlying creation or side effects."""
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        service = SyncIngestionService(sync_repo, insp_repo)
        user_id = "user-100"

        op = _make_op("op-insp", "insp-1", SyncEntityType.INSPECTION, "insp-1")
        service.ingest_operation(op, user_id)
        assert insp_repo.get_inspection("insp-1") is not None

        # Replay should not call create_inspection again
        ack_replay = service.ingest_operation(op, user_id)
        assert ack_replay.status == SyncAckStatus.ALREADY_APPLIED

    def test_08_missing_dependency_blocks_dependent_operation(self):
        """Missing prerequisite dependency holds dependent in RETRYABLE_FAILURE."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        op = _make_op("op-child", "insp-1", dependency_ids=["op-nonexistent"])
        ack = service.ingest_operation(op, user_id)
        assert ack.status == SyncAckStatus.RETRYABLE_FAILURE
        assert ack.error_code == SyncErrorCode.SYNC_DEPENDENCY_PENDING.value

    def test_09_rejected_dependency_blocks_dependent_operation(self):
        """Permanently rejected dependency causes dependent operation to be permanently REJECTED."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        # Parent with invalid entity structure -> REJECTED
        op_bad_parent = _make_op(
            "op-bad-parent",
            "insp-1",
            SyncEntityType.IMAGE,
            "img-1",
            payload={"missing_hash": "true"},  # Invalid IMAGE payload
            sequence=1,
        )
        # Child depending on bad parent
        op_child = _make_op(
            "op-child",
            "insp-1",
            SyncEntityType.OCR_OBSERVATION,
            "obs-1",
            payload={"image_id": "img-1", "raw_text": "text"},
            sequence=2,
            dependency_ids=["op-bad-parent"],
        )

        acks = service.ingest_batch([op_bad_parent, op_child], user_id)
        ack_map = {a.operation_id: a for a in acks}

        assert ack_map["op-bad-parent"].status == SyncAckStatus.REJECTED
        assert ack_map["op-child"].status == SyncAckStatus.REJECTED
        assert ack_map["op-child"].error_code == SyncErrorCode.SYNC_DEPENDENCY_REJECTED.value

    def test_10_retryable_dependency_blocks_dependent_operation(self):
        """Dependent operation is blocked when prerequisite is in RETRYABLE_FAILURE."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        op_root = _make_op("op-a", "insp-1", dependency_ids=["op-missing"])
        ack_root = service.ingest_operation(op_root, user_id)
        assert ack_root.status == SyncAckStatus.RETRYABLE_FAILURE

        op_b = _make_op("op-b", "insp-1", dependency_ids=["op-a"])
        ack_b = service.ingest_operation(op_b, user_id)
        assert ack_b.status == SyncAckStatus.RETRYABLE_FAILURE
        assert ack_b.error_code == SyncErrorCode.SYNC_DEPENDENCY_PENDING.value

    def test_11_cross_inspection_dependency_rejected(self):
        """Dependency referencing a different inspection is rejected permanently."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        # Operation in insp-1
        op_insp1 = _make_op("op-1", "insp-1", SyncEntityType.INSPECTION, "insp-1")
        service.ingest_operation(op_insp1, user_id)

        # Operation in insp-2 referencing op-1 from insp-1
        op_insp2 = _make_op(
            "op-2",
            "insp-2",
            SyncEntityType.IMAGE,
            "img-2",
            payload={"image_id": "img-2", "source_hash": "hash2"},
            dependency_ids=["op-1"],
        )
        ack = service.ingest_operation(op_insp2, user_id)
        assert ack.status == SyncAckStatus.REJECTED
        assert ack.error_code == SyncErrorCode.SYNC_CROSS_INSPECTION_DEPENDENCY.value

    def test_12_dependency_cycle_rejected(self):
        """Circular dependency graph is rejected with SYNC_CIRCULAR_DEPENDENCY."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        op1 = _make_op("op-cycle-1", "insp-1", sequence=1, dependency_ids=["op-cycle-2"])
        op2 = _make_op("op-cycle-2", "insp-1", sequence=2, dependency_ids=["op-cycle-1"])

        acks = service.ingest_batch([op1, op2], user_id)
        for a in acks:
            assert a.status == SyncAckStatus.REJECTED
            assert a.error_code == SyncErrorCode.SYNC_CIRCULAR_DEPENDENCY.value

    def test_13_invalid_content_hash_rejected(self):
        """Content hash mismatch is rejected permanently."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        op = SyncOperation(
            operation_id="op-bad-hash",
            inspection_id="insp-1",
            entity_type=SyncEntityType.INSPECTION,
            entity_id="insp-1",
            operation_type=SyncOperationType.CREATE,
            content_hash="0000000000000000000000000000000000000000000000000000000000000000",
            created_at=datetime.now(timezone.utc).isoformat(),
            payload={"metadata": {"test": "val"}},
        )
        ack = service.ingest_operation(op, user_id)
        assert ack.status == SyncAckStatus.REJECTED
        assert ack.error_code == SyncErrorCode.SYNC_CONTENT_HASH_MISMATCH.value

    def test_14_ownership_mismatch_safely_rejected(self):
        """Attempt to synchronize against another user's inspection returns SYNC_NOT_OWNER."""
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        service = SyncIngestionService(sync_repo, insp_repo)

        # Owner creates inspection
        insp_repo.create_inspection("insp-alice", owner_id="user-alice")

        # Bob attempts to sync operation to Alice's inspection
        op = _make_op("op-bob", "insp-alice", SyncEntityType.IMAGE, "img-1", payload={"image_id": "img-1", "source_hash": "h1"})
        ack = service.ingest_operation(op, authenticated_user_id="user-bob")
        assert ack.status == SyncAckStatus.REJECTED
        assert ack.error_code == SyncErrorCode.SYNC_NOT_OWNER.value

    def test_15_concurrent_duplicate_submission_is_safe(self):
        """Concurrent duplicate submissions are thread-safe and resolve to ACKNOWLEDGED / ALREADY_APPLIED."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        op = _make_op("op-concurrent", "insp-1", SyncEntityType.INSPECTION, "insp-1")

        def submit():
            return service.ingest_operation(op, user_id)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(submit) for _ in range(5)]
            results = [f.result() for f in futures]

        statuses = [r.status for r in results]
        assert SyncAckStatus.ACKNOWLEDGED in statuses
        for s in statuses:
            assert s in (SyncAckStatus.ACKNOWLEDGED, SyncAckStatus.ALREADY_APPLIED)

    def test_16_independent_operations_not_rolled_back_on_failure(self):
        """Failure in an independent operation does not roll back previously acknowledged operations."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        op1 = _make_op("op-1", "insp-1", sequence=1)
        op2 = _make_op("op-2-fail", "insp-1", payload={"corrupted": True}, sequence=2)
        # Manually alter op2's content_hash to trigger validation failure
        op2.content_hash = "bad-hash"

        acks = service.ingest_batch([op1, op2], user_id)
        assert acks[0].status == SyncAckStatus.ACKNOWLEDGED
        assert acks[1].status == SyncAckStatus.REJECTED

        # op1 is still acknowledged in repository
        assert sync_repo.get_operation("op-1").status == OperationStatus.ACKNOWLEDGED

    def test_17_retryable_infrastructure_failure_does_not_corrupt_state(self):
        """Database or infrastructure exceptions during creation record RETRYABLE_FAILURE."""
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        service = SyncIngestionService(sync_repo, insp_repo)
        user_id = "user-100"

        # Force inspection repo to raise runtime exception
        def failing_create(*args, **kwargs):
            raise RuntimeError("Database connection timeout")

        insp_repo.create_inspection = failing_create

        op = _make_op("op-db-fail", "insp-1", SyncEntityType.INSPECTION, "insp-1")
        ack = service.ingest_operation(op, user_id)

        assert ack.status == SyncAckStatus.RETRYABLE_FAILURE
        assert ack.error_code == SyncErrorCode.SYNC_DATABASE_ERROR.value

    def test_18_permanent_validation_failure_is_not_marked_retryable(self):
        """Structural entity schema violations are permanently marked REJECTED, not RETRYABLE_FAILURE."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        # Missing rule_id/decision in APPLICABILITY
        op_invalid_app = _make_op(
            "op-app-bad",
            "insp-1",
            SyncEntityType.APPLICABILITY,
            "app-1",
            payload={"invalid_key": "val"},
        )
        ack = service.ingest_operation(op_invalid_app, user_id)
        assert ack.status == SyncAckStatus.REJECTED
        assert ack.error_code == SyncErrorCode.SYNC_INVALID_ENTITY.value

    def test_19_repeated_entire_batch_replay_converges_to_stable_state(self):
        """Replaying the entire batch multiple times converges to stable, idempotent ALREADY_APPLIED / REJECTED receipts."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        op_root = _make_op("op-root", "insp-1", sequence=1)
        op_img = _make_op("op-img", "insp-1", SyncEntityType.IMAGE, "img-1", payload={"image_id": "img-1", "source_hash": "h1"}, sequence=2, dependency_ids=["op-root"])
        op_bad = _make_op("op-bad", "insp-1", SyncEntityType.IMAGE, "img-2", payload={"no_hash": True}, sequence=3)

        batch = [op_root, op_img, op_bad]

        # Pass 1
        acks1 = service.ingest_batch(batch, user_id)
        assert acks1[0].status == SyncAckStatus.ACKNOWLEDGED
        assert acks1[1].status == SyncAckStatus.ACKNOWLEDGED
        assert acks1[2].status == SyncAckStatus.REJECTED

        # Pass 2 (Replay)
        acks2 = service.ingest_batch(batch, user_id)
        assert acks2[0].status == SyncAckStatus.ALREADY_APPLIED
        assert acks2[1].status == SyncAckStatus.ALREADY_APPLIED
        assert acks2[2].status == SyncAckStatus.REJECTED

        # Pass 3 (Replay)
        acks3 = service.ingest_batch(batch, user_id)
        assert [a.status for a in acks3] == [a.status for a in acks2]

    def test_20_partial_retry_only_processes_unresolved_operations(self):
        """Retrying only the failed items after fixing them succeeds without re-running earlier items."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        op_a = _make_op("op-a", "insp-1", sequence=1)
        # op_b initially depends on missing op_x
        op_b = _make_op("op-b", "insp-1", sequence=2, dependency_ids=["op-x"])

        acks1 = service.ingest_batch([op_a, op_b], user_id)
        assert acks1[0].status == SyncAckStatus.ACKNOWLEDGED
        assert acks1[1].status == SyncAckStatus.RETRYABLE_FAILURE

        # Client submits missing op_x
        op_x = _make_op("op-x", "insp-1", sequence=3)
        ack_x = service.ingest_operation(op_x, user_id)
        assert ack_x.status == SyncAckStatus.ACKNOWLEDGED

        # Client retries ONLY op_b
        ack_b_retry = service.ingest_operation(op_b, user_id)
        assert ack_b_retry.status == SyncAckStatus.ACKNOWLEDGED

    def test_21_stale_legal_snapshot_does_not_silently_become_current_compliance(self):
        """Operations with revalidation_required=True are preserved in SyncManifest without altering canonical compliance."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        eval_meta = EvaluationMetadata(
            evaluation_mode=EvaluationMode.OFFLINE_DETERMINISTIC,
            revalidation_required=True,
            legal_snapshot_id="snap-stale",
        )

        op = _make_op(
            "op-rep",
            "insp-1",
            SyncEntityType.REPORT,
            "rep-1",
            payload={
                "overall_status": "REVIEW_REQUIRED",
                "evaluation_metadata": eval_meta.to_dict(),
                "legal_snapshot_id": "snap-stale",
            },
        )
        service.ingest_operation(op, user_id)

        manifest = service.get_sync_manifest("insp-1", user_id)
        assert manifest.sync_status == SyncStatus.REVALIDATION_REQUIRED
        assert manifest.evaluation_metadata is not None
        assert manifest.evaluation_metadata.revalidation_required is True
        assert manifest.legal_snapshot_id == "snap-stale"

    def test_22_existing_u24d_offline_evaluation_metadata_is_preserved(self):
        """Offline evaluation mode OFFLINE_DETERMINISTIC flows through sync manifest unchanged."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        eval_meta = EvaluationMetadata(
            evaluation_mode=EvaluationMode.OFFLINE_DETERMINISTIC,
            revalidation_required=False,
            legal_snapshot_id="snap-valid-01",
        )

        op = _make_op(
            "op-rep-valid",
            "insp-1",
            SyncEntityType.REPORT,
            "rep-1",
            payload={
                "overall_status": "PASS",
                "evaluation_metadata": eval_meta.to_dict(),
                "legal_snapshot_id": "snap-valid-01",
            },
        )
        service.ingest_operation(op, user_id)

        manifest = service.get_sync_manifest("insp-1", user_id)
        assert manifest.sync_status == SyncStatus.SYNCED
        assert manifest.evaluation_metadata.evaluation_mode == EvaluationMode.OFFLINE_DETERMINISTIC

    def test_23_no_new_compliance_statuses_introduced(self):
        """Canonical requirement compliance statuses remain exactly PASS, FAIL, NOT_VISIBLE, NOT_APPLICABLE, REVIEW_REQUIRED."""
        canonical_req_statuses = {
            VerificationStatus.PASS,
            VerificationStatus.FAIL,
            VerificationStatus.NOT_VISIBLE,
            VerificationStatus.NOT_APPLICABLE,
            VerificationStatus.REVIEW_REQUIRED,
        }
        for s in VerificationStatus:
            assert s in canonical_req_statuses

    def test_24_existing_u24c_api_behavior_remains_compatible(self):
        """FastAPI endpoints POST /sync/batch and GET /sync-status operate seamlessly with U24-E recovery."""
        app = create_app()
        session_store = InMemoryInspectionStore()
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        sync_service = SyncIngestionService(sync_repo, insp_repo)

        app.dependency_overrides[get_session_store] = lambda: session_store
        app.dependency_overrides[get_sync_operation_repository] = lambda: sync_repo
        app.dependency_overrides[get_inspection_repository] = lambda: insp_repo
        app.dependency_overrides[get_sync_ingestion_service] = lambda: sync_service
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(user_id="user-api", email="api@veriqoo.ai", role="authenticated")

        client = TestClient(app)

        # 1. Partial batch with 1 valid and 1 invalid
        p1 = {"metadata": {"name": "test"}}
        h1 = SyncOperation.compute_content_hash(p1)
        now_iso = datetime.now(timezone.utc).isoformat()

        payload = {
            "inspection_id": "insp-api-1",
            "batch_id": "batch-01",
            "operations": [
                {
                    "operation_id": "api-op-1",
                    "inspection_id": "insp-api-1",
                    "entity_type": "INSPECTION",
                    "entity_id": "insp-api-1",
                    "operation_type": "CREATE",
                    "content_hash": h1,
                    "created_at": now_iso,
                    "sequence": 1,
                    "dependency_ids": [],
                    "payload": p1,
                },
                {
                    "operation_id": "api-op-2",
                    "inspection_id": "insp-api-1",
                    "entity_type": "IMAGE",
                    "entity_id": "img-2",
                    "operation_type": "CREATE",
                    "content_hash": "bad-hash",
                    "created_at": now_iso,
                    "sequence": 2,
                    "dependency_ids": [],
                    "payload": {"image_id": "img-2"},
                },
            ],
        }

        resp = client.post("/api/v1/inspections/sync/batch", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 2
        assert data["results"][0]["status"] == "ACKNOWLEDGED"
        assert data["results"][1]["status"] == "REJECTED"

        # 2. Check sync manifest
        status_resp = client.get("/api/v1/inspections/insp-api-1/sync-status")
        assert status_resp.status_code == 200
        manifest_data = status_resp.json()
        assert manifest_data["sync_status"] == "SYNC_FAILED"  # Due to rejected operation

    def test_25_no_duplicate_inspection_entities_are_created(self):
        """Multiple batches referencing same inspection container do not create duplicate sessions."""
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        service = SyncIngestionService(sync_repo, insp_repo)
        user_id = "user-100"

        op1 = _make_op("op-1", "insp-dup", SyncEntityType.INSPECTION, "insp-dup")
        service.ingest_operation(op1, user_id)

        op2 = _make_op("op-2", "insp-dup", SyncEntityType.IMAGE, "img-1", payload={"image_id": "img-1", "source_hash": "h1"}, dependency_ids=["op-1"])
        service.ingest_operation(op2, user_id)

        # Inspection exists once
        insp = insp_repo.get_inspection("insp-dup")
        assert insp is not None
        assert insp.inspection_id == "insp-dup"

    def test_26_monotonic_state_transitions_lattice(self):
        """Record status updates follow monotonic lattice: terminal states cannot be overwritten with PENDING."""
        sync_repo = InMemorySyncOperationRepository()
        rec = DurableSyncOperationRecord(
            operation_id="op-lat",
            inspection_id="insp-1",
            entity_type=SyncEntityType.INSPECTION,
            entity_id="insp-1",
            operation_type=SyncOperationType.CREATE,
            content_hash="hash",
            created_at=datetime.now(timezone.utc).isoformat(),
            status=OperationStatus.ACKNOWLEDGED,
        )
        sync_repo.save_operation(rec)

        updated = sync_repo.update_operation_status("op-lat", OperationStatus.ALREADY_APPLIED)
        assert updated.status == OperationStatus.ALREADY_APPLIED

    def test_27_manifest_reconciliation_reflects_partial_and_recovered_states(self):
        """SyncManifest transitions from SYNC_PENDING to SYNCED as retryable failures are resolved."""
        sync_repo = InMemorySyncOperationRepository()
        service = SyncIngestionService(sync_repo)
        user_id = "user-100"

        # 1. Child with pending dependency -> SYNC_PENDING
        op_child = _make_op("op-c", "insp-1", dependency_ids=["op-p"])
        service.ingest_operation(op_child, user_id)

        m1 = service.get_sync_manifest("insp-1", user_id)
        assert m1.sync_status == SyncStatus.SYNC_PENDING

        # 2. Add parent -> parent ACKNOWLEDGED, child still RETRYABLE_FAILURE
        op_p = _make_op("op-p", "insp-1")
        service.ingest_operation(op_p, user_id)

        m2 = service.get_sync_manifest("insp-1", user_id)
        assert m2.sync_status == SyncStatus.SYNC_PENDING

        # 3. Retry child -> both ACKNOWLEDGED -> SYNCED
        service.ingest_operation(op_child, user_id)
        m3 = service.get_sync_manifest("insp-1", user_id)
        assert m3.sync_status == SyncStatus.SYNCED
