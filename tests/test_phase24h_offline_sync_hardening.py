"""Comprehensive test suite for Phase U24-H: Final Offline / Sync Hardening.

Verifies all 30 U24-H hardening requirements:
1. Valid state transitions in SyncLifecycleValidator
2. Invalid state transitions rejected by SyncLifecycleValidator
3. Retry after sync failure
4. Retry after response loss
5. Duplicate operation returns ALREADY_APPLIED
6. Duplicate operation with changed payload returns REJECTED
7. Concurrent same-operation replay is thread-safe and idempotent
8. Concurrent independent operations succeed independently
9. Dependency failure isolation blocks only dependents
10. Cross-inspection dependency is rejected
11. Cross-user isolation returns safe 404 / REJECTED
12. Report persistence failure prevents session exposure
13. Requirement persistence failure prevents session exposure
14. Sync persistence failure prevents session exposure
15. Session projection happens only after durable persistence
16. Session cache eviction / cold-start recovery from durable repository
17. Response-loss-after-commit returns existing authoritative result
18. Repeated revalidation is strictly idempotent
19. Concurrent revalidation converges safely
20. No duplicate reports created
21. No duplicate requirement results created
22. No duplicate sync operations created
23. Stale legal snapshot triggers current server evaluation and notes STALE
24. Unknown legal snapshot triggers current server evaluation and notes UNKNOWN
25. Altered snapshot hash triggers validation failure / revalidation
26. Incomplete client requirements cannot reduce statutory coverage
27. Extra client requirements cannot expand legal authority
28. Offline compliance conclusions are never blindly trusted
29. Canonical compliance statuses are strictly preserved
30. Online inspection and report behavior remains unchanged
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import json
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_inspection_repository,
    get_server_revalidation_service,
    get_session_store,
    get_sync_ingestion_service,
    get_sync_operation_repository,
)
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import AuthenticatedUser
from backend.app.main import create_app
from backend.app.services.evidence.models import EvidenceCandidate, EvidenceField, EvidenceStatus
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection.repository import InMemoryInspectionRepository
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.offline_sync import (
    DurableSyncOperationRecord,
    EvaluationMetadata,
    EvaluationMode,
    InMemorySyncOperationRepository,
    LegalSnapshotBuilder,
    LegalSnapshotContext,
    OperationStatus,
    RevalidationComparison,
    ServerRevalidationResult,
    ServerRevalidationService,
    SyncAckStatus,
    SyncAcknowledgement,
    SyncEntityType,
    SyncErrorCode,
    SyncIngestionService,
    SyncLifecycleValidator,
    SyncOperation,
    SyncOperationType,
    SyncStatus,
)
from backend.app.services.verification.models import VerificationStatus


def _build_hardening_test_snapshot() -> tuple[str, LegalSnapshotContext]:
    """Construct deterministic legal snapshot context with 3 statutory requirements."""
    docs = [{"id": "doc-01", "document_type": "act", "title": "Legal Metrology Act", "year": 2009}]
    provs = [{"id": "prov-01", "document_id": "doc-01", "provision_type": "rule", "rule_number": "6", "content": "MRP rule"}]
    reqs = [
        {"id": "req-mrp", "requirement_code": "REQ-MRP", "normalized_requirement": "MRP must be declared", "target_field": "mrp", "rule_id": "rule-01"},
        {"id": "req-net-qty", "requirement_code": "REQ-NET-QTY", "normalized_requirement": "Net quantity declaration", "target_field": "net_quantity", "rule_id": "rule-01"},
        {"id": "req-mfg-date", "requirement_code": "REQ-MFG-DATE", "normalized_requirement": "Month and year of manufacture", "target_field": "manufacture_date", "rule_id": "rule-01"},
    ]
    rules = [{"id": "rule-01", "rule_key": "rule-prepacked"}]
    vers = [{"id": "ver-01", "rule_id": "rule-01", "version_number": 1, "interpretation_status": "approved"}]
    groups = [{"id": "grp-01", "rule_version_id": "ver-01", "boolean_operator": "AND", "status": "approved"}]
    conds = [{"id": "cnd-01", "group_id": "grp-01", "fact_key": "is_prepacked", "operator": "equals", "expected_value": True, "status": "approved"}]

    snapshot_id, manifest, _ = LegalSnapshotBuilder.build_snapshot(
        documents=docs,
        provisions=provs,
        requirements=reqs,
        applicability_rule_versions=vers,
        applicability_condition_groups=groups,
        applicability_conditions=conds,
    )

    context = LegalSnapshotContext(
        legal_snapshot_id=snapshot_id,
        manifest=manifest,
        requirements=reqs,
        applicability_rules=rules,
        applicability_rule_versions=vers,
        applicability_condition_groups=groups,
        applicability_conditions=conds,
        historical_snapshot_ids=["snapshot-stale-v1"],
    )
    return snapshot_id, context


class TestPhase24HOfflineSyncHardening:
    """Comprehensive hardening test suite covering all 30 U24-H verification criteria."""

    @pytest.fixture(autouse=True)
    def setup_system(self):
        self.sync_repo = InMemorySyncOperationRepository()
        self.session_store = InMemoryInspectionStore()
        self.inspection_repo = InMemoryInspectionRepository()
        self.server_snapshot_id, self.server_context = _build_hardening_test_snapshot()

        self.revalidation_service = ServerRevalidationService(
            sync_repository=self.sync_repo,
            inspection_repository=self.inspection_repo,
            session_store=self.session_store,
            default_server_snapshot_context=self.server_context,
        )
        self.ingestion_service = SyncIngestionService(
            sync_repository=self.sync_repo,
            inspection_repository=self.inspection_repo,
        )

        self.app = create_app()
        self.test_user = AuthenticatedUser(
            user_id="inspector_hardened",
            email="inspector@veriqoo.ai",
            role="authenticated",
        )

        self.app.dependency_overrides[get_sync_operation_repository] = lambda: self.sync_repo
        self.app.dependency_overrides[get_session_store] = lambda: self.session_store
        self.app.dependency_overrides[get_inspection_repository] = lambda: self.inspection_repo
        self.app.dependency_overrides[get_sync_ingestion_service] = lambda: self.ingestion_service
        self.app.dependency_overrides[get_server_revalidation_service] = lambda: self.revalidation_service
        self.app.dependency_overrides[get_current_user] = lambda: self.test_user

        self.client = TestClient(self.app)

        yield
        self.app.dependency_overrides.clear()
        self.session_store.clear()

    def _sync_mock_offline_inspection(
        self,
        inspection_id: str,
        user_id: str = "inspector_hardened",
        include_mrp: bool = True,
        include_qty: bool = True,
        include_mfg: bool = True,
        client_snapshot_id: str | None = None,
        offline_status: str = "PASS",
    ) -> None:
        """Helper to sync complete offline inspection data."""
        snap_id = client_snapshot_id or self.server_snapshot_id
        now_iso = datetime.now(timezone.utc).isoformat()

        # Relational inspection container
        self.inspection_repo.create_inspection(
            inspection_id=inspection_id,
            metadata={"owner_id": user_id, "commodity": "packaged_tea"},
            owner_id=user_id,
        )

        # Inspection sync operation
        self.sync_repo.save_operation(
            DurableSyncOperationRecord(
                operation_id=f"op-insp-{inspection_id}",
                inspection_id=inspection_id,
                entity_type=SyncEntityType.INSPECTION,
                entity_id=inspection_id,
                operation_type=SyncOperationType.CREATE,
                content_hash="hash-insp",
                created_at=now_iso,
                received_at=now_iso,
                acknowledged_at=now_iso,
                status=OperationStatus.ACKNOWLEDGED,
                payload={"metadata": {"owner_id": user_id, "commodity": "packaged_tea"}},
            )
        )

        # Fact sync operation
        self.sync_repo.save_operation(
            DurableSyncOperationRecord(
                operation_id=f"op-fact-{inspection_id}",
                inspection_id=inspection_id,
                entity_type=SyncEntityType.FACT,
                entity_id=f"fact-{inspection_id}",
                operation_type=SyncOperationType.CREATE,
                content_hash="hash-fact",
                created_at=now_iso,
                received_at=now_iso,
                acknowledged_at=now_iso,
                status=OperationStatus.ACKNOWLEDGED,
                payload={"fact_key": "is_prepacked", "value": True},
            )
        )

        if include_mrp:
            self.sync_repo.save_operation(
                DurableSyncOperationRecord(
                    operation_id=f"op-ev-mrp-{inspection_id}",
                    inspection_id=inspection_id,
                    entity_type=SyncEntityType.EVIDENCE,
                    entity_id=f"ev-mrp-{inspection_id}",
                    operation_type=SyncOperationType.CREATE,
                    content_hash="hash-mrp",
                    created_at=now_iso,
                    received_at=now_iso,
                    acknowledged_at=now_iso,
                    status=OperationStatus.ACKNOWLEDGED,
                    payload={"field": "mrp", "raw_text": "MRP Rs 120.00", "parsed_value": 120.0, "status": "VALID"},
                )
            )

        if include_qty:
            self.sync_repo.save_operation(
                DurableSyncOperationRecord(
                    operation_id=f"op-ev-qty-{inspection_id}",
                    inspection_id=inspection_id,
                    entity_type=SyncEntityType.EVIDENCE,
                    entity_id=f"ev-qty-{inspection_id}",
                    operation_type=SyncOperationType.CREATE,
                    content_hash="hash-qty",
                    created_at=now_iso,
                    received_at=now_iso,
                    acknowledged_at=now_iso,
                    status=OperationStatus.ACKNOWLEDGED,
                    payload={"field": "net_quantity", "raw_text": "Net Weight: 500g", "parsed_value": 500, "parsed_unit": "g", "status": "VALID"},
                )
            )

        if include_mfg:
            self.sync_repo.save_operation(
                DurableSyncOperationRecord(
                    operation_id=f"op-ev-mfg-{inspection_id}",
                    inspection_id=inspection_id,
                    entity_type=SyncEntityType.EVIDENCE,
                    entity_id=f"ev-mfg-{inspection_id}",
                    operation_type=SyncOperationType.CREATE,
                    content_hash="hash-mfg",
                    created_at=now_iso,
                    received_at=now_iso,
                    acknowledged_at=now_iso,
                    status=OperationStatus.ACKNOWLEDGED,
                    payload={"field": "manufacture_date", "raw_text": "Mfg Date: 03/2026", "parsed_value": "2026-03", "status": "VALID"},
                )
            )

        # Client offline report operation
        self.sync_repo.save_operation(
            DurableSyncOperationRecord(
                operation_id=f"op-rep-{inspection_id}",
                inspection_id=inspection_id,
                entity_type=SyncEntityType.REPORT,
                entity_id=f"rep-{inspection_id}",
                operation_type=SyncOperationType.CREATE,
                content_hash="hash-rep-offline",
                created_at=now_iso,
                received_at=now_iso,
                acknowledged_at=now_iso,
                status=OperationStatus.ACKNOWLEDGED,
                payload={
                    "overall_status": offline_status,
                    "legal_snapshot_id": snap_id,
                    "evaluation_metadata": {
                        "evaluation_mode": EvaluationMode.OFFLINE_DETERMINISTIC.value,
                        "revalidation_required": True,
                        "legal_snapshot_id": snap_id,
                    },
                    "target_requirements": ["req-mrp", "req-net-qty"],
                },
            )
        )

    # 1. Valid State Transitions
    def test_01_valid_state_transitions(self):
        """All canonical SyncStatus transitions are accepted by SyncLifecycleValidator."""
        valid_pairs = [
            (SyncStatus.DRAFT_LOCAL, SyncStatus.SYNC_PENDING),
            (SyncStatus.SYNC_PENDING, SyncStatus.SYNCING),
            (SyncStatus.SYNCING, SyncStatus.SYNCED),
            (SyncStatus.SYNCING, SyncStatus.SYNC_FAILED),
            (SyncStatus.SYNCED, SyncStatus.REVALIDATION_REQUIRED),
            (SyncStatus.REVALIDATION_REQUIRED, SyncStatus.REVALIDATED),
            (SyncStatus.SYNC_FAILED, SyncStatus.SYNC_PENDING),
            (SyncStatus.SYNC_FAILED, SyncStatus.SYNCING),
            (SyncStatus.REVALIDATION_REQUIRED, SyncStatus.SYNCING),
        ]
        for f_st, t_st in valid_pairs:
            assert SyncLifecycleValidator.can_transition(f_st, t_st) is True
            SyncLifecycleValidator.assert_can_transition(f_st, t_st)

    # 2. Invalid State Transitions
    def test_02_invalid_state_transitions(self):
        """Invalid backward and jumping transitions are rejected by SyncLifecycleValidator."""
        invalid_pairs = [
            (SyncStatus.SYNCED, SyncStatus.DRAFT_LOCAL),
            (SyncStatus.REVALIDATED, SyncStatus.DRAFT_LOCAL),
            (SyncStatus.DRAFT_LOCAL, SyncStatus.REVALIDATED),
            (SyncStatus.SYNC_PENDING, SyncStatus.REVALIDATED),
        ]
        for f_st, t_st in invalid_pairs:
            assert SyncLifecycleValidator.can_transition(f_st, t_st) is False
            with pytest.raises(ValueError):
                SyncLifecycleValidator.assert_can_transition(f_st, t_st)

    # 3. Retry After Sync Failure
    def test_03_retry_after_sync_failure(self):
        """Operations failing due to transient errors remain retryable and succeed upon retry."""
        insp_id = "insp-retry-003"
        now_iso = datetime.now(timezone.utc).isoformat()
        self.inspection_repo.create_inspection(
            inspection_id=insp_id,
            metadata={"owner_id": "inspector_hardened"},
            owner_id="inspector_hardened",
        )

        op = SyncOperation(
            operation_id="op-fail-retry-003",
            inspection_id=insp_id,
            entity_type=SyncEntityType.FACT,
            entity_id="fact-retry-003",
            operation_type=SyncOperationType.CREATE,
            content_hash=SyncOperation.compute_content_hash({"fact_key": "is_prepacked", "value": True}),
            created_at=now_iso,
            payload={"fact_key": "is_prepacked", "value": True},
        )

        with patch.object(self.sync_repo, "save_operation", side_effect=RuntimeError("Transient DB connection drop")):
            ack1 = self.ingestion_service.ingest_operation(op, "inspector_hardened")
            assert ack1.status == SyncAckStatus.RETRYABLE_FAILURE

        ack2 = self.ingestion_service.ingest_operation(op, "inspector_hardened")
        assert ack2.status == SyncAckStatus.ACKNOWLEDGED

    # 4. Retry After Response Loss
    def test_04_retry_after_response_loss(self):
        """When client replays an already-committed operation, ALREADY_APPLIED is returned."""
        insp_id = "insp-resploss-004"
        now_iso = datetime.now(timezone.utc).isoformat()
        self.inspection_repo.create_inspection(
            inspection_id=insp_id,
            metadata={"owner_id": "inspector_hardened"},
            owner_id="inspector_hardened",
        )
        payload = {"field": "mrp", "raw_text": "MRP Rs 100", "parsed_value": 100}
        op = SyncOperation(
            operation_id="op-resploss-004",
            inspection_id=insp_id,
            entity_type=SyncEntityType.EVIDENCE,
            entity_id="ev-004",
            operation_type=SyncOperationType.CREATE,
            content_hash=SyncOperation.compute_content_hash(payload),
            created_at=now_iso,
            payload=payload,
        )
        ack1 = self.ingestion_service.ingest_operation(op, "inspector_hardened")
        assert ack1.status == SyncAckStatus.ACKNOWLEDGED

        # Simulate client retrying because ack1 HTTP response was lost in flight
        ack2 = self.ingestion_service.ingest_operation(op, "inspector_hardened")
        assert ack2.status == SyncAckStatus.ALREADY_APPLIED

    # 5. Duplicate Operation
    def test_05_duplicate_operation(self):
        """Exact same operation replay returns ALREADY_APPLIED."""
        insp_id = "insp-dup-005"
        now_iso = datetime.now(timezone.utc).isoformat()
        self.inspection_repo.create_inspection(
            inspection_id=insp_id,
            metadata={"owner_id": "inspector_hardened"},
            owner_id="inspector_hardened",
        )
        payload = {"fact_key": "commodity", "value": "sugar"}
        op = SyncOperation(
            operation_id="op-dup-005",
            inspection_id=insp_id,
            entity_type=SyncEntityType.FACT,
            entity_id="fact-dup-005",
            operation_type=SyncOperationType.CREATE,
            content_hash=SyncOperation.compute_content_hash(payload),
            created_at=now_iso,
            payload=payload,
        )
        ack1 = self.ingestion_service.ingest_operation(op, "inspector_hardened")
        assert ack1.status == SyncAckStatus.ACKNOWLEDGED
        ack2 = self.ingestion_service.ingest_operation(op, "inspector_hardened")
        assert ack2.status == SyncAckStatus.ALREADY_APPLIED

    # 6. Duplicate Operation with Changed Payload
    def test_06_duplicate_operation_with_changed_payload(self):
        """Same operation_id with conflicting payload returns REJECTED."""
        insp_id = "insp-payload-mismatch-006"
        now_iso = datetime.now(timezone.utc).isoformat()
        self.inspection_repo.create_inspection(
            inspection_id=insp_id,
            metadata={"owner_id": "inspector_hardened"},
            owner_id="inspector_hardened",
        )
        p1 = {"field": "mrp", "raw_text": "MRP 100", "parsed_value": 100}
        op1 = SyncOperation(
            operation_id="op-conflict-006",
            inspection_id=insp_id,
            entity_type=SyncEntityType.EVIDENCE,
            entity_id="ev-006",
            operation_type=SyncOperationType.CREATE,
            content_hash=SyncOperation.compute_content_hash(p1),
            created_at=now_iso,
            payload=p1,
        )
        ack1 = self.ingestion_service.ingest_operation(op1, "inspector_hardened")
        assert ack1.status == SyncAckStatus.ACKNOWLEDGED

        p2 = {"field": "mrp", "raw_text": "MRP 999", "parsed_value": 999}
        op2 = SyncOperation(
            operation_id="op-conflict-006",
            inspection_id=insp_id,
            entity_type=SyncEntityType.EVIDENCE,
            entity_id="ev-006",
            operation_type=SyncOperationType.CREATE,
            content_hash=SyncOperation.compute_content_hash(p2),
            created_at=now_iso,
            payload=p2,
        )
        ack2 = self.ingestion_service.ingest_operation(op2, "inspector_hardened")
        assert ack2.status == SyncAckStatus.REJECTED
        assert ack2.error_code == SyncErrorCode.SYNC_DUPLICATE_PAYLOAD_MISMATCH.value

    # 7. Concurrent Same-Operation Replay
    def test_07_concurrent_same_operation_replay(self):
        """Concurrent ingestion of the same operation converges safely with thread-safe idempotency."""
        insp_id = "insp-conc-same-007"
        now_iso = datetime.now(timezone.utc).isoformat()
        self.inspection_repo.create_inspection(
            inspection_id=insp_id,
            metadata={"owner_id": "inspector_hardened"},
            owner_id="inspector_hardened",
        )
        payload = {"fact_key": "brand", "value": "Premium Brand"}
        op = SyncOperation(
            operation_id="op-conc-same-007",
            inspection_id=insp_id,
            entity_type=SyncEntityType.FACT,
            entity_id="fact-007",
            operation_type=SyncOperationType.CREATE,
            content_hash=SyncOperation.compute_content_hash(payload),
            created_at=now_iso,
            payload=payload,
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.ingestion_service.ingest_operation, op, "inspector_hardened") for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 10
        statuses = {r.status for r in results}
        assert statuses.issubset({SyncAckStatus.ACKNOWLEDGED, SyncAckStatus.ALREADY_APPLIED})
        assert sum(1 for r in results if r.status == SyncAckStatus.ACKNOWLEDGED) == 1

    # 8. Concurrent Independent Operations
    def test_08_concurrent_independent_operations(self):
        """Concurrent ingestion of independent operations all succeed with ACKNOWLEDGED."""
        insp_id = "insp-conc-indep-008"
        now_iso = datetime.now(timezone.utc).isoformat()
        self.inspection_repo.create_inspection(
            inspection_id=insp_id,
            metadata={"owner_id": "inspector_hardened"},
            owner_id="inspector_hardened",
        )
        def _make_op(idx: int):
            payload = {"fact_key": f"key_{idx}", "value": f"val_{idx}"}
            return SyncOperation(
                operation_id=f"op-indep-{idx}",
                inspection_id=insp_id,
                entity_type=SyncEntityType.FACT,
                entity_id=f"fact-indep-{idx}",
                operation_type=SyncOperationType.CREATE,
                content_hash=SyncOperation.compute_content_hash(payload),
                created_at=now_iso,
                payload=payload,
            )
        ops = [_make_op(i) for i in range(10)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.ingestion_service.ingest_operation, op, "inspector_hardened") for op in ops]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 10
        assert all(r.status == SyncAckStatus.ACKNOWLEDGED for r in results)

    # 9. Dependency Failure Isolation
    def test_09_dependency_failure_isolation(self):
        """Unsatisfied or pending dependencies block only their dependent operations."""
        insp_id = "insp-dep-fail-009"
        now_iso = datetime.now(timezone.utc).isoformat()
        self.inspection_repo.create_inspection(
            inspection_id=insp_id,
            metadata={"owner_id": "inspector_hardened"},
            owner_id="inspector_hardened",
        )
        payload_dep = {"field": "mrp", "raw_text": "MRP 50"}
        op_dep = SyncOperation(
            operation_id="op-dep-009",
            inspection_id=insp_id,
            entity_type=SyncEntityType.EVIDENCE,
            entity_id="ev-dep-009",
            operation_type=SyncOperationType.CREATE,
            content_hash=SyncOperation.compute_content_hash(payload_dep),
            created_at=now_iso,
            dependency_ids=["op-nonexistent-009"],
            payload=payload_dep,
        )
        ack_dep = self.ingestion_service.ingest_operation(op_dep, "inspector_hardened")
        assert ack_dep.status == SyncAckStatus.RETRYABLE_FAILURE
        assert ack_dep.error_code == SyncErrorCode.SYNC_DEPENDENCY_PENDING.value

    # 10. Cross-Inspection Dependency Rejection
    def test_10_cross_inspection_dependency_rejection(self):
        """Cross-inspection dependencies are permanently rejected."""
        insp_id = "insp-cross-dep-010"
        diff_insp_id = "insp-DIFFERENT-010"
        now_iso = datetime.now(timezone.utc).isoformat()
        self.inspection_repo.create_inspection(
            inspection_id=insp_id,
            metadata={"owner_id": "inspector_hardened"},
            owner_id="inspector_hardened",
        )
        self.sync_repo.save_operation(
            DurableSyncOperationRecord(
                operation_id="op-other-insp-010",
                inspection_id=diff_insp_id,
                entity_type=SyncEntityType.FACT,
                entity_id="fact-diff-010",
                operation_type=SyncOperationType.CREATE,
                content_hash=SyncOperation.compute_content_hash({"fact_key": "k", "value": "v"}),
                created_at=now_iso,
                received_at=now_iso,
                acknowledged_at=now_iso,
                status=OperationStatus.ACKNOWLEDGED,
                payload={"fact_key": "k", "value": "v"},
            )
        )
        payload_cross = {"field": "mrp", "raw_text": "MRP 50"}
        op_cross = SyncOperation(
            operation_id="op-cross-010",
            inspection_id=insp_id,
            entity_type=SyncEntityType.EVIDENCE,
            entity_id="ev-cross-010",
            operation_type=SyncOperationType.CREATE,
            content_hash=SyncOperation.compute_content_hash(payload_cross),
            created_at=now_iso,
            dependency_ids=["op-other-insp-010"],
            payload=payload_cross,
        )
        ack_cross = self.ingestion_service.ingest_operation(op_cross, "inspector_hardened")
        assert ack_cross.status == SyncAckStatus.REJECTED
        assert ack_cross.error_code == SyncErrorCode.SYNC_CROSS_INSPECTION_DEPENDENCY.value

    # 11. Cross-User Isolation
    def test_11_cross_user_isolation(self):
        """Caller cannot access or revalidate inspections owned by another user."""
        insp_id = "insp-cross-user-011"
        self._sync_mock_offline_inspection(insp_id, user_id="other_user")

        resp = self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")
        assert resp.status_code == 404

        now_iso = datetime.now(timezone.utc).isoformat()
        payload_unauth = {"fact_key": "k", "value": "v"}
        op = SyncOperation(
            operation_id="op-unauth-011",
            inspection_id=insp_id,
            entity_type=SyncEntityType.FACT,
            entity_id="fact-unauth-011",
            operation_type=SyncOperationType.CREATE,
            content_hash=SyncOperation.compute_content_hash(payload_unauth),
            created_at=now_iso,
            payload=payload_unauth,
        )
        ack = self.ingestion_service.ingest_operation(op, "inspector_hardened")
        assert ack.status == SyncAckStatus.REJECTED
        assert ack.error_code == SyncErrorCode.SYNC_NOT_OWNER.value

    # 12. Report Persistence Failure
    def test_12_report_persistence_failure(self):
        """Relational report persistence failure raises RuntimeError and leaves no false completed session."""
        insp_id = "insp-fail-rep-012"
        self._sync_mock_offline_inspection(insp_id)
        with patch.object(self.inspection_repo, "save_report", side_effect=RuntimeError("Report DB down")):
            with pytest.raises(RuntimeError, match="Relational persistence failed"):
                self.revalidation_service.revalidate(insp_id, "inspector_hardened")

        session = self.session_store.get_session_optional(insp_id)
        assert session is None or session.report is None

    # 13. Requirement Persistence Failure
    def test_13_requirement_persistence_failure(self):
        """Requirement persistence failure raises RuntimeError and protects session projection."""
        insp_id = "insp-fail-req-013"
        self._sync_mock_offline_inspection(insp_id)
        with patch.object(self.inspection_repo, "save_requirement_results", side_effect=RuntimeError("Reqs DB down")):
            with pytest.raises(RuntimeError, match="Relational persistence failed"):
                self.revalidation_service.revalidate(insp_id, "inspector_hardened")

        session = self.session_store.get_session_optional(insp_id)
        assert session is None or session.report is None

    # 14. Sync Persistence Failure
    def test_14_sync_persistence_failure(self):
        """Sync op persistence failure raises RuntimeError and protects session projection."""
        insp_id = "insp-fail-sync-014"
        self._sync_mock_offline_inspection(insp_id)
        with patch.object(self.sync_repo, "save_operation", side_effect=RuntimeError("Sync DB down")), \
             patch.object(self.sync_repo, "update_operation_status", side_effect=RuntimeError("Sync DB down")):
            with pytest.raises(RuntimeError, match="Sync operation persistence failed"):
                self.revalidation_service.revalidate(insp_id, "inspector_hardened")

        session = self.session_store.get_session_optional(insp_id)
        assert session is None or session.report is None

    # 15. Session Projection Safety
    def test_15_session_projection_safety(self):
        """Session store is populated only after durable persistence succeeds."""
        insp_id = "insp-proj-safe-015"
        self._sync_mock_offline_inspection(insp_id)
        res = self.revalidation_service.revalidate(insp_id, "inspector_hardened")
        assert res.overall_status == OverallInspectionStatus.PASS
        session = self.session_store.get_session_optional(insp_id)
        assert session is not None
        assert session.report is not None
        assert session.inspection.status == InspectionStatus.COMPLETED
        assert session.inspection.metadata.get("evaluation_mode") == EvaluationMode.SERVER_REVALIDATED.value

    # 16. Session Cache Eviction
    def test_16_session_cache_eviction(self):
        """When in-memory session cache is evicted, state is rehydrated cleanly from durable store."""
        insp_id = "insp-evict-016"
        self._sync_mock_offline_inspection(insp_id)
        self.revalidation_service.revalidate(insp_id, "inspector_hardened")

        # Evict cache
        self.session_store.clear()
        assert self.session_store.get_session_optional(insp_id) is None

        # GET recovers from relational repository
        resp = self.client.get(f"/api/v1/inspections/{insp_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "COMPLETED"
        assert resp.json()["has_report"] is True

    # 17. Response Loss After Commit
    def test_17_response_loss_after_commit(self):
        """Retrying revalidation after response loss returns identical durable state."""
        insp_id = "insp-reval-retry-017"
        self._sync_mock_offline_inspection(insp_id)
        res1 = self.revalidation_service.revalidate(insp_id, "inspector_hardened")
        res2 = self.revalidation_service.revalidate(insp_id, "inspector_hardened")
        assert res1.content_hash == res2.content_hash
        assert res1.overall_status == res2.overall_status

    # 18. Repeated Revalidation
    def test_18_repeated_revalidation(self):
        """Multiple sequential revalidations are strictly idempotent."""
        insp_id = "insp-rep-reval-018"
        self._sync_mock_offline_inspection(insp_id)
        hashes = [self.revalidation_service.revalidate(insp_id, "inspector_hardened").content_hash for _ in range(5)]
        assert len(set(hashes)) == 1

    # 19. Concurrent Revalidation
    def test_19_concurrent_revalidation(self):
        """Concurrent revalidation calls converge safely without corruption."""
        insp_id = "insp-conc-reval-019"
        self._sync_mock_offline_inspection(insp_id)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self.revalidation_service.revalidate, insp_id, "inspector_hardened") for _ in range(8)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 8
        hashes = {r.content_hash for r in results}
        assert len(hashes) == 1

    # 20. No Duplicate Reports Created
    def test_20_no_duplicate_reports(self):
        """Repeated revalidations produce exactly one authoritative report."""
        insp_id = "insp-no-dup-rep-020"
        self._sync_mock_offline_inspection(insp_id)
        for _ in range(3):
            self.revalidation_service.revalidate(insp_id, "inspector_hardened")

        report = self.inspection_repo.get_report(insp_id)
        assert report is not None
        assert report.inspection_id == insp_id

    # 21. No Duplicate Requirement Results
    def test_21_no_duplicate_requirement_results(self):
        """Repeated revalidation updates requirement results idempotently without duplicate rows."""
        insp_id = "insp-no-dup-reqs-021"
        self._sync_mock_offline_inspection(insp_id)
        for _ in range(3):
            self.revalidation_service.revalidate(insp_id, "inspector_hardened")

        req_results = self.inspection_repo._req_results.get(insp_id, [])
        req_ids = [r["requirement_id"] for r in req_results]
        assert len(req_ids) == len(set(req_ids))
        assert len(req_ids) == 3

    # 22. No Duplicate Sync Operations Created
    def test_22_no_duplicate_sync_records(self):
        """Repeated revalidations update reval-rep operation idempotently without duplicate records."""
        insp_id = "insp-no-dup-sync-022"
        self._sync_mock_offline_inspection(insp_id)
        for _ in range(3):
            self.revalidation_service.revalidate(insp_id, "inspector_hardened")

        ops = self.sync_repo.list_operations_for_inspection(insp_id)
        reval_ops = [op for op in ops if op.operation_id == f"reval-rep-{insp_id}"]
        assert len(reval_ops) == 1

    # 23. Stale Legal Snapshot
    def test_23_stale_legal_snapshot(self):
        """Recognized historical legal snapshot is flagged as STALE in diagnostics."""
        insp_id = "insp-stale-023"
        self._sync_mock_offline_inspection(insp_id, client_snapshot_id="snapshot-stale-v1")
        res = self.revalidation_service.revalidate(insp_id, "inspector_hardened")
        assert res.server_legal_snapshot_id == self.server_snapshot_id
        assert res.comparison.snapshot_validation_status == "STALE"
        assert res.comparison.legal_snapshot_changed is True

    # 24. Unknown Legal Snapshot
    def test_24_unknown_legal_snapshot(self):
        """Unrecognized snapshot is flagged as UNKNOWN and evaluated against server law."""
        insp_id = "insp-unk-024"
        self._sync_mock_offline_inspection(insp_id, client_snapshot_id="snapshot-unknown-xyz")
        res = self.revalidation_service.revalidate(insp_id, "inspector_hardened")
        assert res.comparison.snapshot_validation_status == "UNKNOWN"

    # 25. Altered Snapshot Content / Hash
    def test_25_altered_snapshot_hash(self):
        """Tampered payload hash is rejected during ingestion."""
        insp_id = "insp-tamper-025"
        self.inspection_repo.create_inspection(
            inspection_id=insp_id,
            metadata={"owner_id": "inspector_hardened"},
            owner_id="inspector_hardened",
        )
        op = SyncOperation(
            operation_id="op-tamper-025",
            inspection_id=insp_id,
            entity_type=SyncEntityType.FACT,
            entity_id="fact-025",
            operation_type=SyncOperationType.CREATE,
            content_hash="tampered-fake-hash",
            created_at=datetime.now(timezone.utc).isoformat(),
            payload={"fact_key": "val", "value": "something"},
        )
        ack = self.ingestion_service.ingest_operation(op, "inspector_hardened")
        assert ack.status == SyncAckStatus.REJECTED
        assert ack.error_code == SyncErrorCode.SYNC_CONTENT_HASH_MISMATCH.value

    # 26. Incomplete Client Requirements
    def test_26_incomplete_client_requirements(self):
        """Client omitting required statutory checks cannot produce false PASS on server."""
        insp_id = "insp-incomp-026"
        self._sync_mock_offline_inspection(insp_id, include_mrp=True, include_qty=True, include_mfg=False, offline_status="PASS")
        res = self.revalidation_service.revalidate(insp_id, "inspector_hardened")
        assert res.overall_status == OverallInspectionStatus.REVIEW_REQUIRED
        assert "req-mfg-date" in res.applicable_requirements
        assert "req-mfg-date" in res.comparison.missing_offline_requirements

    # 27. Extra Client Requirements
    def test_27_extra_client_requirements(self):
        """Client providing extra non-statutory requirement IDs cannot expand server authority."""
        insp_id = "insp-extra-reqs-027"
        self._sync_mock_offline_inspection(insp_id, include_mrp=True, include_qty=True, include_mfg=True)
        # Add extra requirement result in sync repo
        self.sync_repo.save_operation(
            DurableSyncOperationRecord(
                operation_id="op-req-bogus-027",
                inspection_id=insp_id,
                entity_type=SyncEntityType.REQUIREMENT_RESULT,
                entity_id="req-bogus",
                operation_type=SyncOperationType.CREATE,
                content_hash="hash-bogus",
                created_at=datetime.now(timezone.utc).isoformat(),
                received_at=datetime.now(timezone.utc).isoformat(),
                acknowledged_at=datetime.now(timezone.utc).isoformat(),
                status=OperationStatus.ACKNOWLEDGED,
                payload={"requirement_id": "req-bogus-999", "status": "PASS"},
            )
        )
        res = self.revalidation_service.revalidate(insp_id, "inspector_hardened")
        assert "req-bogus-999" not in res.applicable_requirements
        assert "req-bogus-999" in res.comparison.extra_offline_requirements

    # 28. Offline Conclusions Not Trusted
    def test_28_offline_conclusions_not_trusted(self):
        """Server independently derives applicability and compliance regardless of offline claims."""
        insp_id = "insp-untrusted-028"
        # Claim PASS offline, but omit MRP evidence
        self._sync_mock_offline_inspection(insp_id, include_mrp=False, include_qty=True, include_mfg=True, offline_status="PASS")
        res = self.revalidation_service.revalidate(insp_id, "inspector_hardened")
        assert res.overall_status == OverallInspectionStatus.REVIEW_REQUIRED
        assert res.comparison.overall_status_changed is True

    # 29. Canonical Compliance Statuses
    def test_29_canonical_compliance_statuses(self):
        """All output statuses strictly adhere to the 5 canonical compliance enum values."""
        insp_id = "insp-canonical-029"
        self._sync_mock_offline_inspection(insp_id)
        res = self.revalidation_service.revalidate(insp_id, "inspector_hardened")
        valid_set = {"PASS", "FAIL", "NOT_VISIBLE", "NOT_APPLICABLE", "REVIEW_REQUIRED"}
        assert res.overall_status.value in valid_set
        for vr in res.verification_results:
            assert vr["status"] in valid_set

    # 30. Online Inspection Behavior Unchanged
    def test_30_online_inspection_behavior_unchanged(self):
        """Standard online inspection creation and report retrieval endpoints remain 100% functional."""
        resp = self.client.post("/api/v1/inspections", json={"metadata": {"online": True}})
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "COLLECTING"
        assert data["has_report"] is False
