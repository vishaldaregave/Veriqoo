"""Domain models and data contracts for Phase U5 — Consumer Scan Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ScanContext(str, Enum):
    """Context and actor role of an inspection scan."""
    CONSUMER = "CONSUMER"
    INSPECTOR = "INSPECTOR"


class IdentityConfidence(str, Enum):
    """Deterministic confidence rating for product identity extraction."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class RiskSignal(str, Enum):
    """Deterministic consumer risk classification signal."""
    HIGH_RISK_NON_COMPLIANCE = "HIGH_RISK_NON_COMPLIANCE"
    POTENTIAL_COMPLIANCE_ISSUE = "POTENTIAL_COMPLIANCE_ISSUE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PRODUCT_IDENTITY_UNCERTAIN = "PRODUCT_IDENTITY_UNCERTAIN"
    NO_MAJOR_ISSUES_DETECTED = "NO_MAJOR_ISSUES_DETECTED"


class ConsumerAction(str, Enum):
    """Deterministic action suggestions for consumer guidance."""
    REVIEW_LABEL = "REVIEW_LABEL"
    CHECK_MRP = "CHECK_MRP"
    CHECK_NET_QUANTITY = "CHECK_NET_QUANTITY"
    CHECK_MANUFACTURER_DETAILS = "CHECK_MANUFACTURER_DETAILS"
    CHECK_CONSUMER_CARE_DETAILS = "CHECK_CONSUMER_CARE_DETAILS"
    CAPTURE_BACK_PANEL = "CAPTURE_BACK_PANEL"
    CAPTURE_FRONT_PANEL = "CAPTURE_FRONT_PANEL"
    RESCAN_PACKAGE = "RESCAN_PACKAGE"
    REVIEW_REPORT = "REVIEW_REPORT"


class ScanQualityIssue(str, Enum):
    """Deterministic scan quality diagnostic signals."""
    INSUFFICIENT_IMAGES = "INSUFFICIENT_IMAGES"
    LOW_OCR_CONFIDENCE = "LOW_OCR_CONFIDENCE"
    INCOMPLETE_PACKAGE_VIEW = "INCOMPLETE_PACKAGE_VIEW"
    CONFLICTING_OBSERVATIONS = "CONFLICTING_OBSERVATIONS"
    INSUFFICIENT_REQUIRED_DECLARATIONS = "INSUFFICIENT_REQUIRED_DECLARATIONS"
    PRODUCT_IDENTITY_UNCERTAIN = "PRODUCT_IDENTITY_UNCERTAIN"


@dataclass
class FieldProvenance:
    """Provenance tracking origin of an extracted product declaration field."""
    evidence_id: str | None = None
    observation_id: str | None = None
    image_id: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "observation_id": self.observation_id,
            "image_id": self.image_id,
            "confidence": self.confidence,
        }


@dataclass
class ExtractedProductField:
    """Single extracted declaration field with provenance and conflict tracking."""
    value: Any
    unit: str | None = None
    provenance: list[FieldProvenance] = field(default_factory=list)
    is_conflicting: bool = False
    conflicting_values: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "provenance": [p.to_dict() for p in self.provenance],
            "is_conflicting": self.is_conflicting,
            "conflicting_values": self.conflicting_values,
        }


@dataclass
class ProductIdentity:
    """Structured product and commodity identity inferred from evidence candidates."""
    brand: ExtractedProductField | None = None
    generic_name: ExtractedProductField | None = None
    commodity: ExtractedProductField | None = None
    net_quantity: ExtractedProductField | None = None
    package_type: ExtractedProductField | None = None
    manufacturer_name: ExtractedProductField | None = None
    manufacturer_address: ExtractedProductField | None = None
    country_of_origin: ExtractedProductField | None = None
    batch_number: ExtractedProductField | None = None
    barcode: ExtractedProductField | None = None
    declared_mrp: ExtractedProductField | None = None
    user_entered_selling_price: float | None = None
    manufacturing_date: ExtractedProductField | None = None
    expiry_date: ExtractedProductField | None = None
    consumer_care: ExtractedProductField | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "brand": self.brand.to_dict() if self.brand else None,
            "generic_name": self.generic_name.to_dict() if self.generic_name else None,
            "commodity": self.commodity.to_dict() if self.commodity else None,
            "net_quantity": self.net_quantity.to_dict() if self.net_quantity else None,
            "package_type": self.package_type.to_dict() if self.package_type else None,
            "manufacturer_name": self.manufacturer_name.to_dict() if self.manufacturer_name else None,
            "manufacturer_address": self.manufacturer_address.to_dict() if self.manufacturer_address else None,
            "country_of_origin": self.country_of_origin.to_dict() if self.country_of_origin else None,
            "batch_number": self.batch_number.to_dict() if self.batch_number else None,
            "barcode": self.barcode.to_dict() if self.barcode else None,
            "declared_mrp": self.declared_mrp.to_dict() if self.declared_mrp else None,
            "user_entered_selling_price": self.user_entered_selling_price,
            "manufacturing_date": self.manufacturing_date.to_dict() if self.manufacturing_date else None,
            "expiry_date": self.expiry_date.to_dict() if self.expiry_date else None,
            "consumer_care": self.consumer_care.to_dict() if self.consumer_care else None,
        }


@dataclass
class ScanQuality:
    """Deterministic quality signals of the input package capture."""
    is_acceptable: bool = True
    quality_score: float = 1.0
    issues: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_acceptable": self.is_acceptable,
            "quality_score": self.quality_score,
            "issues": self.issues,
            "details": self.details,
        }


@dataclass
class ConsumerComplianceSummary:
    """Lightweight compliance summary projection for consumer scan context."""
    overall_status: str
    pass_count: int = 0
    fail_count: int = 0
    review_required_count: int = 0
    not_visible_count: int = 0
    not_applicable_count: int = 0
    total_evaluated: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "review_required_count": self.review_required_count,
            "not_visible_count": self.not_visible_count,
            "not_applicable_count": self.not_applicable_count,
            "total_evaluated": self.total_evaluated,
        }


@dataclass
class ConsumerScanIntelligence:
    """Authoritative structured intelligence output for consumer 'Scan Before You Buy'."""
    schema_version: str = "1.0.0"
    inspection_id: str = ""
    scan_context: str = ScanContext.CONSUMER.value
    product_identity: ProductIdentity = field(default_factory=ProductIdentity)
    identity_confidence: str = IdentityConfidence.UNKNOWN.value
    scan_quality: ScanQuality = field(default_factory=ScanQuality)
    compliance_summary: ConsumerComplianceSummary = field(default_factory=lambda: ConsumerComplianceSummary(overall_status="REVIEW_REQUIRED"))
    risk_signal: str = RiskSignal.POTENTIAL_COMPLIANCE_ISSUE.value
    risk_signal_label: str = "Potential Compliance Issue"
    consumer_actions: list[str] = field(default_factory=list)
    consumer_action_labels: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "inspection_id": self.inspection_id,
            "scan_context": self.scan_context,
            "product_identity": self.product_identity.to_dict(),
            "identity_confidence": self.identity_confidence,
            "scan_quality": self.scan_quality.to_dict(),
            "compliance_summary": self.compliance_summary.to_dict(),
            "risk_signal": self.risk_signal,
            "risk_signal_label": self.risk_signal_label,
            "consumer_actions": self.consumer_actions,
            "consumer_action_labels": self.consumer_action_labels,
            "missing_information": self.missing_information,
            "generated_at": self.generated_at,
            "metadata": self.metadata,
        }
