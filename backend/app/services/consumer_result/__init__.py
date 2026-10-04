"""Phase U6 — Consumer Compliance Result & Explanation Package."""

from backend.app.services.consumer_result.models import (
    ConsumerComplianceResult,
    ConsumerFinding,
    ConsumerOverallResult,
    ConsumerReportReference,
    ConsumerScore,
    FindingSeverity,
    LegalReference,
)
from backend.app.services.consumer_result.service import (
    ConsumerResultService,
    get_consumer_result_service,
)

__all__ = [
    "ConsumerComplianceResult",
    "ConsumerFinding",
    "ConsumerOverallResult",
    "ConsumerReportReference",
    "ConsumerScore",
    "FindingSeverity",
    "LegalReference",
    "ConsumerResultService",
    "get_consumer_result_service",
]
