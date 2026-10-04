"""Server Revalidation Engine for Offline Inspections (Phase U24-F).

Executes authoritative server-side compliance revalidation:
1. Enforces authentication and inspection ownership.
2. Reconstructs evidence, observations, and facts from durable server-persisted sync operations.
3. Validates offline legal snapshot against active approved server legal context.
4. Independently evaluates applicability using pure in-memory ApplicabilityService.
5. Independently resolves complete statutory requirements (treating client target_requirements as untrusted).
6. Executes deterministic verification using DeterministicVerifier.
7. Performs structured comparison between offline deterministic results and server revalidated results.
8. Produces authoritative SERVER_REVALIDATED metadata and persists updated report state.
9. Operates 100% deterministically with zero Gemini, network, or cloud dependencies.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import threading
from typing import Any, Sequence
import uuid

from backend.app.services.applicability.models import (
    ApplicabilityCondition,
    ApplicabilityConditionGroup,
    ApplicabilityDecision,
    ApplicabilityRule,
    ApplicabilityRuleVersion,
    ApplicabilityRun,
    InspectionFact,
    TriState,
)
from backend.app.services.applicability.service import ApplicabilityService
from backend.app.services.evidence.models import EvidenceCandidate, EvidenceField, EvidenceStatus, ImageArtifact
from backend.app.services.evidence.service import EvidenceNormalizationService
from backend.app.services.inspection.errors import InspectionNotFoundError
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection.repository import InspectionRepository
from backend.app.services.inspection_pipeline.annotations import generate_evidence_annotations
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport, compute_overall_status
from backend.app.services.offline_sync.bundle import LegalSnapshotContext, OfflineInspectionBundle
from backend.app.services.offline_sync.models import (
    DurableSyncOperationRecord,
    EvaluationMetadata,
    EvaluationMode,
    LegalSnapshotValidationResult,
    LegalSnapshotValidationStatus,
    OperationStatus,
    SyncEntityType,
    SyncOperation,
    SyncOperationType,
)
from backend.app.services.offline_sync.repository import SyncOperationRepository
from backend.app.services.offline_sync.snapshot import LegalSnapshotBuilder, LegalSnapshotValidator
from backend.app.services.verification.deterministic import DeterministicVerifier
from backend.app.services.verification.models import RequirementReference, VerificationResult, VerificationStatus


def _canonical_json(data: Any) -> str:
    """Deterministic JSON string."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class RevalidationComparison:
    """Structured diagnostic comparison between client offline evaluation and authoritative server result."""

    def __init__(
        self,
        offline_overall_status: str | None,
        server_overall_status: str,
        overall_status_changed: bool,
        offline_legal_snapshot_id: str | None,
        server_legal_snapshot_id: str,
        legal_snapshot_changed: bool,
        snapshot_validation_status: str,
        offline_requirement_count: int = 0,
        server_requirement_count: int = 0,
        missing_offline_requirements: list[str] | None = None,
        extra_offline_requirements: list[str] | None = None,
        requirement_status_diffs: list[dict[str, Any]] | None = None,
        applicability_changed: bool = False,
        summary_notes: list[str] | None = None,
    ) -> None:
        self.offline_overall_status = offline_overall_status
        self.server_overall_status = str(server_overall_status)
        self.overall_status_changed = bool(overall_status_changed)
        self.offline_legal_snapshot_id = offline_legal_snapshot_id
        self.server_legal_snapshot_id = str(server_legal_snapshot_id)
        self.legal_snapshot_changed = bool(legal_snapshot_changed)
        self.snapshot_validation_status = str(snapshot_validation_status)
        self.offline_requirement_count = int(offline_requirement_count)
        self.server_requirement_count = int(server_requirement_count)
        self.missing_offline_requirements = list(missing_offline_requirements or [])
        self.extra_offline_requirements = list(extra_offline_requirements or [])
        self.requirement_status_diffs = list(requirement_status_diffs or [])
        self.applicability_changed = bool(applicability_changed)
        self.summary_notes = list(summary_notes or [])

    def to_dict(self) -> dict[str, Any]:
        """Serialize comparison to dictionary."""
        return {
            "offline_overall_status": self.offline_overall_status,
            "server_overall_status": self.server_overall_status,
            "overall_status_changed": self.overall_status_changed,
            "offline_legal_snapshot_id": self.offline_legal_snapshot_id,
            "server_legal_snapshot_id": self.server_legal_snapshot_id,
            "legal_snapshot_changed": self.legal_snapshot_changed,
            "snapshot_validation_status": self.snapshot_validation_status,
            "offline_requirement_count": self.offline_requirement_count,
            "server_requirement_count": self.server_requirement_count,
            "missing_offline_requirements": self.missing_offline_requirements,
            "extra_offline_requirements": self.extra_offline_requirements,
            "requirement_status_diffs": self.requirement_status_diffs,
            "applicability_changed": self.applicability_changed,
            "summary_notes": self.summary_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevalidationComparison:
        """Instantiate comparison from dictionary."""
        return cls(
            offline_overall_status=data.get("offline_overall_status"),
            server_overall_status=data.get("server_overall_status", "REVIEW_REQUIRED"),
            overall_status_changed=data.get("overall_status_changed", False),
            offline_legal_snapshot_id=data.get("offline_legal_snapshot_id"),
            server_legal_snapshot_id=data.get("server_legal_snapshot_id", ""),
            legal_snapshot_changed=data.get("legal_snapshot_changed", False),
            snapshot_validation_status=data.get("snapshot_validation_status", "UNKNOWN"),
            offline_requirement_count=data.get("offline_requirement_count", 0),
            server_requirement_count=data.get("server_requirement_count", 0),
            missing_offline_requirements=data.get("missing_offline_requirements"),
            extra_offline_requirements=data.get("extra_offline_requirements"),
            requirement_status_diffs=data.get("requirement_status_diffs"),
            applicability_changed=data.get("applicability_changed", False),
            summary_notes=data.get("summary_notes"),
        )


class ServerRevalidationResult:
    """Authoritative result produced by the server revalidation engine."""

    def __init__(
        self,
        inspection_id: str,
        overall_status: OverallInspectionStatus | str,
        verification_results: list[VerificationResult | dict[str, Any]],
        summary: str,
        counts: dict[str, int] | None = None,
        applicable_requirements: list[str] | None = None,
        server_legal_snapshot_id: str | None = None,
        offline_legal_snapshot_id: str | None = None,
        evaluation_metadata: EvaluationMetadata | dict[str, Any] | None = None,
        comparison: RevalidationComparison | dict[str, Any] | None = None,
        evidence_annotations: list[dict[str, Any]] | None = None,
        errors: list[dict[str, Any]] | None = None,
        revalidated_at: str | None = None,
        content_hash: str | None = None,
    ) -> None:
        self.inspection_id = str(inspection_id).strip()

        if isinstance(overall_status, OverallInspectionStatus):
            self.overall_status = overall_status
        else:
            try:
                self.overall_status = OverallInspectionStatus(str(overall_status).upper())
            except ValueError:
                self.overall_status = OverallInspectionStatus.REVIEW_REQUIRED

        self.verification_results: list[dict[str, Any]] = []
        for r in verification_results:
            if isinstance(r, VerificationResult):
                self.verification_results.append(r.to_dict())
            elif isinstance(r, dict):
                self.verification_results.append(r)

        self.summary = str(summary)
        self.applicable_requirements = list(applicable_requirements or [])
        self.server_legal_snapshot_id = str(server_legal_snapshot_id) if server_legal_snapshot_id else ""
        self.offline_legal_snapshot_id = str(offline_legal_snapshot_id) if offline_legal_snapshot_id else None

        if isinstance(evaluation_metadata, EvaluationMetadata):
            self.evaluation_metadata = evaluation_metadata
        elif isinstance(evaluation_metadata, dict):
            self.evaluation_metadata = EvaluationMetadata.from_dict(evaluation_metadata)
        else:
            self.evaluation_metadata = EvaluationMetadata(
                evaluation_mode=EvaluationMode.SERVER_REVALIDATED,
                legal_snapshot_id=self.server_legal_snapshot_id,
                revalidation_required=False,
            )

        if isinstance(comparison, RevalidationComparison):
            self.comparison = comparison
        elif isinstance(comparison, dict):
            self.comparison = RevalidationComparison.from_dict(comparison)
        else:
            self.comparison = RevalidationComparison(
                offline_overall_status=None,
                server_overall_status=self.overall_status.value,
                overall_status_changed=False,
                offline_legal_snapshot_id=self.offline_legal_snapshot_id,
                server_legal_snapshot_id=self.server_legal_snapshot_id,
                legal_snapshot_changed=False,
                snapshot_validation_status="MATCHED",
            )

        self.evidence_annotations = list(evidence_annotations or [])
        self.errors = list(errors or [])
        self.revalidated_at = str(revalidated_at) if revalidated_at else datetime.now(timezone.utc).isoformat()

        if counts is not None:
            self.counts = dict(counts)
        else:
            self.counts = self._compute_counts()

        if content_hash:
            self.content_hash = str(content_hash).strip()
        else:
            self.content_hash = self.compute_content_hash()

    def _compute_counts(self) -> dict[str, int]:
        """Compute standard compliance breakdown counts."""
        pass_c = sum(1 for r in self.verification_results if r.get("status") == VerificationStatus.PASS.value)
        fail_c = sum(1 for r in self.verification_results if r.get("status") == VerificationStatus.FAIL.value)
        not_vis_c = sum(1 for r in self.verification_results if r.get("status") == VerificationStatus.NOT_VISIBLE.value)
        not_app_c = sum(1 for r in self.verification_results if r.get("status") == VerificationStatus.NOT_APPLICABLE.value)
        review_c = sum(1 for r in self.verification_results if r.get("status") == VerificationStatus.REVIEW_REQUIRED.value)

        return {
            "total_requirements": len(self.verification_results),
            "pass_count": pass_c,
            "fail_count": fail_c,
            "not_visible_count": not_vis_c,
            "not_applicable_count": not_app_c,
            "review_required_count": review_c,
        }

    def compute_content_hash(self) -> str:
        """Compute deterministic SHA-256 hash over revalidation result payload."""
        norm_ver_results = []
        for vr in self.verification_results:
            d = dict(vr)
            d.pop("created_at", None)
            norm_ver_results.append(d)

        payload = {
            "inspection_id": self.inspection_id,
            "overall_status": self.overall_status.value,
            "verification_results": norm_ver_results,
            "summary": self.summary,
            "counts": self.counts,
            "applicable_requirements": self.applicable_requirements,
            "server_legal_snapshot_id": self.server_legal_snapshot_id,
            "offline_legal_snapshot_id": self.offline_legal_snapshot_id,
            "evaluation_metadata": {
                "evaluation_mode": self.evaluation_metadata.evaluation_mode.value if hasattr(self.evaluation_metadata.evaluation_mode, "value") else str(self.evaluation_metadata.evaluation_mode),
                "revalidation_required": self.evaluation_metadata.revalidation_required,
                "legal_snapshot_id": self.evaluation_metadata.legal_snapshot_id,
            },
            "comparison": self.comparison.to_dict(),
            "errors": self.errors,
        }
        canonical_str = _canonical_json(payload)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to dictionary."""
        return {
            "inspection_id": self.inspection_id,
            "overall_status": self.overall_status.value,
            "verification_results": list(self.verification_results),
            "summary": self.summary,
            "counts": dict(self.counts),
            "applicable_requirements": list(self.applicable_requirements),
            "server_legal_snapshot_id": self.server_legal_snapshot_id,
            "offline_legal_snapshot_id": self.offline_legal_snapshot_id,
            "evaluation_metadata": self.evaluation_metadata.to_dict(),
            "comparison": self.comparison.to_dict(),
            "evidence_annotations": list(self.evidence_annotations),
            "errors": list(self.errors),
            "revalidated_at": self.revalidated_at,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServerRevalidationResult:
        """Instantiate result from dictionary."""
        return cls(
            inspection_id=data.get("inspection_id", ""),
            overall_status=data.get("overall_status", OverallInspectionStatus.REVIEW_REQUIRED),
            verification_results=data.get("verification_results", []),
            summary=data.get("summary", ""),
            counts=data.get("counts"),
            applicable_requirements=data.get("applicable_requirements"),
            server_legal_snapshot_id=data.get("server_legal_snapshot_id"),
            offline_legal_snapshot_id=data.get("offline_legal_snapshot_id"),
            evaluation_metadata=data.get("evaluation_metadata"),
            comparison=data.get("comparison"),
            evidence_annotations=data.get("evidence_annotations"),
            errors=data.get("errors"),
            revalidated_at=data.get("revalidated_at"),
            content_hash=data.get("content_hash"),
        )

    def to_json(self) -> str:
        """Produce deterministic UTF-8 JSON string."""
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> ServerRevalidationResult:
        """Parse result from JSON string."""
        return cls.from_dict(json.loads(json_str))


class ServerRevalidationService:
    """Authoritative server-side compliance revalidation service for offline inspections."""

    def __init__(
        self,
        sync_repository: SyncOperationRepository,
        inspection_repository: InspectionRepository | None = None,
        session_store: Any | None = None,
        evidence_service: EvidenceNormalizationService | None = None,
        default_server_snapshot_context: LegalSnapshotContext | None = None,
    ) -> None:
        self.sync_repo = sync_repository
        self.inspection_repo = inspection_repository
        self.session_store = session_store
        self.evidence_service = evidence_service or EvidenceNormalizationService()
        self.default_server_snapshot = default_server_snapshot_context
        self._lock = threading.RLock()

    def revalidate(
        self,
        inspection_id: str,
        authenticated_user_id: str,
        server_snapshot_context: LegalSnapshotContext | None = None,
        force: bool = False,
    ) -> ServerRevalidationResult:
        """Execute authoritative server-side compliance revalidation of an offline inspection."""
        with self._lock:
            auth_user = str(authenticated_user_id).strip()
            now_iso = datetime.now(timezone.utc).isoformat()
            errors: list[dict[str, Any]] = []

            # 1. Inspection Ownership & Existence Check
            if self.session_store is not None:
                session = self.session_store.get_session_optional(inspection_id)
                if session is not None:
                    owner_id = getattr(session.inspection, "owner_id", None) or (
                        session.inspection.metadata.get("owner_id") if isinstance(session.inspection.metadata, dict) else None
                    )
                    if owner_id and str(owner_id).strip() != auth_user:
                        raise PermissionError(f"User '{auth_user}' is not authorized to revalidate inspection '{inspection_id}'.")

            if self.inspection_repo is not None:
                try:
                    inspection = self.inspection_repo.get_inspection(inspection_id)
                    owner_id = getattr(inspection, "owner_id", None) or (
                        inspection.metadata.get("owner_id") if isinstance(inspection.metadata, dict) else None
                    )
                    if owner_id and str(owner_id).strip() != auth_user:
                        raise PermissionError(f"User '{auth_user}' is not authorized to revalidate inspection '{inspection_id}'.")
                except Exception as e:
                    if isinstance(e, PermissionError):
                        raise
                    # If not in inspection_repo, continue to check sync_repo

            # 2. Query Synced Operations
            ops = self.sync_repo.list_operations_for_inspection(inspection_id)
            if not ops:
                session = self.session_store.get_session_optional(inspection_id) if self.session_store else None
                if session is None:
                    if self.inspection_repo is not None:
                        try:
                            self.inspection_repo.get_inspection(inspection_id)
                        except Exception:
                            raise InspectionNotFoundError(
                                f"Inspection '{inspection_id}' not found.",
                                details={"inspection_id": inspection_id},
                            )
                    else:
                        raise InspectionNotFoundError(
                            f"Inspection '{inspection_id}' not found.",
                            details={"inspection_id": inspection_id},
                        )

            # 3. Determine Active Server Legal Snapshot Context
            active_snapshot = server_snapshot_context or self.default_server_snapshot
            if active_snapshot is None:
                # If no active snapshot provided, create empty/stub context to safely require revalidation
                active_snapshot = LegalSnapshotContext(
                    legal_snapshot_id="server-active-placeholder",
                    manifest=None,
                    requirements=[],
                )
                errors.append({
                    "stage": "server_snapshot_resolution",
                    "error_code": "MISSING_SERVER_SNAPSHOT",
                    "error_message": "Active server legal snapshot context was not configured.",
                })

            server_snapshot_id = active_snapshot.legal_snapshot_id

            # 4. Extract Client Offline State and Synced Entities
            client_snapshot_id: str | None = None
            offline_overall_status: str | None = None
            offline_req_results: dict[str, str] = {}  # req_id -> status
            offline_target_reqs: list[str] = []
            offline_eval_meta: EvaluationMetadata | None = None

            facts: list[InspectionFact] = []
            evidence_candidates: list[EvidenceCandidate] = []
            image_artifacts: list[ImageArtifact] = []

            for op in ops:
                payload = op.payload or {}

                if op.entity_type == SyncEntityType.INSPECTION:
                    op_owner_id = payload.get("owner_id") or payload.get("metadata", {}).get("owner_id")
                    if op_owner_id and str(op_owner_id).strip() != auth_user:
                        raise PermissionError(f"User '{auth_user}' is not authorized to revalidate inspection '{inspection_id}'.")

                elif op.entity_type == SyncEntityType.REPORT:
                    # Ignore server-generated revalidation reports when reconstructing client offline state
                    if str(op.operation_id).startswith("reval-rep-"):
                        continue
                    eval_mode_in_payload = str(payload.get("evaluation_metadata", {}).get("evaluation_mode", "")).upper()
                    if eval_mode_in_payload == EvaluationMode.SERVER_REVALIDATED.value:
                        continue

                    if payload.get("legal_snapshot_id"):
                        client_snapshot_id = str(payload["legal_snapshot_id"])
                    if payload.get("overall_status"):
                        offline_overall_status = str(payload["overall_status"])
                    if payload.get("evaluation_metadata"):
                        offline_eval_meta = EvaluationMetadata.from_dict(payload["evaluation_metadata"])
                    if payload.get("target_requirements"):
                        offline_target_reqs = [
                            tr if isinstance(tr, str) else str(tr.get("requirement_id") or tr.get("id"))
                            for tr in payload["target_requirements"]
                        ]
                    if payload.get("verification_results"):
                        for vr in payload["verification_results"]:
                            r_id = vr.get("requirement_id")
                            if r_id:
                                offline_req_results[str(r_id)] = str(vr.get("status", "REVIEW_REQUIRED"))

                elif op.entity_type == SyncEntityType.REQUIREMENT_RESULT:
                    r_id = payload.get("requirement_id")
                    if r_id:
                        offline_req_results[str(r_id)] = str(payload.get("status", "REVIEW_REQUIRED"))

                elif op.entity_type == SyncEntityType.FACT:
                    f_id = op.entity_id or payload.get("id") or str(uuid.uuid4())
                    facts.append(
                        InspectionFact(
                            id=str(f_id),
                            run_id=inspection_id,
                            fact_key=str(payload.get("fact_key") or payload.get("key", "")),
                            value=payload.get("value"),
                            unit=payload.get("unit"),
                            fact_status=str(payload.get("fact_status", "known")),
                            origin=str(payload.get("origin", "sync_fact")),
                            observed_text=payload.get("observed_text"),
                            sequence=int(payload.get("sequence", op.sequence)),
                        )
                    )

                elif op.entity_type == SyncEntityType.EVIDENCE:
                    try:
                        f_val = str(payload.get("field", "generic_declaration")).strip().lower()
                        if f_val in ("mfg_date", "mfg", "date_of_manufacture"):
                            f_val = "manufacture_date"
                        elif f_val in ("net_qty", "quantity"):
                            f_val = "net_quantity"

                        try:
                            field_enum = EvidenceField(f_val)
                        except ValueError:
                            field_enum = EvidenceField.GENERIC_DECLARATION

                        s_val = str(payload.get("status", "VALID")).strip().upper()
                        try:
                            status_enum = EvidenceStatus(s_val)
                        except ValueError:
                            status_enum = EvidenceStatus.VALID

                        evidence_candidates.append(
                            EvidenceCandidate(
                                evidence_id=str(payload.get("evidence_id") or op.entity_id),
                                field=field_enum,
                                raw_text=str(payload.get("raw_text", "")),
                                normalized_text=str(payload.get("normalized_text") or payload.get("raw_text", "")),
                                parsed_value=payload.get("parsed_value"),
                                parsed_unit=payload.get("parsed_unit"),
                                status=status_enum,
                                observation_id=payload.get("observation_id", ""),
                                image_id=payload.get("image_id", ""),
                                confidence=float(payload.get("confidence", 1.0)),
                                metadata=payload.get("metadata", {}),
                            )
                        )
                    except Exception as err:
                        errors.append({
                            "stage": "evidence_reconstruction",
                            "error_message": str(err),
                        })

                elif op.entity_type == SyncEntityType.IMAGE:
                    image_artifacts.append(
                        ImageArtifact(
                            image_id=str(payload.get("image_id") or op.entity_id),
                            source_hash=str(payload.get("source_hash") or "hash-placeholder"),
                            normalized_hash=str(payload.get("normalized_hash") or "hash-placeholder"),
                            source_format=payload.get("source_format", "PNG"),
                            normalized_format=payload.get("normalized_format", "PNG"),
                            original_width=payload.get("original_width", 1000),
                            original_height=payload.get("original_height", 1000),
                            normalized_width=payload.get("normalized_width", 1000),
                            normalized_height=payload.get("normalized_height", 1000),
                            pixel_count=payload.get("pixel_count", 1_000_000),
                            aspect_ratio=payload.get("aspect_ratio", 1.0),
                            file_size_bytes=payload.get("file_size_bytes", 1000),
                            source_file_size_bytes=payload.get("source_file_size_bytes", 1000),
                            color_mode=payload.get("color_mode", "RGB"),
                            normalized_bytes=b"",
                            metadata=payload.get("metadata", {}),
                        )
                    )

            # 5. Validate Legal Snapshot Context
            snap_val_res = LegalSnapshotValidator.validate_snapshot(
                client_snapshot_id=client_snapshot_id or "",
                server_active_snapshot_id=server_snapshot_id,
                historical_snapshot_ids=getattr(active_snapshot, "historical_snapshot_ids", None),
            )

            # 6. Evaluate Applicability Rules Against Active Server Snapshot
            applicability_decisions: dict[str, Any] = {}
            if active_snapshot.applicability_rules and active_snapshot.applicability_rule_versions:
                try:
                    run_obj = ApplicabilityRun(
                        id=str(uuid.uuid4()),
                        inspection_reference=inspection_id,
                        inspection_date=date.today(),
                    )

                    rule_objs = [
                        ApplicabilityRule(
                            id=str(r.get("id") or r.get("rule_key")),
                            rule_key=str(r.get("rule_key") or r.get("id")),
                        )
                        for r in active_snapshot.applicability_rules
                    ]

                    ver_objs = [
                        ApplicabilityRuleVersion(
                            id=str(v.get("id")),
                            rule_id=str(v.get("rule_id")),
                            version_number=int(v.get("version_number", 1)),
                            interpretation_status=str(v.get("interpretation_status", "approved")),
                            valid_from=None,
                            valid_to=None,
                        )
                        for v in active_snapshot.applicability_rule_versions
                    ]

                    grp_objs = [
                        ApplicabilityConditionGroup(
                            id=str(g.get("id")),
                            rule_version_id=str(g.get("rule_version_id")),
                            parent_group_id=g.get("parent_group_id"),
                            group_purpose=str(g.get("group_purpose", "applicability")),
                            boolean_operator=str(g.get("boolean_operator", "AND")),
                            sequence=int(g.get("sequence", 1)),
                        )
                        for g in active_snapshot.applicability_condition_groups
                    ]

                    cond_objs = []
                    for c in active_snapshot.applicability_conditions:
                        raw_op = str(c.get("operator", "equals")).strip().lower()
                        if raw_op in ("eq", "=="):
                            norm_op = "equals"
                        elif raw_op in ("ne", "!="):
                            norm_op = "not_equals"
                        elif raw_op in ("in", "oneof"):
                            norm_op = "one_of"
                        elif raw_op in ("gt", ">"):
                            norm_op = "greater_than"
                        elif raw_op in ("gte", ">="):
                            norm_op = "greater_or_equal"
                        elif raw_op in ("lt", "<"):
                            norm_op = "less_than"
                        elif raw_op in ("lte", "<="):
                            norm_op = "less_or_equal"
                        else:
                            norm_op = raw_op

                        cond_objs.append(
                            ApplicabilityCondition(
                                id=str(c.get("id")),
                                group_id=str(c.get("group_id")),
                                fact_key=str(c.get("fact_key")),
                                operator=norm_op,
                                expected_value=c.get("expected_value"),
                                expected_unit=c.get("expected_unit"),
                                sequence=int(c.get("sequence", 1)),
                            )
                        )

                    app_results = ApplicabilityService.evaluate_run(
                        run=run_obj,
                        facts=facts,
                        rules=rule_objs,
                        rule_versions=ver_objs,
                        groups=grp_objs,
                        conditions=cond_objs,
                    )

                    for idx, (decision, _) in enumerate(app_results):
                        v_id = str(decision.rule_version_id)
                        applicability_decisions[v_id] = decision
                        if idx < len(rule_objs):
                            r_id = str(rule_objs[idx].id)
                            r_key = str(rule_objs[idx].rule_key)
                            applicability_decisions[r_id] = decision
                            applicability_decisions[r_key] = decision
                except Exception as err:
                    errors.append({
                        "stage": "server_applicability_evaluation",
                        "error_message": str(err),
                    })

            # 7. Complete Statutory Requirement Derivation from Server Snapshot
            authoritative_reqs: list[RequirementReference] = []
            for sr in active_snapshot.requirements:
                if isinstance(sr, dict):
                    r_id = str(sr.get("id") or sr.get("requirement_code") or sr.get("source_identifier", "")).strip()
                    if not r_id:
                        continue

                    t_field = sr.get("target_field")
                    if t_field in ("mfg_date", "mfg", "date_of_manufacture"):
                        t_field = "manufacture_date"
                    elif t_field in ("net_qty", "quantity"):
                        t_field = "net_quantity"
                    elif not t_field:
                        lower_id = r_id.lower()
                        if "mrp" in lower_id:
                            t_field = "mrp"
                        elif "net_qty" in lower_id or "quantity" in lower_id:
                            t_field = "net_quantity"
                        elif "mfg" in lower_id or "date" in lower_id:
                            t_field = "manufacture_date"

                    authoritative_reqs.append(
                        RequirementReference(
                            requirement_id=r_id,
                            rule_number=sr.get("rule_number"),
                            section_reference=sr.get("section_reference"),
                            requirement_text=sr.get("requirement_text") or sr.get("normalized_requirement"),
                            target_field=t_field,
                            target_fields=sr.get("target_fields", []),
                            metadata=sr.get("metadata", sr),
                        )
                    )
                elif isinstance(sr, RequirementReference):
                    authoritative_reqs.append(sr)

            if not authoritative_reqs:
                errors.append({
                    "stage": "server_requirement_derivation",
                    "error_code": "EMPTY_SERVER_REQUIREMENTS",
                    "error_message": "No authoritative statutory requirements available in active server snapshot.",
                })

            # 8. Deterministic Verification Across COMPLETE Server Requirement Set
            verification_results: list[VerificationResult] = []
            server_req_status_map: dict[str, str] = {}
            general_decision = list(applicability_decisions.values())[0] if len(applicability_decisions) == 1 else None

            for req_ref in authoritative_reqs:
                app_state = TriState.TRUE
                req_rule_id = str(req_ref.metadata.get("rule_id") or req_ref.metadata.get("rule_version_id") or "")

                if req_ref.requirement_id in applicability_decisions:
                    app_state = DeterministicVerifier._normalize_applicability(applicability_decisions[req_ref.requirement_id])
                elif req_rule_id and req_rule_id in applicability_decisions:
                    app_state = DeterministicVerifier._normalize_applicability(applicability_decisions[req_rule_id])
                elif general_decision is not None:
                    app_state = DeterministicVerifier._normalize_applicability(general_decision)

                v_res = DeterministicVerifier.verify(
                    requirement=req_ref,
                    applicability=app_state,
                    candidates=evidence_candidates,
                    verification_id=f"reval-{inspection_id}-{req_ref.requirement_id}",
                )
                verification_results.append(v_res)
                server_req_status_map[req_ref.requirement_id] = v_res.status.value

            # 9. Compute Server Overall Status & Diagnostics
            overall_status, summary = compute_overall_status(verification_results)

            # 10. Perform Structured Comparison (Offline vs Server)
            server_req_ids = {r.requirement_id for r in authoritative_reqs}
            client_req_ids = set(offline_req_results.keys()) | set(offline_target_reqs)

            missing_offline = sorted(list(server_req_ids - client_req_ids))
            extra_offline = sorted(list(client_req_ids - server_req_ids))

            req_diffs: list[dict[str, Any]] = []
            for r_id, s_status in server_req_status_map.items():
                if r_id in offline_req_results:
                    off_status = offline_req_results[r_id]
                    if off_status != s_status:
                        req_diffs.append({
                            "requirement_id": r_id,
                            "offline_status": off_status,
                            "server_status": s_status,
                        })

            notes: list[str] = []
            if snap_val_res.status != LegalSnapshotValidationStatus.MATCHED:
                notes.append(f"Legal snapshot was evaluated as {snap_val_res.status.value}: {snap_val_res.reason}")
            if missing_offline:
                notes.append(f"Offline evaluation omitted {len(missing_offline)} statutory requirement(s): {missing_offline}")
            if extra_offline:
                notes.append(f"Offline evaluation included {len(extra_offline)} non-statutory requirement(s): {extra_offline}")
            if req_diffs:
                notes.append(f"Requirement compliance statuses differed for {len(req_diffs)} requirement(s).")
            if offline_overall_status and offline_overall_status != overall_status.value:
                notes.append(f"Overall status migrated from offline '{offline_overall_status}' to server '{overall_status.value}'.")

            comparison = RevalidationComparison(
                offline_overall_status=offline_overall_status,
                server_overall_status=overall_status.value,
                overall_status_changed=bool(offline_overall_status and offline_overall_status != overall_status.value),
                offline_legal_snapshot_id=client_snapshot_id,
                server_legal_snapshot_id=server_snapshot_id,
                legal_snapshot_changed=bool(client_snapshot_id != server_snapshot_id),
                snapshot_validation_status=snap_val_res.status.value,
                offline_requirement_count=len(offline_req_results) if offline_req_results else len(offline_target_reqs),
                server_requirement_count=len(authoritative_reqs),
                missing_offline_requirements=missing_offline,
                extra_offline_requirements=extra_offline,
                requirement_status_diffs=req_diffs,
                applicability_changed=bool(snap_val_res.status != LegalSnapshotValidationStatus.MATCHED),
                summary_notes=notes,
            )

            # 11. Generate Evidence Annotations
            raw_annotations = generate_evidence_annotations(
                verification_results=verification_results,
                evidence_candidates=evidence_candidates,
                images=image_artifacts,
                inspection_id=inspection_id,
            )
            annotations = [a.to_dict() if hasattr(a, "to_dict") else dict(a) for a in raw_annotations]

            # 12. Evaluation Metadata
            eval_meta = EvaluationMetadata(
                evaluation_mode=EvaluationMode.SERVER_REVALIDATED,
                revalidation_required=False,
                legal_snapshot_id=server_snapshot_id,
                engine_version="1.0.0",
            )

            result = ServerRevalidationResult(
                inspection_id=inspection_id,
                overall_status=overall_status,
                verification_results=verification_results,
                summary=summary,
                applicable_requirements=[r.requirement_id for r in authoritative_reqs],
                server_legal_snapshot_id=server_snapshot_id,
                offline_legal_snapshot_id=client_snapshot_id,
                evaluation_metadata=eval_meta,
                comparison=comparison,
                evidence_annotations=annotations,
                errors=errors,
                revalidated_at=now_iso,
            )

            # 13. Construct Authoritative InspectionReport
            reval_report = InspectionReport(
                inspection_id=inspection_id,
                overall_status=overall_status,
                verification_results=verification_results,
                summary=summary,
                evidence_count=len(evidence_candidates),
                image_count=len(image_artifacts),
                applicable_requirement_count=len(authoritative_reqs),
                pass_count=result.counts.get("pass_count", 0),
                fail_count=result.counts.get("fail_count", 0),
                not_visible_count=result.counts.get("not_visible_count", 0),
                not_applicable_count=result.counts.get("not_applicable_count", 0),
                review_required_count=result.counts.get("review_required_count", 0),
                evidence_annotations=annotations,
                created_at=datetime.fromisoformat(now_iso),
                errors=errors,
                metadata={
                    "evaluation_metadata": eval_meta.to_dict(),
                    "revalidation_comparison": comparison.to_dict(),
                    "server_legal_snapshot_id": server_snapshot_id,
                    "offline_legal_snapshot_id": client_snapshot_id,
                    "revalidated_at": now_iso,
                    "content_hash": result.content_hash,
                },
            )

            # 14. Persist to Relational Inspection Repository (if configured)
            if self.inspection_repo is not None:
                try:
                    self.inspection_repo.save_report(inspection_id, reval_report)
                    self.inspection_repo.save_requirement_results(inspection_id, verification_results)
                except Exception as err:
                    raise RuntimeError(f"Relational persistence failed for inspection '{inspection_id}': {err}") from err

            # 15. Persist to Durable Sync Operations Repository
            try:
                report_op_id = f"reval-rep-{inspection_id}"
                rec = DurableSyncOperationRecord(
                    operation_id=report_op_id,
                    inspection_id=inspection_id,
                    entity_type=SyncEntityType.REPORT,
                    entity_id=f"rep-{inspection_id}",
                    operation_type=SyncOperationType.UPSERT,
                    content_hash=result.content_hash,
                    created_at=now_iso,
                    received_at=now_iso,
                    acknowledged_at=now_iso,
                    status=OperationStatus.ACKNOWLEDGED,
                    payload={
                        "overall_status": overall_status.value,
                        "summary": summary,
                        "legal_snapshot_id": server_snapshot_id,
                        "evaluation_metadata": eval_meta.to_dict(),
                        "counts": result.counts,
                        "revalidation_comparison": comparison.to_dict(),
                        "verification_results": [r.to_dict() for r in verification_results],
                        "applicable_requirements": [r.requirement_id for r in authoritative_reqs],
                        "evidence_annotations": annotations,
                        "revalidated_at": now_iso,
                        "content_hash": result.content_hash,
                    },
                )
                try:
                    self.sync_repo.save_operation(rec)
                except Exception:
                    self.sync_repo.update_operation_status(
                        operation_id=report_op_id,
                        status=OperationStatus.ACKNOWLEDGED,
                        acknowledged_at=now_iso,
                    )
            except Exception as err:
                raise RuntimeError(f"Sync operation persistence failed for inspection '{inspection_id}': {err}") from err

            # 16. In-Memory Session Store Projection (ONLY updated after durable persistence succeeds)
            if self.session_store is not None:
                session = self.session_store.get_session_optional(inspection_id)
                if session is not None:
                    session.report = reval_report
                    session.inspection.status = InspectionStatus.COMPLETED
                    session.inspection.metadata["evaluation_mode"] = EvaluationMode.SERVER_REVALIDATED.value
                    session.inspection.metadata["last_revalidated_at"] = now_iso
                    session.inspection.metadata["server_legal_snapshot_id"] = server_snapshot_id
                    session.inspection.metadata["revalidation_comparison"] = comparison.to_dict()
                    session.updated_at = datetime.now(timezone.utc)
                else:
                    new_session = self.session_store.create_session(
                        inspection_id=inspection_id,
                        metadata={
                            "evaluation_mode": EvaluationMode.SERVER_REVALIDATED.value,
                            "last_revalidated_at": now_iso,
                            "server_legal_snapshot_id": server_snapshot_id,
                            "revalidation_comparison": comparison.to_dict(),
                        },
                        owner_id=auth_user if auth_user and auth_user != "anonymous" else None,
                    )
                    new_session.report = reval_report
                    new_session.inspection.status = InspectionStatus.COMPLETED
                    for img in image_artifacts:
                        new_session.artifacts[img.image_id] = img

            return result
