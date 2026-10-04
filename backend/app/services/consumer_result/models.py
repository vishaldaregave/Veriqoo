"""Domain models and data contracts for Phase U6 — Consumer Compliance Result & Explanation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ConsumerOverallResult(str, Enum):
    """Consumer-facing classification of overall inspection compliance."""
    NO_MAJOR_ISSUES_DETECTED = "NO_MAJOR_ISSUES_DETECTED"
    COMPLIANCE_ISSUE_DETECTED = "COMPLIANCE_ISSUE_DETECTED"
    REVIEW_RECOMMENDED = "REVIEW_RECOMMENDED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class FindingSeverity(str, Enum):
    """Consumer-facing severity categorization for individual findings."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class LegalReference:
    """Safe, statutory citation details for a verified requirement."""
    requirement_id: str
    rule_number: str | None = None
    statutory_label: str | None = None
    section_reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "rule_number": self.rule_number,
            "statutory_label": self.statutory_label,
            "section_reference": self.section_reference,
        }


@dataclass
class ConsumerScore:
    """Consumer projection of the canonical compliance score."""
    score: float | None = None
    percentage: str | None = None
    rating: str = "NOT_APPLICABLE"
    rating_label: str = "Not Applicable"
    evaluated_requirements: int = 0
    pass_count: int = 0
    fail_count: int = 0
    review_count: int = 0
    not_visible_count: int = 0
    not_applicable_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "percentage": self.percentage,
            "rating": self.rating,
            "rating_label": self.rating_label,
            "evaluated_requirements": self.evaluated_requirements,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "review_count": self.review_count,
            "not_visible_count": self.not_visible_count,
            "not_applicable_count": self.not_applicable_count,
        }


@dataclass
class ConsumerFinding:
    """Structured, consumer-friendly explanation of a single requirement verification."""
    finding_id: str
    requirement_id: str
    status: str
    consumer_title: str
    consumer_explanation: str
    evidence_ids: list[str] = field(default_factory=list)
    annotation_ids: list[str] = field(default_factory=list)
    legal_reference: LegalReference | None = None
    corrective_action: str | None = None
    severity: str = FindingSeverity.INFO.value
    severity_label: str = "Info"

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "requirement_id": self.requirement_id,
            "status": self.status,
            "consumer_title": self.consumer_title,
            "consumer_explanation": self.consumer_explanation,
            "evidence_ids": list(self.evidence_ids),
            "annotation_ids": list(self.annotation_ids),
            "legal_reference": self.legal_reference.to_dict() if self.legal_reference else None,
            "corrective_action": self.corrective_action,
            "severity": self.severity,
            "severity_label": self.severity_label,
        }


@dataclass
class ConsumerReportReference:
    """Safe, non-sensitive reference to the underlying canonical inspection report."""
    inspection_id: str = ""
    image_count: int = 0
    evidence_count: int = 0
    applicable_requirement_count: int = 0
    has_report: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "inspection_id": self.inspection_id,
            "image_count": self.image_count,
            "evidence_count": self.evidence_count,
            "applicable_requirement_count": self.applicable_requirement_count,
            "has_report": self.has_report,
            "created_at": self.created_at,
        }


@dataclass
class ConsumerComplianceResult:
    """Authoritative consumer-facing compliance result and explanation layer."""
    schema_version: str = "1.0.0"
    inspection_id: str = ""
    overall_result: str = ConsumerOverallResult.NO_MAJOR_ISSUES_DETECTED.value
    canonical_status: str = "PASS"
    result_label: str = "No Major Issues Detected"
    summary: str = ""
    what_this_means: str = ""
    score: ConsumerScore = field(default_factory=ConsumerScore)
    risk_signal: str = "NO_MAJOR_ISSUES_DETECTED"
    risk_signal_label: str = "No Major Issues Detected"
    key_findings: list[ConsumerFinding] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    recommended_action_labels: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    limitation_labels: list[str] = field(default_factory=list)
    report_reference: ConsumerReportReference = field(default_factory=ConsumerReportReference)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "inspection_id": self.inspection_id,
            "overall_result": self.overall_result,
            "canonical_status": self.canonical_status,
            "result_label": self.result_label,
            "summary": self.summary,
            "what_this_means": self.what_this_means,
            "score": self.score.to_dict(),
            "risk_signal": self.risk_signal,
            "risk_signal_label": self.risk_signal_label,
            "key_findings": [f.to_dict() for f in self.key_findings],
            "recommended_actions": list(self.recommended_actions),
            "recommended_action_labels": list(self.recommended_action_labels),
            "limitations": list(self.limitations),
            "limitation_labels": list(self.limitation_labels),
            "report_reference": self.report_reference.to_dict(),
            "generated_at": self.generated_at,
            "metadata": self.metadata,
        }
