"""Unified End-to-End Inspection Pipeline Orchestrator for Phase 7.

Coordinates Image Ingestion, OCR, Evidence Normalization, Applicability Gating,
Legal RAG context retrieval, Gemini Evidence Reasoning, and Phase 5E Safety Verification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from backend.app.services.applicability.models import ApplicabilityDecision, TriState
from backend.app.services.applicability.service import ApplicabilityService
from backend.app.services.evidence.models import EvidenceCandidate, ImageArtifact
from backend.app.services.evidence.service import EvidenceNormalizationService
from backend.app.services.gemini.service import GeminiEvidenceService
from backend.app.services.inspection_pipeline.errors import (
    InvalidPipelineInputError,
    PipelineExecutionError,
)
from backend.app.services.inspection_pipeline.models import (
    InspectionPipelineContext,
    InspectionPipelineRequest,
    OverallInspectionStatus,
)
from backend.app.services.inspection_pipeline.annotations import generate_evidence_annotations
from backend.app.services.inspection_pipeline.report import (
    InspectionReport,
    compute_overall_status,
)
from backend.app.services.legal_rag.service import LegalRetrievalService
from backend.app.services.ocr.extractor import OCRExtractor
from backend.app.services.ocr.models import OCRObservation, OCRProcessingStatus, OCRResult
from backend.app.services.verification.deterministic import DeterministicVerifier
from backend.app.services.verification.evidence_matcher import EvidenceMatcher
from backend.app.services.verification.models import (
    RequirementReference,
    VerificationResult,
    VerificationStatus,
)
from backend.app.services.verification.service import VerificationService


class InspectionPipelineOrchestrator:
    """Deterministic orchestrator managing the 10-step inspection workflow."""

    def __init__(
        self,
        ocr_engine: Any | None = None,
        evidence_service: EvidenceNormalizationService | None = None,
        applicability_service: ApplicabilityService | None = None,
        rag_service: LegalRetrievalService | None = None,
        gemini_service: GeminiEvidenceService | None = None,
        verification_service: VerificationService | None = None,
    ) -> None:
        self.ocr_engine = ocr_engine
        self.evidence_service = evidence_service or EvidenceNormalizationService()
        self.applicability_service = applicability_service
        self.rag_service = rag_service
        self.gemini_service = gemini_service
        self.verification_service = verification_service or VerificationService()

    def run(self, request: InspectionPipelineRequest) -> InspectionReport:
        """Execute the 10-step inspection pipeline deterministically."""
        # =================================================================
        # STEP 1: Validate inspection input
        # =================================================================
        if not request.inspection_id or not str(request.inspection_id).strip():
            raise InvalidPipelineInputError("inspection_id is mandatory and cannot be empty.")

        context = InspectionPipelineContext(
            inspection_id=request.inspection_id,
            images=list(request.image_artifacts or []),
            inspection_facts=list(request.inspection_facts or []),
        )

        # =================================================================
        # STEP 2: Validate ImageArtifacts
        # =================================================================
        for idx, artifact in enumerate(context.images):
            if not isinstance(artifact, ImageArtifact):
                raise InvalidPipelineInputError(f"Item at index {idx} is not a valid ImageArtifact: {type(artifact)}")

        # =================================================================
        # STEP 3: Run OCR on all images (with resilient error isolation)
        # =================================================================
        ocr_results: list[OCRResult] = []
        for artifact in context.images:
            try:
                res: Any = None
                if self.ocr_engine is not None:
                    if hasattr(self.ocr_engine, "extract_from_artifact"):
                        res = self.ocr_engine.extract_from_artifact(artifact)
                    elif hasattr(self.ocr_engine, "extract_text"):
                        res = self.ocr_engine.extract_text(artifact.normalized_bytes, image_id=artifact.image_id)
                    elif hasattr(self.ocr_engine, "extract"):
                        res = self.ocr_engine.extract(artifact.normalized_bytes, image_id=artifact.image_id)
                    elif callable(self.ocr_engine):
                        res = self.ocr_engine(artifact.normalized_bytes, image_id=artifact.image_id)

                if res is None:
                    res = OCRResult(
                        image_id=artifact.image_id,
                        status=OCRProcessingStatus.NO_TEXT_DETECTED,
                        observations=[],
                    )

                if isinstance(res, OCRResult):
                    # Ensure image_id is populated
                    if not res.image_id:
                        res.image_id = artifact.image_id
                    ocr_results.append(res)
                else:
                    ocr_results.append(
                        OCRResult(
                            image_id=artifact.image_id,
                            status=OCRProcessingStatus.NO_TEXT_DETECTED,
                            observations=[],
                        )
                    )
            except Exception as err:
                # Record OCR failure without aborting entire pipeline
                context.ocr_errors.append({
                    "image_id": artifact.image_id,
                    "error_type": type(err).__name__,
                    "error_message": str(err),
                })
                ocr_results.append(
                    OCRResult(
                        image_id=artifact.image_id,
                        status=OCRProcessingStatus.FAILED,
                        error_message=str(err),
                        observations=[],
                    )
                )

        context.ocr_results = ocr_results

        # =================================================================
        # STEP 4: Normalize OCR observations into EvidenceCandidates
        # =================================================================
        evidence_candidates: list[EvidenceCandidate] = []
        try:
            if ocr_results:
                evidence_candidates = self.evidence_service.normalize_ocr_results(ocr_results)
        except Exception as err:
            context.errors.append({
                "stage": "evidence_normalization",
                "error_type": type(err).__name__,
                "error_message": str(err),
            })
        context.evidence_candidates = evidence_candidates

        # =================================================================
        # STEP 5: Build / collect inspection facts for applicability
        # =================================================================
        # Facts are already stored in context.inspection_facts

        # =================================================================
        # STEP 6: Run applicability evaluation
        # =================================================================
        applicability_decisions: dict[str, Any] = dict(request.applicability_context or {})
        if self.applicability_service is not None and hasattr(self.applicability_service, "evaluate_run"):
            try:
                app_run = self.applicability_service.evaluate_run(
                    inspection_reference=context.inspection_id,
                    facts=context.inspection_facts,
                )
                if isinstance(app_run, dict):
                    applicability_decisions.update(app_run)
            except Exception as err:
                context.errors.append({
                    "stage": "applicability_evaluation",
                    "error_type": type(err).__name__,
                    "error_message": str(err),
                })
        context.applicability_decisions = applicability_decisions

        # =================================================================
        # STEP 7: Collect target / applicable legal requirements
        # =================================================================
        target_reqs: list[RequirementReference] = []
        for req in request.target_requirements:
            if isinstance(req, RequirementReference):
                target_reqs.append(req)
            elif isinstance(req, str) and req.strip():
                target_reqs.append(RequirementReference(requirement_id=req.strip()))

        context.applicable_requirements = target_reqs

        # =================================================================
        # STEP 8: Retrieve legal context via Legal RAG (for applicable reqs)
        # =================================================================
        legal_contexts: dict[str, Any] = {}
        if self.rag_service is not None and target_reqs:
            for req in target_reqs:
                app_state = self._get_applicability_state(req.requirement_id, applicability_decisions)
                if app_state == TriState.TRUE:
                    try:
                        if hasattr(self.rag_service, "retrieve_for_applicable_requirements"):
                            ctx_resp = self.rag_service.retrieve_for_applicable_requirements([req.requirement_id])
                            legal_contexts[req.requirement_id] = ctx_resp
                        elif hasattr(self.rag_service, "retrieve"):
                            legal_contexts[req.requirement_id] = self.rag_service.retrieve(req.requirement_id)
                    except Exception as err:
                        context.errors.append({
                            "stage": "rag_retrieval",
                            "requirement_id": req.requirement_id,
                            "error_type": type(err).__name__,
                            "error_message": str(err),
                        })
        context.legal_contexts = legal_contexts

        # =================================================================
        # STEP 9: Evaluate requirements against evidence candidates
        # =================================================================
        verification_results: list[VerificationResult] = []

        for req in target_reqs:
            app_state = self._get_applicability_state(req.requirement_id, applicability_decisions)

            # Applicability Gate Check: NOT_APPLICABLE -> skip Gemini & RAG
            if app_state == TriState.FALSE:
                verification_results.append(
                    VerificationResult(
                        requirement_id=req.requirement_id,
                        status=VerificationStatus.NOT_APPLICABLE,
                        reason="Requirement is not applicable under current inspection facts.",
                    )
                )
                continue

            # Applicability Gate Check: UNKNOWN -> skip Gemini & RAG
            if app_state == TriState.UNKNOWN:
                verification_results.append(
                    VerificationResult(
                        requirement_id=req.requirement_id,
                        status=VerificationStatus.REVIEW_REQUIRED,
                        reason="Applicability of requirement is UNKNOWN. Requires manual review.",
                        review_required=True,
                    )
                )
                continue

            # Requirement is APPLICABLE: Match evidence candidates
            matched_candidates = EvidenceMatcher.match_candidates(req, context.evidence_candidates)

            # Missing evidence check
            if not matched_candidates:
                verification_results.append(
                    VerificationResult(
                        requirement_id=req.requirement_id,
                        status=VerificationStatus.NOT_VISIBLE,
                        reason="Requirement applies, but required declaration was not visible in provided evidence.",
                        review_required=False,
                    )
                )
                continue

            # Evaluate with Gemini Reasoning (if available) with Phase 5E safety gate
            if self.gemini_service is not None:
                try:
                    res = self.gemini_service.verify_with_gemini_and_gate(
                        requirement=req,
                        applicability=TriState.TRUE,
                        candidates=matched_candidates,
                    )
                    verification_results.append(res)
                    continue
                except Exception as err:
                    context.errors.append({
                        "stage": "gemini_verification",
                        "requirement_id": req.requirement_id,
                        "error_type": type(err).__name__,
                        "error_message": str(err),
                    })

            # Fallback to pure deterministic verification
            res = self.verification_service.verify_requirement(
                requirement=req,
                applicability=TriState.TRUE,
                candidates=matched_candidates,
            )
            verification_results.append(res)

        context.verification_results = verification_results
        context.completed_at = datetime.now(timezone.utc)

        # =================================================================
        # STEP 10: Generate Final InspectionReport
        # =================================================================
        overall_status, summary = compute_overall_status(verification_results)

        pass_count = sum(1 for r in verification_results if r.status == VerificationStatus.PASS)
        fail_count = sum(1 for r in verification_results if r.status == VerificationStatus.FAIL)
        not_visible_count = sum(1 for r in verification_results if r.status == VerificationStatus.NOT_VISIBLE)
        not_applicable_count = sum(1 for r in verification_results if r.status == VerificationStatus.NOT_APPLICABLE)
        review_required_count = sum(1 for r in verification_results if r.status == VerificationStatus.REVIEW_REQUIRED)

        # Generate structured evidence image highlight annotations for non-compliant/review findings
        evidence_annotations = generate_evidence_annotations(
            verification_results=verification_results,
            evidence_candidates=context.evidence_candidates,
            images=context.images,
            inspection_id=context.inspection_id,
        )

        # Combine errors from context
        all_errors = list(context.errors) + list(context.ocr_errors)

        return InspectionReport(
            inspection_id=context.inspection_id,
            overall_status=overall_status,
            verification_results=verification_results,
            summary=summary,
            evidence_count=len(context.evidence_candidates),
            image_count=len(context.images),
            applicable_requirement_count=len(target_reqs),
            pass_count=pass_count,
            fail_count=fail_count,
            not_visible_count=not_visible_count,
            not_applicable_count=not_applicable_count,
            review_required_count=review_required_count,
            evidence_annotations=evidence_annotations,
            errors=all_errors,
            metadata=request.metadata,
        )

    @staticmethod
    def _get_applicability_state(requirement_id: str, decisions: dict[str, Any]) -> TriState:
        """Extract normalized TriState applicability for a given requirement_id."""
        if not decisions:
            return TriState.TRUE

        val = decisions.get(requirement_id)
        if val is None:
            val = decisions.get("default", TriState.TRUE)

        return DeterministicVerifier._normalize_applicability(val)

