"""Offline Deterministic Inspection Executor & Result Contract for Phase U24-D.

Executes 100% deterministic, in-memory evaluation of an offline inspection bundle:
1. Validates bundle integrity & legal snapshot identity
2. Normalizes OCR observations into evidence candidates
3. Evaluates applicability rules using the pure in-memory ApplicabilityService
4. Executes deterministic verification using DeterministicVerifier (PASS, FAIL, NOT_VISIBLE, NOT_APPLICABLE, REVIEW_REQUIRED)
5. Aggregates canonical overall status and flags revalidation_required
6. Strictly excludes Gemini, Supabase, and network calls
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
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
from backend.app.services.inspection_pipeline.annotations import generate_evidence_annotations
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import compute_overall_status
from backend.app.services.ocr.models import OCRObservation, OCRProcessingStatus, OCRResult
from backend.app.services.offline_sync.bundle import LegalSnapshotContext, OfflineInspectionBundle
from backend.app.services.offline_sync.models import EvaluationMetadata, EvaluationMode
from backend.app.services.verification.deterministic import DeterministicVerifier
from backend.app.services.verification.evidence_matcher import EvidenceMatcher
from backend.app.services.verification.models import RequirementReference, VerificationResult, VerificationStatus


def _canonical_json(data: Any) -> str:
    """Deterministic JSON string."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class OfflineEvaluationResult:
    """Authoritative result of an offline deterministic inspection evaluation."""

    def __init__(
        self,
        inspection_id: str,
        overall_status: OverallInspectionStatus | str,
        verification_results: list[VerificationResult | dict[str, Any]],
        summary: str,
        counts: dict[str, int] | None = None,
        applicable_requirements: list[str] | None = None,
        legal_snapshot_id: str | None = None,
        evaluation_metadata: EvaluationMetadata | dict[str, Any] | None = None,
        evidence_annotations: list[dict[str, Any]] | None = None,
        errors: list[dict[str, Any]] | None = None,
        created_at: str | None = None,
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
        self.legal_snapshot_id = str(legal_snapshot_id) if legal_snapshot_id else None

        if isinstance(evaluation_metadata, EvaluationMetadata):
            self.evaluation_metadata = evaluation_metadata
        elif isinstance(evaluation_metadata, dict):
            self.evaluation_metadata = EvaluationMetadata.from_dict(evaluation_metadata)
        else:
            self.evaluation_metadata = EvaluationMetadata(
                evaluation_mode=EvaluationMode.OFFLINE_DETERMINISTIC,
                legal_snapshot_id=self.legal_snapshot_id,
            )

        self.evidence_annotations = list(evidence_annotations or [])
        self.errors = list(errors or [])
        self.created_at = str(created_at) if created_at else datetime.now(timezone.utc).isoformat()

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
        """Compute deterministic SHA-256 hash over evaluation result payload."""
        payload = {
            "inspection_id": self.inspection_id,
            "overall_status": self.overall_status.value,
            "verification_results": self.verification_results,
            "summary": self.summary,
            "counts": self.counts,
            "applicable_requirements": self.applicable_requirements,
            "legal_snapshot_id": self.legal_snapshot_id,
            "evaluation_metadata": self.evaluation_metadata.to_dict(),
            "evidence_annotations": self.evidence_annotations,
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
            "legal_snapshot_id": self.legal_snapshot_id,
            "evaluation_metadata": self.evaluation_metadata.to_dict(),
            "evidence_annotations": list(self.evidence_annotations),
            "errors": list(self.errors),
            "created_at": self.created_at,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OfflineEvaluationResult:
        """Instantiate evaluation result from dictionary."""
        return cls(
            inspection_id=data.get("inspection_id", ""),
            overall_status=data.get("overall_status", OverallInspectionStatus.REVIEW_REQUIRED),
            verification_results=data.get("verification_results", []),
            summary=data.get("summary", ""),
            counts=data.get("counts"),
            applicable_requirements=data.get("applicable_requirements"),
            legal_snapshot_id=data.get("legal_snapshot_id"),
            evaluation_metadata=data.get("evaluation_metadata"),
            evidence_annotations=data.get("evidence_annotations"),
            errors=data.get("errors"),
            created_at=data.get("created_at"),
            content_hash=data.get("content_hash"),
        )

    def to_json(self) -> str:
        """Produce deterministic UTF-8 JSON representation."""
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> OfflineEvaluationResult:
        """Parse result from JSON string."""
        return cls.from_dict(json.loads(json_str))


class OfflineInspectionExecutor:
    """Pure in-memory offline deterministic compliance evaluation service."""

    def __init__(
        self,
        evidence_service: EvidenceNormalizationService | None = None,
    ) -> None:
        self.evidence_service = evidence_service or EvidenceNormalizationService()

    def execute(
        self,
        bundle: OfflineInspectionBundle,
        snapshot_context: LegalSnapshotContext | None,
        strict_snapshot: bool = False,
    ) -> OfflineEvaluationResult:
        """Execute deterministic offline inspection evaluation against an approved legal snapshot."""
        errors: list[dict[str, Any]] = []

        # 1. Validate Bundle Integrity
        is_bundle_valid, bundle_err = bundle.validate_integrity()
        if not is_bundle_valid:
            errors.append({
                "stage": "bundle_validation",
                "error_code": "INVALID_BUNDLE_HASH",
                "error_message": bundle_err or "Offline bundle hash verification failed.",
            })

        # 2. Validate Legal Snapshot Context
        snapshot_valid = False
        reval_required = False

        if snapshot_context is None:
            errors.append({
                "stage": "legal_snapshot_validation",
                "error_code": "MISSING_LEGAL_SNAPSHOT",
                "error_message": f"Legal snapshot context was not provided for snapshot '{bundle.legal_snapshot_id}'.",
            })
            reval_required = True
        else:
            if snapshot_context.legal_snapshot_id != bundle.legal_snapshot_id:
                errors.append({
                    "stage": "legal_snapshot_validation",
                    "error_code": "SNAPSHOT_ID_MISMATCH",
                    "error_message": (
                        f"Bundle snapshot ID '{bundle.legal_snapshot_id}' does not match "
                        f"provided context ID '{snapshot_context.legal_snapshot_id}'."
                    ),
                })
                reval_required = True
            else:
                is_intact, comp_id = snapshot_context.verify_integrity()
                if not is_intact:
                    errors.append({
                        "stage": "legal_snapshot_validation",
                        "error_code": "SNAPSHOT_INTEGRITY_FAILED",
                        "error_message": f"Snapshot integrity verification failed. Computed '{comp_id}' != declared '{snapshot_context.legal_snapshot_id}'.",
                    })
                    reval_required = True
                else:
                    snapshot_valid = True

        if strict_snapshot and not snapshot_valid:
            eval_meta = EvaluationMetadata(
                evaluation_mode=EvaluationMode.OFFLINE_DETERMINISTIC,
                revalidation_required=True,
                legal_snapshot_id=bundle.legal_snapshot_id,
            )
            return OfflineEvaluationResult(
                inspection_id=bundle.inspection_id,
                overall_status=OverallInspectionStatus.REVIEW_REQUIRED,
                verification_results=[],
                summary=f"Offline evaluation aborted: Legal snapshot '{bundle.legal_snapshot_id}' is invalid or missing.",
                applicable_requirements=[],
                legal_snapshot_id=bundle.legal_snapshot_id,
                evaluation_metadata=eval_meta,
                evidence_annotations=[],
                errors=errors,
            )

        # 3. Assemble Inspection Facts
        facts: list[InspectionFact] = []
        for f in bundle.inspection_facts:
            f_id = f.get("id") or str(uuid.uuid4())
            run_id = f.get("run_id") or bundle.inspection_id
            facts.append(
                InspectionFact(
                    id=f_id,
                    run_id=run_id,
                    fact_key=str(f.get("fact_key") or f.get("key", "")),
                    value=f.get("value"),
                    unit=f.get("unit"),
                    fact_status=f.get("fact_status", "known"),
                    origin=f.get("origin", "inspection"),
                    observed_text=f.get("observed_text"),
                    sequence=int(f.get("sequence", 1)),
                )
            )

        # 4. Assemble Evidence Candidates (from explicit list or normalized OCR)
        evidence_candidates: list[EvidenceCandidate] = []
        if bundle.evidence_candidates:
            for ec in bundle.evidence_candidates:
                try:
                    f_val = str(ec.get("field", "generic_declaration")).strip().lower()
                    if f_val in ("mfg_date", "mfg", "date_of_manufacture"):
                        f_val = "manufacture_date"
                    elif f_val in ("net_qty", "quantity"):
                        f_val = "net_quantity"

                    try:
                        field_enum = EvidenceField(f_val)
                    except ValueError:
                        field_enum = EvidenceField.GENERIC_DECLARATION

                    s_val = str(ec.get("status", "VALID")).strip().upper()
                    try:
                        status_enum = EvidenceStatus(s_val)
                    except ValueError:
                        status_enum = EvidenceStatus.VALID

                    evidence_candidates.append(
                        EvidenceCandidate(
                            evidence_id=str(ec.get("evidence_id") or uuid.uuid4()),
                            field=field_enum,
                            raw_text=str(ec.get("raw_text", "")),
                            normalized_text=str(ec.get("normalized_text") or ec.get("raw_text", "")),
                            parsed_value=ec.get("parsed_value"),
                            parsed_unit=ec.get("parsed_unit"),
                            status=status_enum,
                            observation_id=ec.get("observation_id", ""),
                            image_id=ec.get("image_id", ""),
                            confidence=float(ec.get("confidence", 1.0)),
                            metadata=ec.get("metadata", {}),
                        )
                    )
                except Exception as err:

                    errors.append({
                        "stage": "evidence_candidate_parsing",
                        "error_type": type(err).__name__,
                        "error_message": str(err),
                    })
        elif bundle.ocr_results:
            # Normalize OCR observations into evidence candidates using pure parser engine
            ocr_obj_list: list[OCRResult] = []
            for r in bundle.ocr_results:
                obs_list = []
                for o in r.get("observations", []):
                    obs_list.append(
                        OCRObservation(
                            text=o.get("text", ""),
                            confidence=o.get("confidence", 1.0),
                            bounding_box=o.get("bounding_box"),
                            image_id=o.get("image_id") or r.get("image_id"),
                            observation_id=o.get("observation_id") or str(uuid.uuid4()),
                            sequence=o.get("sequence", 0),
                        )
                    )
                ocr_obj_list.append(
                    OCRResult(
                        image_id=r.get("image_id", ""),
                        status=OCRProcessingStatus.SUCCESS if obs_list else OCRProcessingStatus.NO_TEXT_DETECTED,
                        observations=obs_list,
                    )
                )

            try:
                evidence_candidates = self.evidence_service.normalize_ocr_results(ocr_obj_list)
            except Exception as err:
                errors.append({
                    "stage": "evidence_normalization",
                    "error_type": type(err).__name__,
                    "error_message": str(err),
                })

        # 5. Evaluate Applicability Rules (using pure in-memory ApplicabilityService)
        applicability_decisions: dict[str, Any] = {}
        if snapshot_context and snapshot_context.applicability_rules and snapshot_context.applicability_rule_versions:
            try:
                run_obj = ApplicabilityRun(
                    id=str(uuid.uuid4()),
                    inspection_reference=bundle.inspection_id,
                    inspection_date=date.today(),
                )

                rule_objs = [
                    ApplicabilityRule(
                        id=str(r.get("id") or r.get("rule_key")),
                        rule_key=str(r.get("rule_key") or r.get("id")),
                    )
                    for r in snapshot_context.applicability_rules
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
                    for v in snapshot_context.applicability_rule_versions
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
                    for g in snapshot_context.applicability_condition_groups
                ]

                cond_objs = []
                for c in snapshot_context.applicability_conditions:
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
                    "stage": "applicability_evaluation",
                    "error_type": type(err).__name__,
                    "error_message": str(err),
                })

        # 6. Complete Authoritative Requirements Resolution (Legal Snapshot is Authoritative)
        authoritative_reqs: list[RequirementReference] = []
        snap_req_map: dict[str, dict[str, Any]] = {}

        if snapshot_context and snapshot_context.requirements:
            for sr in snapshot_context.requirements:
                if isinstance(sr, dict):
                    r_id = str(sr.get("id") or sr.get("requirement_code") or sr.get("source_identifier", "")).strip()
                    if not r_id:
                        continue
                    snap_req_map[r_id] = sr
                    code = str(sr.get("requirement_code") or sr.get("source_identifier") or "").strip()
                    if code:
                        snap_req_map[code] = sr

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
                    snap_req_map[sr.requirement_id] = {"id": sr.requirement_id, "target_field": sr.target_field}

        if not authoritative_reqs:
            errors.append({
                "stage": "legal_coverage_validation",
                "error_code": "INCOMPLETE_LEGAL_SNAPSHOT",
                "error_message": "Legal snapshot does not contain any authoritative requirements for complete evaluation.",
            })
            reval_required = True
            # Fallback for evaluation of client items under forced review status
            if bundle.target_requirements:
                for tr in bundle.target_requirements:
                    req_id = (tr if isinstance(tr, str) else str(tr.get("requirement_id") or tr.get("id", ""))).strip()
                    if req_id:
                        authoritative_reqs.append(
                            RequirementReference(
                                requirement_id=req_id,
                                target_field=tr.get("target_field") if isinstance(tr, dict) else None,
                            )
                        )

        # 7. Validate Client target_requirements Assertion (Consistency Check)
        auth_req_ids = {r.requirement_id for r in authoritative_reqs}
        if bundle.target_requirements:
            client_req_ids = set()
            for tr in bundle.target_requirements:
                if isinstance(tr, str) and tr.strip():
                    client_req_ids.add(tr.strip())
                elif isinstance(tr, dict):
                    cid = str(tr.get("requirement_id") or tr.get("id", "")).strip()
                    if cid:
                        client_req_ids.add(cid)

            missing_from_client = auth_req_ids - client_req_ids
            extra_from_client = client_req_ids - auth_req_ids

            if missing_from_client or extra_from_client:
                errors.append({
                    "stage": "legal_coverage_validation",
                    "error_code": "REQUIREMENT_COVERAGE_MISMATCH",
                    "error_message": (
                        f"Client target_requirements assertion does not match authoritative snapshot requirements. "
                        f"Missing: {sorted(list(missing_from_client))}; Extra: {sorted(list(extra_from_client))}."
                    ),
                    "missing_from_client": sorted(list(missing_from_client)),
                    "extra_from_client": sorted(list(extra_from_client)),
                })
                reval_required = True

        # 8. Execute Pure Deterministic Verification over COMPLETE Authoritative Set
        verification_results: list[VerificationResult] = []
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
            elif "default" in applicability_decisions:
                app_state = DeterministicVerifier._normalize_applicability(applicability_decisions["default"])

            # Deterministic evaluation without Gemini, Supabase, or HTTP
            v_res = DeterministicVerifier.verify(
                requirement=req_ref,
                applicability=app_state,
                candidates=evidence_candidates,
            )
            verification_results.append(v_res)

        # 9. Compute Overall Compliance Status & Revalidation Trigger
        overall_status, summary = compute_overall_status(verification_results)


        # Trigger revalidation if any uncertainty, review requirement, or error occurred
        if (
            overall_status == OverallInspectionStatus.REVIEW_REQUIRED
            or any(r.review_required for r in verification_results)
            or bool(errors)
        ):
            reval_required = True

        # 9. Generate Evidence Annotations for Highlight Overlays
        # Recreate lightweight ImageArtifact representations for annotations
        image_artifacts = [
            ImageArtifact(
                image_id=str(img.get("image_id") or f"img-{idx}"),
                source_hash=str(img.get("source_hash") or "hash-placeholder"),
                normalized_hash=str(img.get("normalized_hash") or "hash-placeholder"),
                source_format=img.get("source_format", "PNG"),
                normalized_format=img.get("normalized_format", "PNG"),
                original_width=img.get("original_width", 1000),
                original_height=img.get("original_height", 1000),
                normalized_width=img.get("normalized_width", 1000),
                normalized_height=img.get("normalized_height", 1000),
                pixel_count=img.get("pixel_count", 1_000_000),
                aspect_ratio=img.get("aspect_ratio", 1.0),
                file_size_bytes=img.get("file_size_bytes", 1000),
                source_file_size_bytes=img.get("source_file_size_bytes", 1000),
                color_mode=img.get("color_mode", "RGB"),
                normalized_bytes=b"",
                metadata=img.get("metadata", {}),
            )
            for idx, img in enumerate(bundle.image_artifacts)
        ]

        raw_annotations = generate_evidence_annotations(
            verification_results=verification_results,
            evidence_candidates=evidence_candidates,
            images=image_artifacts,
            inspection_id=bundle.inspection_id,
        )
        evidence_annotations = [
            a.to_dict() if hasattr(a, "to_dict") else dict(a) for a in raw_annotations
        ]

        # 10. Assemble Evaluation Metadata
        eval_meta = EvaluationMetadata(
            evaluation_mode=EvaluationMode.OFFLINE_DETERMINISTIC,
            revalidation_required=reval_required,
            legal_snapshot_id=bundle.legal_snapshot_id,
            engine_version="1.0.0",
        )

        return OfflineEvaluationResult(
            inspection_id=bundle.inspection_id,
            overall_status=overall_status,
            verification_results=verification_results,
            summary=summary,
            applicable_requirements=[r.requirement_id for r in authoritative_reqs],
            legal_snapshot_id=bundle.legal_snapshot_id,
            evaluation_metadata=eval_meta,
            evidence_annotations=evidence_annotations,
            errors=errors,
        )

