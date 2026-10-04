"""Phase 3C Applicability Authoring Linter and Invariant Enforcement Service.

Enforces the 11 Phase 3C authoring invariants before any rule version can exit
draft status or enter review/approval. Approved versions are strictly immutable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID

from backend.app.services.applicability.models import (
    ApplicabilityCondition,
    ApplicabilityConditionGroup,
    ApplicabilityRule,
    ApplicabilityRuleSource,
    ApplicabilityRuleVersion,
)


# Canonical FACT_KEYS approved for Phase 3C authoring.
CANONICAL_FACT_KEYS: frozenset[str] = frozenset(
    {
        "is_prepackaged",
        "commodity",
        "quantity",
        "quantity_unit",
        "actor_role",
        "sale_context",
        "consumer_type",
        "observed_declarations",
        "is_imported",
        "package_type",
    }
)

# Fact keys strictly forbidden / deferred in Phase 3C.
FORBIDDEN_FACT_KEYS: frozenset[str] = frozenset(
    {
        "commodity_category",
        "sold_by",
        "general_consumer",
        "e_commerce",
    }
)

VALID_OPERATORS: frozenset[str] = frozenset(
    {
        "equals",
        "not_equals",
        "one_of",
        "greater_than",
        "greater_or_equal",
        "less_than",
        "less_or_equal",
        "range_inclusive",
        "exists",
    }
)

DIMENSIONAL_OPERATORS: frozenset[str] = frozenset(
    {
        "greater_than",
        "greater_or_equal",
        "less_than",
        "less_or_equal",
        "range_inclusive",
    }
)

NON_QUANTITATIVE_FACTS: frozenset[str] = frozenset(
    {
        "is_prepackaged",
        "is_imported",
        "actor_role",
        "sale_context",
        "consumer_type",
        "package_type",
    }
)

ALLOWED_TRANSITIONS: Mapping[str, frozenset[str]] = {
    "draft": frozenset({"draft", "in_review", "rejected"}),
    "in_review": frozenset({"in_review", "approved", "rejected"}),
    "approved": frozenset({"approved", "retired"}),
    "rejected": frozenset({"rejected"}),
    "retired": frozenset({"retired"}),
}

AI_REVIEWER_IDENTIFIERS: frozenset[str] = frozenset(
    {
        "ai",
        "gemini",
        "assistant",
        "system",
        "auto",
        "automated",
        "bot",
        "llm",
        "chatgpt",
        "claude",
    }
)

FORBIDDEN_PLACEHOLDER_DATES: frozenset[date] = frozenset(
    {
        date(2021, 12, 31),
        date(2022, 1, 1),
    }
)


class LintValidationError(ValueError):
    """Raised when an applicability rule version fails authoring linting."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors: list[str] = errors or [message]


class ImmutabilityViolationError(LintValidationError):
    """Raised when an operation attempts to modify an approved rule version."""


@dataclass
class LintResult:
    """The outcome of running the authoring linter against a rule version."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def raise_if_invalid(self) -> None:
        """Raise an appropriate exception if validation failed."""
        if not self.is_valid:
            # If any error is an immutability violation, raise ImmutabilityViolationError
            for err in self.errors:
                if "Immutability violation" in err:
                    raise ImmutabilityViolationError(err, errors=self.errors)
            msg = "Authoring lint validation failed:\n  - " + "\n  - ".join(self.errors)
            raise LintValidationError(msg, errors=self.errors)


def _get(obj: Any, field_name: str, default: Any = None) -> Any:
    """Extract a field from either a dict or an object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(field_name, default)
    return getattr(obj, field_name, default)


def _parse_date(val: Any) -> date | None:
    """Parse date from date, datetime, or ISO string."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return None
        try:
            return date.fromisoformat(val_str)
        except ValueError:
            return None
    return None


class ApplicabilityLinter:
    """Phase 3C statutory applicability authoring linter."""

    def __init__(self, canonical_fact_keys: frozenset[str] = CANONICAL_FACT_KEYS):
        self.canonical_fact_keys = canonical_fact_keys

    def lint(
        self,
        rule: ApplicabilityRule | Mapping[str, Any],
        version: ApplicabilityRuleVersion | Mapping[str, Any],
        groups: Sequence[ApplicabilityConditionGroup | Mapping[str, Any]],
        conditions: Sequence[ApplicabilityCondition | Mapping[str, Any]],
        sources: Sequence[ApplicabilityRuleSource | Mapping[str, Any]],
        previous_version: ApplicabilityRuleVersion | Mapping[str, Any] | None = None,
        previous_groups: Sequence[ApplicabilityConditionGroup | Mapping[str, Any]] | None = None,
        previous_conditions: Sequence[ApplicabilityCondition | Mapping[str, Any]] | None = None,
        previous_sources: Sequence[ApplicabilityRuleSource | Mapping[str, Any]] | None = None,
    ) -> LintResult:
        """Run all 11 authoring invariants against the provided rule package."""
        errors: list[str] = []
        warnings: list[str] = []

        # -------------------------------------------------------------
        # Invariant 1: Rule key matches ^[a-z0-9_]+$
        # -------------------------------------------------------------
        rule_key = _get(rule, "rule_key")
        if not rule_key or not isinstance(rule_key, str) or not re.match(r"^[a-z0-9_]+$", rule_key):
            errors.append(
                f"Rule key '{rule_key}' is invalid: must be a non-empty string matching ^[a-z0-9_]+$"
            )

        # -------------------------------------------------------------
        # Invariant 2: Version number is integer > 0
        # -------------------------------------------------------------
        version_number = _get(version, "version_number")
        if not isinstance(version_number, int) or isinstance(version_number, bool) or version_number <= 0:
            errors.append(
                f"Version number '{version_number}' is invalid: must be an integer > 0"
            )

        # -------------------------------------------------------------
        # Invariant 3: Temporal bounds sanity & no ungrounded dates
        # -------------------------------------------------------------
        raw_valid_from = _get(version, "valid_from")
        raw_valid_to = _get(version, "valid_to")
        parsed_from = _parse_date(raw_valid_from)
        parsed_to = _parse_date(raw_valid_to)

        if raw_valid_from is not None and parsed_from is None:
            errors.append(f"Invalid valid_from date format: '{raw_valid_from}'")
        if raw_valid_to is not None and parsed_to is None:
            errors.append(f"Invalid valid_to date format: '{raw_valid_to}'")

        if parsed_from is not None and parsed_to is not None:
            if parsed_to < parsed_from:
                errors.append(
                    f"Temporal bounds invalid: valid_to ({parsed_to}) cannot be earlier than valid_from ({parsed_from})"
                )

        amendment_id = _get(version, "amendment_id")
        if parsed_from in FORBIDDEN_PLACEHOLDER_DATES and not amendment_id:
            errors.append(
                f"Disallowed hardcoded/invented temporal boundary '{raw_valid_from}': dates must be grounded in verified amendment evidence"
            )
        if parsed_to in FORBIDDEN_PLACEHOLDER_DATES and not amendment_id:
            errors.append(
                f"Disallowed hardcoded/invented temporal boundary '{raw_valid_to}': dates must be grounded in verified amendment evidence"
            )

        # -------------------------------------------------------------
        # Invariant 4: Exactly one root applicability group
        # -------------------------------------------------------------
        root_applicability = [
            g for g in groups
            if _get(g, "parent_group_id") is None and _get(g, "group_purpose") == "applicability"
        ]
        if len(root_applicability) == 0:
            errors.append(
                "Rule version must have exactly one root applicability group with parent_group_id=None and group_purpose='applicability' (found 0)"
            )
        elif len(root_applicability) > 1:
            errors.append(
                f"Rule version must have exactly one root applicability group (found {len(root_applicability)})"
            )

        # Validate purpose and operator of all groups
        for g in groups:
            gid = _get(g, "id")
            purpose = _get(g, "group_purpose")
            op = _get(g, "boolean_operator")
            status = _get(g, "review_status")
            if purpose not in ("applicability", "exception"):
                errors.append(f"Condition group '{gid}' has invalid group_purpose '{purpose}'")
            if op not in ("AND", "OR"):
                errors.append(f"Condition group '{gid}' has invalid boolean_operator '{op}'")
            if status not in ("draft", "in_review", "approved", "rejected"):
                errors.append(f"Condition group '{gid}' has invalid review_status '{status}'")

        # -------------------------------------------------------------
        # Invariant 5: Acyclic condition tree
        # -------------------------------------------------------------
        group_ids = {str(_get(g, "id")) for g in groups}
        for g in groups:
            gid = str(_get(g, "id"))
            pid = _get(g, "parent_group_id")
            if pid is not None:
                pid_str = str(pid)
                if pid_str == gid:
                    errors.append(f"Condition group '{gid}' cannot be its own parent")
                elif pid_str not in group_ids:
                    errors.append(
                        f"Condition group '{gid}' references non-existent parent_group_id '{pid}'"
                    )

        # Cycle check
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def _dfs_cycle(gid: str) -> bool:
            if gid in rec_stack:
                return True
            if gid in visited:
                return False
            visited.add(gid)
            rec_stack.add(gid)
            for other in groups:
                other_pid = _get(other, "parent_group_id")
                if other_pid is not None and str(other_pid) == gid:
                    if _dfs_cycle(str(_get(other, "id"))):
                        return True
            rec_stack.remove(gid)
            return False

        has_cycle = False
        for g in groups:
            gid = str(_get(g, "id"))
            if gid not in visited:
                if _dfs_cycle(gid):
                    has_cycle = True
                    errors.append(f"Cyclic condition tree detected involving group '{gid}'")
                    break

        # -------------------------------------------------------------
        # Invariant 6: Maximum condition-tree depth <= 3
        # -------------------------------------------------------------
        if not has_cycle:
            group_lookup = {str(_get(g, "id")): g for g in groups}
            for g in groups:
                gid = str(_get(g, "id"))
                curr = g
                depth = 1
                loop_limit = len(groups) + 1
                while _get(curr, "parent_group_id") is not None and loop_limit > 0:
                    pid = str(_get(curr, "parent_group_id"))
                    if pid not in group_lookup:
                        break
                    curr = group_lookup[pid]
                    depth += 1
                    loop_limit -= 1
                if depth > 3:
                    errors.append(
                        f"Condition group '{gid}' exceeds maximum allowed tree depth of 3 (depth={depth})"
                    )

        # -------------------------------------------------------------
        # Invariant 7: Canonical Fact Keys
        # -------------------------------------------------------------
        for cond in conditions:
            cid = _get(cond, "id")
            fkey = _get(cond, "fact_key")
            if not fkey or fkey not in self.canonical_fact_keys:
                if fkey in FORBIDDEN_FACT_KEYS:
                    errors.append(
                        f"Condition '{cid}' uses unapproved/forbidden fact_key '{fkey}'"
                    )
                else:
                    errors.append(
                        f"Condition '{cid}' uses unknown fact_key '{fkey}'. Must be in canonical vocabulary"
                    )

        # -------------------------------------------------------------
        # Invariant 8: Operator/unit compatibility
        # -------------------------------------------------------------
        for cond in conditions:
            cid = _get(cond, "id")
            op = _get(cond, "operator")
            fkey = _get(cond, "fact_key")
            exp_val = _get(cond, "expected_value")
            exp_unit = _get(cond, "expected_unit")

            if op not in VALID_OPERATORS:
                errors.append(f"Condition '{cid}' uses invalid operator '{op}'")
                continue

            # Dimensional operator on quantity requires expected_unit
            if fkey == "quantity" and op in DIMENSIONAL_OPERATORS:
                if not exp_unit or not str(exp_unit).strip():
                    errors.append(
                        f"Condition '{cid}' uses dimensional operator '{op}' on 'quantity' but is missing required expected_unit"
                    )

            # Non-quantitative facts must not specify expected_unit
            if fkey in NON_QUANTITATIVE_FACTS and exp_unit is not None:
                errors.append(
                    f"Condition '{cid}' on non-quantitative fact '{fkey}' must not specify expected_unit (got '{exp_unit}')"
                )

            # Value structure per operator
            if op == "one_of":
                if not isinstance(exp_val, (list, tuple, set)) or len(exp_val) == 0:
                    errors.append(
                        f"Condition '{cid}' with operator 'one_of' requires a non-empty list of expected values"
                    )
            elif op == "range_inclusive":
                if not isinstance(exp_val, (list, tuple)) or len(exp_val) != 2:
                    errors.append(
                        f"Condition '{cid}' with operator 'range_inclusive' requires a 2-element list [min, max]"
                    )
                else:
                    try:
                        if float(exp_val[0]) > float(exp_val[1]):
                            errors.append(
                                f"Condition '{cid}' with range_inclusive has min ({exp_val[0]}) > max ({exp_val[1]})"
                            )
                    except (ValueError, TypeError):
                        pass
            elif op in ("equals", "not_equals"):
                if exp_val is None:
                    errors.append(
                        f"Condition '{cid}' with operator '{op}' requires non-null expected_value"
                    )

        # -------------------------------------------------------------
        # Invariant 9: Source-to-condition provenance consistency
        # -------------------------------------------------------------
        source_map_cond: set[str] = set()
        source_map_group: set[str] = set()
        supports_count = 0

        cond_id_set = {str(_get(c, "id")) for c in conditions}

        for src in sources:
            sid = _get(src, "id")
            role = _get(src, "source_role")
            quote = _get(src, "source_quote")
            prov_id = _get(src, "provision_id")
            req_id = _get(src, "requirement_id")
            cid = _get(src, "condition_id")
            gid = _get(src, "condition_group_id")

            if not quote or not str(quote).strip():
                errors.append(
                    f"Source '{sid}' has empty source_quote: verbatim quote is strictly required"
                )
            if prov_id is None:
                errors.append(f"Source '{sid}' is missing provision_id")
            if req_id is None:
                errors.append(f"Source '{sid}' is missing requirement_id")

            if role == "supports":
                supports_count += 1
            elif role == "condition":
                if cid is not None:
                    source_map_cond.add(str(cid))
                if gid is not None:
                    source_map_group.add(str(gid))
            elif role == "exception":
                if gid is not None:
                    source_map_group.add(str(gid))

            # Mismatched/dangling source links
            if cid is not None and str(cid) not in cond_id_set:
                errors.append(
                    f"Source '{sid}' references non-existent condition_id '{cid}'"
                )
            if gid is not None and str(gid) not in group_ids:
                errors.append(
                    f"Source '{sid}' references non-existent condition_group_id '{gid}'"
                )

        if supports_count == 0:
            errors.append(
                "Rule version must have at least one source link with source_role='supports'"
            )

        # Every leaf condition must have supporting provenance
        for cond in conditions:
            cid_str = str(_get(cond, "id"))
            gid_str = str(_get(cond, "group_id"))
            if cid_str not in source_map_cond and gid_str not in source_map_group:
                errors.append(
                    f"Condition '{cid_str}' (fact_key='{_get(cond, 'fact_key')}') has no supporting statutory provenance with source_role='condition'"
                )

        # Every exception group must have supporting exception provenance
        for g in groups:
            gid_str = str(_get(g, "id"))
            if _get(g, "group_purpose") == "exception":
                if gid_str not in source_map_group:
                    errors.append(
                        f"Exception group '{gid_str}' has no supporting statutory provenance with source_role='exception'"
                    )

        # -------------------------------------------------------------
        # Invariant 10: Valid interpretation lifecycle transitions
        # -------------------------------------------------------------
        curr_status = _get(version, "interpretation_status")
        prev_status = _get(previous_version, "interpretation_status") if previous_version else None

        if prev_status is not None:
            allowed = ALLOWED_TRANSITIONS.get(prev_status, frozenset())
            if curr_status not in allowed:
                errors.append(
                    f"Invalid lifecycle transition from '{prev_status}' to '{curr_status}'"
                )

        # Human accreditation invariant for approval
        if curr_status == "approved":
            reviewed_by = _get(version, "reviewed_by")
            reviewed_at = _get(version, "reviewed_at")
            if not reviewed_by or not str(reviewed_by).strip():
                errors.append(
                    "Rule version cannot be approved without an identified human reviewer (reviewed_by)"
                )
            else:
                rev_clean = str(reviewed_by).strip().lower()
                if rev_clean in AI_REVIEWER_IDENTIFIERS:
                    errors.append(
                        f"AI/automated reviewer '{reviewed_by}' cannot approve rule versions. Human legal review is strictly required"
                    )
            if reviewed_at is None:
                errors.append(
                    "Rule version cannot be approved without review timestamp (reviewed_at)"
                )

        # -------------------------------------------------------------
        # Invariant 11: Approved versions are immutable
        # -------------------------------------------------------------
        if previous_version is not None:
            prev_status = _get(previous_version, "interpretation_status")
            if prev_status == "approved":
                prev_num = _get(previous_version, "version_number")
                curr_num = _get(version, "version_number")

                if prev_num == curr_num:
                    # Attempted in-place modification of approved version
                    is_allowed_retirement = (curr_status == "retired")
                    has_structural_mods = False

                    # Check version fields
                    for f in ("valid_from", "valid_to", "amendment_id"):
                        if _get(version, f) != _get(previous_version, f):
                            has_structural_mods = True
                            break

                    # Check group / condition / source changes if provided
                    if previous_groups is not None:
                        curr_g_tuples = {(str(_get(g, "id")), _get(g, "group_purpose"), _get(g, "boolean_operator")) for g in groups}
                        prev_g_tuples = {(str(_get(g, "id")), _get(g, "group_purpose"), _get(g, "boolean_operator")) for g in previous_groups}
                        if curr_g_tuples != prev_g_tuples:
                            has_structural_mods = True

                    if previous_conditions is not None:
                        curr_c_tuples = {(str(_get(c, "id")), _get(c, "fact_key"), _get(c, "operator"), str(_get(c, "expected_value")), str(_get(c, "expected_unit"))) for c in conditions}
                        prev_c_tuples = {(str(_get(c, "id")), _get(c, "fact_key"), _get(c, "operator"), str(_get(c, "expected_value")), str(_get(c, "expected_unit"))) for c in previous_conditions}
                        if curr_c_tuples != prev_c_tuples:
                            has_structural_mods = True

                    if previous_sources is not None:
                        curr_s_tuples = {(str(_get(s, "id")), _get(s, "source_role"), _get(s, "source_quote")) for s in sources}
                        prev_s_tuples = {(str(_get(s, "id")), _get(s, "source_role"), _get(s, "source_quote")) for s in previous_sources}
                        if curr_s_tuples != prev_s_tuples:
                            has_structural_mods = True

                    if has_structural_mods or not is_allowed_retirement:
                        errors.append(
                            f"Immutability violation: Version {prev_num} is 'approved' and cannot be modified. "
                            f"Corrections or amendments must be authored as a new version (Version {prev_num + 1}) in 'draft' status."
                        )

        return LintResult(is_valid=(len(errors) == 0), errors=errors, warnings=warnings)


def lint_rule_version(
    rule: ApplicabilityRule | Mapping[str, Any],
    version: ApplicabilityRuleVersion | Mapping[str, Any],
    groups: Sequence[ApplicabilityConditionGroup | Mapping[str, Any]],
    conditions: Sequence[ApplicabilityCondition | Mapping[str, Any]],
    sources: Sequence[ApplicabilityRuleSource | Mapping[str, Any]],
    previous_version: ApplicabilityRuleVersion | Mapping[str, Any] | None = None,
    previous_groups: Sequence[ApplicabilityConditionGroup | Mapping[str, Any]] | None = None,
    previous_conditions: Sequence[ApplicabilityCondition | Mapping[str, Any]] | None = None,
    previous_sources: Sequence[ApplicabilityRuleSource | Mapping[str, Any]] | None = None,
) -> LintResult:
    """Convenience functional interface to lint a rule version package."""
    linter = ApplicabilityLinter()
    return linter.lint(
        rule=rule,
        version=version,
        groups=groups,
        conditions=conditions,
        sources=sources,
        previous_version=previous_version,
        previous_groups=previous_groups,
        previous_conditions=previous_conditions,
        previous_sources=previous_sources,
    )
