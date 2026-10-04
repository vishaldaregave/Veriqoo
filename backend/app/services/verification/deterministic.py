"""Deterministic Verification Engine for Phase 5E."""

from __future__ import annotations

from typing import Any, Sequence
import uuid

from backend.app.services.applicability.models import ApplicabilityDecision, TriState
from backend.app.services.evidence.models import EvidenceCandidate, EvidenceStatus
from backend.app.services.verification.errors import MissingRequirementError
from backend.app.services.verification.evidence_matcher import EvidenceMatcher
from backend.app.services.verification.models import (
    RequirementReference,
    VerificationResult,
    VerificationStatus,
)


class DeterministicVerifier:
    """Pure in-memory deterministic verifier for legal metrology requirements."""

    @classmethod
    def verify(
        cls,
        requirement: RequirementReference | str,
        applicability: ApplicabilityDecision | TriState | str | bool | None,
        candidates: Sequence[EvidenceCandidate] | None = None,
        applicability_decision_id: str | None = None,
        verification_id: str | None = None,
    ) -> VerificationResult:
        req_ref: RequirementReference
        if isinstance(requirement, str):
            if not requirement.strip():
                raise MissingRequirementError("requirement_id is mandatory and cannot be empty.")
            req_ref = RequirementReference(requirement_id=requirement.strip())
        elif isinstance(requirement, RequirementReference):
            req_ref = requirement
        else:
            raise MissingRequirementError(f"Invalid requirement type: {type(requirement)}")

        if not req_ref.requirement_id or not str(req_ref.requirement_id).strip():
            raise MissingRequirementError("requirement_id is mandatory and cannot be empty.")

        v_id = verification_id or str(uuid.uuid4())
        app_dec_id = applicability_decision_id
        if isinstance(applicability, ApplicabilityDecision):
            app_dec_id = str(applicability.id)

        app_state = cls._normalize_applicability(applicability)

        if app_state == TriState.FALSE:
            return VerificationResult(
                verification_id=v_id,
                requirement_id=str(req_ref.requirement_id),
                applicability_decision_id=app_dec_id,
                status=VerificationStatus.NOT_APPLICABLE,
                reason="Requirement is not applicable under current inspection facts.",
                evidence_ids=[],
                source_observation_ids=[],
                image_ids=[],
                confidence=None,
                review_required=False,
            )

        if app_state == TriState.UNKNOWN:
            return VerificationResult(
                verification_id=v_id,
                requirement_id=str(req_ref.requirement_id),
                applicability_decision_id=app_dec_id,
                status=VerificationStatus.REVIEW_REQUIRED,
                reason="Applicability of requirement is UNKNOWN. Human review required before compliance evaluation.",
                evidence_ids=[],
                source_observation_ids=[],
                image_ids=[],
                confidence=None,
                review_required=True,
            )

        evidence_list = list(candidates or [])
        matched = EvidenceMatcher.match_candidates(req_ref, evidence_list)

        evidence_ids: list[str] = []
        observation_ids: list[str] = []
        image_ids: list[str] = []

        for cand in matched:
            if cand.evidence_id:
                evidence_ids.append(str(cand.evidence_id))
            if cand.observation_id:
                observation_ids.append(str(cand.observation_id))
            if cand.image_id:
                image_ids.append(str(cand.image_id))

        evidence_ids = list(dict.fromkeys(evidence_ids))
        observation_ids = list(dict.fromkeys(observation_ids))
        image_ids = list(dict.fromkeys(image_ids))

        if not matched:
            return VerificationResult(
                verification_id=v_id,
                requirement_id=str(req_ref.requirement_id),
                applicability_decision_id=app_dec_id,
                status=VerificationStatus.NOT_VISIBLE,
                reason="Requirement applies, but required declaration was not visible in provided evidence.",
                evidence_ids=[],
                source_observation_ids=[],
                image_ids=[],
                confidence=None,
                review_required=False,
            )

        contradictions = EvidenceMatcher.find_contradictions(matched)
        if contradictions:
            c1, c2 = contradictions[0]
            return VerificationResult(
                verification_id=v_id,
                requirement_id=str(req_ref.requirement_id),
                applicability_decision_id=app_dec_id,
                status=VerificationStatus.REVIEW_REQUIRED,
                reason=(
                    f"Contradictory declarations detected for requirement {req_ref.requirement_id}: "
                    f"candidate {c1.evidence_id} ('{c1.raw_text}') vs candidate {c2.evidence_id} ('{c2.raw_text}')."
                ),
                evidence_ids=evidence_ids,
                source_observation_ids=observation_ids,
                image_ids=image_ids,
                confidence=None,
                review_required=True,
                metadata={"contradictions_count": len(contradictions)},
            )

        valid_candidates = [c for c in matched if c.status == EvidenceStatus.VALID]
        ambiguous_candidates = [c for c in matched if c.status == EvidenceStatus.AMBIGUOUS]
        unparsed_candidates = [
            c for c in matched if c.status in (EvidenceStatus.UNPARSED, EvidenceStatus.INSUFFICIENT_EVIDENCE)
        ]

        if not valid_candidates:
            ambig_notes = []
            if ambiguous_candidates:
                ambig_notes.append(f"{len(ambiguous_candidates)} ambiguous candidate(s)")
            if unparsed_candidates:
                ambig_notes.append(f"{len(unparsed_candidates)} unparsed candidate(s)")

            reason_detail = ", ".join(ambig_notes) if ambig_notes else "insufficient evidence"
            return VerificationResult(
                verification_id=v_id,
                requirement_id=str(req_ref.requirement_id),
                applicability_decision_id=app_dec_id,
                status=VerificationStatus.REVIEW_REQUIRED,
                reason=f"Evidence for requirement is ambiguous or unparsed ({reason_detail}). Requires manual review.",
                evidence_ids=evidence_ids,
                source_observation_ids=observation_ids,
                image_ids=image_ids,
                confidence=None,
                review_required=True,
            )

        return VerificationResult(
            verification_id=v_id,
            requirement_id=str(req_ref.requirement_id),
            applicability_decision_id=app_dec_id,
            status=VerificationStatus.PASS,
            reason=f"Requirement satisfied by {len(valid_candidates)} valid declaration candidate(s).",
            evidence_ids=evidence_ids,
            source_observation_ids=observation_ids,
            image_ids=image_ids,
            confidence=None,
            review_required=False,
            metadata={"valid_candidate_count": len(valid_candidates)},
        )

    @staticmethod
    def _normalize_applicability(applicability: Any) -> TriState:
        if applicability is None:
            return TriState.UNKNOWN

        if isinstance(applicability, TriState):
            return applicability

        if isinstance(applicability, ApplicabilityDecision):
            res = str(applicability.result).lower().strip()
            if res in ("true", "applicable", "yes", "1"):
                return TriState.TRUE
            if res in ("false", "not_applicable", "no", "0"):
                return TriState.FALSE
            return TriState.UNKNOWN

        if isinstance(applicability, bool):
            return TriState.TRUE if applicability else TriState.FALSE

        if isinstance(applicability, str):
            res = applicability.lower().strip()
            if res in ("true", "applicable", "pass", "yes", "1"):
                return TriState.TRUE
            if res in ("false", "not_applicable", "no", "0"):
                return TriState.FALSE
            if res in ("unknown", "undetermined", "review_required"):
                return TriState.UNKNOWN

        return TriState.UNKNOWN

