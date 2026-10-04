"""Evidence recording and provenance tracking for applicability evaluation runs."""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from backend.app.services.applicability.models import (
    ApplicabilityDecision,
    ApplicabilityDecisionEvidence,
    TriState,
)


def create_decision(
    run_id: str | UUID,
    rule_version_id: str | UUID,
    result: str,
    reason: str,
    evidence_needed: list[str] | None = None,
) -> ApplicabilityDecision:
    """Create a structured applicability decision record."""
    return ApplicabilityDecision(
        id=str(uuid.uuid4()),
        run_id=run_id,
        rule_version_id=rule_version_id,
        result=result,
        reason=reason,
        evidence_needed=sorted(set(evidence_needed or [])),
        review_status="draft",
    )


def create_evidence(
    decision_id: str | UUID,
    evaluation: TriState | str,
    reason: str,
    condition_id: str | UUID | None = None,
    fact_id: str | UUID | None = None,
    source_link_id: str | UUID | None = None,
) -> ApplicabilityDecisionEvidence:
    """Create an atomic evidence justification entry for a condition evaluation."""
    eval_str = evaluation.value if isinstance(evaluation, TriState) else str(evaluation)
    return ApplicabilityDecisionEvidence(
        id=str(uuid.uuid4()),
        decision_id=decision_id,
        condition_id=condition_id,
        fact_id=fact_id,
        source_link_id=source_link_id,
        evaluation=eval_str,
        reason=reason,
    )

