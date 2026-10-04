"""FastAPI router for Phase U9 — Authority Intelligence & Risk Prioritization."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.dependencies import get_authority_service
from backend.app.api.schemas import (
    AuthorityLocationResponse,
    AuthorityOverviewResponse,
    AuthorityPriorityItemResponse,
    AuthorityPriorityQueueResponse,
    AuthorityRiskSignalResponse,
    ManufacturerIntelligenceListResponse,
    ManufacturerIntelligenceResponse,
    ProductIntelligenceListResponse,
    ProductIntelligenceResponse,
    TopViolatedRequirementResponse,
    TopViolationCategoryResponse,
)
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.services.authority.intelligence import AuthorityIntelligenceService
from backend.app.services.authority.models import AuthorityPriorityItem
from backend.app.services.inspection.errors import InspectionNotFoundError

router = APIRouter(prefix="/authority/intelligence", tags=["Authority Intelligence"])


def _map_priority_item(item: AuthorityPriorityItem) -> AuthorityPriorityItemResponse:
    """Helper to convert domain AuthorityPriorityItem to Pydantic schema."""
    loc_resp = None
    if item.location:
        loc_resp = AuthorityLocationResponse(
            state_code=item.location.get("state_code"),
            district_code=item.location.get("district_code"),
            state_name=item.location.get("state_name"),
            district_name=item.location.get("district_name"),
        )

    signals_resp = [
        AuthorityRiskSignalResponse(
            code=s.code,
            severity=s.severity,
            explanation=s.explanation,
            source=s.source,
            evidence_ids=s.evidence_ids,
            requirement_ids=s.requirement_ids,
        )
        for s in item.risk_signals
    ]

    return AuthorityPriorityItemResponse(
        inspection_id=item.inspection_id,
        priority=item.priority.value if hasattr(item.priority, "value") else str(item.priority),
        priority_score=item.priority_score,
        reasons=item.reasons,
        canonical_status=item.canonical_status,
        risk_signal=item.risk_signal,
        compliance_score=item.compliance_score,
        rating=item.rating,
        failed_requirement_count=item.failed_requirement_count,
        review_required_count=item.review_required_count,
        not_visible_count=item.not_visible_count,
        risk_signals=signals_resp,
        product_summary=item.product_summary,
        identity_confidence=item.identity_confidence,
        location=loc_resp,
        created_at=item.created_at,
    )


@router.get("/priorities", response_model=AuthorityPriorityQueueResponse)
def get_priorities_queue(
    min_priority: str | None = Query(
        default=None,
        description="Filter by minimum priority level: CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL",
    ),
    status: str | None = Query(
        default=None,
        description="Filter by canonical inspection status: PASS, FAIL, REVIEW_REQUIRED",
    ),
    state_code: str | None = Query(
        default=None,
        description="Filter by 2-letter state code (e.g. MH, DL)",
    ),
    district_code: str | None = Query(
        default=None,
        description="Filter by district code (e.g. PUN)",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
    authority_service: AuthorityIntelligenceService = Depends(get_authority_service),
) -> AuthorityPriorityQueueResponse:
    """Retrieve prioritized inspection enforcement queue for authority review.

    Guarantees:
    - Protected: Requires authenticated user identity.
    - Deterministic ranking: Ranked by priority score (0-100) and recency.
    - Explainable: Includes structured reasons and risk signals for each ranking.
    - Privacy: No private consumer credentials, tokens, or raw OCR exposed.
    """
    items, total = authority_service.get_priority_queue(
        min_priority=min_priority,
        status_filter=status,
        state_filter=state_code,
        district_filter=district_code,
        limit=limit,
        offset=offset,
    )

    return AuthorityPriorityQueueResponse(
        total_count=total,
        items=[_map_priority_item(item) for item in items],
    )


@router.get("/inspections/{inspection_id}", response_model=AuthorityPriorityItemResponse)
def get_inspection_detail_intelligence(
    inspection_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    authority_service: AuthorityIntelligenceService = Depends(get_authority_service),
) -> AuthorityPriorityItemResponse:
    """Retrieve typed intelligence and priority ranking for a single inspection."""
    try:
        item = authority_service.get_inspection_detail_intelligence(inspection_id=inspection_id)
        return _map_priority_item(item)
    except InspectionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "INSPECTION_NOT_FOUND",
                "message": str(e),
                "details": {"inspection_id": inspection_id},
            },
        )


@router.get("/manufacturers", response_model=ManufacturerIntelligenceListResponse)
def get_manufacturer_intelligence(
    min_inspections: int = Query(default=1, ge=1),
    search: str | None = Query(default=None, description="Search manufacturer by name substring"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
    authority_service: AuthorityIntelligenceService = Depends(get_authority_service),
) -> ManufacturerIntelligenceListResponse:
    """Retrieve aggregated compliance profiles across manufacturers with verified identity.

    Guarantees:
    - Only includes inspections with HIGH or MEDIUM product identity confidence.
    - Uses neutral regulatory language (never labels entities illegal/fraudulent).
    - Includes legal and sample disclaimers.
    """
    summaries, total = authority_service.get_manufacturer_summaries(
        min_inspections=min_inspections,
        search=search,
        limit=limit,
        offset=offset,
    )

    items = [
        ManufacturerIntelligenceResponse(
            manufacturer_name=s.manufacturer_name,
            inspection_count=s.inspection_count,
            pass_count=s.pass_count,
            fail_count=s.fail_count,
            review_count=s.review_count,
            observed_issue_rate=s.observed_issue_rate,
            repeat_issue_count=s.repeat_issue_count,
            top_violation_categories=[
                TopViolationCategoryResponse(
                    category=c["category"],
                    failure_count=c["failure_count"],
                )
                for c in s.top_violation_categories
            ],
            identity_confidence=s.identity_confidence,
            trend=s.trend.value if hasattr(s.trend, "value") else str(s.trend),
            last_inspected_at=s.last_inspected_at,
            disclaimer=s.disclaimer,
        )
        for s in summaries
    ]

    return ManufacturerIntelligenceListResponse(
        total_count=total,
        items=items,
    )


@router.get("/products", response_model=ProductIntelligenceListResponse)
def get_product_intelligence(
    commodity: str | None = Query(default=None, description="Filter by legal metrology commodity"),
    brand: str | None = Query(default=None, description="Filter by brand name"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
    authority_service: AuthorityIntelligenceService = Depends(get_authority_service),
) -> ProductIntelligenceListResponse:
    """Retrieve aggregated compliance profiles across products and commodities."""
    summaries, total = authority_service.get_product_summaries(
        commodity_filter=commodity,
        brand_filter=brand,
        limit=limit,
        offset=offset,
    )

    items = [
        ProductIntelligenceResponse(
            product_key=p.product_key,
            brand=p.brand,
            generic_name=p.generic_name,
            commodity=p.commodity,
            barcode=p.barcode,
            inspection_count=p.inspection_count,
            pass_count=p.pass_count,
            fail_count=p.fail_count,
            review_count=p.review_count,
            observed_issue_rate=p.observed_issue_rate,
            top_violation_categories=[
                TopViolationCategoryResponse(
                    category=c["category"],
                    failure_count=c["failure_count"],
                )
                for c in p.top_violation_categories
            ],
            identity_confidence=p.identity_confidence,
            trend=p.trend.value if hasattr(p.trend, "value") else str(p.trend),
            last_inspected_at=p.last_inspected_at,
        )
        for p in summaries
    ]

    return ProductIntelligenceListResponse(
        total_count=total,
        items=items,
    )


@router.get("/overview", response_model=AuthorityOverviewResponse)
def get_authority_overview(
    current_user: AuthenticatedUser = Depends(get_current_user),
    authority_service: AuthorityIntelligenceService = Depends(get_authority_service),
) -> AuthorityOverviewResponse:
    """Retrieve high-level overview metrics for authority decision support dashboard."""
    metrics = authority_service.get_overview_metrics()

    return AuthorityOverviewResponse(
        total_completed_inspections=metrics.total_completed_inspections,
        critical_priority_count=metrics.critical_priority_count,
        high_priority_count=metrics.high_priority_count,
        medium_priority_count=metrics.medium_priority_count,
        low_priority_count=metrics.low_priority_count,
        overall_observed_issue_rate=metrics.overall_observed_issue_rate,
        active_manufacturers_tracked=metrics.active_manufacturers_tracked,
        top_violated_requirements=[
            TopViolatedRequirementResponse(
                requirement=r["requirement"],
                failure_count=r["failure_count"],
            )
            for r in metrics.top_violated_requirements
        ],
        generated_at=metrics.generated_at,
    )
