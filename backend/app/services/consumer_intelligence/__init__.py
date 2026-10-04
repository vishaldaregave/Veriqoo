"""Consumer Scan Intelligence package for Phase U5."""

from backend.app.services.consumer_intelligence.models import (
    ConsumerAction,
    ConsumerComplianceSummary,
    ConsumerScanIntelligence,
    ExtractedProductField,
    FieldProvenance,
    IdentityConfidence,
    ProductIdentity,
    RiskSignal,
    ScanContext,
    ScanQuality,
    ScanQualityIssue,
)
from backend.app.services.consumer_intelligence.service import (
    ConsumerIntelligenceService,
    get_consumer_intelligence_service,
)

__all__ = [
    "ConsumerAction",
    "ConsumerComplianceSummary",
    "ConsumerScanIntelligence",
    "ExtractedProductField",
    "FieldProvenance",
    "IdentityConfidence",
    "ProductIdentity",
    "RiskSignal",
    "ScanContext",
    "ScanQuality",
    "ScanQualityIssue",
    "ConsumerIntelligenceService",
    "get_consumer_intelligence_service",
]
