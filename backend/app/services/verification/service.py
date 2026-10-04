"""Verification Service Orchestrator for Phase 5E."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.app.services.applicability.models import ApplicabilityDecision, TriState
from backend.app.services.evidence.models import EvidenceCandidate
from backend.app.services.verification.deterministic import DeterministicVerifier
from backend.app.services.verification.errors import MissingRequirementError
from backend.app.services.verification.models import (
    RequirementReference,
    VerificationResult,
    VerificationStatus,
)


class VerificationService:
    """Service layer managing deterministic requirement verification across inspections."""

    def __init__(self, verifier_cls: type[DeterministicVerifier] = DeterministicVerifier) -> None:
        self._verifier = verifier_cls

    def verify_requirement(
        self,
        requirement: RequirementReference | str,
        applicability: ApplicabilityDecision | TriState | str | bool | None = TriState.TRUE,
        candidates: Sequence[EvidenceCandidate] | None = None,
        applicability_decision_id: str | None = None,
    ) -> VerificationResult:
        return self._verifier.verify(
            requirement=requirement,
            applicability=applicability,
            candidates=candidates,
            applicability_decision_id=applicability_decision_id,
        )

    def verify_inspection(
        self,
        requirements: Sequence[RequirementReference | str],
        applicability_decisions: Mapping[str, ApplicabilityDecision | TriState | str | bool] | Sequence[ApplicabilityDecision | TriState | str | bool] | None = None,
        candidates: Sequence[EvidenceCandidate] | None = None,
    ) -> list[VerificationResult]:
        results: list[VerificationResult] = []
        evidence_list = list(candidates or [])

        for idx, req in enumerate(requirements):
            req_id: str
            if isinstance(req, str):
                req_id = req.strip()
            elif isinstance(req, RequirementReference):
                req_id = req.requirement_id
            else:
                raise MissingRequirementError(f"Invalid requirement type at index {idx}: {type(req)}")

            app_val: Any = TriState.TRUE
            app_dec_id: str | None = None

            if applicability_decisions is not None:
                if isinstance(applicability_decisions, Mapping):
                    app_val = applicability_decisions.get(req_id, TriState.UNKNOWN)
                elif isinstance(applicability_decisions, Sequence):
                    if idx < len(applicability_decisions):
                        app_val = applicability_decisions[idx]
                    else:
                        app_val = TriState.UNKNOWN

            if isinstance(app_val, ApplicabilityDecision):
                app_dec_id = str(app_val.id)

            res = self.verify_requirement(
                requirement=req,
                applicability=app_val,
                candidates=evidence_list,
                applicability_decision_id=app_dec_id,
            )
            results.append(res)

        return results

