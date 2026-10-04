"""Service engine for Phase U7 — India Compliance Heatmap Intelligence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.api.session_store import InMemoryInspectionStore, InspectionSession
from backend.app.localization.service import LocalizationService, get_localization_service
from backend.app.services.consumer_intelligence.service import ConsumerIntelligenceService
from backend.app.services.heatmap.models import (
    ComplianceHeatmapReport,
    GeographicLevel,
    HeatmapCell,
    HeatmapSummary,
    INDIA_STATES,
    IssueCategoryCount,
    LocationConfidence,
    NormalizedLocationContext,
    RiskDistribution,
)
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport


DEFAULT_PUBLIC_SUPPRESSION_THRESHOLD = 5


class HeatmapService:
    """Aggregates inspection compliance intelligence across coarse geographic regions."""

    def __init__(
        self,
        store: InMemoryInspectionStore | None = None,
        localization: LocalizationService | None = None,
        intelligence_service: ConsumerIntelligenceService | None = None,
        public_suppression_threshold: int = DEFAULT_PUBLIC_SUPPRESSION_THRESHOLD,
    ) -> None:
        self._store = store
        self._localization = localization or get_localization_service()
        self._intelligence_service = intelligence_service or ConsumerIntelligenceService(
            store=store, localization=self._localization
        )
        self._threshold = public_suppression_threshold

    def parse_time_window(
        self,
        window_preset: str = "30d",
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> tuple[datetime, datetime, str]:
        """Resolve deterministic UTC time window bounds."""
        now = datetime.now(timezone.utc)

        if from_time is not None or to_time is not None:
            resolved_from = from_time or (now - timedelta(days=30))
            resolved_to = to_time or now
            if resolved_from.tzinfo is None:
                resolved_from = resolved_from.replace(tzinfo=timezone.utc)
            if resolved_to.tzinfo is None:
                resolved_to = resolved_to.replace(tzinfo=timezone.utc)
            return resolved_from, resolved_to, "custom"

        preset_lower = (window_preset or "30d").strip().lower()
        if preset_lower == "7d":
            return now - timedelta(days=7), now, "7d"
        elif preset_lower == "30d":
            return now - timedelta(days=30), now, "30d"
        elif preset_lower == "90d":
            return now - timedelta(days=90), now, "90d"
        elif preset_lower in ("all", "all_time"):
            # Cover from early epoch to now
            return datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc), now, "all"
        else:
            # Default fallback to 30d
            return now - timedelta(days=30), now, "30d"

    def compute_heatmap(
        self,
        level: GeographicLevel | str = GeographicLevel.STATE,
        time_window: str = "30d",
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        state_filter: str | None = None,
        public_mode: bool = True,
        threshold_override: int | None = None,
    ) -> ComplianceHeatmapReport:
        """Compute aggregated compliance intelligence report across regions.

        Guarantees:
        - Only completed inspections with valid reports are counted.
        - Strict unique inspection deduplication by inspection_id.
        - Public mode strictly enforces suppression threshold (< 5 inspections).
        - Privacy preservation: zero PII, zero coordinates, zero individual inspection IDs.
        """
        # Resolve geographic level
        if isinstance(level, str):
            try:
                geo_level = GeographicLevel(level.upper())
            except ValueError:
                geo_level = GeographicLevel.STATE
        else:
            geo_level = level

        resolved_from, resolved_to, resolved_window_name = self.parse_time_window(
            window_preset=time_window,
            from_time=from_time,
            to_time=to_time,
        )

        effective_threshold = self._threshold
        if not public_mode and threshold_override is not None:
            effective_threshold = max(0, threshold_override)

        generated_at = datetime.now(timezone.utc)

        # Retrieve sessions
        sessions: list[InspectionSession] = []
        if self._store is not None:
            sessions = self._store.list_sessions()

        # Grouping accumulator: region_key -> dict of inspection data
        # region_key:
        #   STATE: state_code
        #   DISTRICT: f"{state_code}_{district_code or district_name}"
        cell_data: dict[str, dict[str, Any]] = {}

        total_completed_in_window = 0
        total_pass_in_window = 0
        total_fail_in_window = 0
        total_review_in_window = 0
        all_applicable_scores: list[float] = []
        unassigned_count = 0

        # Track processed inspection_ids to guarantee single-counting
        seen_inspection_ids: set[str] = set()

        for session in sessions:
            insp = session.inspection
            report = session.report

            # Guard 1: Must be completed with an existing report
            if insp.status != InspectionStatus.COMPLETED or report is None:
                continue

            # Guard 2: Deduplication by unique inspection_id
            if insp.inspection_id in seen_inspection_ids:
                continue

            # Guard 3: Time window filtering
            created_at = insp.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            if not (resolved_from <= created_at <= resolved_to):
                continue

            seen_inspection_ids.add(insp.inspection_id)
            total_completed_in_window += 1

            # Determine overall report outcome
            overall_status = report.overall_status.upper()
            if overall_status == "PASS":
                total_pass_in_window += 1
            elif overall_status == "FAIL":
                total_fail_in_window += 1
            elif overall_status == "REVIEW_REQUIRED":
                total_review_in_window += 1

            # Extract location context
            raw_loc = insp.metadata.get("location") or insp.metadata.get("location_context")
            loc_context = NormalizedLocationContext.from_dict(raw_loc)

            # If location is missing or low/unknown without state
            if loc_context is None or not loc_context.state_code:
                unassigned_count += 1
                continue

            # Apply state filter if requested
            if state_filter:
                filter_code = state_filter.strip().upper()
                if loc_context.state_code != filter_code:
                    continue

            # Determine cell keys based on requested level
            if geo_level == GeographicLevel.STATE:
                region_key = loc_context.state_code
                region_code = loc_context.state_code
                region_name = loc_context.state_name or INDIA_STATES.get(region_code, region_code)
                state_code = loc_context.state_code
                district_code = None
            else:  # DISTRICT
                d_code = loc_context.district_code or loc_context.district_name or "UNKNOWN"
                region_key = f"{loc_context.state_code}_{d_code}"
                region_code = region_key
                region_name = loc_context.district_name or loc_context.district_code or "District Area"
                state_code = loc_context.state_code
                district_code = loc_context.district_code or loc_context.district_name

            if region_key not in cell_data:
                cell_data[region_key] = {
                    "region_code": region_code,
                    "region_name": region_name,
                    "level": geo_level,
                    "state_code": state_code,
                    "district_code": district_code,
                    "inspection_count": 0,
                    "pass_count": 0,
                    "fail_count": 0,
                    "review_required_count": 0,
                    "not_visible_count": 0,
                    "not_applicable_count": 0,
                    "scores": [],
                    "risk_distribution": RiskDistribution(),
                    "issue_categories": {},  # category_id -> {"name": str, "fail": int, "review": int}
                }

            c = cell_data[region_key]
            c["inspection_count"] += 1

            if overall_status == "PASS":
                c["pass_count"] += 1
            elif overall_status == "FAIL":
                c["fail_count"] += 1
            elif overall_status == "REVIEW_REQUIRED":
                c["review_required_count"] += 1

            c["not_visible_count"] += report.not_visible_count
            c["not_applicable_count"] += report.not_applicable_count

            # U1 Score aggregation (only when applicable requirements exist)
            total_eval = report.applicable_requirement_count
            if total_eval > 0:
                score = round((report.pass_count / total_eval) * 100.0, 1)
                c["scores"].append(score)
                all_applicable_scores.append(score)

            # U5 Risk aggregation
            from backend.app.services.consumer_intelligence.models import IdentityConfidence
            risk_signal = self._intelligence_service.derive_risk_signal(report, IdentityConfidence.HIGH).value
            rd: RiskDistribution = c["risk_distribution"]
            if risk_signal == "HIGH_RISK_NON_COMPLIANCE":
                rd.high_risk_count += 1
            elif risk_signal == "POTENTIAL_COMPLIANCE_ISSUE":
                rd.potential_issue_count += 1
            elif risk_signal == "INSUFFICIENT_EVIDENCE":
                rd.insufficient_evidence_count += 1
            elif risk_signal == "PRODUCT_IDENTITY_UNCERTAIN":
                rd.identity_uncertain_count += 1
            elif risk_signal == "NO_MAJOR_ISSUES_DETECTED":
                rd.no_major_issues_count += 1

            # Issue category extraction from failed / review verification results
            for v in report.verification_results:
                v_status = v.status.value if hasattr(v.status, "value") else str(v.status)
                if v_status in ("FAIL", "REVIEW_REQUIRED"):
                    req_id = v.requirement_id
                    cat_map = c["issue_categories"]
                    if req_id not in cat_map:
                        cat_label = self._localization.get_statutory_label(req_id, lang="en")
                        if not cat_label or cat_label == req_id:
                            cat_label = req_id
                        cat_map[req_id] = {
                            "name": cat_label,
                            "fail": 0,
                            "review": 0,
                        }
                    if v_status == "FAIL":
                        cat_map[req_id]["fail"] += 1
                    else:
                        cat_map[req_id]["review"] += 1

        # Build response cells
        cells: list[HeatmapCell] = []
        active_count = 0
        suppressed_count = 0

        for region_key, raw in cell_data.items():
            insp_count = raw["inspection_count"]
            is_suppressed = public_mode and (insp_count < effective_threshold)

            if is_suppressed:
                suppressed_count += 1
                cell = HeatmapCell(
                    region_code=raw["region_code"],
                    region_name=raw["region_name"],
                    level=raw["level"],
                    state_code=raw["state_code"],
                    district_code=raw["district_code"],
                    is_suppressed=True,
                    inspection_count=None,
                    pass_count=None,
                    fail_count=None,
                    review_required_count=None,
                    not_visible_count=None,
                    not_applicable_count=None,
                    issue_rate=None,
                    verified_pass_rate=None,
                    average_compliance_score=None,
                    risk_distribution=None,
                    top_issue_categories=[],
                )
            else:
                active_count += 1
                p_count = raw["pass_count"]
                f_count = raw["fail_count"]
                r_count = raw["review_required_count"]

                # issue_rate = FAIL / total_inspections
                issue_rate = round(f_count / insp_count, 4) if insp_count > 0 else 0.0

                # verified_pass_rate = PASS / (PASS + FAIL) (only when denominator > 0)
                decided_sum = p_count + f_count
                verified_pass_rate = round(p_count / decided_sum, 4) if decided_sum > 0 else None

                # Average compliance score
                scores = raw["scores"]
                avg_score = round(sum(scores) / len(scores), 1) if scores else None

                # Top issue categories sorted by fail_count descending
                sorted_cats = sorted(
                    raw["issue_categories"].items(),
                    key=lambda x: (x[1]["fail"], x[1]["review"]),
                    reverse=True,
                )
                top_cats = [
                    IssueCategoryCount(
                        category_id=cid,
                        category_name=cinfo["name"],
                        fail_count=cinfo["fail"],
                        review_count=cinfo["review"],
                    )
                    for cid, cinfo in sorted_cats[:5]
                ]

                cell = HeatmapCell(
                    region_code=raw["region_code"],
                    region_name=raw["region_name"],
                    level=raw["level"],
                    state_code=raw["state_code"],
                    district_code=raw["district_code"],
                    is_suppressed=False,
                    inspection_count=insp_count,
                    pass_count=p_count,
                    fail_count=f_count,
                    review_required_count=r_count,
                    not_visible_count=raw["not_visible_count"],
                    not_applicable_count=raw["not_applicable_count"],
                    issue_rate=issue_rate,
                    verified_pass_rate=verified_pass_rate,
                    average_compliance_score=avg_score,
                    risk_distribution=raw["risk_distribution"],
                    top_issue_categories=top_cats,
                )

            cells.append(cell)

        # Sort cells deterministically: active cells first by inspection_count desc, then region_name
        cells.sort(
            key=lambda c: (
                0 if not c.is_suppressed else 1,
                -(c.inspection_count or 0),
                c.region_name,
            )
        )

        # Compute summary
        overall_issue_rate = (
            round(total_fail_in_window / total_completed_in_window, 4)
            if total_completed_in_window > 0
            else None
        )
        total_decided = total_pass_in_window + total_fail_in_window
        overall_verified_pass = (
            round(total_pass_in_window / total_decided, 4)
            if total_decided > 0
            else None
        )
        overall_avg_score = (
            round(sum(all_applicable_scores) / len(all_applicable_scores), 1)
            if all_applicable_scores
            else None
        )

        summary = HeatmapSummary(
            total_inspections=total_completed_in_window,
            total_pass=total_pass_in_window,
            total_fail=total_fail_in_window,
            total_review_required=total_review_in_window,
            overall_issue_rate=overall_issue_rate,
            overall_verified_pass_rate=overall_verified_pass,
            average_compliance_score=overall_avg_score,
            active_regions_count=active_count,
            suppressed_regions_count=suppressed_count,
            unassigned_location_count=unassigned_count,
        )

        return ComplianceHeatmapReport(
            level=geo_level,
            time_window=resolved_window_name,
            from_time=resolved_from,
            to_time=resolved_to,
            generated_at=generated_at,
            min_threshold=effective_threshold,
            summary=summary,
            cells=cells,
        )
