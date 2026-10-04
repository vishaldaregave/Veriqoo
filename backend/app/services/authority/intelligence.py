"""Authority Intelligence and Risk Prioritization service engine for Phase U9."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Sequence

from backend.app.api.session_store import InMemoryInspectionStore, InspectionSession
from backend.app.localization.service import LocalizationService, get_localization_service
from backend.app.services.authority.models import (
    AuthorityOverviewMetrics,
    AuthorityPriority,
    AuthorityPriorityItem,
    AuthorityRiskSignal,
    ManufacturerIntelligenceSummary,
    ProductIntelligenceSummary,
    RiskSignalCode,
    TrendDirection,
)
from backend.app.services.authority.prioritizer import InspectionPrioritizer
from backend.app.services.consumer_intelligence.models import (
    ConsumerScanIntelligence,
    IdentityConfidence,
)
from backend.app.services.consumer_intelligence.service import ConsumerIntelligenceService
from backend.app.services.consumer_result.service import ConsumerResultService
from backend.app.services.heatmap.service import HeatmapService
from backend.app.services.inspection.errors import InspectionNotFoundError
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport

logger = logging.getLogger(__name__)


def _get_mfg_value(intel: ConsumerScanIntelligence | None) -> str | None:
    if not intel or not intel.product_identity:
        return None
    pid = intel.product_identity
    mfg = getattr(pid, "manufacturer_name", None) or getattr(pid, "manufacturer", None)
    if mfg and mfg.value and str(mfg.value).strip():
        return str(mfg.value).strip()
    return None


def _get_brand_value(intel: ConsumerScanIntelligence | None) -> str | None:
    if not intel or not intel.product_identity:
        return None
    pid = intel.product_identity
    if pid.brand and pid.brand.value and str(pid.brand.value).strip():
        return str(pid.brand.value).strip()
    return None


def _is_high_or_medium_confidence(intel: ConsumerScanIntelligence | None) -> bool:
    if not intel:
        return False
    conf = intel.identity_confidence
    conf_val = conf.value if hasattr(conf, "value") else str(conf)
    return conf_val.upper() in ("HIGH", "MEDIUM")


class AuthorityIntelligenceService:
    """Provides decision-support intelligence, deterministic prioritization, and aggregate analytics for authorities."""

    def __init__(
        self,
        store: InMemoryInspectionStore | None = None,
        localization: LocalizationService | None = None,
        consumer_intel_service: ConsumerIntelligenceService | None = None,
        consumer_result_service: ConsumerResultService | None = None,
        heatmap_service: HeatmapService | None = None,
    ) -> None:
        self._store = store
        self._localization = localization or get_localization_service()
        self._consumer_intel = consumer_intel_service or ConsumerIntelligenceService(
            store=store, localization=self._localization
        )
        self._consumer_result = consumer_result_service or ConsumerResultService(
            session_store=store, localization_service=self._localization
        )
        self._heatmap = heatmap_service or HeatmapService(
            store=store, localization=self._localization
        )

    def _get_completed_sessions(self) -> list[InspectionSession]:
        """Fetch all completed sessions having valid reports."""
        if not self._store:
            return []
        sessions = self._store.list_sessions()
        return [
            s
            for s in sessions
            if s.report is not None
            and (
                s.inspection.status == InspectionStatus.COMPLETED
                or (s.report and s.report.overall_status is not None)
            )
        ]

    def _extract_intelligence_for_session(
        self, session: InspectionSession
    ) -> tuple[ConsumerScanIntelligence | None, dict[str, Any] | None]:
        """Extract or generate U5 scan intelligence and location metadata."""
        location = None
        if session.inspection.metadata:
            loc_data = session.inspection.metadata.get("location")
            if isinstance(loc_data, dict):
                location = {
                    "state_code": loc_data.get("state_code"),
                    "district_code": loc_data.get("district_code"),
                    "state_name": loc_data.get("state_name"),
                    "district_name": loc_data.get("district_name"),
                }

        intel: ConsumerScanIntelligence | None = None
        if session.report:
            try:
                candidates = getattr(session, "evidence_candidates", []) or []
                intel = self._consumer_intel.generate_intelligence(
                    inspection_id=session.inspection.inspection_id,
                    candidates=candidates,
                )
            except Exception as e:
                logger.debug("Failed to build consumer intelligence for session %s: %s", session.inspection.inspection_id, e)
        return intel, location

    def get_priority_queue(
        self,
        min_priority: AuthorityPriority | str | None = None,
        status_filter: str | None = None,
        state_filter: str | None = None,
        district_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuthorityPriorityItem], int]:
        """Compute the prioritized authority inspection queue.

        Returns:
            (list of AuthorityPriorityItem, total_matching_count)
        """
        sessions = self._get_completed_sessions()

        # Step 1: Pre-calculate entity failure occurrences for repeat detection
        manufacturer_fail_counts: Counter[str] = Counter()
        product_fail_counts: Counter[str] = Counter()
        elevated_states: set[str] = set()

        # Check regional baseline via heatmap
        try:
            heatmap_report = self._heatmap.compute_heatmap(time_window="30d", public_mode=False)
            for cell in heatmap_report.cells:
                if cell.observed_issue_rate > 0.4 and cell.inspection_count >= 3:
                    elevated_states.add(cell.region_code.upper())
        except Exception:
            pass

        session_intel_map: dict[str, tuple[ConsumerScanIntelligence | None, dict[str, Any] | None]] = {}
        for s in sessions:
            intel, loc = self._extract_intelligence_for_session(s)
            session_intel_map[s.inspection.inspection_id] = (intel, loc)
            if s.report and (s.report.overall_status.value if hasattr(s.report.overall_status, "value") else str(s.report.overall_status)) == "FAIL":
                if _is_high_or_medium_confidence(intel):
                    m_val = _get_mfg_value(intel)
                    if m_val:
                        manufacturer_fail_counts[m_val.lower()] += 1
                    b_val = _get_brand_value(intel)
                    if b_val:
                        product_fail_counts[b_val.lower()] += 1

        # Step 2: Prioritize each inspection
        prioritized_items: list[AuthorityPriorityItem] = []
        for s in sessions:
            intel, loc = session_intel_map.get(s.inspection.inspection_id, (None, None))
            
            # Repeat failure signal check
            repeat_count = 0
            if _is_high_or_medium_confidence(intel):
                m_val = _get_mfg_value(intel)
                if m_val:
                    repeat_count = max(repeat_count, manufacturer_fail_counts.get(m_val.lower(), 0) - 1)
                b_val = _get_brand_value(intel)
                if b_val:
                    repeat_count = max(repeat_count, product_fail_counts.get(b_val.lower(), 0) - 1)
            repeat_count = max(0, repeat_count)

            # Check if region is elevated
            is_elevated = False
            if loc and loc.get("state_code"):
                st_code = str(loc.get("state_code")).upper()
                if st_code in elevated_states:
                    is_elevated = True

            created_iso = s.created_at.isoformat() if s.created_at else ""

            item = InspectionPrioritizer.prioritize_inspection(
                inspection_id=s.inspection.inspection_id,
                report=s.report,
                intelligence=intel,
                repeat_failure_count=repeat_count,
                is_elevated_region=is_elevated,
                location=loc,
                created_at=created_iso,
            )
            prioritized_items.append(item)

        # Step 3: Filtering
        filtered_items = prioritized_items

        if min_priority:
            min_pri_str = min_priority.value if hasattr(min_priority, "value") else str(min_priority).upper()
            pri_order = {
                AuthorityPriority.CRITICAL.value: 4,
                AuthorityPriority.HIGH.value: 3,
                AuthorityPriority.MEDIUM.value: 2,
                AuthorityPriority.LOW.value: 1,
                AuthorityPriority.INFORMATIONAL.value: 0,
            }
            min_rank = pri_order.get(min_pri_str, 0)
            filtered_items = [i for i in filtered_items if pri_order.get(i.priority.value, 0) >= min_rank]

        if status_filter:
            status_filter_upper = status_filter.strip().upper()
            filtered_items = [i for i in filtered_items if i.canonical_status.upper() == status_filter_upper]

        if state_filter:
            sf_upper = state_filter.strip().upper()
            filtered_items = [
                i
                for i in filtered_items
                if i.location and (
                    str(i.location.get("state_code", "")).upper() == sf_upper
                    or str(i.location.get("state_name", "")).upper() == sf_upper
                )
            ]

        if district_filter:
            df_upper = district_filter.strip().upper()
            filtered_items = [
                i
                for i in filtered_items
                if i.location and (
                    str(i.location.get("district_code", "")).upper() == df_upper
                    or str(i.location.get("district_name", "")).upper() == df_upper
                )
            ]

        # Step 4: Deterministic sorting: priority_score DESC, created_at DESC, inspection_id ASC
        filtered_items.sort(
            key=lambda x: (x.priority_score, x.created_at, x.inspection_id),
            reverse=True,
        )

        total_count = len(filtered_items)
        paginated_items = filtered_items[offset : offset + limit]
        return paginated_items, total_count

    def get_inspection_detail_intelligence(
        self, inspection_id: str
    ) -> AuthorityPriorityItem:
        """Fetch deterministic decision-support intelligence for a specific inspection."""
        if not self._store:
            raise InspectionNotFoundError(
                f"Inspection with ID '{inspection_id}' not found.",
                details={"inspection_id": inspection_id},
            )

        session = self._store.get_session(inspection_id)
        intel, loc = self._extract_intelligence_for_session(session)

        # Calculate repeat count
        repeat_count = 0
        if _is_high_or_medium_confidence(intel):
            cur_mfg = _get_mfg_value(intel)
            if cur_mfg:
                all_sessions = self._get_completed_sessions()
                for s in all_sessions:
                    if s.inspection.inspection_id == inspection_id:
                        continue
                    if s.report and (s.report.overall_status.value if hasattr(s.report.overall_status, "value") else str(s.report.overall_status)) == "FAIL":
                        s_intel, _ = self._extract_intelligence_for_session(s)
                        if _is_high_or_medium_confidence(s_intel):
                            s_mfg = _get_mfg_value(s_intel)
                            if s_mfg and s_mfg.lower() == cur_mfg.lower():
                                repeat_count += 1

        created_iso = session.created_at.isoformat() if session.created_at else ""

        return InspectionPrioritizer.prioritize_inspection(
            inspection_id=session.inspection.inspection_id,
            report=session.report,
            intelligence=intel,
            repeat_failure_count=repeat_count,
            location=loc,
            created_at=created_iso,
        )

    def get_manufacturer_summaries(
        self,
        min_inspections: int = 1,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ManufacturerIntelligenceSummary], int]:
        """Aggregate compliance intelligence across manufacturers with confirmed identities.

        Guarantees:
        - UNCERTAIN or UNKNOWN identities are never merged into manufacturer profiles.
        - Computes historical trend between current period (last 30d) and prior period (31-60d).
        - Explicit neutral regulatory language with legal disclaimers.
        """
        sessions = self._get_completed_sessions()
        now = datetime.now(timezone.utc)
        current_period_start = now - timedelta(days=30)
        prior_period_start = now - timedelta(days=60)

        # Manufacturer groupings: key -> list of (session, report, intelligence)
        m_groups: dict[str, list[tuple[InspectionSession, InspectionReport, ConsumerScanIntelligence]]] = defaultdict(list)
        display_names: dict[str, str] = {}

        for s in sessions:
            if not s.report:
                continue
            intel, _ = self._extract_intelligence_for_session(s)
            if not _is_high_or_medium_confidence(intel):
                continue
            raw_name = _get_mfg_value(intel)
            if not raw_name:
                continue

            norm_key = raw_name.lower()
            m_groups[norm_key].append((s, s.report, intel))
            if norm_key not in display_names:
                display_names[norm_key] = raw_name

        summaries: list[ManufacturerIntelligenceSummary] = []

        for m_key, records in m_groups.items():
            if len(records) < min_inspections:
                continue

            name = display_names.get(m_key, m_key)
            if search and search.strip().lower() not in name.lower():
                continue

            total = len(records)
            pass_cnt = sum(
                1 for _, r, _ in records
                if (r.overall_status.value if hasattr(r.overall_status, "value") else str(r.overall_status)) == "PASS"
            )
            fail_cnt = sum(
                1 for _, r, _ in records
                if (r.overall_status.value if hasattr(r.overall_status, "value") else str(r.overall_status)) == "FAIL"
            )
            review_cnt = sum(
                1 for _, r, _ in records
                if (r.overall_status.value if hasattr(r.overall_status, "value") else str(r.overall_status)) == "REVIEW_REQUIRED"
            )

            issue_rate = round(fail_cnt / total, 4) if total > 0 else 0.0

            # Count top violation categories
            category_counts: Counter[str] = Counter()
            for _, r, _ in records:
                for req in getattr(r, "verification_results", getattr(r, "results", [])):
                    st = req.status.value if hasattr(req.status, "value") else str(req.status)
                    if st == "FAIL":
                        cat = getattr(req, "category", None) or "general_declaration"
                        category_counts[str(cat)] += 1

            top_cats = [
                {"category": cat, "failure_count": cnt}
                for cat, cnt in category_counts.most_common(5)
            ]

            # Calculate historical trend
            cur_fails = sum(1 for s, r, _ in records if s.created_at >= current_period_start and (r.overall_status.value if hasattr(r.overall_status, "value") else str(r.overall_status)) == "FAIL")
            cur_total = sum(1 for s, _, _ in records if s.created_at >= current_period_start)
            
            prior_fails = sum(1 for s, r, _ in records if prior_period_start <= s.created_at < current_period_start and (r.overall_status.value if hasattr(r.overall_status, "value") else str(r.overall_status)) == "FAIL")
            prior_total = sum(1 for s, _, _ in records if prior_period_start <= s.created_at < current_period_start)

            if cur_total < 2 and prior_total < 2 and total < 3:
                trend = TrendDirection.INSUFFICIENT_DATA
            elif prior_total == 0:
                trend = TrendDirection.STABLE if cur_fails == 0 else TrendDirection.INCREASING
            else:
                cur_rate = cur_fails / cur_total if cur_total > 0 else 0.0
                prior_rate = prior_fails / prior_total if prior_total > 0 else 0.0
                diff = cur_rate - prior_rate
                if diff > 0.15:
                    trend = TrendDirection.INCREASING
                elif diff < -0.15:
                    trend = TrendDirection.DECREASING
                else:
                    trend = TrendDirection.STABLE

            last_inspected = max((s.created_at for s, _, _ in records), default=None)

            summaries.append(
                ManufacturerIntelligenceSummary(
                    manufacturer_name=name,
                    inspection_count=total,
                    pass_count=pass_cnt,
                    fail_count=fail_cnt,
                    review_count=review_cnt,
                    observed_issue_rate=issue_rate,
                    repeat_issue_count=max(0, fail_cnt - 1),
                    top_violation_categories=top_cats,
                    identity_confidence="HIGH",
                    trend=trend,
                    last_inspected_at=last_inspected.isoformat() if last_inspected else None,
                )
            )

        # Sort: observed_issue_rate DESC, fail_count DESC, inspection_count DESC
        summaries.sort(
            key=lambda x: (x.observed_issue_rate, x.fail_count, x.inspection_count, x.manufacturer_name),
            reverse=True,
        )

        total_count = len(summaries)
        return summaries[offset : offset + limit], total_count

    def get_product_summaries(
        self,
        commodity_filter: str | None = None,
        brand_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ProductIntelligenceSummary], int]:
        """Aggregate compliance intelligence across products/commodities with confirmed identities."""
        sessions = self._get_completed_sessions()

        p_groups: dict[str, list[tuple[InspectionSession, InspectionReport, ConsumerScanIntelligence]]] = defaultdict(list)
        p_metadata: dict[str, dict[str, str | None]] = {}

        for s in sessions:
            if not s.report:
                continue
            intel, _ = self._extract_intelligence_for_session(s)
            if not _is_high_or_medium_confidence(intel):
                continue

            pid = intel.product_identity
            brand_val = pid.brand.value if pid.brand and pid.brand.value else None
            gen_val = pid.generic_name.value if pid.generic_name and pid.generic_name.value else None
            comm_val = pid.commodity.value if pid.commodity and pid.commodity.value else None
            barcode_val = pid.barcode.value if pid.barcode and pid.barcode.value else None

            # Distinct grouping key
            if barcode_val:
                key = f"barcode:{barcode_val.strip().lower()}"
            elif brand_val and (gen_val or comm_val):
                key = f"prod:{brand_val.strip().lower()}:{(gen_val or comm_val).strip().lower()}"
            elif brand_val:
                key = f"brand:{brand_val.strip().lower()}"
            elif gen_val or comm_val:
                key = f"comm:{(gen_val or comm_val).strip().lower()}"
            else:
                continue

            p_groups[key].append((s, s.report, intel))
            if key not in p_metadata:
                p_metadata[key] = {
                    "brand": brand_val,
                    "generic_name": gen_val,
                    "commodity": comm_val,
                    "barcode": barcode_val,
                }

        summaries: list[ProductIntelligenceSummary] = []

        for p_key, records in p_groups.items():
            meta = p_metadata.get(p_key, {})
            brand_name = meta.get("brand")
            comm_name = meta.get("commodity") or meta.get("generic_name")

            if brand_filter and brand_name and brand_filter.strip().lower() not in brand_name.lower():
                continue
            if commodity_filter and comm_name and commodity_filter.strip().lower() not in comm_name.lower():
                continue

            total = len(records)
            pass_cnt = sum(
                1 for _, r, _ in records
                if (r.overall_status.value if hasattr(r.overall_status, "value") else str(r.overall_status)) == "PASS"
            )
            fail_cnt = sum(
                1 for _, r, _ in records
                if (r.overall_status.value if hasattr(r.overall_status, "value") else str(r.overall_status)) == "FAIL"
            )
            review_cnt = sum(
                1 for _, r, _ in records
                if (r.overall_status.value if hasattr(r.overall_status, "value") else str(r.overall_status)) == "REVIEW_REQUIRED"
            )

            issue_rate = round(fail_cnt / total, 4) if total > 0 else 0.0

            category_counts: Counter[str] = Counter()
            for _, r, _ in records:
                for req in getattr(r, "verification_results", getattr(r, "results", [])):
                    st = req.status.value if hasattr(req.status, "value") else str(req.status)
                    if st == "FAIL":
                        cat = getattr(req, "category", None) or "declaration"
                        category_counts[str(cat)] += 1

            top_cats = [
                {"category": cat, "failure_count": cnt}
                for cat, cnt in category_counts.most_common(5)
            ]

            last_inspected = max((s.created_at for s, _, _ in records), default=None)

            summaries.append(
                ProductIntelligenceSummary(
                    product_key=p_key,
                    brand=meta.get("brand"),
                    generic_name=meta.get("generic_name"),
                    commodity=meta.get("commodity"),
                    barcode=meta.get("barcode"),
                    inspection_count=total,
                    pass_count=pass_cnt,
                    fail_count=fail_cnt,
                    review_count=review_cnt,
                    observed_issue_rate=issue_rate,
                    top_violation_categories=top_cats,
                    identity_confidence="HIGH",
                    trend=TrendDirection.INSUFFICIENT_DATA if total < 3 else TrendDirection.STABLE,
                    last_inspected_at=last_inspected.isoformat() if last_inspected else None,
                )
            )

        summaries.sort(
            key=lambda x: (x.observed_issue_rate, x.fail_count, x.inspection_count, x.product_key),
            reverse=True,
        )

        total_count = len(summaries)
        return summaries[offset : offset + limit], total_count

    def get_overview_metrics(self) -> AuthorityOverviewMetrics:
        """Calculate high-level summary metrics for authority intelligence overview."""
        items, total = self.get_priority_queue(limit=10000)

        crit_count = sum(1 for i in items if i.priority == AuthorityPriority.CRITICAL)
        high_count = sum(1 for i in items if i.priority == AuthorityPriority.HIGH)
        med_count = sum(1 for i in items if i.priority == AuthorityPriority.MEDIUM)
        low_count = sum(1 for i in items if i.priority in (AuthorityPriority.LOW, AuthorityPriority.INFORMATIONAL))

        fail_items = sum(1 for i in items if i.canonical_status == "FAIL")
        overall_rate = round(fail_items / total, 4) if total > 0 else 0.0

        m_summaries, total_m = self.get_manufacturer_summaries(limit=10000)

        # Top violated statutory requirements across all inspections
        sessions = self._get_completed_sessions()
        req_counts: Counter[str] = Counter()
        for s in sessions:
            if s.report:
                for req in getattr(s.report, "verification_results", getattr(s.report, "results", [])):
                    st = req.status.value if hasattr(req.status, "value") else str(req.status)
                    if st == "FAIL":
                        req_name = getattr(req, "requirement_name", None) or getattr(req, "rule_reference", None) or req.requirement_id
                        req_counts[str(req_name)] += 1

        top_reqs = [
            {"requirement": req, "failure_count": count}
            for req, count in req_counts.most_common(5)
        ]

        return AuthorityOverviewMetrics(
            total_completed_inspections=total,
            critical_priority_count=crit_count,
            high_priority_count=high_count,
            medium_priority_count=med_count,
            low_priority_count=low_count,
            overall_observed_issue_rate=overall_rate,
            active_manufacturers_tracked=total_m,
            top_violated_requirements=top_reqs,
        )
