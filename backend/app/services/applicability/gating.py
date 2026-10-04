"""Gating layer: approval checks, temporal selection, and hierarchy validation."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from backend.app.services.applicability.models import (
    ApplicabilityConditionGroup,
    ApplicabilityRuleVersion,
)


class GatingError(Exception):
    """Base exception for gating violations."""


class UnapprovedRuleVersionError(GatingError):
    """Raised when an unapproved rule version is submitted for evaluation."""


def filter_approved_versions(
    versions: Sequence[ApplicabilityRuleVersion],
) -> list[ApplicabilityRuleVersion]:
    """Filter rule versions to only those formally approved by accredited review."""
    return [v for v in versions if v.interpretation_status == "approved"]


def select_temporal_version(
    approved_versions: Sequence[ApplicabilityRuleVersion],
    inspection_date: date | None,
) -> tuple[ApplicabilityRuleVersion | None, str | None]:
    """Select the single active rule version for an inspection date.

    Semantics:
    - 0 matching approved versions: (None, "no approved rule version matches inspection date")
    - 1 matching approved version: (version, None)
    - >1 matching approved versions: (None, "ambiguous approved rule versions")
    - Never uses version_number, created_at, specificity, or ordering to resolve ties.

    If inspection_date is NULL:
    - Only entirely unbounded versions (valid_from is None and valid_to is None) match.
    - If date-bounded approved versions exist alongside, temporal information is required,
      making the situation ambiguous -> (None, "ambiguous approved rule versions").
    """
    if not approved_versions:
        return None, "no approved rule version matches inspection date"

    if inspection_date is not None:
        matching = [
            v
            for v in approved_versions
            if (v.valid_from is None or inspection_date >= v.valid_from)
            and (v.valid_to is None or inspection_date <= v.valid_to)
        ]
    else:
        # Inspection date is None
        bounded_versions = [
            v for v in approved_versions if v.valid_from is not None or v.valid_to is not None
        ]
        unbounded_versions = [
            v for v in approved_versions if v.valid_from is None and v.valid_to is None
        ]
        if bounded_versions and unbounded_versions:
            return None, "ambiguous approved rule versions: inspection date required"
        matching = unbounded_versions

    count = len(matching)
    if count == 0:
        return None, "no approved rule version matches inspection date"
    if count == 1:
        return matching[0], None
    return None, "ambiguous approved rule versions"


def validate_group_hierarchy(
    groups: Sequence[ApplicabilityConditionGroup],
) -> tuple[bool, str | None, ApplicabilityConditionGroup | None, list[ApplicabilityConditionGroup]]:
    """Validate structural invariants of condition group hierarchy for a rule version.

    Invariants:
    1. Exactly ONE root applicability group (group_purpose='applicability', parent_group_id is None).
    2. Zero or more root exception groups (group_purpose='exception', parent_group_id is None).
    3. No orphaned parent_group_id references.
    4. No cyclic graphs in parent_group_id.

    Returns:
        (is_valid, diagnostic_reason, root_applicability_group, root_exception_groups)
    """
    group_map = {str(g.id): g for g in groups}

    root_app_groups = [
        g for g in groups if g.parent_group_id is None and g.group_purpose == "applicability"
    ]
    root_exc_groups = [
        g for g in groups if g.parent_group_id is None and g.group_purpose == "exception"
    ]

    # Validate exactly one root applicability group
    if len(root_app_groups) == 0:
        return False, "Malformed rule hierarchy: expected exactly one root applicability group", None, []
    if len(root_app_groups) > 1:
        return False, "Malformed rule hierarchy: multiple root applicability groups", None, []

    # Validate parent references exist (no orphans)
    for g in groups:
        if g.parent_group_id is not None:
            parent_id_str = str(g.parent_group_id)
            if parent_id_str not in group_map:
                return False, "Malformed rule hierarchy: orphaned parent group reference", None, []

    # Validate acyclicity
    for g in groups:
        visited = set()
        curr: ApplicabilityConditionGroup | None = g
        while curr is not None and curr.parent_group_id is not None:
            curr_id = str(curr.id)
            if curr_id in visited:
                return False, "Malformed rule hierarchy: cycle detected", None, []
            visited.add(curr_id)
            curr = group_map.get(str(curr.parent_group_id))

    return True, None, root_app_groups[0], root_exc_groups

