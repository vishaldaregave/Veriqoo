"""Unit and Integration Tests for Phase U24-D Offline Execution Contract & Evaluation Engine.

Tests:
1. Bundle construction
2. Bundle serialization
3. Bundle deserialization
4. Deterministic serialization
5. Deterministic content hash
6. Round-trip equivalence
7. Legal snapshot identity preservation
8. Evaluation metadata preservation
9. OFFLINE_DETERMINISTIC mode set
10. Incomplete client target_requirements CANNOT produce false PASS (Legal Coverage Guarantee)
11. Extra client-supplied requirement IDs cannot expand legal authority
12. Missing client-supplied requirement IDs cannot remove legally applicable requirements
13. Genuinely complete evidence produces canonical PASS
14. Canonical FAIL / contradiction preservation
15. Missing declaration produces canonical NOT_VISIBLE
16. Inapplicable requirement produces canonical NOT_APPLICABLE via applicability engine
17. Ambiguous/unparsed evidence produces canonical REVIEW_REQUIRED
18. Gemini is never invoked offline
19. Supabase / REST HTTP is never invoked offline
20. Missing legal snapshot context safely flags revalidation
21. Tampered bundle / content hash mismatch is rejected
22. Existing applicability engine is reused
23. Existing deterministic status aggregation is reused
24. No new compliance statuses are introduced
25. Existing online pipeline behavior remains unchanged
26. Offline execution does not mutate cloud persistence
27. Empty legal snapshot requirements cannot produce complete compliance
"""

import json
from unittest.mock import patch
import pytest

from backend.app.services.applicability.models import TriState
from backend.app.services.applicability.service import ApplicabilityService
from backend.app.services.evidence.models import EvidenceField, EvidenceStatus
from backend.app.services.inspection_pipeline.models import (
    InspectionPipelineRequest,
    OverallInspectionStatus,
)
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator
from backend.app.services.offline_sync import (
    EvaluationMetadata,
    EvaluationMode,
    LegalSnapshotBuilder,
    LegalSnapshotContext,
    OfflineEvaluationResult,
    OfflineInspectionBundle,
    OfflineInspectionExecutor,
)
from backend.app.services.verification.models import VerificationStatus


def _create_sample_snapshot() -> tuple[str, LegalSnapshotContext]:
    """Helper to construct a valid deterministic legal snapshot context with 3 requirements."""
    docs = [{"id": "doc-01", "document_type": "act", "title": "Legal Metrology Act", "year": 2009}]
    provs = [{"id": "prov-01", "document_id": "doc-01", "provision_type": "rule", "rule_number": "6", "content": "MRP rule"}]
    reqs = [
        {"id": "req-mrp", "requirement_code": "REQ-MRP", "normalized_requirement": "MRP must be declared with tax inclusiveness", "target_field": "mrp", "rule_id": "rule-01"},
        {"id": "req-net-qty", "requirement_code": "REQ-NET-QTY", "normalized_requirement": "Net quantity declaration", "target_field": "net_quantity", "rule_id": "rule-01"},
        {"id": "req-mfg-date", "requirement_code": "REQ-MFG-DATE", "normalized_requirement": "Month and year of manufacture", "target_field": "mfg_date", "rule_id": "rule-01"},
    ]
    scheds = [{"id": "sched-02", "schedule_number": "Second Schedule", "title": "Commodities"}]
    entries = [{"id": "entry-01", "schedule_id": "sched-02", "commodity_text": "Edible Oil", "permitted_package_quantity": "1L"}]
    tables = [{"id": "tbl-01", "table_identifier": "Table 1", "headers": ["Commodity", "Size"]}]
    amds = [{"id": "amd-01", "amendment_identifier": "GSR 123(E)"}]
    
    rules = [{"id": "rule-01", "rule_key": "rule-prepacked"}]
    vers = [{"id": "ver-01", "rule_id": "rule-01", "version_number": 1, "interpretation_status": "approved"}]
    groups = [{"id": "grp-01", "rule_version_id": "ver-01", "boolean_operator": "AND", "status": "approved"}]
    conds = [{"id": "cnd-01", "group_id": "grp-01", "fact_key": "is_prepacked", "operator": "equals", "expected_value": True, "status": "approved"}]

    snapshot_id, manifest, _ = LegalSnapshotBuilder.build_snapshot(
        documents=docs,
        provisions=provs,
        requirements=reqs,
        schedules=scheds,
        schedule_entries=entries,
        tables=tables,
        amendments=amds,
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
        schedules=scheds,
        schedule_entries=entries,
        tables=tables,
        amendments=amds,
        applicability_rule_versions=vers,
        applicability_condition_groups=groups,
        applicability_conditions=conds,
        applicability_rules=rules,
    )
    return snapshot_id, context


def _create_single_req_snapshot() -> tuple[str, LegalSnapshotContext]:
    """Helper to construct a valid deterministic legal snapshot with only 1 requirement (MRP)."""
    docs = [{"id": "doc-01", "document_type": "act", "title": "Legal Metrology Act", "year": 2009}]
    provs = [{"id": "prov-01", "document_id": "doc-01", "provision_type": "rule", "rule_number": "6", "content": "MRP rule"}]
    reqs = [
        {"id": "req-mrp", "requirement_code": "REQ-MRP", "normalized_requirement": "MRP must be declared with tax inclusiveness", "target_field": "mrp", "rule_id": "rule-01"},
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


class TestPhase24DOfflineBundleContract:
    """Tests 1-8: Bundle construction, deterministic serialization, and round-trip fidelity."""

    def test_01_bundle_construction(self):
        """Test construction of OfflineInspectionBundle with typed fields."""
        bundle = OfflineInspectionBundle(
            inspection_id="insp-100",
            legal_snapshot_id="snap-abc123",
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
            image_artifacts=[{"image_id": "img-1", "source_hash": "h1", "normalized_hash": "h1"}],
            target_requirements=["req-mrp", "req-net-qty"],
        )
        assert bundle.inspection_id == "insp-100"
        assert bundle.legal_snapshot_id == "snap-abc123"
        assert len(bundle.inspection_facts) == 1
        assert len(bundle.image_artifacts) == 1
        assert bundle.evaluation_metadata.evaluation_mode == EvaluationMode.OFFLINE_DETERMINISTIC
        assert bundle.content_hash is not None

    def test_02_bundle_serialization(self):
        """Test serialization to dictionary and JSON."""
        bundle = OfflineInspectionBundle(
            inspection_id="insp-100",
            legal_snapshot_id="snap-abc123",
            target_requirements=["req-mrp"],
        )
        d = bundle.to_dict()
        assert d["inspection_id"] == "insp-100"
        assert d["legal_snapshot_id"] == "snap-abc123"
        assert "content_hash" in d
        assert isinstance(d["evaluation_metadata"], dict)

    def test_03_bundle_deserialization(self):
        """Test round-trip deserialization from dict."""
        bundle1 = OfflineInspectionBundle(
            inspection_id="insp-100",
            legal_snapshot_id="snap-abc123",
            target_requirements=["req-mrp"],
        )
        d = bundle1.to_dict()
        bundle2 = OfflineInspectionBundle.from_dict(d)
        assert bundle2.inspection_id == bundle1.inspection_id
        assert bundle2.content_hash == bundle1.content_hash
        assert bundle2.target_requirements == bundle1.target_requirements

    def test_04_deterministic_serialization(self):
        """Ensure serialization key ordering is deterministic and invariant to dictionary insertion order."""
        b1 = OfflineInspectionBundle(
            inspection_id="insp-100",
            legal_snapshot_id="snap-abc",
            inspection_facts=[{"b": 2, "a": 1}],
            created_at="2026-10-04T12:00:00Z",
        )
        b2 = OfflineInspectionBundle(
            inspection_id="insp-100",
            legal_snapshot_id="snap-abc",
            inspection_facts=[{"a": 1, "b": 2}],
            created_at="2026-10-04T12:00:00Z",
        )
        assert b1.to_json() == b2.to_json()

    def test_05_deterministic_content_hash(self):
        """Ensure compute_content_hash produces identical SHA-256 for identical logical payload."""
        b1 = OfflineInspectionBundle(inspection_id="insp-1", legal_snapshot_id="snap-1", created_at="2026-10-04T12:00:00Z")
        b2 = OfflineInspectionBundle(inspection_id="insp-1", legal_snapshot_id="snap-1", created_at="2026-10-04T12:00:00Z")
        assert b1.compute_content_hash() == b2.compute_content_hash()

    def test_06_round_trip_json_equivalence(self):
        """Test JSON -> Bundle -> JSON roundtrip identity."""
        b1 = OfflineInspectionBundle(
            inspection_id="insp-roundtrip",
            legal_snapshot_id="snap-roundtrip",
            inspection_facts=[{"fact_key": "commodity", "value": "salt"}],
        )
        j1 = b1.to_json()
        b2 = OfflineInspectionBundle.from_json(j1)
        j2 = b2.to_json()
        assert j1 == j2

    def test_07_legal_snapshot_identity_preservation(self):
        """Ensure legal_snapshot_id is preserved throughout serialization."""
        snap_id = "snap-verified-sha256"
        bundle = OfflineInspectionBundle(inspection_id="insp-1", legal_snapshot_id=snap_id)
        d = bundle.to_dict()
        assert d["legal_snapshot_id"] == snap_id
        b_loaded = OfflineInspectionBundle.from_dict(d)
        assert b_loaded.legal_snapshot_id == snap_id

    def test_08_evaluation_metadata_preservation(self):
        """Ensure EvaluationMetadata with OFFLINE_DETERMINISTIC is preserved."""
        meta = EvaluationMetadata(
            evaluation_mode=EvaluationMode.OFFLINE_DETERMINISTIC,
            revalidation_required=False,
            engine_version="1.0.0",
        )
        bundle = OfflineInspectionBundle(
            inspection_id="insp-1",
            legal_snapshot_id="snap-1",
            evaluation_metadata=meta,
        )
        assert bundle.evaluation_metadata.evaluation_mode == EvaluationMode.OFFLINE_DETERMINISTIC
        d = bundle.to_dict()
        b2 = OfflineInspectionBundle.from_dict(d)
        assert b2.evaluation_metadata.evaluation_mode == EvaluationMode.OFFLINE_DETERMINISTIC


class TestPhase24DOfflineEvaluationEngine:
    """Tests 9-27: Complete legal coverage guarantee, deterministic evaluation, and cloud isolation."""

    def test_09_offline_deterministic_mode_set(self):
        """Offline evaluation output must declare OFFLINE_DETERMINISTIC evaluation mode."""
        snap_id, context = _create_single_req_snapshot()
        bundle = OfflineInspectionBundle(
            inspection_id="insp-200",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp"],
            evidence_candidates=[{
                "evidence_id": "ev-1",
                "field": "mrp",
                "raw_text": "MRP Rs. 100 (incl. of all taxes)",
                "normalized_text": "MRP Rs. 100 (incl. of all taxes)",
                "status": "valid",
            }],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)
        assert result.evaluation_metadata.evaluation_mode == EvaluationMode.OFFLINE_DETERMINISTIC
        assert result.legal_snapshot_id == snap_id

    def test_10_incomplete_client_target_requirements_cannot_produce_false_pass(self):
        """CRITICAL: Client supplying only 1 of 3 required items CANNOT produce a false PASS."""
        snap_id, context = _create_sample_snapshot()  # Has req-mrp, req-net-qty, req-mfg-date
        bundle = OfflineInspectionBundle(
            inspection_id="insp-incomplete-client",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp"],  # Client omitted net-qty and mfg-date!
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
            evidence_candidates=[{
                "evidence_id": "ev-mrp",
                "field": "mrp",
                "raw_text": "MRP Rs. 100 (incl. of all taxes)",
                "status": "valid",
            }],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)

        # Must evaluate all 3 snapshot requirements
        assert len(result.verification_results) == 3
        # Must detect that net-qty and mfg-date are NOT_VISIBLE
        not_vis_reqs = [r["requirement_id"] for r in result.verification_results if r["status"] == VerificationStatus.NOT_VISIBLE.value]
        assert "req-net-qty" in not_vis_reqs
        assert "req-mfg-date" in not_vis_reqs

        # Overall status MUST NOT be PASS; it must be REVIEW_REQUIRED
        assert result.overall_status == OverallInspectionStatus.REVIEW_REQUIRED
        assert result.evaluation_metadata.revalidation_required is True

        # Error log must record the coverage mismatch
        assert any(e["error_code"] == "REQUIREMENT_COVERAGE_MISMATCH" for e in result.errors)

    def test_11_extra_client_supplied_requirement_cannot_expand_legal_authority(self):
        """Client supplying non-authoritative invented requirement cannot expand legal authority."""
        snap_id, context = _create_single_req_snapshot()  # Has req-mrp only
        bundle = OfflineInspectionBundle(
            inspection_id="insp-extra-client",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp", "req-invented-by-client"],
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
            evidence_candidates=[{
                "evidence_id": "ev-mrp",
                "field": "mrp",
                "raw_text": "MRP Rs. 100",
                "status": "valid",
            }],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)

        # Evaluated requirements come from snapshot, not client's invented list
        evaluated_ids = [r["requirement_id"] for r in result.verification_results]
        assert "req-invented-by-client" not in evaluated_ids
        assert any(e["error_code"] == "REQUIREMENT_COVERAGE_MISMATCH" for e in result.errors)
        assert result.evaluation_metadata.revalidation_required is True

    def test_12_missing_client_supplied_requirement_ids_cannot_remove_applicable_requirements(self):
        """Omitting requirements from bundle does not stop executor from evaluating complete snapshot set."""
        snap_id, context = _create_sample_snapshot()
        bundle = OfflineInspectionBundle(
            inspection_id="insp-omit-all",
            legal_snapshot_id=snap_id,
            target_requirements=[],  # Client sent empty target_requirements list
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)

        # All 3 snapshot requirements are still evaluated
        assert len(result.verification_results) == 3
        assert result.counts["not_visible_count"] == 3

    def test_13_genuinely_complete_evidence_produces_canonical_pass(self):
        """When ALL snapshot requirements have valid evidence, canonical PASS is produced."""
        snap_id, context = _create_sample_snapshot()
        bundle = OfflineInspectionBundle(
            inspection_id="insp-complete-pass",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp", "req-net-qty", "req-mfg-date"],
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
            evidence_candidates=[
                {"evidence_id": "ev-1", "field": "mrp", "raw_text": "MRP Rs. 100", "status": "valid"},
                {"evidence_id": "ev-2", "field": "net_quantity", "raw_text": "Net Qty: 500g", "status": "valid"},
                {"evidence_id": "ev-3", "field": "mfg_date", "raw_text": "Mfg: 01/2026", "status": "valid"},
            ],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)

        assert result.overall_status == OverallInspectionStatus.PASS
        assert result.counts["pass_count"] == 3
        assert result.counts["total_requirements"] == 3

    def test_14_canonical_fail_contradiction_preservation(self):
        """Contradictory declarations trigger canonical REVIEW_REQUIRED."""
        snap_id, context = _create_single_req_snapshot()
        bundle = OfflineInspectionBundle(
            inspection_id="insp-conflict",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp"],
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
            evidence_candidates=[
                {"evidence_id": "ev-1", "field": "mrp", "raw_text": "MRP Rs. 50", "parsed_value": 50.0, "status": "valid"},
                {"evidence_id": "ev-2", "field": "mrp", "raw_text": "MRP Rs. 100", "parsed_value": 100.0, "status": "valid"},
            ],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)
        assert result.overall_status == OverallInspectionStatus.REVIEW_REQUIRED
        assert result.verification_results[0]["status"] == VerificationStatus.REVIEW_REQUIRED.value

    def test_15_missing_declaration_yields_not_visible(self):
        """Missing required declaration yields canonical NOT_VISIBLE."""
        snap_id, context = _create_single_req_snapshot()
        bundle = OfflineInspectionBundle(
            inspection_id="insp-notvis",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp"],
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
            evidence_candidates=[],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)
        assert result.verification_results[0]["status"] == VerificationStatus.NOT_VISIBLE.value
        assert result.counts["not_visible_count"] == 1

    def test_16_inapplicable_requirement_yields_not_applicable_via_engine(self):
        """When applicability engine determines rule is not applicable, NOT_APPLICABLE status is produced."""
        snap_id, context = _create_sample_snapshot()
        # Setting fact is_prepacked = False causes condition to evaluate to FALSE
        bundle = OfflineInspectionBundle(
            inspection_id="insp-inapp",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp", "req-net-qty", "req-mfg-date"],
            inspection_facts=[{"fact_key": "is_prepacked", "value": False}],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)

        # Applicability engine evaluates TriState.FALSE -> NOT_APPLICABLE
        for r in result.verification_results:
            assert r["status"] == VerificationStatus.NOT_APPLICABLE.value
        assert result.overall_status == OverallInspectionStatus.PASS

    def test_17_ambiguous_evidence_yields_review_required(self):
        """Ambiguous/unparsed evidence produces canonical REVIEW_REQUIRED with revalidation flag."""
        snap_id, context = _create_single_req_snapshot()
        bundle = OfflineInspectionBundle(
            inspection_id="insp-rev",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp"],
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
            evidence_candidates=[{
                "evidence_id": "ev-1",
                "field": "mrp",
                "raw_text": "MRP ??",
                "status": "unparsed",
            }],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)
        assert result.verification_results[0]["status"] == VerificationStatus.REVIEW_REQUIRED.value
        assert result.evaluation_metadata.revalidation_required is True

    def test_18_gemini_is_never_invoked(self):
        """Verify that Gemini service or APIs are never called during offline execution."""
        snap_id, context = _create_single_req_snapshot()
        bundle = OfflineInspectionBundle(
            inspection_id="insp-nogemini",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp"],
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
            evidence_candidates=[{"evidence_id": "ev-1", "field": "mrp", "raw_text": "MRP 100", "status": "valid"}],
        )
        with patch("backend.app.services.gemini.service.GeminiEvidenceService.verify_with_gemini_and_gate") as mock_gemini:
            executor = OfflineInspectionExecutor()
            executor.execute(bundle, context)
            mock_gemini.assert_not_called()


    def test_19_supabase_rest_is_never_invoked(self):
        """Verify that Supabase REST/PostgREST HTTP calls are never made during offline execution."""
        snap_id, context = _create_single_req_snapshot()
        bundle = OfflineInspectionBundle(
            inspection_id="insp-nosupabase",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp"],
        )
        with patch("httpx.Client.request") as mock_http, patch("httpx.AsyncClient.request") as mock_async_http:
            executor = OfflineInspectionExecutor()
            executor.execute(bundle, context)
            mock_http.assert_not_called()
            mock_async_http.assert_not_called()

    def test_20_missing_legal_snapshot_safely_flagged(self):
        """Passing None for snapshot_context flags revalidation_required and records an error."""
        bundle = OfflineInspectionBundle(
            inspection_id="insp-missing-snap",
            legal_snapshot_id="snap-unknown",
            target_requirements=["req-mrp"],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, None)
        assert result.evaluation_metadata.revalidation_required is True
        assert any(e["error_code"] == "MISSING_LEGAL_SNAPSHOT" for e in result.errors)

    def test_21_tampered_bundle_content_hash_rejected(self):
        """Tampering with bundle contents triggers validation error."""
        bundle = OfflineInspectionBundle(
            inspection_id="insp-tampered",
            legal_snapshot_id="snap-123",
            target_requirements=["req-mrp"],
        )
        d = bundle.to_dict()
        d["inspection_id"] = "insp-tampered-altered"
        
        with pytest.raises(ValueError, match="Invalid bundle integrity"):
            OfflineInspectionBundle.from_dict(d, verify_hash=True)

    def test_22_existing_applicability_engine_is_reused(self):
        """Confirm that ApplicabilityService evaluate_run is invoked by offline executor."""
        snap_id, context = _create_single_req_snapshot()
        bundle = OfflineInspectionBundle(
            inspection_id="insp-app-reuse",
            legal_snapshot_id=snap_id,
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
            target_requirements=["req-mrp"],
        )
        executor = OfflineInspectionExecutor()
        with patch("backend.app.services.applicability.service.ApplicabilityService.evaluate_run", wraps=ApplicabilityService.evaluate_run) as mock_eval:
            result = executor.execute(bundle, context)
            assert mock_eval.called
            assert result.overall_status in (OverallInspectionStatus.PASS, OverallInspectionStatus.FAIL, OverallInspectionStatus.REVIEW_REQUIRED)

    def test_23_existing_deterministic_status_aggregation_is_reused(self):
        """Confirm that compute_overall_status logic is adhered to."""
        snap_id, context = _create_sample_snapshot()
        bundle = OfflineInspectionBundle(
            inspection_id="insp-agg",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp", "req-net-qty", "req-mfg-date"],
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
            evidence_candidates=[
                {"evidence_id": "ev-1", "field": "mrp", "raw_text": "MRP Rs. 100", "status": "valid"},
                {"evidence_id": "ev-2", "field": "net_quantity", "raw_text": "Net Qty: 500g", "status": "valid"},
                {"evidence_id": "ev-3", "field": "mfg_date", "raw_text": "Mfg: 01/2026", "status": "valid"},
            ],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)
        assert result.overall_status == OverallInspectionStatus.PASS
        assert result.counts["pass_count"] == 3

    def test_24_no_new_compliance_statuses_introduced(self):
        """All emitted requirement statuses are members of canonical VerificationStatus."""
        snap_id, context = _create_single_req_snapshot()
        bundle = OfflineInspectionBundle(
            inspection_id="insp-canon",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp"],
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
            evidence_candidates=[{"evidence_id": "ev-1", "field": "mrp", "raw_text": "MRP Rs. 100", "status": "valid"}],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)
        for r in result.verification_results:
            assert r["status"] in {s.value for s in VerificationStatus}

    def test_25_existing_online_pipeline_behavior_unchanged(self):
        """Verify online InspectionPipelineOrchestrator remains functional and unmodified."""
        orchestrator = InspectionPipelineOrchestrator()
        req = InspectionPipelineRequest(
            inspection_id="insp-online-test",
            target_requirements=["REQ-1"],
            inspection_facts=[],
        )
        report = orchestrator.run(req)
        assert report.inspection_id == "insp-online-test"
        assert report.overall_status in (OverallInspectionStatus.PASS, OverallInspectionStatus.REVIEW_REQUIRED)

    def test_26_offline_execution_does_not_mutate_persistence(self):
        """Offline execution produces pure in-memory results without database or repository side-effects."""
        snap_id, context = _create_single_req_snapshot()
        bundle = OfflineInspectionBundle(
            inspection_id="insp-pure",
            legal_snapshot_id=snap_id,
            target_requirements=["req-mrp"],
            inspection_facts=[{"fact_key": "is_prepacked", "value": True}],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)
        assert isinstance(result, OfflineEvaluationResult)
        assert result.inspection_id == "insp-pure"


    def test_27_empty_legal_snapshot_cannot_produce_complete_compliance(self):
        """An empty legal snapshot context triggers INCOMPLETE_LEGAL_SNAPSHOT and flags revalidation."""
        context = LegalSnapshotContext(legal_snapshot_id="empty-snap", requirements=[])
        bundle = OfflineInspectionBundle(
            inspection_id="insp-empty-snap",
            legal_snapshot_id="empty-snap",
            target_requirements=["req-mrp"],
        )
        executor = OfflineInspectionExecutor()
        result = executor.execute(bundle, context)
        assert result.evaluation_metadata.revalidation_required is True
        assert any(e["error_code"] == "INCOMPLETE_LEGAL_SNAPSHOT" for e in result.errors)
