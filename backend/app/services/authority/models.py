"""Domain models and data contracts for Phase U9 — Authority Intelligence & Risk Prioritization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AuthorityPriority(str, Enum):
    """Deterministic priority classification for inspection queue ranking."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class TrendDirection(str, Enum):
    """Observed historical frequency trend."""
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class RiskSignalCode(str, Enum):
    """Categorical risk signals for authority decision support."""
    REPEATED_FAILURES = "REPEATED_FAILURES"
    HIGH_FAILURE_BURDEN = "HIGH_FAILURE_BURDEN"
    LOW_COMPLIANCE_SCORE = "LOW_COMPLIANCE_SCORE"
    HIGH_RISK_NON_COMPLIANCE = "HIGH_RISK_NON_COMPLIANCE"
    POTENTIAL_COMPLIANCE_ISSUE = "POTENTIAL_COMPLIANCE_ISSUE"
    PRODUCT_IDENTITY_CONFIRMED = "PRODUCT_IDENTITY_CONFIRMED"
    PRODUCT_IDENTITY_UNCERTAIN = "PRODUCT_IDENTITY_UNCERTAIN"
    GEOGRAPHIC_ISSUE_ELEVATED = "GEOGRAPHIC_ISSUE_ELEVATED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_MAJOR_ISSUES_DETECTED = "NO_MAJOR_ISSUES_DETECTED"


@dataclass
class AuthorityRiskSignal:
    """Structured, explainable risk indicator derived from canonical inspection facts."""
    code: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    explanation: str
    source: str  # U1, U5, U6, U7, REPEAT_ANALYSIS
    evidence_ids: list[str] = field(default_factory=list)
    requirement_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "explanation": self.explanation,
            "source": self.source,
            "evidence_ids": list(self.evidence_ids),
            "requirement_ids": list(self.requirement_ids),
        }


@dataclass
class AuthorityPriorityItem:
    """Prioritized inspection item for authority enforcement decision support."""
    inspection_id: str
    priority: AuthorityPriority
    priority_score: int  # 0 to 100 bounded deterministic integer
    reasons: list[str]
    canonical_status: str  # PASS, FAIL, REVIEW_REQUIRED
    risk_signal: str  # U5 risk signal
    compliance_score: float | None
    rating: str | None
    failed_requirement_count: int
    review_required_count: int
    not_visible_count: int
    risk_signals: list[AuthorityRiskSignal] = field(default_factory=list)
    product_summary: dict[str, Any] = field(default_factory=dict)
    identity_confidence: str = "UNKNOWN"
    location: dict[str, Any] | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "inspection_id": self.inspection_id,
            "priority": self.priority.value,
            "priority_score": self.priority_score,
            "reasons": list(self.reasons),
            "canonical_status": self.canonical_status,
            "risk_signal": self.risk_signal,
            "compliance_score": self.compliance_score,
            "rating": self.rating,
            "failed_requirement_count": self.failed_requirement_count,
            "review_required_count": self.review_required_count,
            "not_visible_count": self.not_visible_count,
            "risk_signals": [s.to_dict() for s in self.risk_signals],
            "product_summary": dict(self.product_summary),
            "identity_confidence": self.identity_confidence,
            "location": dict(self.location) if self.location else None,
            "created_at": self.created_at,
        }


@dataclass
class ManufacturerIntelligenceSummary:
    """Aggregated compliance profile for an identified manufacturer."""
    manufacturer_name: str
    inspection_count: int
    pass_count: int
    fail_count: int
    review_count: int
    observed_issue_rate: float
    repeat_issue_count: int
    top_violation_categories: list[dict[str, Any]] = field(default_factory=list)
    identity_confidence: str = "HIGH"
    trend: TrendDirection = TrendDirection.INSUFFICIENT_DATA
    last_inspected_at: str | None = None
    disclaimer: str = (
        "Based strictly on Veriqoo observed inspection sample records. "
        "Does not constitute an official legal determination or regulatory penalty."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "manufacturer_name": self.manufacturer_name,
            "inspection_count": self.inspection_count,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "review_count": self.review_count,
            "observed_issue_rate": self.observed_issue_rate,
            "repeat_issue_count": self.repeat_issue_count,
            "top_violation_categories": list(self.top_violation_categories),
            "identity_confidence": self.identity_confidence,
            "trend": self.trend.value,
            "last_inspected_at": self.last_inspected_at,
            "disclaimer": self.disclaimer,
        }


@dataclass
class ProductIntelligenceSummary:
    """Aggregated compliance profile for an identified commodity or product."""
    product_key: str
    brand: str | None = None
    generic_name: str | None = None
    commodity: str | None = None
    barcode: str | None = None
    inspection_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    review_count: int = 0
    observed_issue_rate: float = 0.0
    top_violation_categories: list[dict[str, Any]] = field(default_factory=list)
    identity_confidence: str = "HIGH"
    trend: TrendDirection = TrendDirection.INSUFFICIENT_DATA
    last_inspected_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_key": self.product_key,
            "brand": self.brand,
            "generic_name": self.generic_name,
            "commodity": self.commodity,
            "barcode": self.barcode,
            "inspection_count": self.inspection_count,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "review_count": self.review_count,
            "observed_issue_rate": self.observed_issue_rate,
            "top_violation_categories": list(self.top_violation_categories),
            "identity_confidence": self.identity_confidence,
            "trend": self.trend.value,
            "last_inspected_at": self.last_inspected_at,
        }


@dataclass
class AuthorityOverviewMetrics:
    """High-level summary metrics for authority intelligence overview dashboard."""
    total_completed_inspections: int
    critical_priority_count: int
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    overall_observed_issue_rate: float
    active_manufacturers_tracked: int
    top_violated_requirements: list[dict[str, Any]] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_completed_inspections": self.total_completed_inspections,
            "critical_priority_count": self.critical_priority_count,
            "high_priority_count": self.high_priority_count,
            "medium_priority_count": self.medium_priority_count,
            "low_priority_count": self.low_priority_count,
            "overall_observed_issue_rate": self.overall_observed_issue_rate,
            "active_manufacturers_tracked": self.active_manufacturers_tracked,
            "top_violated_requirements": list(self.top_violated_requirements),
            "generated_at": self.generated_at,
        }
