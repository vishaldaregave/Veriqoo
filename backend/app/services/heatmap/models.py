"""Domain models and data contracts for Phase U7 — India Compliance Heatmap Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class GeographicLevel(str, Enum):
    """Supported coarse geographic aggregation granularity."""
    STATE = "STATE"
    DISTRICT = "DISTRICT"


class LocationSource(str, Enum):
    """Source classification for geographic context."""
    DEVICE = "DEVICE"
    USER_SELECTED = "USER_SELECTED"
    BACKEND_DERIVED = "BACKEND_DERIVED"
    AUTHORITY = "AUTHORITY"
    UNKNOWN = "UNKNOWN"


class LocationConfidence(str, Enum):
    """Trust rating for supplied geographic context."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


# Canonical Indian State/UT code to name registry
INDIA_STATES: dict[str, str] = {
    "AN": "Andaman and Nicobar Islands",
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CH": "Chandigarh",
    "CG": "Chhattisgarh",
    "CT": "Chhattisgarh",
    "DN": "Dadra and Nagar Haveli and Daman and Diu",
    "DD": "Dadra and Nagar Haveli and Daman and Diu",
    "DL": "Delhi",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JK": "Jammu and Kashmir",
    "JH": "Jharkhand",
    "KA": "Karnataka",
    "KL": "Kerala",
    "LA": "Ladakh",
    "LD": "Lakshadweep",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "OR": "Odisha",
    "PY": "Puducherry",
    "PB": "Punjab",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TG": "Telangana",
    "TR": "Tripura",
    "UP": "Uttar Pradesh",
    "UK": "Uttarakhand",
    "UT": "Uttarakhand",
    "WB": "West Bengal",
}

# Reverse lookup for state names (lowercased)
INDIA_STATE_NAME_LOOKUP: dict[str, tuple[str, str]] = {
    name.lower(): (code, name) for code, name in INDIA_STATES.items()
}


@dataclass
class NormalizedLocationContext:
    """Normalized, privacy-preserving coarse geographic context for an inspection."""
    country_code: str = "IN"
    state_code: str = ""
    state_name: str = ""
    district_code: str | None = None
    district_name: str | None = None
    source: LocationSource = LocationSource.UNKNOWN
    confidence: LocationConfidence = LocationConfidence.UNKNOWN

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> NormalizedLocationContext | None:
        """Parse and normalize location context from inspection metadata.

        Does NOT guess location if data is missing or empty.
        """
        if not data or not isinstance(data, dict):
            return None

        # Extract state info
        raw_state_code = str(data.get("state_code", "")).strip().upper()
        raw_state_name = str(data.get("state_name", "")).strip()

        state_code = ""
        state_name = ""

        if raw_state_code in INDIA_STATES:
            state_code = raw_state_code
            state_name = raw_state_name or INDIA_STATES[raw_state_code]
        elif raw_state_name.lower() in INDIA_STATE_NAME_LOOKUP:
            state_code, canonical_name = INDIA_STATE_NAME_LOOKUP[raw_state_name.lower()]
            state_name = raw_state_name or canonical_name
        elif raw_state_code:
            state_code = raw_state_code
            state_name = raw_state_name or raw_state_code

        if not state_code and not state_name:
            # Cannot establish even state-level context
            return None

        # Extract district info
        raw_district_code = data.get("district_code")
        district_code = str(raw_district_code).strip().upper() if raw_district_code else None
        raw_district_name = data.get("district_name")
        district_name = str(raw_district_name).strip() if raw_district_name else None

        # Extract source and confidence
        raw_source = str(data.get("source", "UNKNOWN")).upper()
        try:
            source = LocationSource(raw_source)
        except ValueError:
            source = LocationSource.UNKNOWN

        raw_conf = str(data.get("confidence", "UNKNOWN")).upper()
        try:
            confidence = LocationConfidence(raw_conf)
        except ValueError:
            confidence = LocationConfidence.UNKNOWN

        country_code = str(data.get("country_code", "IN")).strip().upper() or "IN"

        return cls(
            country_code=country_code,
            state_code=state_code,
            state_name=state_name,
            district_code=district_code,
            district_name=district_name,
            source=source,
            confidence=confidence,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize normalized location context."""
        return {
            "country_code": self.country_code,
            "state_code": self.state_code,
            "state_name": self.state_name,
            "district_code": self.district_code,
            "district_name": self.district_name,
            "source": self.source.value,
            "confidence": self.confidence.value,
        }


@dataclass
class RiskDistribution:
    """Distribution of U5 risk signals across aggregated inspections."""
    high_risk_count: int = 0
    potential_issue_count: int = 0
    insufficient_evidence_count: int = 0
    identity_uncertain_count: int = 0
    no_major_issues_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "high_risk_count": self.high_risk_count,
            "potential_issue_count": self.potential_issue_count,
            "insufficient_evidence_count": self.insufficient_evidence_count,
            "identity_uncertain_count": self.identity_uncertain_count,
            "no_major_issues_count": self.no_major_issues_count,
        }


@dataclass
class IssueCategoryCount:
    """Aggregated occurrence of a statutory non-compliance finding category."""
    category_id: str
    category_name: str
    fail_count: int
    review_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "category_name": self.category_name,
            "fail_count": self.fail_count,
            "review_count": self.review_count,
        }


@dataclass
class HeatmapCell:
    """Aggregated compliance intelligence for a single geographic cell (State or District)."""
    region_code: str
    region_name: str
    level: GeographicLevel
    state_code: str
    district_code: str | None = None
    is_suppressed: bool = False
    inspection_count: int | None = 0
    pass_count: int | None = 0
    fail_count: int | None = 0
    review_required_count: int | None = 0
    not_visible_count: int | None = 0
    not_applicable_count: int | None = 0
    issue_rate: float | None = None
    verified_pass_rate: float | None = None
    average_compliance_score: float | None = None
    risk_distribution: RiskDistribution | None = None
    top_issue_categories: list[IssueCategoryCount] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Deterministic serialization for API layer."""
        if self.is_suppressed:
            return {
                "region_code": self.region_code,
                "region_name": self.region_name,
                "level": self.level.value,
                "state_code": self.state_code,
                "district_code": self.district_code,
                "is_suppressed": True,
                "inspection_count": None,
                "pass_count": None,
                "fail_count": None,
                "review_required_count": None,
                "not_visible_count": None,
                "not_applicable_count": None,
                "issue_rate": None,
                "verified_pass_rate": None,
                "average_compliance_score": None,
                "risk_distribution": None,
                "top_issue_categories": [],
            }

        return {
            "region_code": self.region_code,
            "region_name": self.region_name,
            "level": self.level.value,
            "state_code": self.state_code,
            "district_code": self.district_code,
            "is_suppressed": False,
            "inspection_count": self.inspection_count,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "review_required_count": self.review_required_count,
            "not_visible_count": self.not_visible_count,
            "not_applicable_count": self.not_applicable_count,
            "issue_rate": self.issue_rate,
            "verified_pass_rate": self.verified_pass_rate,
            "average_compliance_score": self.average_compliance_score,
            "risk_distribution": self.risk_distribution.to_dict() if self.risk_distribution else None,
            "top_issue_categories": [cat.to_dict() for cat in self.top_issue_categories],
        }


@dataclass
class HeatmapSummary:
    """High-level national or filtered summary statistics across all cells."""
    total_inspections: int = 0
    total_pass: int = 0
    total_fail: int = 0
    total_review_required: int = 0
    overall_issue_rate: float | None = None
    overall_verified_pass_rate: float | None = None
    average_compliance_score: float | None = None
    active_regions_count: int = 0
    suppressed_regions_count: int = 0
    unassigned_location_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_inspections": self.total_inspections,
            "total_pass": self.total_pass,
            "total_fail": self.total_fail,
            "total_review_required": self.total_review_required,
            "overall_issue_rate": self.overall_issue_rate,
            "overall_verified_pass_rate": self.overall_verified_pass_rate,
            "average_compliance_score": self.average_compliance_score,
            "active_regions_count": self.active_regions_count,
            "suppressed_regions_count": self.suppressed_regions_count,
            "unassigned_location_count": self.unassigned_location_count,
        }


@dataclass
class ComplianceHeatmapReport:
    """Authoritative output of the compliance heatmap aggregation engine."""
    level: GeographicLevel
    time_window: str
    from_time: datetime
    to_time: datetime
    generated_at: datetime
    min_threshold: int
    summary: HeatmapSummary
    cells: list[HeatmapCell]
    disclaimer: str = (
        "Observed inspection compliance intelligence based on verified sample records. "
        "Does not represent statistical population prevalence or definitive market-wide illegality rates."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "time_window": self.time_window,
            "from_time": self.from_time.isoformat(),
            "to_time": self.to_time.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "min_threshold": self.min_threshold,
            "disclaimer": self.disclaimer,
            "summary": self.summary.to_dict(),
            "cells": [c.to_dict() for c in self.cells],
        }
