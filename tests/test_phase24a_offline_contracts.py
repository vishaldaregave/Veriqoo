"""Comprehensive test suite for Phase U24-A — Offline Data & Evaluation Contract + Legal Snapshot.

Validates:
1. Evaluation mode enum contains exactly ONLINE, OFFLINE_DETERMINISTIC, SERVER_REVALIDATED.
2. Canonical compliance statuses remain unchanged.
3. Legal snapshot serialization is deterministic.
4. Same legal input produces exact same SHA-256 legal_snapshot_id.
5. Reordered database records produce exact same snapshot hash.
6. generated_at does not affect snapshot hash.
7. Approved applicability versions, condition groups, and conditions are included.
8. Non-approved (draft/rejected/in_review/retired) applicability versions are excluded.
9. Snapshot manifest counts match actual data.
10. Sync operation serializes deterministically and calculates content hash.
11. Sync acknowledgement validates and serializes correctly.
12. Sync conflict model validates classification and references.
13. Sync manifest validates structure and acknowledgements.
14. SyncStatus is distinct and orthogonal to InspectionStatus.
15. Client owner/user identity cannot be represented as trusted authority in OfflineInspectionMetadata.
16. Snapshot comparison supports MATCHED, STALE, and UNKNOWN with appropriate revalidation flags.
"""

from datetime import datetime, timezone
import pytest

from backend.app.services.verification.models import VerificationStatus
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.offline_sync.models import (
    EvaluationMetadata,
    EvaluationMode,
    LegalSnapshotManifest,
    LegalSnapshotValidationResult,
    LegalSnapshotValidationStatus,
    OfflineInspectionMetadata,
    SyncAckStatus,
    SyncAcknowledgement,
    SyncConflict,
    SyncConflictClassification,
    SyncEntityType,
    SyncManifest,
    SyncOperation,
    SyncOperationType,
    SyncStatus,
)
from backend.app.services.offline_sync.snapshot import (
    LegalSnapshotBuilder,
    LegalSnapshotValidator,
)


# =====================================================================
# 1. EvaluationMode & EvaluationMetadata Tests
# =====================================================================
def test_evaluation_mode_enum_values():
    """Verify EvaluationMode contains exactly the three specified modes."""
    modes = {m.value for m in EvaluationMode}
    assert modes == {"ONLINE", "OFFLINE_DETERMINISTIC", "SERVER_REVALIDATED"}
    assert len(EvaluationMode) == 3


def test_evaluation_metadata_serialization_roundtrip():
    """Verify EvaluationMetadata serializes and deserializes accurately with timezone awareness."""
    meta = EvaluationMetadata(
        evaluation_mode=EvaluationMode.OFFLINE_DETERMINISTIC,
        revalidation_required=True,
        engine_version="1.5.0",
        legal_snapshot_id="sha256-snapshot-xyz",
        metadata={"custom_flag": True},
    )
    d = meta.to_dict()
    assert d["evaluation_mode"] == "OFFLINE_DETERMINISTIC"
    assert d["revalidation_required"] is True
    assert d["engine_version"] == "1.5.0"
    assert d["legal_snapshot_id"] == "sha256-snapshot-xyz"
    assert d["metadata"]["custom_flag"] is True

    reconstituted = EvaluationMetadata.from_dict(d)
    assert reconstituted.evaluation_mode == EvaluationMode.OFFLINE_DETERMINISTIC
    assert reconstituted.revalidation_required is True
    assert reconstituted.evaluated_at.tzinfo is not None


# =====================================================================
# 2. Canonical Compliance Statuses Test
# =====================================================================
def test_canonical_compliance_statuses_unmodified():
    """Verify canonical compliance statuses remain exactly PASS, FAIL, NOT_VISIBLE, NOT_APPLICABLE, REVIEW_REQUIRED."""
    statuses = {s.value for s in VerificationStatus}
    assert statuses == {"PASS", "FAIL", "NOT_VISIBLE", "NOT_APPLICABLE", "REVIEW_REQUIRED"}
    # Verify no pseudo-statuses exist
    assert "PROVISIONAL_PASS" not in statuses
    assert "PROVISIONAL_FAIL" not in statuses
    assert "OFFLINE_PASS" not in statuses
    assert "OFFLINE_FAIL" not in statuses


def test_snapshot_manifest_serialization_roundtrip():
    """Verify LegalSnapshotManifest serializes and deserializes cleanly."""
    manifest = LegalSnapshotManifest(
        legal_snapshot_id="snapshot-12345",
        document_count=5,
        provision_count=10,
        requirement_count=15,
        schedule_count=2,
        schedule_entry_count=8,
        table_count=3,
        amendment_count=1,
        approved_applicability_rule_version_count=4,
        serialization_version="1.0.0",
    )
    d = manifest.to_dict()
    assert d["total_entity_count"] == 48
    assert d["legal_snapshot_id"] == "snapshot-12345"

    reconstituted = LegalSnapshotManifest.from_dict(d)
    assert reconstituted.total_entity_count == 48
    assert reconstituted.legal_snapshot_id == "snapshot-12345"


# =====================================================================
# 3. Deterministic Snapshot Serialization & 4. SHA-256 Stability
# =====================================================================
def test_snapshot_builder_deterministic_sha256():
    """Verify same legal data produces identical SHA-256 snapshot ID."""
    documents = [
        {"id": "doc-1", "title": "Legal Metrology Act, 2009", "act_name": "LM Act", "year": 2009, "status": "ACTIVE"},
        {"id": "doc-2", "title": "Legal Metrology (Packaged Commodities) Rules, 2011", "act_name": "PCR", "year": 2011, "status": "ACTIVE"},
    ]
    provisions = [
        {"id": "prov-1", "document_id": "doc-2", "rule_number": "Rule 6", "title": "Declarations on package", "status": "ACTIVE"},
    ]
    requirements = [
        {"id": "req-1", "provision_id": "prov-1", "requirement_code": "REQ_MRP", "description": "Maximum Retail Price inclusive of all taxes", "status": "ACTIVE"},
    ]

    snapshot_id_1, manifest_1, canonical_json_1 = LegalSnapshotBuilder.build_snapshot(
        documents=documents,
        provisions=provisions,
        requirements=requirements,
    )

    snapshot_id_2, manifest_2, canonical_json_2 = LegalSnapshotBuilder.build_snapshot(
        documents=documents,
        provisions=provisions,
        requirements=requirements,
    )

    assert snapshot_id_1 == snapshot_id_2
    assert canonical_json_1 == canonical_json_2
    assert len(snapshot_id_1) == 64  # Valid SHA-256 hex length
    assert manifest_1.legal_snapshot_id == snapshot_id_1


# =====================================================================
# 5. Entity Reordering Stability
# =====================================================================
def test_snapshot_builder_order_invariance():
    """Verify input order permutation does not alter the generated snapshot ID."""
    docs_ordered = [
        {"id": "doc-a", "title": "Document A", "status": "ACTIVE"},
        {"id": "doc-b", "title": "Document B", "status": "ACTIVE"},
        {"id": "doc-c", "title": "Document C", "status": "ACTIVE"},
    ]
    docs_reversed = list(reversed(docs_ordered))
    docs_shuffled = [docs_ordered[1], docs_ordered[2], docs_ordered[0]]

    id_1, _, _ = LegalSnapshotBuilder.build_snapshot(documents=docs_ordered)
    id_2, _, _ = LegalSnapshotBuilder.build_snapshot(documents=docs_reversed)
    id_3, _, _ = LegalSnapshotBuilder.build_snapshot(documents=docs_shuffled)

    assert id_1 == id_2
    assert id_2 == id_3


# =====================================================================
# 6. generated_at Exclusion from Hash
# =====================================================================
def test_generated_at_does_not_affect_snapshot_hash():
    """Verify manifest generated_at timestamp is informational and excluded from hash computation."""
    docs = [{"id": "doc-1", "title": "Standard Rules", "status": "ACTIVE"}]

    snapshot_id, manifest, canonical_json = LegalSnapshotBuilder.build_snapshot(documents=docs)

    manifest_a = LegalSnapshotManifest(
        legal_snapshot_id=snapshot_id,
        document_count=1,
        generated_at="2026-01-01T00:00:00+00:00",
    )
    manifest_b = LegalSnapshotManifest(
        legal_snapshot_id=snapshot_id,
        document_count=1,
        generated_at="2026-10-04T12:00:00+00:00",
    )

    # Hash depends only on canonical content, not manifest timestamp
    assert manifest_a.legal_snapshot_id == manifest_b.legal_snapshot_id
    assert "generated_at" not in canonical_json


# =====================================================================
# 7 & 8. Approved vs Non-Approved Applicability Filtering
# =====================================================================
def test_applicability_filtering_approved_only():
    """Verify only APPROVED or ACTIVE applicability rules are included; DRAFT/RETIRED/REJECTED are filtered out."""
    rule_versions = [
        {"id": "rv-1", "rule_id": "r-1", "status": "APPROVED", "version_number": 1, "description": "Approved Rule V1"},
        {"id": "rv-2", "rule_id": "r-2", "status": "DRAFT", "version_number": 1, "description": "Draft Rule"},
        {"id": "rv-3", "rule_id": "r-3", "status": "REJECTED", "version_number": 1, "description": "Rejected Rule"},
        {"id": "rv-4", "rule_id": "r-4", "status": "IN_REVIEW", "version_number": 1, "description": "In Review Rule"},
        {"id": "rv-5", "rule_id": "r-5", "status": "RETIRED", "version_number": 1, "description": "Retired Rule"},
        {"id": "rv-6", "rule_id": "r-6", "status": "ACTIVE", "version_number": 2, "description": "Active Rule V2"},
    ]

    condition_groups = [
        {"id": "cg-1", "rule_version_id": "rv-1", "group_type": "ALL"},
        {"id": "cg-2", "rule_version_id": "rv-2", "group_type": "ALL"},  # Associated with draft rule
    ]

    conditions = [
        {"id": "c-1", "condition_group_id": "cg-1", "field": "category", "operator": "EQUALS", "value": "packaged_commodity"},
        {"id": "c-2", "condition_group_id": "cg-2", "field": "brand", "operator": "EQUALS", "value": "test"},
    ]

    snapshot_id, manifest, canonical_json = LegalSnapshotBuilder.build_snapshot(
        applicability_rule_versions=rule_versions,
        applicability_condition_groups=condition_groups,
        applicability_conditions=conditions,
    )

    # Only rv-1 and rv-6 are approved/active
    assert manifest.approved_applicability_rule_version_count == 2
    assert manifest.approved_condition_group_count == 1
    assert manifest.approved_condition_count == 1

    assert "Approved Rule V1" in canonical_json
    assert "Active Rule V2" in canonical_json
    assert "Draft Rule" not in canonical_json
    assert "Rejected Rule" not in canonical_json
    assert "In Review Rule" not in canonical_json
    assert "Retired Rule" not in canonical_json


# =====================================================================
# 9. Manifest Count Accuracy
# =====================================================================
def test_manifest_counts_match_actual_data():
    """Verify all manifest entity counts precisely match authoritative data elements."""
    docs = [{"id": "d1"}, {"id": "d2"}]
    provs = [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}]
    reqs = [{"id": "r1"}]
    scheds = [{"id": "s1"}]
    sched_entries = [{"id": "se1"}, {"id": "se2"}]
    tables = [{"id": "t1"}]
    amendments = [{"id": "a1"}, {"id": "a2"}]
    rules = [{"id": "rv1", "status": "APPROVED"}]

    snapshot_id, manifest, _ = LegalSnapshotBuilder.build_snapshot(
        documents=docs,
        provisions=provs,
        requirements=reqs,
        schedules=scheds,
        schedule_entries=sched_entries,
        tables=tables,
        amendments=amendments,
        applicability_rule_versions=rules,
    )

    assert manifest.document_count == 2
    assert manifest.provision_count == 3
    assert manifest.requirement_count == 1
    assert manifest.schedule_count == 1
    assert manifest.schedule_entry_count == 2
    assert manifest.table_count == 1
    assert manifest.amendment_count == 2
    assert manifest.approved_applicability_rule_version_count == 1
    assert manifest.total_entity_count == 13


# =====================================================================
# 10. Sync Operation Serialization & Content Hashing
# =====================================================================
def test_sync_operation_serialization():
    """Verify SyncOperation models are serializable, type-safe, and compute content hashes."""
    payload = {"commodity_type": "food", "net_quantity": "500g"}
    content_hash = SyncOperation.compute_content_hash(payload)

    op = SyncOperation(
        operation_id="op-12345",
        inspection_id="insp-999",
        entity_type=SyncEntityType.EVIDENCE,
        entity_id="ev-888",
        operation_type=SyncOperationType.CREATE,
        content_hash=content_hash,
        created_at="2026-10-04T12:00:00+00:00",
        sequence=1,
        dependency_ids=["op-10000"],
        payload=payload,
    )

    d = op.to_dict()
    assert d["operation_id"] == "op-12345"
    assert d["entity_type"] == "EVIDENCE"
    assert d["operation_type"] == "CREATE"
    assert d["content_hash"] == content_hash
    assert d["dependency_ids"] == ["op-10000"]

    reconstituted = SyncOperation.from_dict(d)
    assert reconstituted.operation_id == op.operation_id
    assert reconstituted.entity_type == SyncEntityType.EVIDENCE
    assert reconstituted.payload == payload


# =====================================================================
# 11. Sync Acknowledgement Validation
# =====================================================================
def test_sync_acknowledgement_validation():
    """Verify SyncAcknowledgement serialization and status values."""
    ack = SyncAcknowledgement(
        operation_id="op-1",
        entity_id="ent-1",
        status=SyncAckStatus.ACKNOWLEDGED,
        server_timestamp="2026-10-04T12:00:01+00:00",
        server_version="1.2.0",
    )
    d = ack.to_dict()
    assert d["status"] == "ACKNOWLEDGED"
    assert d["server_version"] == "1.2.0"

    ack_rejected = SyncAcknowledgement(
        operation_id="op-2",
        entity_id="ent-2",
        status=SyncAckStatus.REJECTED,
        error_code="INVALID_PAYLOAD",
        error_message="Missing required fields",
    )
    assert ack_rejected.status == SyncAckStatus.REJECTED
    assert ack_rejected.error_code == "INVALID_PAYLOAD"


# =====================================================================
# 12. Sync Conflict Validation
# =====================================================================
def test_sync_conflict_validation():
    """Verify SyncConflict captures conflict classifications and state references."""
    conflict = SyncConflict(
        conflict_id="conf-1",
        inspection_id="insp-1",
        entity_type=SyncEntityType.REQUIREMENT_RESULT,
        entity_id="res-1",
        classification=SyncConflictClassification.MUST_REVALIDATE,
        code="RULE_VERSION_MISMATCH",
        message="Client evaluated with older snapshot",
        server_state_reference={"snapshot_id": "snap-new"},
        client_state_reference={"snapshot_id": "snap-old"},
    )
    d = conflict.to_dict()
    assert d["classification"] == "MUST_REVALIDATE"
    assert d["server_state_reference"]["snapshot_id"] == "snap-new"


# =====================================================================
# 13. Sync Manifest Validation
# =====================================================================
def test_sync_manifest_validation():
    """Verify SyncManifest links lifecycle status, sync status, and acknowledgements."""
    eval_meta = EvaluationMetadata(
        evaluation_mode=EvaluationMode.OFFLINE_DETERMINISTIC,
        revalidation_required=True,
        engine_version="1.0.0",
        legal_snapshot_id="sha256-dummy",
    )
    ack = SyncAcknowledgement(
        operation_id="op-1",
        entity_id="img-1",
        status=SyncAckStatus.ACKNOWLEDGED,
    )
    manifest = SyncManifest(
        inspection_id="insp-1",
        lifecycle_status=InspectionStatus.COMPLETED.value,
        sync_status=SyncStatus.SYNCED,
        entity_acknowledgements=[ack],
        image_hashes={"img-1": "hash123"},
        legal_snapshot_id="sha256-dummy",
        evaluation_metadata=eval_meta,
    )
    d = manifest.to_dict()
    assert d["lifecycle_status"] == "COMPLETED"
    assert d["sync_status"] == "SYNCED"
    assert len(d["entity_acknowledgements"]) == 1
    assert d["evaluation_metadata"]["evaluation_mode"] == "OFFLINE_DETERMINISTIC"


# =====================================================================
# 14. Sync Status Orthogonality to InspectionStatus
# =====================================================================
def test_sync_status_orthogonal_to_inspection_status():
    """Verify SyncStatus values are distinct and orthogonal to InspectionStatus values."""
    sync_statuses = {s.value for s in SyncStatus}
    inspection_statuses = {s.value for s in InspectionStatus}

    # No overlapping values
    intersection = sync_statuses.intersection(inspection_statuses)
    assert len(intersection) == 0

    assert sync_statuses == {
        "DRAFT_LOCAL",
        "SYNC_PENDING",
        "SYNCING",
        "SYNCED",
        "SYNC_FAILED",
        "REVALIDATION_REQUIRED",
        "REVALIDATED",
    }


# =====================================================================
# 15. Security: Client Identity Trust Boundary
# =====================================================================
def test_offline_inspection_metadata_does_not_trust_client_identity():
    """Verify OfflineInspectionMetadata does not store or accept trusted user_id/owner_id/role parameters."""
    meta = OfflineInspectionMetadata(
        inspection_id="insp-100",
        client_created_at="2026-10-04T12:00:00+00:00",
        device_id="device-xyz",
        legal_snapshot_id="snapshot-abc",
        evaluation_mode=EvaluationMode.OFFLINE_DETERMINISTIC,
        revalidation_required=True,
    )

    d = meta.to_dict()
    # Contract does not expose or trust owner_id or user_id
    assert "owner_id" not in d
    assert "user_id" not in d
    assert "role" not in d
    assert d["device_id"] == "device-xyz"
    assert d["revalidation_required"] is True


# =====================================================================
# 16. Legal Snapshot Validator: MATCHED / STALE / UNKNOWN
# =====================================================================
def test_legal_snapshot_validator_states():
    """Verify LegalSnapshotValidator accurately returns MATCHED, STALE, and UNKNOWN with proper flags."""
    active_snapshot = "active-snap-sha256"
    historical_snapshots = {"past-snap-1", "past-snap-2"}

    # Case 1: MATCHED
    res_matched = LegalSnapshotValidator.validate_snapshot(
        client_snapshot_id="active-snap-sha256",
        server_active_snapshot_id=active_snapshot,
        historical_snapshot_ids=historical_snapshots,
    )
    assert res_matched.status == LegalSnapshotValidationStatus.MATCHED
    assert res_matched.is_valid_for_evaluation is True
    assert res_matched.requires_server_revalidation is False

    # Case 2: STALE
    res_stale = LegalSnapshotValidator.validate_snapshot(
        client_snapshot_id="past-snap-1",
        server_active_snapshot_id=active_snapshot,
        historical_snapshot_ids=historical_snapshots,
    )
    assert res_stale.status == LegalSnapshotValidationStatus.STALE
    assert res_stale.is_valid_for_evaluation is False
    assert res_stale.requires_server_revalidation is True

    # Case 3: UNKNOWN
    res_unknown = LegalSnapshotValidator.validate_snapshot(
        client_snapshot_id="foreign-or-fabricated-id",
        server_active_snapshot_id=active_snapshot,
        historical_snapshot_ids=historical_snapshots,
    )
    assert res_unknown.status == LegalSnapshotValidationStatus.UNKNOWN
    assert res_unknown.is_valid_for_evaluation is False
    assert res_unknown.requires_server_revalidation is True
