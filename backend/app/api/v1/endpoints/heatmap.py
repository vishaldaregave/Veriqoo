"""FastAPI router for Phase U7 — India Compliance Heatmap Intelligence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.app.api.dependencies import get_heatmap_service
from backend.app.api.schemas import (
    ComplianceHeatmapResponse,
    HeatmapCellResponse,
    HeatmapIssueCategoryResponse,
    HeatmapRiskDistributionResponse,
    HeatmapSummaryResponse,
)
from backend.app.services.heatmap import GeographicLevel, HeatmapService


router = APIRouter(prefix="/analytics", tags=["Analytics & Heatmap"])


@router.get("/compliance-heatmap", response_model=ComplianceHeatmapResponse)
def get_compliance_heatmap(
    level: str = Query(
        default="STATE",
        description="Geographic aggregation granularity: STATE or DISTRICT",
    ),
    time_window: str = Query(
        default="30d",
        description="Predefined time window: 7d, 30d, 90d, all",
    ),
    from_date: str | None = Query(
        default=None,
        description="Optional custom start date/time (ISO-8601)",
    ),
    to_date: str | None = Query(
        default=None,
        description="Optional custom end date/time (ISO-8601)",
    ),
    state_code: str | None = Query(
        default=None,
        description="Optional 2-letter Indian state filter (e.g. MH, DL, KA)",
    ),
    heatmap_service: HeatmapService = Depends(get_heatmap_service),
) -> ComplianceHeatmapResponse:
    """Retrieve geographically aggregated compliance intelligence for India map rendering.

    Guarantees:
    - Observed inspection evidence aggregates (never claims population prevalence).
    - Coarse geographic boundaries only (STATE, DISTRICT). Zero GPS or coordinates exposed.
    - Strict privacy suppression threshold: Cells with < 5 completed inspections are suppressed.
    - Zero user PII, zero inspection IDs, zero private image URLs.
    """
    from_dt: datetime | None = None
    to_dt: datetime | None = None

    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date)
        except ValueError:
            from_dt = None

    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date)
        except ValueError:
            to_dt = None

    report = heatmap_service.compute_heatmap(
        level=level,
        time_window=time_window,
        from_time=from_dt,
        to_time=to_dt,
        state_filter=state_code,
        public_mode=True,
    )

    cells_response: list[HeatmapCellResponse] = []
    for c in report.cells:
        rd_resp = None
        if c.risk_distribution:
            rd_resp = HeatmapRiskDistributionResponse(
                high_risk_count=c.risk_distribution.high_risk_count,
                potential_issue_count=c.risk_distribution.potential_issue_count,
                insufficient_evidence_count=c.risk_distribution.insufficient_evidence_count,
                identity_uncertain_count=c.risk_distribution.identity_uncertain_count,
                no_major_issues_count=c.risk_distribution.no_major_issues_count,
            )

        top_cats = [
            HeatmapIssueCategoryResponse(
                category_id=cat.category_id,
                category_name=cat.category_name,
                fail_count=cat.fail_count,
                review_count=cat.review_count,
            )
            for cat in c.top_issue_categories
        ]

        cells_response.append(
            HeatmapCellResponse(
                region_code=c.region_code,
                region_name=c.region_name,
                level=c.level.value,
                state_code=c.state_code,
                district_code=c.district_code,
                is_suppressed=c.is_suppressed,
                inspection_count=c.inspection_count,
                pass_count=c.pass_count,
                fail_count=c.fail_count,
                review_required_count=c.review_required_count,
                not_visible_count=c.not_visible_count,
                not_applicable_count=c.not_applicable_count,
                issue_rate=c.issue_rate,
                verified_pass_rate=c.verified_pass_rate,
                average_compliance_score=c.average_compliance_score,
                risk_distribution=rd_resp,
                top_issue_categories=top_cats,
            )
        )

    summary_resp = HeatmapSummaryResponse(
        total_inspections=report.summary.total_inspections,
        total_pass=report.summary.total_pass,
        total_fail=report.summary.total_fail,
        total_review_required=report.summary.total_review_required,
        overall_issue_rate=report.summary.overall_issue_rate,
        overall_verified_pass_rate=report.summary.overall_verified_pass_rate,
        average_compliance_score=report.summary.average_compliance_score,
        active_regions_count=report.summary.active_regions_count,
        suppressed_regions_count=report.summary.suppressed_regions_count,
        unassigned_location_count=report.summary.unassigned_location_count,
    )

    return ComplianceHeatmapResponse(
        level=report.level.value,
        time_window=report.time_window,
        from_time=report.from_time.isoformat(),
        to_time=report.to_time.isoformat(),
        generated_at=report.generated_at.isoformat(),
        min_threshold=report.min_threshold,
        disclaimer=report.disclaimer,
        summary=summary_resp,
        cells=cells_response,
    )
