"""In-memory domain models and three-valued logic representations for Phase 3B."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


class TriState(str, Enum):
    """Strong Kleene Three-Valued Logic states plus not-evaluated tracking."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    NOT_EVALUATED = "not_evaluated"

    @classmethod
    def kleene_and(cls, left: TriState, right: TriState) -> TriState:
        """Strong Kleene AND (conjunction).

        FALSE dominates.
        TRUE only if both are TRUE.
        Otherwise UNKNOWN.
        """
        if left == cls.FALSE or right == cls.FALSE:
            return cls.FALSE
        if left == cls.TRUE and right == cls.TRUE:
            return cls.TRUE
        return cls.UNKNOWN

    @classmethod
    def kleene_or(cls, left: TriState, right: TriState) -> TriState:
        """Strong Kleene OR (disjunction).

        TRUE dominates.
        FALSE only if both are FALSE.
        Otherwise UNKNOWN.
        """
        if left == cls.TRUE or right == cls.TRUE:
            return cls.TRUE
        if left == cls.FALSE and right == cls.FALSE:
            return cls.FALSE
        return cls.UNKNOWN

    @classmethod
    def kleene_not(cls, value: TriState) -> TriState:
        """Strong Kleene NOT (negation)."""
        if value == cls.TRUE:
            return cls.FALSE
        if value == cls.FALSE:
            return cls.TRUE
        return cls.UNKNOWN


@dataclass(frozen=True)
class ApplicabilityRun:
    """Represents an inspection applicability evaluation run."""

    id: str | UUID
    inspection_reference: str
    inspection_date: date | None = None
    created_at: datetime | None = None
    engine_version: str = "1.0.0"
    status: str = "draft"


@dataclass(frozen=True)
class InspectionFact:
    """An observed or attested inspection fact."""

    id: str | UUID
    run_id: str | UUID
    fact_key: str
    value: Any = None
    unit: str | None = None
    fact_status: str = "known"
    origin: str = "inspection"
    evidence_reference: dict[str, Any] | None = None
    observed_text: str | None = None
    sequence: int = 1
    review_status: str = "draft"


@dataclass(frozen=True)
class ApplicabilityRule:
    """A legal applicability rule entity."""

    id: str | UUID
    rule_key: str
    created_at: datetime | None = None
    created_by: str | None = None


@dataclass(frozen=True)
class ApplicabilityRuleVersion:
    """A versioned interpretation of an applicability rule."""

    id: str | UUID
    rule_id: str | UUID
    version_number: int
    interpretation_status: str
    valid_from: date | None = None
    valid_to: date | None = None
    amendment_id: str | UUID | None = None
    created_at: datetime | None = None
    created_by: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    review_note: str | None = None


@dataclass(frozen=True)
class ApplicabilityConditionGroup:
    """Hierarchical boolean condition group."""

    id: str | UUID
    rule_version_id: str | UUID
    parent_group_id: str | UUID | None = None
    group_purpose: str = "applicability"
    boolean_operator: str = "AND"
    sequence: int = 1
    review_status: str = "approved"
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None


@dataclass(frozen=True)
class ApplicabilityCondition:
    """Atomic evaluation condition evaluated against inspection facts."""

    id: str | UUID
    group_id: str | UUID
    fact_key: str
    operator: str
    expected_value: Any = None
    expected_unit: str | None = None
    sequence: int = 1
    review_status: str = "approved"
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None


@dataclass(frozen=True)
class ApplicabilityRuleSource:
    """Statutory provenance link for a rule version or condition."""

    id: str | UUID
    rule_version_id: str | UUID
    requirement_id: str | UUID
    provision_id: int
    schedule_id: str | UUID | None = None
    schedule_entry_id: str | UUID | None = None
    table_id: str | UUID | None = None
    amendment_id: str | UUID | None = None
    condition_group_id: str | UUID | None = None
    condition_id: str | UUID | None = None
    source_role: str = "supports"
    source_quote: str = ""
    source_reference: dict[str, Any] = field(default_factory=dict)
    review_status: str = "approved"
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None


@dataclass
class ApplicabilityDecision:
    """Final applicability determination for a run and rule version."""

    id: str | UUID
    run_id: str | UUID
    rule_version_id: str | UUID
    result: str
    reason: str
    evidence_needed: list[str] = field(default_factory=list)
    review_status: str = "draft"
    created_at: datetime | None = None
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None


@dataclass
class ApplicabilityDecisionEvidence:
    """Fine-grained atomic evidence justification row."""

    id: str | UUID
    decision_id: str | UUID
    condition_id: str | UUID | None = None
    fact_id: str | UUID | None = None
    source_link_id: str | UUID | None = None
    evaluation: str = "not_evaluated"
    reason: str = ""

