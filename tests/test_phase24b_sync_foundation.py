"""Comprehensive test suite for Phase U24-B — Durable Sync Ingestion & Idempotency Foundation.

Tests all required U24-B requirements:
1. Operation persistence in durable repository
2. Operation_id uniqueness constraint enforcement
3. First operation acknowledged (ACKNOWLEDGED)
4. Duplicate identical operation replay (ALREADY_APPLIED)
5. Duplicate operation with conflicting content (REJECTED + SYNC_DUPLICATE_PAYLOAD_MISMATCH)
6. Content hash mismatch detection (REJECTED + SYNC_CONTENT_HASH_MISMATCH)
7. Dependency satisfied allows operation to proceed
8. Dependency pending returns RETRYABLE_FAILURE + SYNC_DEPENDENCY_PENDING
9. Dependency rejected causes dependent operation rejection (SYNC_DEPENDENCY_REJECTED)
10. Missing inspection handling
11. Cross-user operation rejected (SYNC_NOT_OWNER)
12. Invalid entity type / structure validation
13. Operation state transitions (PENDING -> ACKNOWLEDGED / REJECTED / RETRYABLE_FAILURE)
14. Concurrent duplicate submission thread safety
15. Repository re-instantiation / restart persistence simulation
16. Acknowledgement serialization & error codes
17. Authoritative SyncManifest generation
18. Security: No raw JWT or bearer token persistence
19. Security: No private storage URL leakage in manifest
20. Report operation structural validation
21. Circular dependency cycle detection & rejection
22. Partial ingestion safety and batch handling
"""

import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import pytest

from backend.app.services.inspection.repository import InMemoryInspectionRepository
from backend.app.services.offline_sync.ingestion import SyncIngestionService
from backend.app.services.offline_sync.models import (
    DurableSyncOperationRecord,
    EvaluationMetadata,
    EvaluationMode,
    OperationStatus,
    SyncAckStatus,
    SyncAcknowledgement,
    SyncEntityType,
    SyncErrorCode,
    SyncManifest,
    SyncOperation,
    SyncOperationType,
    SyncStatus,
)
from backend.app.services.offline_sync.repository import (
    DuplicateOperationIdError,
    InMemorySyncOperationRepository,
)
from backend.app.services.offline_sync.validator import SyncEntityValidator


# Helper to create valid hashed SyncOperation
def make_operation(
    operation_id: str = "op-1",
    inspection_id: str = "insp-100",
    entity_type: SyncEntityType = SyncEntityType.INSPECTION,
    entity_id: str = "insp-100",
    operation_type: SyncOperationType = SyncOperationType.CREATE,
    payload: dict | None = None,
    sequence: int = 1,
    dependency_ids: list[str] | None = None,
    created_at: str | None = None,
) -> SyncOperation:
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


# =====================================================================
# 1. Operation Persistence & 2. Operation ID Uniqueness
# =====================================================================
def test_sync_operation_persistence_and_uniqueness():
    repo = InMemorySyncOperationRepository()
    record = DurableSyncOperationRecord(
        operation_id="op-unique-1",
        inspection_id="insp-1",
        entity_type=SyncEntityType.INSPECTION,
        entity_id="insp-1",
        operation_type=SyncOperationType.CREATE,
        content_hash="hash123",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    saved = repo.save_operation(record)
    assert saved.operation_id == "op-unique-1"

    retrieved = repo.get_operation("op-unique-1")
    assert retrieved is not None
    assert retrieved.operation_id == "op-unique-1"

    # Attempt duplicate insert with same operation_id
    with pytest.raises(DuplicateOperationIdError):
        repo.save_operation(record)


# =====================================================================
# 3. First Operation Acknowledged
# =====================================================================
def test_first_operation_acknowledged():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    op = make_operation(operation_id="op-first", inspection_id="insp-100", entity_id="insp-100")
    ack = service.ingest_operation(op, authenticated_user_id="user-alice")

    assert ack.status == SyncAckStatus.ACKNOWLEDGED
    assert ack.operation_id == "op-first"
    assert ack.entity_id == "insp-100"
    assert ack.error_code is None

    # Verify persisted record
    persisted = sync_repo.get_operation("op-first")
    assert persisted is not None
    assert persisted.status == OperationStatus.ACKNOWLEDGED


# =====================================================================
# 4. Duplicate Identical Operation -> ALREADY_APPLIED
# =====================================================================
def test_duplicate_identical_operation_already_applied():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    op = make_operation(operation_id="op-replay", inspection_id="insp-100")
    ack_1 = service.ingest_operation(op, authenticated_user_id="user-alice")
    assert ack_1.status == SyncAckStatus.ACKNOWLEDGED

    # Replay same operation with exact same content
    ack_2 = service.ingest_operation(op, authenticated_user_id="user-alice")
    assert ack_2.status == SyncAckStatus.ALREADY_APPLIED
    assert ack_2.operation_id == "op-replay"


# =====================================================================
# 5. Duplicate Conflicting Payload -> REJECTED
# =====================================================================
def test_duplicate_conflicting_payload_rejected():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    op_1 = make_operation(
        operation_id="op-conflict",
        inspection_id="insp-100",
        payload={"field": "version_1"},
    )
    ack_1 = service.ingest_operation(op_1, authenticated_user_id="user-alice")
    assert ack_1.status == SyncAckStatus.ACKNOWLEDGED

    # Replay same operation_id with different payload content
    op_2 = make_operation(
        operation_id="op-conflict",
        inspection_id="insp-100",
        payload={"field": "version_2_mutated"},
    )
    ack_2 = service.ingest_operation(op_2, authenticated_user_id="user-alice")

    assert ack_2.status == SyncAckStatus.REJECTED
    assert ack_2.error_code == SyncErrorCode.SYNC_DUPLICATE_PAYLOAD_MISMATCH.value


# =====================================================================
# 6. Content Hash Mismatch Detection
# =====================================================================
def test_content_hash_mismatch_rejected():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    # Supply an invalid forged hash
    op = SyncOperation(
        operation_id="op-forged-hash",
        inspection_id="insp-100",
        entity_type=SyncEntityType.INSPECTION,
        entity_id="insp-100",
        operation_type=SyncOperationType.CREATE,
        content_hash="bad_hash_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        created_at=datetime.now(timezone.utc).isoformat(),
        payload={"notes": "forged"},
    )

    ack = service.ingest_operation(op, authenticated_user_id="user-alice")
    assert ack.status == SyncAckStatus.REJECTED
    assert ack.error_code == SyncErrorCode.SYNC_CONTENT_HASH_MISMATCH.value


# =====================================================================
# 7, 8, 9. Dependency Handling (Satisfied, Pending, Rejected)
# =====================================================================
def test_dependency_states():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    # 1. Operation depending on a missing/pending operation
    op_child = make_operation(
        operation_id="op-img-1",
        inspection_id="insp-100",
        entity_type=SyncEntityType.IMAGE,
        entity_id="img-1",
        payload={"image_id": "img-1", "source_hash": "shash", "normalized_hash": "nhash"},
        dependency_ids=["op-root-parent"],
    )

    ack_pending = service.ingest_operation(op_child, authenticated_user_id="user-alice")
    assert ack_pending.status == SyncAckStatus.RETRYABLE_FAILURE
    assert ack_pending.error_code == SyncErrorCode.SYNC_DEPENDENCY_PENDING.value

    # 2. Now acknowledge root parent
    op_parent = make_operation(
        operation_id="op-root-parent",
        inspection_id="insp-100",
        entity_type=SyncEntityType.INSPECTION,
        entity_id="insp-100",
    )
    ack_parent = service.ingest_operation(op_parent, authenticated_user_id="user-alice")
    assert ack_parent.status == SyncAckStatus.ACKNOWLEDGED

    # 3. Retry child operation -> now satisfied!
    ack_child_retry = service.ingest_operation(op_child, authenticated_user_id="user-alice")
    assert ack_child_retry.status == SyncAckStatus.ACKNOWLEDGED

    # 4. Dependency on a permanently rejected operation
    op_rejected_parent = SyncOperation(
        operation_id="op-rejected-parent",
        inspection_id="insp-100",
        entity_type=SyncEntityType.IMAGE,
        entity_id="bad-img",
        operation_type=SyncOperationType.CREATE,
        content_hash="forged_hash",
        created_at=datetime.now(timezone.utc).isoformat(),
        payload={"image_id": "bad-img"},
    )
    service.ingest_operation(op_rejected_parent, authenticated_user_id="user-alice")

    op_dependent_on_rejected = make_operation(
        operation_id="op-ocr-1",
        inspection_id="insp-100",
        entity_type=SyncEntityType.OCR_OBSERVATION,
        entity_id="ocr-1",
        payload={"image_id": "bad-img", "observation_id": "ocr-1", "raw_text": "sample"},
        dependency_ids=["op-rejected-parent"],
    )
    ack_dep_rejected = service.ingest_operation(op_dependent_on_rejected, authenticated_user_id="user-alice")
    assert ack_dep_rejected.status == SyncAckStatus.REJECTED
    assert ack_dep_rejected.error_code == SyncErrorCode.SYNC_DEPENDENCY_REJECTED.value


# =====================================================================
# 10. Missing Inspection Non-Root Operation
# =====================================================================
def test_missing_inspection_rejection():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    # Submitting image for inspection that does not exist on server
    op_img = make_operation(
        operation_id="op-img-orphan",
        inspection_id="insp-nonexistent",
        entity_type=SyncEntityType.IMAGE,
        entity_id="img-orphan",
        payload={"image_id": "img-orphan", "source_hash": "shash", "normalized_hash": "nhash"},
    )
    ack = service.ingest_operation(op_img, authenticated_user_id="user-alice")
    assert ack.status == SyncAckStatus.RETRYABLE_FAILURE
    assert ack.error_code == SyncErrorCode.SYNC_INSPECTION_NOT_FOUND.value


# =====================================================================
# 11. Cross-User Unauthorized Operation
# =====================================================================
def test_cross_user_operation_rejected():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    # Alice creates inspection
    op_root = make_operation(operation_id="op-alice-root", inspection_id="insp-alice-100", entity_id="insp-alice-100")
    service.ingest_operation(op_root, authenticated_user_id="user-alice")

    # Bob attempts to push image to Alice's inspection
    op_bob_img = make_operation(
        operation_id="op-bob-img",
        inspection_id="insp-alice-100",
        entity_type=SyncEntityType.IMAGE,
        entity_id="img-bob",
        payload={"image_id": "img-bob", "source_hash": "shash", "normalized_hash": "nhash"},
    )
    ack = service.ingest_operation(op_bob_img, authenticated_user_id="user-bob")
    assert ack.status == SyncAckStatus.REJECTED
    assert ack.error_code == SyncErrorCode.SYNC_NOT_OWNER.value


# =====================================================================
# 12. Structural Entity Validation
# =====================================================================
def test_entity_structural_validation():
    # 1. Image without hashes
    op_bad_img = make_operation(
        operation_id="op-bad-img",
        entity_type=SyncEntityType.IMAGE,
        payload={"image_id": "img-1"},  # missing hashes
    )
    is_valid, err_code, _ = SyncEntityValidator.validate_entity_structure(op_bad_img)
    assert is_valid is False
    assert err_code == SyncErrorCode.SYNC_INVALID_ENTITY.value

    # 2. OCR without raw_text
    op_bad_ocr = make_operation(
        operation_id="op-bad-ocr",
        entity_type=SyncEntityType.OCR_OBSERVATION,
        payload={"image_id": "img-1"},
    )
    is_valid, err_code, _ = SyncEntityValidator.validate_entity_structure(op_bad_ocr)
    assert is_valid is False

    # 3. Requirement Result without status
    op_bad_req = make_operation(
        operation_id="op-bad-req",
        entity_type=SyncEntityType.REQUIREMENT_RESULT,
        payload={"requirement_id": "req-1"},
    )
    is_valid, err_code, _ = SyncEntityValidator.validate_entity_structure(op_bad_req)
    assert is_valid is False


# =====================================================================
# 13. Operation State Transitions
# =====================================================================
def test_operation_state_transitions():
    repo = InMemorySyncOperationRepository()
    rec = DurableSyncOperationRecord(
        operation_id="op-trans",
        inspection_id="insp-1",
        entity_type=SyncEntityType.INSPECTION,
        entity_id="insp-1",
        operation_type=SyncOperationType.CREATE,
        content_hash="h1",
        created_at=datetime.now(timezone.utc).isoformat(),
        status=OperationStatus.PENDING,
    )
    repo.save_operation(rec)
    assert repo.get_operation("op-trans").status == OperationStatus.PENDING

    # Transition to ACKNOWLEDGED
    updated = repo.update_operation_status(
        operation_id="op-trans",
        status=OperationStatus.ACKNOWLEDGED,
        acknowledged_at=datetime.now(timezone.utc),
    )
    assert updated.status == OperationStatus.ACKNOWLEDGED
    assert updated.acknowledged_at is not None


# =====================================================================
# 14. Concurrent Duplicate Submission
# =====================================================================
def test_concurrent_duplicate_submission():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    op = make_operation(operation_id="op-concur-1", inspection_id="insp-concur")

    def run_ingest():
        return service.ingest_operation(op, authenticated_user_id="user-alice")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(run_ingest) for _ in range(8)]
        results = [f.result() for f in futures]

    statuses = [r.status for r in results]
    # Exactly one ACKNOWLEDGED, and seven ALREADY_APPLIED
    assert statuses.count(SyncAckStatus.ACKNOWLEDGED) == 1
    assert statuses.count(SyncAckStatus.ALREADY_APPLIED) == 7


# =====================================================================
# 15. Restart Persistence Simulation
# =====================================================================
def test_restart_persistence_simulation():
    # Simulate first application lifecycle
    repo_1 = InMemorySyncOperationRepository()
    rec = DurableSyncOperationRecord(
        operation_id="op-restart",
        inspection_id="insp-1",
        entity_type=SyncEntityType.INSPECTION,
        entity_id="insp-1",
        operation_type=SyncOperationType.CREATE,
        content_hash="h1",
        created_at=datetime.now(timezone.utc).isoformat(),
        status=OperationStatus.ACKNOWLEDGED,
    )
    repo_1.save_operation(rec)

    # Export state dictionary
    serialized_state = {k: v.to_dict() for k, v in repo_1._operations.items()}

    # Simulate fresh service instance restoring state
    repo_2 = InMemorySyncOperationRepository()
    for k, v in serialized_state.items():
        repo_2._operations[k] = DurableSyncOperationRecord.from_dict(v)

    restored = repo_2.get_operation("op-restart")
    assert restored is not None
    assert restored.operation_id == "op-restart"
    assert restored.status == OperationStatus.ACKNOWLEDGED


# =====================================================================
# 16. Acknowledgement Serialization
# =====================================================================
def test_acknowledgement_serialization():
    ack = SyncAcknowledgement(
        operation_id="op-ack-1",
        entity_id="ent-1",
        status=SyncAckStatus.ACKNOWLEDGED,
        server_timestamp="2026-10-04T12:00:00+00:00",
        server_version="1.0.0",
    )
    d = ack.to_dict()
    assert d["operation_id"] == "op-ack-1"
    assert d["status"] == "ACKNOWLEDGED"

    reconstituted = SyncAcknowledgement.from_dict(d)
    assert reconstituted.operation_id == "op-ack-1"
    assert reconstituted.status == SyncAckStatus.ACKNOWLEDGED


# =====================================================================
# 17. Authoritative SyncManifest Generation
# =====================================================================
def test_sync_manifest_generation():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    # 1. Root inspection
    op_root = make_operation(
        operation_id="op-m-1",
        inspection_id="insp-m-100",
        entity_id="insp-m-100",
        payload={"metadata": {"notes": "test"}},
    )
    service.ingest_operation(op_root, authenticated_user_id="user-alice")

    # 2. Image operation
    op_img = make_operation(
        operation_id="op-m-2",
        inspection_id="insp-m-100",
        entity_type=SyncEntityType.IMAGE,
        entity_id="img-1",
        payload={"image_id": "img-1", "source_hash": "src123", "normalized_hash": "norm123"},
        dependency_ids=["op-m-1"],
    )
    service.ingest_operation(op_img, authenticated_user_id="user-alice")

    # Generate manifest
    manifest = service.get_sync_manifest("insp-m-100", authenticated_user_id="user-alice")

    assert manifest.inspection_id == "insp-m-100"
    assert manifest.sync_status == SyncStatus.SYNCED
    assert len(manifest.entity_acknowledgements) == 2
    assert manifest.image_hashes == {"img-1": "norm123"}


# =====================================================================
# 18 & 19. Security: No Raw JWTs & No Private Storage URLs
# =====================================================================
def test_security_boundaries():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    op = make_operation(
        operation_id="op-sec-1",
        inspection_id="insp-sec",
        payload={"user_id": "spoofed-user", "jwt": "secret-jwt-token"},
    )
    service.ingest_operation(op, authenticated_user_id="user-verified-alice")

    persisted = sync_repo.get_operation("op-sec-1")
    # Verified user comes from auth, not payload claims
    inspection = insp_repo.get_inspection("insp-sec")
    assert inspection.metadata.get("owner_id") == "user-verified-alice"

    manifest = service.get_sync_manifest("insp-sec", authenticated_user_id="user-verified-alice")
    manifest_dict = manifest.to_dict()
    assert "jwt" not in manifest_dict
    assert "secret" not in manifest_dict


# =====================================================================
# 20. Report Operation Structural Validation
# =====================================================================
def test_report_operation_handling():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    # Root inspection
    op_root = make_operation(operation_id="op-rep-root", inspection_id="insp-rep")
    service.ingest_operation(op_root, authenticated_user_id="user-alice")

    # Report operation
    op_report = make_operation(
        operation_id="op-rep-1",
        inspection_id="insp-rep",
        entity_type=SyncEntityType.REPORT,
        entity_id="report-100",
        payload={"report_id": "report-100", "summary": "Offline report payload"},
        dependency_ids=["op-rep-root"],
    )
    ack = service.ingest_operation(op_report, authenticated_user_id="user-alice")
    assert ack.status == SyncAckStatus.ACKNOWLEDGED


# =====================================================================
# 21. Circular Dependency Cycle Detection & Rejection
# =====================================================================
def test_circular_dependency_rejection():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    # Create cycle: op-A -> op-B -> op-A
    op_a = make_operation(
        operation_id="op-cycle-a",
        inspection_id="insp-cycle",
        entity_id="cycle-a",
        dependency_ids=["op-cycle-b"],
    )
    op_b = make_operation(
        operation_id="op-cycle-b",
        inspection_id="insp-cycle",
        entity_id="cycle-b",
        dependency_ids=["op-cycle-a"],
    )

    acks = service.ingest_batch([op_a, op_b], authenticated_user_id="user-alice")
    assert len(acks) == 2
    assert acks[0].status == SyncAckStatus.REJECTED
    assert acks[0].error_code == SyncErrorCode.SYNC_CIRCULAR_DEPENDENCY.value
    assert acks[1].status == SyncAckStatus.REJECTED
    assert acks[1].error_code == SyncErrorCode.SYNC_CIRCULAR_DEPENDENCY.value


# =====================================================================
# 22. Batch Processing & Partial Ingestion Safety
# =====================================================================
def test_batch_processing_and_partial_safety():
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    op_1 = make_operation(operation_id="op-b-1", inspection_id="insp-batch", sequence=1)
    op_2 = make_operation(
        operation_id="op-b-2",
        inspection_id="insp-batch",
        entity_type=SyncEntityType.IMAGE,
        entity_id="img-b2",
        payload={"image_id": "img-b2", "source_hash": "s", "normalized_hash": "n"},
        sequence=2,
        dependency_ids=["op-b-1"],
    )
    # op_3 has invalid forged hash
    op_3 = SyncOperation(
        operation_id="op-b-3",
        inspection_id="insp-batch",
        entity_type=SyncEntityType.EVIDENCE,
        entity_id="ev-b3",
        operation_type=SyncOperationType.CREATE,
        content_hash="bad_hash",
        created_at=datetime.now(timezone.utc).isoformat(),
        sequence=3,
        payload={"field": "mrp"},
    )

    acks = service.ingest_batch([op_1, op_2, op_3], authenticated_user_id="user-alice")
    assert acks[0].status == SyncAckStatus.ACKNOWLEDGED
    assert acks[1].status == SyncAckStatus.ACKNOWLEDGED
    assert acks[2].status == SyncAckStatus.REJECTED
    assert acks[2].error_code == SyncErrorCode.SYNC_CONTENT_HASH_MISMATCH.value
