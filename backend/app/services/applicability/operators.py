"""Leaf condition operator evaluation implementing Strong Kleene three-valued logic."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from backend.app.services.applicability.models import (
    ApplicabilityCondition,
    InspectionFact,
    TriState,
)
from backend.app.services.applicability.units import convert_quantity, to_decimal

SUPPORTED_OPERATORS = frozenset(
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


def evaluate_condition(
    condition: ApplicabilityCondition,
    fact: InspectionFact | None,
) -> tuple[TriState, str]:
    """Evaluate an atomic applicability condition against an inspection fact.

    Returns:
        (TriState, reason_string)
    """
    op = condition.operator
    if op not in SUPPORTED_OPERATORS:
        return TriState.UNKNOWN, f"Unsupported operator: '{op}'"

    # Handle missing fact record
    if fact is None:
        return (
            TriState.UNKNOWN,
            f"Fact '{condition.fact_key}' is missing from inspection run",
        )

    # 1. Special semantics for operator 'exists'
    # Absence of OCR observation is NOT proof of non-existence.
    if op == "exists":
        if fact.fact_status == "known":
            return TriState.TRUE, f"Fact '{condition.fact_key}' exists and is known"
        if fact.fact_status == "not_applicable":
            return TriState.FALSE, f"Fact '{condition.fact_key}' is not applicable"
        # For 'unknown' or 'not_observed'
        return (
            TriState.UNKNOWN,
            f"Fact '{condition.fact_key}' status is '{fact.fact_status}' (cannot confirm existence)",
        )

    # 2. For all scalar operators, non-known status evaluates to UNKNOWN
    if fact.fact_status != "known":
        return (
            TriState.UNKNOWN,
            f"Fact '{condition.fact_key}' has status '{fact.fact_status}'; value cannot be evaluated",
        )

    # Fact is known: value must be present
    fact_val = fact.value
    expected_val = condition.expected_value

    # Unit conversion and normalization if quantity unit is involved
    if condition.expected_unit is not None or fact.unit is not None:
        dec_fact = to_decimal(fact_val)
        if dec_fact is None:
            return (
                TriState.UNKNOWN,
                f"Malformed fact value: expected numeric Decimal for unit comparison, got '{fact_val}'",
            )

        if condition.expected_unit is not None:
            converted_val, conv_err = convert_quantity(
                dec_fact,
                from_unit=fact.unit,
                to_unit=condition.expected_unit,
            )
            if conv_err is not None:
                return TriState.UNKNOWN, conv_err
            fact_val = converted_val

    # 3. Evaluate specific scalar operators
    if op == "equals":
        # Check numeric equality if both parseable as Decimal
        dec_f = to_decimal(fact_val)
        dec_e = to_decimal(expected_val)
        if dec_f is not None and dec_e is not None:
            eq = dec_f == dec_e
        else:
            eq = fact_val == expected_val
        return (
            (TriState.TRUE, f"Fact '{condition.fact_key}' ({fact_val}) equals expected ({expected_val})")
            if eq
            else (TriState.FALSE, f"Fact '{condition.fact_key}' ({fact_val}) does not equal expected ({expected_val})")
        )

    if op == "not_equals":
        dec_f = to_decimal(fact_val)
        dec_e = to_decimal(expected_val)
        if dec_f is not None and dec_e is not None:
            neq = dec_f != dec_e
        else:
            neq = fact_val != expected_val
        return (
            (TriState.TRUE, f"Fact '{condition.fact_key}' ({fact_val}) not equals ({expected_val})")
            if neq
            else (TriState.FALSE, f"Fact '{condition.fact_key}' ({fact_val}) equals ({expected_val})")
        )

    if op == "one_of":
        if not isinstance(expected_val, (list, tuple, set, frozenset)):
            return (
                TriState.UNKNOWN,
                f"Expected value for 'one_of' must be a list/set, got {type(expected_val).__name__}",
            )
        # Check membership with Decimal tolerance if numeric
        dec_f = to_decimal(fact_val)
        if dec_f is not None:
            dec_list = [to_decimal(x) for x in expected_val]
            matched = any(d is not None and dec_f == d for d in dec_list)
        else:
            matched = fact_val in expected_val
        return (
            (TriState.TRUE, f"Fact '{condition.fact_key}' ({fact_val}) is in {expected_val}")
            if matched
            else (TriState.FALSE, f"Fact '{condition.fact_key}' ({fact_val}) is not in {expected_val}")
        )

    # Numeric comparison operators: greater_than, greater_or_equal, less_than, less_or_equal
    if op in {"greater_than", "greater_or_equal", "less_than", "less_or_equal"}:
        dec_f = to_decimal(fact_val)
        dec_e = to_decimal(expected_val)
        if dec_f is None or dec_e is None:
            return (
                TriState.UNKNOWN,
                f"Malformed fact or expected value for '{op}': expected numeric Decimal",
            )

        if op == "greater_than":
            res = dec_f > dec_e
        elif op == "greater_or_equal":
            res = dec_f >= dec_e
        elif op == "less_than":
            res = dec_f < dec_e
        elif op == "less_or_equal":
            res = dec_f <= dec_e
        else:
            res = False

        return (
            (TriState.TRUE, f"Fact '{condition.fact_key}' ({dec_f}) satisfies {op} ({dec_e})")
            if res
            else (TriState.FALSE, f"Fact '{condition.fact_key}' ({dec_f}) fails {op} ({dec_e})")
        )

    if op == "range_inclusive":
        if not isinstance(expected_val, (list, tuple)) or len(expected_val) != 2:
            return (
                TriState.UNKNOWN,
                f"Expected value for 'range_inclusive' must be a 2-element array [min, max]",
            )
        dec_f = to_decimal(fact_val)
        dec_min = to_decimal(expected_val[0])
        dec_max = to_decimal(expected_val[1])
        if dec_f is None or dec_min is None or dec_max is None:
            return (
                TriState.UNKNOWN,
                "Malformed values for range_inclusive: expected numeric Decimals",
            )

        in_range = dec_min <= dec_f <= dec_max
        return (
            (TriState.TRUE, f"Fact '{condition.fact_key}' ({dec_f}) in range [{dec_min}, {dec_max}]")
            if in_range
            else (TriState.FALSE, f"Fact '{condition.fact_key}' ({dec_f}) outside range [{dec_min}, {dec_max}]")
        )

    return TriState.UNKNOWN, f"Unhandled operator: '{op}'"

