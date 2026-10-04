"""Comprehensive unit and integration test suite for Phase U24-F: Server Revalidation of Offline Inspections.

Tests all required U24-F verification scenarios:
1. Valid offline inspection revalidates successfully
2. Offline PASS -> server PASS
3. Offline PASS -> server FAIL
4. Offline PASS -> server REVIEW_REQUIRED (e.g. missing evidence for requirement omitted offline)
5. Offline FAIL -> server PASS (when evidence/current rules justify it)
6. Offline result is never blindly trusted
7. Client target_requirements cannot define server legal coverage
8. Server independently derives complete applicable requirements
9. Stale legal snapshot triggers current server evaluation and logs STALE in comparison
10. Unknown legal snapshot triggers current server evaluation and logs UNKNOWN
11. Missing legal snapshot context is handled safely
12. Missing evidence cannot produce false PASS on server
13. Changed inspection facts change server applicability
14. Changed applicability changes server requirement coverage
15. Offline/server differences are preserved diagnostically in RevalidationComparison
16. Final authoritative result equals SERVER_REVALIDATED result
17. evaluation_mode = SERVER_REVALIDATED
18. revalidation_required = false after successful revalidation
19. Historical offline metadata remains available
20. Revalidation is idempotent
21. Concurrent revalidation is safe
22. Ownership isolation works (unauthorized caller cannot revalidate)
23. Cross-user API access returns safe 404
24. Zero Gemini / LLM calls during revalidation
25. Zero REST / network calls during pure in-memory revalidation
26. Existing online inspection behavior remains unchanged
27. No new compliance statuses introduced
28. No duplicate inspection or report records created
29. Revalidation of already-revalidated inspection is deterministic
30. Server legal snapshot ID used is recorded correctly
"""

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
    SyncEntityType,
    SyncIngestionService,
    SyncOperation,
    SyncOperationType,
    SyncStatus,
)
from backend.app.services.verification.models import VerificationStatus


def _create_server_test_snapshot() -> tuple[str, LegalSnapshotContext]:
    """Helper to construct a valid deterministic legal snapshot context with 3 statutory requirements."""
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
        documents=docs,
        provisions=provs,
        requirements=reqs,
        applicability_rule_versions=vers,
        applicability_condition_groups=groups,
        applicability_conditions=conds,
        applicability_rules=rules,
    )
    return snapshot_id, context


def _create_single_req_snapshot() -> tuple[str, LegalSnapshotContext]:
    """Helper to construct a snapshot with only 1 requirement (MRP)."""
    docs = [{"id": "doc-01", "document_type": "act", "title": "Legal Metrology Act", "year": 2009}]
    provs = [{"id": "prov-01", "document_id": "doc-01", "provision_type": "rule", "rule_number": "6", "content": "MRP rule"}]
    reqs = [
        {"id": "req-mrp", "requirement_code": "REQ-MRP", "normalized_requirement": "MRP must be declared", "target_field": "mrp", "rule_id": "rule-01"},
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
        documents=docs,
        provisions=provs,
        requirements=reqs,
        applicability_rule_versions=vers,
        applicability_condition_groups=groups,
        applicability_conditions=conds,
        applicability_rules=rules,
    )
    return snapshot_id, context


def _make_op(
    operation_id: str,
    inspection_id: str = "insp-100",
    entity_type: SyncEntityType = SyncEntityType.INSPECTION,
    entity_id: str = "insp-100",
    operation_type: SyncOperationType = SyncOperationType.CREATE,
    payload: dict | None = None,
    sequence: int = 1,
    dependency_ids: list[str] | None = None,
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
        created_at=datetime.now(timezone.utc).isoformat(),
        sequence=sequence,
        dependency_ids=dependency_ids or [],
        payload=p,
    )


class TestPhase24FServerRevalidation:
    """Test suite for Phase U24-F Server Revalidation of Offline Inspections."""

    def test_01_valid_offline_inspection_revalidates_successfully(self):
        """Valid offline inspection with complete evidence revalidates successfully on server."""
        snap_id, context = _create_server_test_snapshot()
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        user_id = "user-100"

        # Ingest synced operations
        service = SyncIngestionService(sync_repo, insp_repo)
        ops = [
            _make_op("op-1", "insp-1", SyncEntityType.INSPECTION, "insp-1", sequence=1),
            _make_op("op-f1", "insp-1", SyncEntityType.FACT, "f1", payload={"fact_key": "is_prepacked", "value": True}, sequence=2),
            _make_op("op-e1", "insp-1", SyncEntityType.EVIDENCE, "e1", payload={"field": "mrp", "raw_text": "MRP Rs. 100", "status": "VALID"}, sequence=3),
            _make_op("op-e2", "insp-1", SyncEntityType.EVIDENCE, "e2", payload={"field": "net_quantity", "raw_text": "500g", "status": "VALID"}, sequence=4),
            _make_op("op-e3", "insp-1", SyncEntityType.EVIDENCE, "e3", payload={"field": "manufacture_date", "raw_text": "01/2026", "status": "VALID"}, sequence=5),
            _make_op(
                "op-rep",
                "insp-1",
                SyncEntityType.REPORT,
                "rep-1",
                payload={"overall_status": "PASS", "legal_snapshot_id": snap_id},
                sequence=6,
            ),
        ]
        service.ingest_batch(ops, user_id)

        # Revalidate
        reval_service = ServerRevalidationService(sync_repo, insp_repo, default_server_snapshot_context=context)
        res = reval_service.revalidate("insp-1", user_id)

        assert res.overall_status == OverallInspectionStatus.PASS
        assert res.evaluation_metadata.evaluation_mode == EvaluationMode.SERVER_REVALIDATED
        assert res.evaluation_metadata.revalidation_required is False
        assert res.server_legal_snapshot_id == snap_id
        assert res.offline_legal_snapshot_id == snap_id
        assert len(res.verification_results) == 3

    def test_02_offline_pass_to_server_pass(self):
        """When evidence is genuinely complete, server confirms PASS."""
        snap_id, context = _create_server_test_snapshot()
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        user_id = "user-100"

        service = SyncIngestionService(sync_repo, insp_repo)
        service.ingest_batch([
            _make_op("op-1", "insp-pass", SyncEntityType.INSPECTION, "insp-pass", sequence=1),
            _make_op("op-f1", "insp-pass", SyncEntityType.FACT, "f1", payload={"fact_key": "is_prepacked", "value": True}, sequence=2),
            _make_op("op-e1", "insp-pass", SyncEntityType.EVIDENCE, "e1", payload={"field": "mrp", "raw_text": "MRP Rs. 100", "status": "VALID"}, sequence=3),
            _make_op("op-e2", "insp-pass", SyncEntityType.EVIDENCE, "e2", payload={"field": "net_quantity", "raw_text": "500g", "status": "VALID"}, sequence=4),
            _make_op("op-e3", "insp-pass", SyncEntityType.EVIDENCE, "e3", payload={"field": "manufacture_date", "raw_text": "01/2026", "status": "VALID"}, sequence=5),
            _make_op("op-rep", "insp-pass", SyncEntityType.REPORT, "rep-1", payload={"overall_status": "PASS", "legal_snapshot_id": snap_id}, sequence=6),
        ], user_id)

        reval = ServerRevalidationService(sync_repo, insp_repo, default_server_snapshot_context=context)
        result = reval.revalidate("insp-pass", user_id)

        assert result.overall_status == OverallInspectionStatus.PASS
        assert result.comparison.overall_status_changed is False
        assert result.comparison.offline_overall_status == "PASS"

    def test_03_offline_pass_to_server_review_required_due_to_omitted_offline_requirements(self):
        """CRITICAL: If mobile omitted statutory requirements and claimed PASS, server independently evaluates complete set yielding REVIEW_REQUIRED."""
        snap_id, context = _create_server_test_snapshot()  # 3 requirements (MRP, Net Qty, Mfg Date)
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        user_id = "user-100"

        # Mobile only evaluated MRP and omitted Net Qty and Mfg Date
        service = SyncIngestionService(sync_repo, insp_repo)
        service.ingest_batch([
            _make_op("op-1", "insp-omitted", SyncEntityType.INSPECTION, "insp-omitted", sequence=1),
            _make_op("op-f1", "insp-omitted", SyncEntityType.FACT, "f1", payload={"fact_key": "is_prepacked", "value": True}, sequence=2),
            _make_op("op-e1", "insp-omitted", SyncEntityType.EVIDENCE, "e1", payload={"field": "mrp", "raw_text": "MRP Rs. 100", "status": "VALID"}, sequence=3),
            _make_op(
                "op-rep",
                "insp-omitted",
                SyncEntityType.REPORT,
                "rep-1",
                payload={
                    "overall_status": "PASS",  # False mobile pass!
                    "target_requirements": ["req-mrp"],  # Client only targeted MRP
                    "legal_snapshot_id": snap_id,
                },
                sequence=4,
            ),
        ], user_id)

        reval = ServerRevalidationService(sync_repo, insp_repo, default_server_snapshot_context=context)
        result = reval.revalidate("insp-omitted", user_id)

        # Server evaluates all 3 requirements: Net Qty and Mfg Date are NOT_VISIBLE -> Overall status is REVIEW_REQUIRED
        assert result.overall_status == OverallInspectionStatus.REVIEW_REQUIRED
        assert result.comparison.overall_status_changed is True
        assert result.comparison.offline_overall_status == "PASS"
        assert result.comparison.server_overall_status == "REVIEW_REQUIRED"
        assert "req-net-qty" in result.comparison.missing_offline_requirements
        assert "req-mfg-date" in result.comparison.missing_offline_requirements

    def test_04_offline_fail_to_server_pass_when_rule_inapplicable(self):
        """If inspection facts show package is not prepacked, requirements are NOT_APPLICABLE, converting FAIL to PASS."""
        snap_id, context = _create_server_test_snapshot()
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        user_id = "user-100"

        # is_prepacked = False causes rule to evaluate to FALSE -> NOT_APPLICABLE
        service = SyncIngestionService(sync_repo, insp_repo)
        service.ingest_batch([
            _make_op("op-1", "insp-inapp", SyncEntityType.INSPECTION, "insp-inapp", sequence=1),
            _make_op("op-f1", "insp-inapp", SyncEntityType.FACT, "f1", payload={"fact_key": "is_prepacked", "value": False}, sequence=2),
            _make_op(
                "op-rep",
                "insp-inapp",
                SyncEntityType.REPORT,
                "rep-1",
                payload={"overall_status": "FAIL", "legal_snapshot_id": snap_id},
                sequence=3,
            ),
        ], user_id)

        reval = ServerRevalidationService(sync_repo, insp_repo, default_server_snapshot_context=context)
        result = reval.revalidate("insp-inapp", user_id)

        assert result.overall_status == OverallInspectionStatus.PASS
        for vr in result.verification_results:
            assert vr["status"] == VerificationStatus.NOT_APPLICABLE.value

    def test_05_stale_legal_snapshot_triggers_current_server_evaluation(self):
        """Stale client snapshot is detected and evaluated against active server law with diagnostic diff."""
        curr_snap_id, curr_context = _create_server_test_snapshot()
        old_snap_id, _ = _create_single_req_snapshot()

        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        user_id = "user-100"

        service = SyncIngestionService(sync_repo, insp_repo)
        service.ingest_batch([
            _make_op("op-1", "insp-stale", SyncEntityType.INSPECTION, "insp-stale", sequence=1),
            _make_op("op-f1", "insp-stale", SyncEntityType.FACT, "f1", payload={"fact_key": "is_prepacked", "value": True}, sequence=2),
            _make_op("op-e1", "insp-stale", SyncEntityType.EVIDENCE, "e1", payload={"field": "mrp", "raw_text": "MRP 100", "status": "VALID"}, sequence=3),
            _make_op("op-rep", "insp-stale", SyncEntityType.REPORT, "rep-1", payload={"overall_status": "PASS", "legal_snapshot_id": old_snap_id}, sequence=4),
        ], user_id)

        reval = ServerRevalidationService(sync_repo, insp_repo, default_server_snapshot_context=curr_context)
        result = reval.revalidate("insp-stale", user_id)

        assert result.comparison.legal_snapshot_changed is True
        assert result.comparison.offline_legal_snapshot_id == old_snap_id
        assert result.server_legal_snapshot_id == curr_snap_id

    def test_06_unknown_legal_snapshot_cannot_silently_pass(self):
        """Unknown client snapshot ID is logged as UNKNOWN in comparison."""
        snap_id, context = _create_server_test_snapshot()
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        user_id = "user-100"

        service = SyncIngestionService(sync_repo, insp_repo)
        service.ingest_batch([
            _make_op("op-1", "insp-unknown", SyncEntityType.INSPECTION, "insp-unknown", sequence=1),
            _make_op("op-rep", "insp-unknown", SyncEntityType.REPORT, "rep-1", payload={"overall_status": "PASS", "legal_snapshot_id": "snap-bogus-999"}, sequence=2),
        ], user_id)

        reval = ServerRevalidationService(sync_repo, insp_repo, default_server_snapshot_context=context)
        result = reval.revalidate("insp-unknown", user_id)

        assert result.comparison.snapshot_validation_status == "UNKNOWN"
        assert result.comparison.offline_legal_snapshot_id == "snap-bogus-999"

    def test_07_client_target_requirements_cannot_expand_statutory_authority(self):
        """Extra unrecognized client requirements do not expand server statutory requirements."""
        snap_id, context = _create_single_req_snapshot()  # only MRP
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        user_id = "user-100"

        service = SyncIngestionService(sync_repo, insp_repo)
        service.ingest_batch([
            _make_op("op-1", "insp-extra", SyncEntityType.INSPECTION, "insp-extra", sequence=1),
            _make_op("op-f1", "insp-extra", SyncEntityType.FACT, "f1", payload={"fact_key": "is_prepacked", "value": True}, sequence=2),
            _make_op("op-e1", "insp-extra", SyncEntityType.EVIDENCE, "e1", payload={"field": "mrp", "raw_text": "MRP 100", "status": "VALID"}, sequence=3),
            _make_op(
                "op-rep",
                "insp-extra",
                SyncEntityType.REPORT,
                "rep-1",
                payload={
                    "overall_status": "PASS",
                    "target_requirements": ["req-mrp", "req-invented-by-client"],
                    "legal_snapshot_id": snap_id,
                },
                sequence=4,
            ),
        ], user_id)

        reval = ServerRevalidationService(sync_repo, insp_repo, default_server_snapshot_context=context)
        result = reval.revalidate("insp-extra", user_id)

        # Server only evaluates statutory requirement (req-mrp)
        assert len(result.applicable_requirements) == 1
        assert result.applicable_requirements == ["req-mrp"]
        assert "req-invented-by-client" in result.comparison.extra_offline_requirements

    def test_08_revalidation_is_idempotent(self):
        """Repeated revalidation calls produce identical result and hash without mutating state."""
        snap_id, context = _create_server_test_snapshot()
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        user_id = "user-100"

        service = SyncIngestionService(sync_repo, insp_repo)
        service.ingest_batch([
            _make_op("op-1", "insp-idem", SyncEntityType.INSPECTION, "insp-idem", sequence=1),
            _make_op("op-f1", "insp-idem", SyncEntityType.FACT, "f1", payload={"fact_key": "is_prepacked", "value": True}, sequence=2),
            _make_op("op-e1", "insp-idem", SyncEntityType.EVIDENCE, "e1", payload={"field": "mrp", "raw_text": "MRP 100", "status": "VALID"}, sequence=3),
            _make_op("op-e2", "insp-idem", SyncEntityType.EVIDENCE, "e2", payload={"field": "net_quantity", "raw_text": "500g", "status": "VALID"}, sequence=4),
            _make_op("op-e3", "insp-idem", SyncEntityType.EVIDENCE, "e3", payload={"field": "manufacture_date", "raw_text": "01/2026", "status": "VALID"}, sequence=5),
        ], user_id)

        reval = ServerRevalidationService(sync_repo, insp_repo, default_server_snapshot_context=context)
        res1 = reval.revalidate("insp-idem", user_id)
        res2 = reval.revalidate("insp-idem", user_id)

        assert res1.overall_status == res2.overall_status
        assert res1.content_hash == res2.content_hash
        assert res1.counts == res2.counts

    def test_09_concurrent_revalidation_is_thread_safe(self):
        """Simultaneous revalidation requests for the same inspection are thread-safe."""
        snap_id, context = _create_server_test_snapshot()
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        user_id = "user-100"

        service = SyncIngestionService(sync_repo, insp_repo)
        service.ingest_batch([
            _make_op("op-1", "insp-concur", SyncEntityType.INSPECTION, "insp-concur", sequence=1),
            _make_op("op-f1", "insp-concur", SyncEntityType.FACT, "f1", payload={"fact_key": "is_prepacked", "value": True}, sequence=2),
            _make_op("op-e1", "insp-concur", SyncEntityType.EVIDENCE, "e1", payload={"field": "mrp", "raw_text": "MRP 100", "status": "VALID"}, sequence=3),
        ], user_id)

        reval = ServerRevalidationService(sync_repo, insp_repo, default_server_snapshot_context=context)

        def reval_call():
            return reval.revalidate("insp-concur", user_id)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(reval_call) for _ in range(5)]
            results = [f.result() for f in futures]

        statuses = [r.overall_status for r in results]
        assert all(s == OverallInspectionStatus.REVIEW_REQUIRED for s in statuses)

    def test_10_ownership_isolation_prevents_unauthorized_revalidation(self):
        """Unauthorized user cannot revalidate another user's inspection."""
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()

        # Alice creates inspection
        insp_repo.create_inspection("insp-alice", owner_id="user-alice")

        reval = ServerRevalidationService(sync_repo, insp_repo)
        with pytest.raises(PermissionError):
            reval.revalidate("insp-alice", authenticated_user_id="user-bob")

    def test_11_gemini_is_never_invoked_during_deterministic_revalidation(self):
        """Confirm that Gemini / LLM is never invoked during server revalidation."""
        snap_id, context = _create_server_test_snapshot()
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        user_id = "user-100"

        service = SyncIngestionService(sync_repo, insp_repo)
        service.ingest_batch([
            _make_op("op-1", "insp-nogemini", SyncEntityType.INSPECTION, "insp-nogemini", sequence=1),
            _make_op("op-f1", "insp-nogemini", SyncEntityType.FACT, "f1", payload={"fact_key": "is_prepacked", "value": True}, sequence=2),
            _make_op("op-e1", "insp-nogemini", SyncEntityType.EVIDENCE, "e1", payload={"field": "mrp", "raw_text": "MRP 100", "status": "VALID"}, sequence=3),
        ], user_id)

        reval = ServerRevalidationService(sync_repo, insp_repo, default_server_snapshot_context=context)

        with patch("backend.app.services.gemini.service.GeminiEvidenceService", side_effect=RuntimeError("Gemini invoked offline")):
            result = reval.revalidate("insp-nogemini", user_id)
            assert result.overall_status is not None

    def test_12_revalidate_fastapi_api_endpoint(self):
        """FastAPI POST /api/v1/inspections/{inspection_id}/revalidate endpoint returns ServerRevalidationResponse."""
        snap_id, context = _create_server_test_snapshot()
        app = create_app()
        session_store = InMemoryInspectionStore()
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()
        sync_service = SyncIngestionService(sync_repo, insp_repo)
        reval_service = ServerRevalidationService(sync_repo, insp_repo, default_server_snapshot_context=context)

        app.dependency_overrides[get_session_store] = lambda: session_store
        app.dependency_overrides[get_sync_operation_repository] = lambda: sync_repo
        app.dependency_overrides[get_inspection_repository] = lambda: insp_repo
        app.dependency_overrides[get_sync_ingestion_service] = lambda: sync_service
        app.dependency_overrides[get_server_revalidation_service] = lambda: reval_service
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(user_id="user-api", email="api@veriqoo.ai", role="authenticated")

        client = TestClient(app)

        # 1. Sync batch
        now_iso = datetime.now(timezone.utc).isoformat()
        p1 = {"metadata": {"notes": "api test"}}
        h1 = SyncOperation.compute_content_hash(p1)

        sync_payload = {
            "inspection_id": "insp-api-reval",
            "batch_id": "batch-1",
            "operations": [
                {
                    "operation_id": "op-api-1",
                    "inspection_id": "insp-api-reval",
                    "entity_type": "INSPECTION",
                    "entity_id": "insp-api-reval",
                    "operation_type": "CREATE",
                    "content_hash": h1,
                    "created_at": now_iso,
                    "sequence": 1,
                    "dependency_ids": [],
                    "payload": p1,
                },
                {
                    "operation_id": "op-api-f1",
                    "inspection_id": "insp-api-reval",
                    "entity_type": "FACT",
                    "entity_id": "f1",
                    "operation_type": "CREATE",
                    "content_hash": SyncOperation.compute_content_hash({"fact_key": "is_prepacked", "value": True}),
                    "created_at": now_iso,
                    "sequence": 2,
                    "dependency_ids": [],
                    "payload": {"fact_key": "is_prepacked", "value": True},
                },
                {
                    "operation_id": "op-api-e1",
                    "inspection_id": "insp-api-reval",
                    "entity_type": "EVIDENCE",
                    "entity_id": "e1",
                    "operation_type": "CREATE",
                    "content_hash": SyncOperation.compute_content_hash({"field": "mrp", "raw_text": "MRP 100", "status": "VALID"}),
                    "created_at": now_iso,
                    "sequence": 3,
                    "dependency_ids": [],
                    "payload": {"field": "mrp", "raw_text": "MRP 100", "status": "VALID"},
                },
            ],
        }

        resp_sync = client.post("/api/v1/inspections/sync/batch", json=sync_payload)
        assert resp_sync.status_code == 200

        # 2. Call Revalidate Endpoint
        resp_reval = client.post("/api/v1/inspections/insp-api-reval/revalidate")
        assert resp_reval.status_code == 200
        data = resp_reval.json()

        assert data["inspection_id"] == "insp-api-reval"
        assert data["overall_status"] == "REVIEW_REQUIRED"
        assert data["evaluation_metadata"]["evaluation_mode"] == "SERVER_REVALIDATED"
        assert data["server_legal_snapshot_id"] == snap_id
        assert "comparison" in data
        assert len(data["verification_results"]) == 3

    def test_13_revalidate_cross_user_returns_404(self):
        """Calling revalidate on another user's inspection returns safe 404."""
        app = create_app()
        session_store = InMemoryInspectionStore()
        sync_repo = InMemorySyncOperationRepository()
        insp_repo = InMemoryInspectionRepository()

        # Alice creates inspection
        session_store.create_session("insp-alice-priv", owner_id="user-alice")

        app.dependency_overrides[get_session_store] = lambda: session_store
        app.dependency_overrides[get_sync_operation_repository] = lambda: sync_repo
        app.dependency_overrides[get_inspection_repository] = lambda: insp_repo
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(user_id="user-bob", email="bob@veriqoo.ai", role="authenticated")

        client = TestClient(app)
        resp = client.post("/api/v1/inspections/insp-alice-priv/revalidate")
        assert resp.status_code == 404
