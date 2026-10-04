"""Gemini Evidence Reasoning Service for Phase 6.

Orchestrates structured evidence assessment via Gemini, enforces prompt injection defenses,
validates model responses, and passes recommendations through the Phase 5E deterministic safety gate.
"""

from __future__ import annotations

import json
from typing import Any, Sequence
import uuid

from backend.app.services.applicability.models import ApplicabilityDecision, TriState
from backend.app.services.evidence.models import EvidenceCandidate, EvidenceStatus
from backend.app.services.gemini.client import BaseGeminiClient, RealGeminiClient
from backend.app.services.gemini.config import GeminiConfig
from backend.app.services.gemini.errors import (
    GeminiAuthenticationError,
    GeminiError,
    GeminiProviderError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiValidationError,
)
from backend.app.services.gemini.models import (
    EvidenceSufficiency,
    GeminiEvidenceAssessment,
    GeminiRecommendation,
    GeminiVerificationRequest,
)
from backend.app.services.gemini.prompts import (
    PROMPT_VERSION,
    SYSTEM_INSTRUCTION,
    format_evidence_reasoning_prompt,
)
from backend.app.services.verification.deterministic import DeterministicVerifier
from backend.app.services.verification.models import (
    RequirementReference,
    VerificationResult,
    VerificationStatus,
)


class GeminiEvidenceService:
    """Constrained evidence reasoning service using Gemini."""

    def __init__(
        self,
        client: BaseGeminiClient | None = None,
        config: GeminiConfig | None = None,
    ) -> None:
        self.config = config or GeminiConfig.from_env()
        self.client = client or (RealGeminiClient(self.config) if self.config.api_key else None)

    def evaluate_requirement(self, request: GeminiVerificationRequest) -> GeminiEvidenceAssessment:
        """Submit evidence candidates to Gemini and validate the structured response."""
        # 1. Applicability Gate Check: Do NOT call Gemini if applicability is NOT_APPLICABLE or UNKNOWN
        app_status = str(request.applicability_status).upper().strip()
        if app_status in ("NOT_APPLICABLE", "FALSE"):
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
                reason="Requirement is not applicable; evaluation bypassed.",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
            )

        if app_status in ("UNKNOWN", "UNDETERMINED"):
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.AMBIGUOUS,
                reason="Applicability status is UNKNOWN. Requires human review.",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
            )

        # 2. Check client availability
        if self.client is None:
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
                reason="Gemini client is unavailable or not configured.",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
            )

        # 3. Format Prompt & Execute with bounded error handling
        prompt = format_evidence_reasoning_prompt(request)
        try:
            raw_response = self.client.generate_content(prompt, system_instruction=SYSTEM_INSTRUCTION)
        except GeminiRateLimitError as err:
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
                reason=f"Gemini rate limit encountered: {err}",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
                metadata={"error_type": "RATE_LIMITED"},
            )
        except GeminiTimeoutError as err:
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
                reason=f"Gemini execution timed out: {err}",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
                metadata={"error_type": "TIMEOUT"},
            )
        except GeminiAuthenticationError as err:
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
                reason=f"Gemini authentication error: {err}",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
                metadata={"error_type": "AUTHENTICATION_ERROR"},
            )
        except GeminiError as err:
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
                reason=f"Gemini provider error: {err}",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
                metadata={"error_type": "PROVIDER_ERROR"},
            )
        except Exception as err:
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
                reason=f"Unexpected failure during Gemini reasoning: {type(err).__name__}",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
                metadata={"error_type": "UNEXPECTED_ERROR"},
            )

        # 4. Parse JSON & Validate Response Contract
        return self._validate_and_parse_response(raw_response, request)

    def _validate_and_parse_response(
        self,
        raw_response: str,
        request: GeminiVerificationRequest,
    ) -> GeminiEvidenceAssessment:
        """Strictly validate Gemini output JSON against allowed schema, IDs, and safety constraints."""
        # Strip potential markdown fences if present
        text = raw_response.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
        except Exception:
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.AMBIGUOUS,
                reason="Malformed non-JSON output returned by Gemini reasoning.",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
                metadata={"raw_response": raw_response[:200]},
            )

        if not isinstance(data, dict):
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.AMBIGUOUS,
                reason="Gemini output is not a JSON object.",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
            )

        # Validate requirement_id match
        resp_req_id = str(data.get("requirement_id", "")).strip()
        if resp_req_id != request.requirement_id:
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.AMBIGUOUS,
                reason=f"Mismatched requirement_id in Gemini response ('{resp_req_id}' vs expected '{request.requirement_id}').",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
            )

        # Validate recommendation enum
        raw_rec = str(data.get("recommendation", "")).upper().strip()
        if raw_rec not in [r.value for r in GeminiRecommendation]:
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.AMBIGUOUS,
                reason=f"Invalid recommendation status '{raw_rec}' returned by Gemini.",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
            )
        recommendation = GeminiRecommendation(raw_rec)

        # Validate evidence_sufficiency enum
        raw_suff = str(data.get("evidence_sufficiency", "")).upper().strip()
        if raw_suff not in [s.value for s in EvidenceSufficiency]:
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.AMBIGUOUS,
                reason=f"Invalid evidence_sufficiency status '{raw_suff}' returned by Gemini.",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
            )
        sufficiency = EvidenceSufficiency(raw_suff)

        reason = str(data.get("reason", "Assessment completed by Gemini."))
        raw_ev_ids = data.get("evidence_ids", [])
        if not isinstance(raw_ev_ids, list):
            raw_ev_ids = []
        evidence_ids = [str(x) for x in raw_ev_ids]

        ambiguities = [str(x) for x in data.get("ambiguities", [])] if isinstance(data.get("ambiguities"), list) else []
        contradictions = [str(x) for x in data.get("contradictions", [])] if isinstance(data.get("contradictions"), list) else []
        unsupported = [str(x) for x in data.get("unsupported_claims", [])] if isinstance(data.get("unsupported_claims"), list) else []

        # Validate Evidence IDs: must actually exist in input evidence_candidates
        valid_input_ids = {c.evidence_id for c in request.evidence_candidates}
        unknown_ids = [eid for eid in evidence_ids if eid not in valid_input_ids]
        if unknown_ids:
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.AMBIGUOUS,
                reason=f"Gemini cited unknown/fabricated evidence IDs: {unknown_ids}.",
                evidence_ids=[eid for eid in evidence_ids if eid in valid_input_ids],
                ambiguities=ambiguities + [f"Cited unknown evidence IDs: {unknown_ids}"],
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
            )

        # Validate Unsupported Claims: recommendation cannot be PASS or FAIL without cited evidence IDs
        if recommendation in (GeminiRecommendation.PASS, GeminiRecommendation.FAIL) and not evidence_ids:
            return GeminiEvidenceAssessment(
                requirement_id=request.requirement_id,
                recommendation=GeminiRecommendation.REVIEW_REQUIRED,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
                reason=f"Gemini recommended {recommendation.value} without citing any supporting evidence IDs.",
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
            )

        # Validate Ambiguity / Contradiction Guard
        if contradictions:
            recommendation = GeminiRecommendation.REVIEW_REQUIRED
            sufficiency = EvidenceSufficiency.CONTRADICTORY

        return GeminiEvidenceAssessment(
            requirement_id=request.requirement_id,
            recommendation=recommendation,
            evidence_sufficiency=sufficiency,
            reason=reason,
            evidence_ids=evidence_ids,
            ambiguities=ambiguities,
            contradictions=contradictions,
            unsupported_claims=unsupported,
            model=self.config.model,
            prompt_version=PROMPT_VERSION,
        )

    def verify_with_gemini_and_gate(
        self,
        requirement: RequirementReference | str,
        applicability: ApplicabilityDecision | TriState | str | bool | None = TriState.TRUE,
        candidates: Sequence[EvidenceCandidate] | None = None,
        applicability_decision_id: str | None = None,
    ) -> VerificationResult:
        """Full verification flow: Applicability Gate -> Gemini Reasoning -> Phase 5E Safety Gate."""
        # 1. Normalize requirement
        req_ref = requirement if isinstance(requirement, RequirementReference) else RequirementReference(requirement_id=str(requirement))
        evidence_list = list(candidates or [])

        # 2. Check Applicability Gate (Gemini is NEVER called if NOT_APPLICABLE or UNKNOWN)
        norm_app = DeterministicVerifier._normalize_applicability(applicability)

        if norm_app == TriState.FALSE:
            return VerificationResult(
                requirement_id=req_ref.requirement_id,
                applicability_decision_id=applicability_decision_id,
                status=VerificationStatus.NOT_APPLICABLE,
                reason="Requirement is not applicable under current inspection facts (applicability gate).",
            )

        if norm_app == TriState.UNKNOWN:
            return VerificationResult(
                requirement_id=req_ref.requirement_id,
                applicability_decision_id=applicability_decision_id,
                status=VerificationStatus.REVIEW_REQUIRED,
                reason="Applicability of requirement is UNKNOWN. Requires manual review (applicability gate).",
                review_required=True,
            )

        # 3. Handle Empty Evidence -> NOT_VISIBLE (NOT FAIL)
        if not evidence_list:
            return VerificationResult(
                requirement_id=req_ref.requirement_id,
                applicability_decision_id=applicability_decision_id,
                status=VerificationStatus.NOT_VISIBLE,
                reason="Requirement applies, but required declaration was not visible in provided evidence.",
                review_required=False,
            )

        # 4. Formulate Gemini Request
        req_text = req_ref.requirement_text or f"Statutory declaration requirement for {req_ref.requirement_id}"
        gemini_req = GeminiVerificationRequest(
            requirement_id=req_ref.requirement_id,
            requirement_text=req_text,
            requirement_source_reference=req_ref.section_reference or req_ref.rule_number,
            applicability_status="APPLICABLE",
            evidence_candidates=evidence_list,
        )

        # 5. Execute Gemini Reasoning
        assessment = self.evaluate_requirement(gemini_req)

        # 6. Extract Traceability from cited evidence candidates
        cited_cands = [c for c in evidence_list if c.evidence_id in assessment.evidence_ids]
        obs_ids = list(dict.fromkeys([str(c.observation_id) for c in cited_cands if c.observation_id]))
        img_ids = list(dict.fromkeys([str(c.image_id) for c in cited_cands if c.image_id]))

        # 7. Pass through Phase 5E Safety Gate
        # If any cited candidate is AMBIGUOUS or UNPARSED, PASS cannot be accepted
        has_ambiguous_evidence = any(c.status != EvidenceStatus.VALID for c in cited_cands)
        if assessment.recommendation == GeminiRecommendation.PASS and has_ambiguous_evidence:
            return VerificationResult(
                requirement_id=req_ref.requirement_id,
                applicability_decision_id=applicability_decision_id,
                status=VerificationStatus.REVIEW_REQUIRED,
                reason="Phase 5E safety gate: Gemini recommended PASS, but underlying evidence status is ambiguous/unparsed.",
                evidence_ids=assessment.evidence_ids,
                source_observation_ids=obs_ids,
                image_ids=img_ids,
                review_required=True,
                metadata={"gemini_assessment": assessment.to_dict()},
            )

        # Map recommendation to VerificationStatus
        if assessment.recommendation == GeminiRecommendation.PASS:
            return VerificationResult(
                requirement_id=req_ref.requirement_id,
                applicability_decision_id=applicability_decision_id,
                status=VerificationStatus.PASS,
                reason=assessment.reason,
                evidence_ids=assessment.evidence_ids,
                source_observation_ids=obs_ids,
                image_ids=img_ids,
                review_required=False,
                metadata={"gemini_assessment": assessment.to_dict()},
            )

        if assessment.recommendation == GeminiRecommendation.FAIL:
            return VerificationResult(
                requirement_id=req_ref.requirement_id,
                applicability_decision_id=applicability_decision_id,
                status=VerificationStatus.FAIL,
                reason=assessment.reason,
                evidence_ids=assessment.evidence_ids,
                source_observation_ids=obs_ids,
                image_ids=img_ids,
                review_required=False,
                metadata={"gemini_assessment": assessment.to_dict()},
            )

        # Default fallback to REVIEW_REQUIRED
        return VerificationResult(
            requirement_id=req_ref.requirement_id,
            applicability_decision_id=applicability_decision_id,
            status=VerificationStatus.REVIEW_REQUIRED,
            reason=assessment.reason,
            evidence_ids=assessment.evidence_ids,
            source_observation_ids=obs_ids,
            image_ids=img_ids,
            review_required=True,
            metadata={"gemini_assessment": assessment.to_dict()},
        )
