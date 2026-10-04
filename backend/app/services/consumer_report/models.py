"""Domain models and data contracts for Phase U10 — Consumer -> Authority Action Bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class ConsumerReportStatus(str, Enum):
    """Lifecycle status of a consumer-submitted authority report."""
    SUBMITTED = "SUBMITTED"
    RECEIVED = "RECEIVED"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"


class ConsumerReportEligibility(str, Enum):
    """Deterministic eligibility classification for reporting an inspection to authorities."""
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE_PASS = "INELIGIBLE_PASS"
    INELIGIBLE_NOT_APPLICABLE = "INELIGIBLE_NOT_APPLICABLE"
    INELIGIBLE_INCOMPLETE = "INELIGIBLE_INCOMPLETE"
    INELIGIBLE_FAILED = "INELIGIBLE_FAILED"


@dataclass
class ReportFindingPackage:
    """Evidence-backed statutory finding package for authority review."""
    finding_id: str
    requirement_id: str
    canonical_status: str  # FAIL, REVIEW_REQUIRED, NOT_VISIBLE
    consumer_title: str
    consumer_explanation: str
    severity: str  # HIGH, MEDIUM, LOW, INFO
    rule_number: str | None = None
    statutory_label: str | None = None
    section_reference: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    observation_ids: list[str] = field(default_factory=list)
    annotation_ids: list[str] = field(default_factory=list)
    image_ids: list[str] = field(default_factory=list)
    annotations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self, lang: str | None = None) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "requirement_id": self.requirement_id,
            "canonical_status": self.canonical_status,
            "consumer_title": self.consumer_title,
            "consumer_explanation": self.consumer_explanation,
            "severity": self.severity,
            "rule_number": self.rule_number,
            "statutory_label": self.statutory_label,
            "section_reference": self.section_reference,
            "evidence_ids": list(self.evidence_ids),
            "observation_ids": list(self.observation_ids),
            "annotation_ids": list(self.annotation_ids),
            "image_ids": list(self.image_ids),
            "annotations": list(self.annotations),
        }


@dataclass
class ConsumerReport:
    """Authoritative, evidence-backed consumer report package prepared for regulatory authority case creation."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    inspection_id: str = ""
    submitted_by: str = ""  # User ID of submitting consumer
    status: ConsumerReportStatus = ConsumerReportStatus.SUBMITTED
    canonical_overall_status: str = "FAIL"
    consumer_overall_result: str = "NON_COMPLIANT"
    consumer_description: str | None = None  # Optional consumer context notes
    product_summary: dict[str, Any] = field(default_factory=dict)
    identity_confidence: str = "UNKNOWN"
    scan_quality: dict[str, Any] = field(default_factory=dict)
    findings: list[ReportFindingPackage] = field(default_factory=list)
    priority_score: int = 0
    priority_band: str = "MEDIUM"
    priority_reasons: list[str] = field(default_factory=list)
    risk_signals: list[dict[str, Any]] = field(default_factory=list)
    location: dict[str, Any] | None = None
    inspection_created_at: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, lang: str | None = None) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "inspection_id": self.inspection_id,
            "submitted_by": self.submitted_by,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "canonical_overall_status": self.canonical_overall_status,
            "consumer_overall_result": self.consumer_overall_result,
            "consumer_description": self.consumer_description,
            "product_summary": dict(self.product_summary),
            "identity_confidence": self.identity_confidence,
            "scan_quality": dict(self.scan_quality),
            "findings": [f.to_dict(lang=lang) for f in self.findings],
            "priority_score": self.priority_score,
            "priority_band": self.priority_band,
            "priority_reasons": list(self.priority_reasons),
            "risk_signals": list(self.risk_signals),
            "location": dict(self.location) if self.location else None,
            "inspection_created_at": self.inspection_created_at,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


@dataclass
class AuthorityCaseInput:
    """Typed data contract for T3 Authority Case Management ingestion."""
    source_report_id: str
    inspection_id: str
    consumer_user_id: str
    case_type: str = "CONSUMER_GRIEVANCE"
    priority: str = "MEDIUM"
    priority_score: int = 0
    canonical_status: str = "FAIL"
    product_identity: dict[str, Any] = field(default_factory=dict)
    manufacturer_name: str | None = None
    commodity: str | None = None
    brand: str | None = None
    barcode: str | None = None
    findings_count: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)
    consumer_notes: str | None = None
    location: dict[str, Any] | None = None
    risk_signals: list[dict[str, Any]] = field(default_factory=list)
    submitted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_report_id": self.source_report_id,
            "inspection_id": self.inspection_id,
            "consumer_user_id": self.consumer_user_id,
            "case_type": self.case_type,
            "priority": self.priority,
            "priority_score": self.priority_score,
            "canonical_status": self.canonical_status,
            "product_identity": dict(self.product_identity),
            "manufacturer_name": self.manufacturer_name,
            "commodity": self.commodity,
            "brand": self.brand,
            "barcode": self.barcode,
            "findings_count": self.findings_count,
            "findings": list(self.findings),
            "consumer_notes": self.consumer_notes,
            "location": dict(self.location) if self.location else None,
            "risk_signals": list(self.risk_signals),
            "submitted_at": self.submitted_at,
        }
