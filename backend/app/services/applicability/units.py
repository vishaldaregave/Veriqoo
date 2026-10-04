"""Reviewed unit conversion registry and exact Decimal dimensional arithmetic.

Conforms strictly to Phase 3B constraints:
- Reviewed units only (derived from Legal Metrology (Packaged Commodities) Rules, 2011).
- No unreviewed units or automatic physical assumptions.
- Exact Decimal calculations (no float).
- Same-dimension conversion only via registered conversion factors.
- Cross-dimension conversions are strictly forbidden (no density or commodity bridges).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

# Reviewed units and their explicit physical dimensions
REVIEWED_UNITS: dict[str, str] = {
    # Weight
    "mg": "weight",
    "g": "weight",
    "kg": "weight",
    # Volume
    "ml": "volume",
    "cl": "volume",
    "l": "volume",
    # Length
    "mm": "length",
    "cm": "length",
    "m": "length",
    # Area
    "sq_cm": "area",
    "sq_dm": "area",
    "sq_m": "area",
    # Discrete Count / Number
    "piece": "number",
    "unit": "number",
}

# Unit alias canonicalization map (case-insensitive normalization)
UNIT_ALIASES: dict[str, str] = {
    "mg": "mg",
    "milligram": "mg",
    "milligramme": "mg",
    "g": "g",
    "gram": "g",
    "gramme": "g",
    "gms": "g",
    "gm": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilogramme": "kg",
    "kgs": "kg",
    "ml": "ml",
    "millilitre": "ml",
    "milliliter": "ml",
    "cl": "cl",
    "centilitre": "cl",
    "centiliter": "cl",
    "l": "l",
    "litre": "l",
    "liter": "l",
    "ltr": "l",
    "mm": "mm",
    "millimetre": "mm",
    "millimeter": "mm",
    "cm": "cm",
    "centimetre": "cm",
    "centimeter": "cm",
    "m": "m",
    "metre": "m",
    "meter": "m",
    "sq_cm": "sq_cm",
    "sq.cm": "sq_cm",
    "cm2": "sq_cm",
    "sq_dm": "sq_dm",
    "sq.dm": "sq_dm",
    "dm2": "sq_dm",
    "sq_m": "sq_m",
    "sq.m": "sq_m",
    "m2": "sq_m",
    "piece": "piece",
    "pieces": "piece",
    "pc": "piece",
    "pcs": "piece",
    "unit": "unit",
    "units": "unit",
    "u": "unit",
}

# Explicitly reviewed intra-dimensional conversion factors (Factor converts unit1 -> unit2: val * factor)
# Only reviewed statutory relationships are registered.
REVIEWED_CONVERSIONS: dict[tuple[str, str], Decimal] = {
    # Weight
    ("kg", "g"): Decimal("1000"),
    ("g", "kg"): Decimal("0.001"),
    ("g", "mg"): Decimal("1000"),
    ("mg", "g"): Decimal("0.001"),
    ("kg", "mg"): Decimal("1000000"),
    ("mg", "kg"): Decimal("0.000001"),
    # Volume
    ("l", "ml"): Decimal("1000"),
    ("ml", "l"): Decimal("0.001"),
    ("l", "cl"): Decimal("100"),
    ("cl", "l"): Decimal("0.01"),
    ("cl", "ml"): Decimal("10"),
    ("ml", "cl"): Decimal("0.1"),
    # Length
    ("m", "cm"): Decimal("100"),
    ("cm", "m"): Decimal("0.01"),
    ("cm", "mm"): Decimal("10"),
    ("mm", "cm"): Decimal("0.1"),
    ("m", "mm"): Decimal("1000"),
    ("mm", "m"): Decimal("0.001"),
    # Area
    ("sq_m", "sq_dm"): Decimal("100"),
    ("sq_dm", "sq_m"): Decimal("0.01"),
    ("sq_dm", "sq_cm"): Decimal("100"),
    ("sq_cm", "sq_dm"): Decimal("0.01"),
    ("sq_m", "sq_cm"): Decimal("10000"),
    ("sq_cm", "sq_m"): Decimal("0.0001"),
    # Number
    ("piece", "unit"): Decimal("1"),
    ("unit", "piece"): Decimal("1"),
}


def normalize_unit(raw_unit: str | None) -> str | None:
    """Canonicalize a unit string to lower-case key without losing original context."""
    if raw_unit is None:
        return None
    cleaned = raw_unit.strip().lower()
    return UNIT_ALIASES.get(cleaned, cleaned)


def is_reviewed_unit(unit: str | None) -> bool:
    """Return True only if unit is recognized in the reviewed ontology."""
    if unit is None:
        return False
    norm = normalize_unit(unit)
    return norm in REVIEWED_UNITS


def get_unit_dimension(unit: str | None) -> str | None:
    """Return the reviewed physical dimension for a unit, or None if unreviewed."""
    if unit is None:
        return None
    norm = normalize_unit(unit)
    return REVIEWED_UNITS.get(norm or "")


def to_decimal(value: Any) -> Decimal | None:
    """Safely parse a numeric value to Decimal without using float intermediates."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        try:
            return Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            return None
    if isinstance(value, float):
        # Convert via exact string representation, but float inputs in legal domain are discouraged
        return Decimal(str(value))
    return None


def convert_quantity(
    value: Decimal,
    from_unit: str | None,
    to_unit: str | None,
) -> tuple[Decimal | None, str | None]:
    """Convert a Decimal quantity between units.

    Returns:
        (converted_value, None) on success.
        (None, error_reason) on failure/rejection.
    """
    if from_unit is None or to_unit is None:
        return None, "Unit must be specified for quantity conversion"

    norm_from = normalize_unit(from_unit)
    norm_to = normalize_unit(to_unit)

    if not norm_from or norm_from not in REVIEWED_UNITS:
        return None, f"Unrecognized or unreviewed source unit: '{from_unit}'"

    if not norm_to or norm_to not in REVIEWED_UNITS:
        return None, f"Unrecognized or unreviewed target unit: '{to_unit}'"

    dim_from = REVIEWED_UNITS[norm_from]
    dim_to = REVIEWED_UNITS[norm_to]

    # Cross-dimension conversions are strictly forbidden
    if dim_from != dim_to:
        return None, (
            f"Incompatible unit dimensions: '{from_unit}' ({dim_from}) vs "
            f"'{to_unit}' ({dim_to}) without approved conversion bridge"
        )

    # Identical units require no arithmetic
    if norm_from == norm_to:
        return value, None

    factor = REVIEWED_CONVERSIONS.get((norm_from, norm_to))
    if factor is None:
        return None, (
            f"Unreviewed unit conversion from '{from_unit}' to '{to_unit}' "
            f"within dimension '{dim_from}'"
        )

    return value * factor, None

