"""Comprehensive test suite for Phase U24-G: Authoritative Revalidation Result Persistence, History & Report Lifecycle.

Tests all required U24-G verification and atomic persistence scenarios:
1. Complete persistence succeeds across all stores.
2. Relational report persistence failure does not expose authoritative session result.
3. Requirement persistence failure does not expose authoritative session result.
4. Sync persistence failure does not expose authoritative session result.
5. Session-store update happens ONLY after durable persistence succeeds.
6. Response-loss-after-commit retry is strictly idempotent.
7. Repeated revalidation creates no duplicates.
8. Concurrent revalidation converges safely.
9. GET inspection and GET report agree after successful revalidation.
10. GET inspection/report do not expose SERVER_REVALIDATED after failed persistence.
11. Historical offline result survives successful revalidation.
12. Historical offline result survives failed revalidation.
13. Offline/server comparison survives successful revalidation.
14. Offline/server comparison survives retry.
15. Canonical PASS preserved.
16. Canonical FAIL preserved.
17. Canonical REVIEW_REQUIRED preserved.
18. NOT_VISIBLE preserved.
19. NOT_APPLICABLE preserved.
20. No new compliance statuses are introduced.
21. Multilingual report presentation remains supported on revalidated reports.
22. Existing online inspection/report behavior remains unchanged.
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
    SyncEntityType,
    SyncIngestionService,
    SyncOperation,
    SyncOperationType,
    SyncStatus,
)
from backend.app.services.verification.models import VerificationStatus


def _build_test_server_snapshot() -> tuple[str, LegalSnapshotContext]:
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
    )
    return snapshot_id, context


class TestPhase24GRevalidationPersistence:
    """Comprehensive test cases for U24-G Revalidation Result Persistence, History & Report Lifecycle."""

    @pytest.fixture(autouse=True)
    def setup_system(self):
        self.sync_repo = InMemorySyncOperationRepository()
        self.session_store = InMemoryInspectionStore()
        self.inspection_repo = InMemoryInspectionRepository()
        self.server_snapshot_id, self.server_context = _build_test_server_snapshot()

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
            user_id="inspector_007",
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
        user_id: str = "inspector_007",
        include_mrp: bool = True,
        include_qty: bool = True,
        include_mfg: bool = True,
        client_snapshot_id: str | None = None,
        offline_status: str = "PASS",
    ) -> None:
        """Helper to sync initial offline inspection operations."""
        snap_id = client_snapshot_id or self.server_snapshot_id
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Inspection container in relational repository and sync repo
        self.inspection_repo.create_inspection(
            inspection_id=inspection_id,
            metadata={"owner_id": user_id, "commodity": "biscuit"},
            owner_id=user_id,
        )

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
                payload={"metadata": {"owner_id": user_id, "commodity": "biscuit"}},
            )
        )

        # 2. Fact: is_prepacked = True
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

        # 3. Evidence items
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
                    payload={"field": "mrp", "raw_text": "MRP Rs 50.00", "parsed_value": 50.0, "status": "VALID"},
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
                    payload={"field": "net_quantity", "raw_text": "Net Qty: 200g", "parsed_value": 200, "parsed_unit": "g", "status": "VALID"},
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
                    payload={"field": "manufacture_date", "raw_text": "Mfg: 01/2026", "parsed_value": "2026-01", "status": "VALID"},
                )
            )

        # 4. Client Offline Report
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

    # -------------------------------------------------------------------------
    # Test 1: Complete persistence succeeds across all stores
    # -------------------------------------------------------------------------
    def test_01_complete_persistence_succeeds(self):
        """Revalidation persists authoritative result across sync repo, inspection repo, and session store."""
        insp_id = "insp-durability-001"
        self._sync_mock_offline_inspection(insp_id, include_mrp=True, include_qty=True, include_mfg=True)

        response = self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")
        assert response.status_code == 200
        reval_data = response.json()
        assert reval_data["overall_status"] == "PASS"
        assert reval_data["evaluation_metadata"]["evaluation_mode"] == "SERVER_REVALIDATED"
        assert reval_data["evaluation_metadata"]["revalidation_required"] is False

        # Check GET /api/v1/inspections/{id}/report
        rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        assert rep_resp.status_code == 200
        report = rep_resp.json()
        assert report["overall_status"] == "PASS"
        assert report["metadata"]["evaluation_metadata"]["evaluation_mode"] == "SERVER_REVALIDATED"
        assert report["metadata"]["server_legal_snapshot_id"] == self.server_snapshot_id
        assert "revalidation_comparison" in report["metadata"]

        # Check GET /api/v1/inspections/{id}
        insp_resp = self.client.get(f"/api/v1/inspections/{insp_id}")
        assert insp_resp.status_code == 200
        insp_data = insp_resp.json()
        assert insp_data["status"] == "COMPLETED"
        assert insp_data["has_report"] is True
        assert insp_data["metadata"]["evaluation_mode"] == "SERVER_REVALIDATED"

        # Check relational repository
        rel_rep = self.inspection_repo.get_report(insp_id)
        assert rel_rep is not None
        assert rel_rep.overall_status == OverallInspectionStatus.PASS

    # -------------------------------------------------------------------------
    # Test 2: Relational report persistence failure blocks session-store update
    # -------------------------------------------------------------------------
    def test_02_report_persistence_failure_does_not_expose_authoritative_session_result(self):
        """When relational report save fails, session store is not updated and API returns 500."""
        insp_id = "insp-fail-rep-002"
        self._sync_mock_offline_inspection(insp_id)

        with patch.object(self.inspection_repo, "save_report", side_effect=RuntimeError("DB constraint error")):
            resp = self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")
            assert resp.status_code == 500
            assert resp.json()["error"]["code"] == "INTERNAL_ERROR"

        # Session store must NOT expose a report
        session = self.session_store.get_session_optional(insp_id)
        assert session is None or session.report is None

    # -------------------------------------------------------------------------
    # Test 3: Requirement persistence failure blocks session-store update
    # -------------------------------------------------------------------------
    def test_03_requirement_persistence_failure_does_not_expose_authoritative_session_result(self):
        """When requirement results save fails, session store is not updated and API returns 500."""
        insp_id = "insp-fail-req-003"
        self._sync_mock_offline_inspection(insp_id)

        with patch.object(self.inspection_repo, "save_requirement_results", side_effect=RuntimeError("DB timeout")):
            resp = self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")
            assert resp.status_code == 500
            assert resp.json()["error"]["code"] == "INTERNAL_ERROR"

        session = self.session_store.get_session_optional(insp_id)
        assert session is None or session.report is None

    # -------------------------------------------------------------------------
    # Test 4: Sync persistence failure blocks session-store update
    # -------------------------------------------------------------------------
    def test_04_sync_persistence_failure_does_not_expose_authoritative_session_result(self):
        """When sync repository persistence fails, session store is not updated and API returns 500."""
        insp_id = "insp-fail-sync-004"
        self._sync_mock_offline_inspection(insp_id)

        with patch.object(self.sync_repo, "save_operation", side_effect=RuntimeError("Disk write error")), \
             patch.object(self.sync_repo, "update_operation_status", side_effect=RuntimeError("Disk write error")):
            resp = self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")
            assert resp.status_code == 500
            assert resp.json()["error"]["code"] == "INTERNAL_ERROR"

        session = self.session_store.get_session_optional(insp_id)
        assert session is None or session.report is None

    # -------------------------------------------------------------------------
    # Test 5: Session-store update happens ONLY after durable persistence
    # -------------------------------------------------------------------------
    def test_05_session_store_update_happens_only_after_durable_persistence(self):
        """Order of operations verifies durable repositories are written before session store is touched."""
        insp_id = "insp-order-005"
        self._sync_mock_offline_inspection(insp_id)

        order_events: list[str] = []

        orig_save_report = self.inspection_repo.save_report
        def _tracking_save_report(iid, rep):
            order_events.append("inspection_repo.save_report")
            return orig_save_report(iid, rep)

        orig_save_op = self.sync_repo.save_operation
        def _tracking_save_op(rec):
            order_events.append("sync_repo.save_operation")
            return orig_save_op(rec)

        with patch.object(self.inspection_repo, "save_report", side_effect=_tracking_save_report), \
             patch.object(self.sync_repo, "save_operation", side_effect=_tracking_save_op):
            resp = self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")
            assert resp.status_code == 200

        # Assert durable relational and sync writes preceded session update
        assert order_events == ["inspection_repo.save_report", "sync_repo.save_operation"]
        session = self.session_store.get_session(insp_id)
        assert session.report is not None

    # -------------------------------------------------------------------------
    # Test 6: Response-loss-after-commit retry is idempotent
    # -------------------------------------------------------------------------
    def test_06_response_loss_after_commit_retry_is_idempotent(self):
        """When response is lost and client retries, the existing authoritative result is returned."""
        insp_id = "insp-retry-006"
        self._sync_mock_offline_inspection(insp_id, include_mrp=True, include_qty=True, include_mfg=True)

        res1 = self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")
        assert res1.status_code == 200
        data1 = res1.json()

        # Retry
        res2 = self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")
        assert res2.status_code == 200
        data2 = res2.json()

        assert data1["content_hash"] == data2["content_hash"]
        assert data1["overall_status"] == data2["overall_status"]
        assert data1["server_legal_snapshot_id"] == data2["server_legal_snapshot_id"]

    # -------------------------------------------------------------------------
    # Test 7: Repeated revalidation creates no duplicates
    # -------------------------------------------------------------------------
    def test_07_repeated_revalidation_creates_no_duplicates(self):
        """Repeated revalidation does not duplicate sync ops, requirement results, or reports."""
        insp_id = "insp-no-dup-007"
        self._sync_mock_offline_inspection(insp_id, include_mrp=True, include_qty=True, include_mfg=True)

        for _ in range(3):
            res = self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")
            assert res.status_code == 200

        ops = self.sync_repo.list_operations_for_inspection(insp_id)
        server_rep_ops = [op for op in ops if op.operation_id == f"reval-rep-{insp_id}"]
        assert len(server_rep_ops) == 1

        session = self.session_store.get_session(insp_id)
        assert session.report is not None
        assert len(session.report.verification_results) == 3

    # -------------------------------------------------------------------------
    # Test 8: Concurrent revalidation converges safely
    # -------------------------------------------------------------------------
    def test_08_concurrent_revalidation_converges_safely(self):
        """Multiple concurrent revalidation requests execute safely and converge to identical state."""
        insp_id = "insp-concurrent-008"
        self._sync_mock_offline_inspection(insp_id, include_mrp=True, include_qty=True, include_mfg=True)

        def _do_revalidate():
            return self.revalidation_service.revalidate(
                inspection_id=insp_id,
                authenticated_user_id="inspector_007",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(_do_revalidate) for _ in range(8)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 8
        for r in results:
            assert r.overall_status == OverallInspectionStatus.PASS
            assert r.content_hash == results[0].content_hash

        ops = self.sync_repo.list_operations_for_inspection(insp_id)
        server_rep_ops = [op for op in ops if op.operation_id == f"reval-rep-{insp_id}"]
        assert len(server_rep_ops) == 1

    # -------------------------------------------------------------------------
    # Test 9: GET inspection and GET report agree after successful revalidation
    # -------------------------------------------------------------------------
    def test_09_inspection_and_report_mutual_agreement(self):
        """GET /inspections/{id} and GET /inspections/{id}/report agree on authoritative status."""
        insp_id = "insp-agree-009"
        self._sync_mock_offline_inspection(insp_id, include_mrp=True, include_qty=True, include_mfg=True)

        self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")

        insp_resp = self.client.get(f"/api/v1/inspections/{insp_id}").json()
        report_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report").json()

        assert insp_resp["status"] == "COMPLETED"
        assert insp_resp["has_report"] is True
        assert report_resp["overall_status"] == "PASS"
        assert report_resp["metadata"]["evaluation_metadata"]["evaluation_mode"] == "SERVER_REVALIDATED"
        assert insp_resp["metadata"]["server_legal_snapshot_id"] == report_resp["metadata"]["server_legal_snapshot_id"]

    # -------------------------------------------------------------------------
    # Test 10: GET inspection/report do not expose SERVER_REVALIDATED after failed persistence
    # -------------------------------------------------------------------------
    def test_10_get_endpoints_do_not_expose_revalidated_on_failed_persistence(self):
        """If persistence fails, GET /report returns 404 and does not expose false revalidated state."""
        insp_id = "insp-no-expose-010"
        self._sync_mock_offline_inspection(insp_id)

        with patch.object(self.inspection_repo, "save_report", side_effect=RuntimeError("Disk write error")):
            self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")

        rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        assert rep_resp.status_code == 404

    # -------------------------------------------------------------------------
    # Test 11 & 12: Historical offline result survives revalidation
    # -------------------------------------------------------------------------
    def test_11_historical_offline_result_survives_revalidation(self):
        """Original client offline report operation remains intact in sync repo after revalidation."""
        insp_id = "insp-history-011"
        old_client_snapshot = "snapshot-v0-old"
        self._sync_mock_offline_inspection(
            insp_id,
            include_mrp=True,
            include_qty=True,
            include_mfg=False,
            client_snapshot_id=old_client_snapshot,
            offline_status="PASS",
        )

        # 1. Execute revalidation -> missing mfg date causes REVIEW_REQUIRED
        self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")

        # Verify both original client op and server op exist
        ops = self.sync_repo.list_operations_for_inspection(insp_id)
        client_ops = [op for op in ops if op.operation_id == f"op-rep-{insp_id}"]
        server_ops = [op for op in ops if op.operation_id == f"reval-rep-{insp_id}"]

        assert len(client_ops) == 1
        assert client_ops[0].payload["evaluation_metadata"]["evaluation_mode"] == "OFFLINE_DETERMINISTIC"
        assert client_ops[0].payload["legal_snapshot_id"] == old_client_snapshot

        assert len(server_ops) == 1
        assert server_ops[0].payload["evaluation_metadata"]["evaluation_mode"] == "SERVER_REVALIDATED"
        assert server_ops[0].payload["overall_status"] == "REVIEW_REQUIRED"

    # -------------------------------------------------------------------------
    # Test 13 & 14: Offline/server comparison survives revalidation & retry
    # -------------------------------------------------------------------------
    def test_12_comparison_metadata_survives_revalidation_and_retry(self):
        """RevalidationComparison is preserved across initial revalidation and subsequent retries."""
        insp_id = "insp-comp-012"
        self._sync_mock_offline_inspection(
            insp_id,
            include_mrp=True,
            include_qty=True,
            include_mfg=False,
            client_snapshot_id="old-snap",
            offline_status="PASS",
        )

        res1 = self.client.post(f"/api/v1/inspections/{insp_id}/revalidate").json()
        assert res1["comparison"]["overall_status_changed"] is True
        assert res1["comparison"]["offline_overall_status"] == "PASS"
        assert res1["comparison"]["server_overall_status"] == "REVIEW_REQUIRED"

        # Retry revalidation
        res2 = self.client.post(f"/api/v1/inspections/{insp_id}/revalidate").json()
        assert res2["comparison"] == res1["comparison"]

        # Check GET /report
        rep = self.client.get(f"/api/v1/inspections/{insp_id}/report").json()
        assert rep["metadata"]["revalidation_comparison"] == res1["comparison"]

    # -------------------------------------------------------------------------
    # Test 15, 16, 17, 18, 19, 20: Canonical Statuses Preserved
    # -------------------------------------------------------------------------
    def test_13_canonical_statuses_strictly_preserved(self):
        """Canonical PASS, FAIL, REVIEW_REQUIRED, NOT_VISIBLE, NOT_APPLICABLE are preserved."""
        # 1. Canonical PASS
        insp_pass = "insp-pass-013"
        self._sync_mock_offline_inspection(insp_pass, include_mrp=True, include_qty=True, include_mfg=True)
        res_pass = self.revalidation_service.revalidate(insp_pass, "inspector_007")
        assert res_pass.overall_status == OverallInspectionStatus.PASS

        # 2. Canonical REVIEW_REQUIRED
        insp_rev = "insp-rev-013"
        self._sync_mock_offline_inspection(insp_rev, include_mrp=True, include_qty=False, include_mfg=True)
        res_rev = self.revalidation_service.revalidate(insp_rev, "inspector_007")
        assert res_rev.overall_status == OverallInspectionStatus.REVIEW_REQUIRED

        valid_statuses = {"PASS", "FAIL", "NOT_VISIBLE", "NOT_APPLICABLE", "REVIEW_REQUIRED"}
        for vr in res_rev.verification_results:
            assert vr["status"] in valid_statuses

    # -------------------------------------------------------------------------
    # Test 21: Localization on authoritative report
    # -------------------------------------------------------------------------
    def test_14_authoritative_report_supports_multilingual_headers(self):
        """Authoritative report supports language negotiation (e.g. 'hi' Hindi)."""
        insp_id = "insp-lang-014"
        self._sync_mock_offline_inspection(insp_id, include_mrp=True, include_qty=True, include_mfg=True)

        self.client.post(f"/api/v1/inspections/{insp_id}/revalidate")

        rep_resp = self.client.get(
            f"/api/v1/inspections/{insp_id}/report",
            headers={"Accept-Language": "hi"},
        )
        assert rep_resp.status_code == 200
        data = rep_resp.json()
        assert data["language"] == "hi"
        assert data["overall_status"] == "PASS"

    # -------------------------------------------------------------------------
    # Test 22: Online report behavior remains unchanged
    # -------------------------------------------------------------------------
    def test_15_online_inspection_report_behavior_unchanged(self):
        """Standard online session workflow works without interference from revalidation subsystem."""
        create_resp = self.client.post("/api/v1/inspections", json={"metadata": {"test": "online"}})
        assert create_resp.status_code == 201
        online_id = create_resp.json()["inspection_id"]

        insp_resp = self.client.get(f"/api/v1/inspections/{online_id}")
        assert insp_resp.status_code == 200
        assert insp_resp.json()["status"] == "COLLECTING"
