"""Temporal applicability and amendment handling for Legal RAG (Phase 4A).

Statutory constraints:
- Do NOT infer legal effective dates.
- Do NOT invent valid_from / valid_to.
- Use ONLY dates explicitly available in the authoritative legal corpus.
- If temporal applicability cannot be established with certainty, preserve UNKNOWN.
"""

from __future__ import annotations

from datetime import date

from backend.app.services.legal_rag.models import TemporalStatus


def resolve_temporal_status(
    effective_from: date | None,
    effective_to: date | None,
    as_of_date: date | None,
) -> TemporalStatus:
    """Resolve the temporal validity status of a legal entity without inventing dates.

    If either the reference inspection date or statutory boundary is missing,
    returns TemporalStatus.UNKNOWN.
    """
    if as_of_date is None:
        # Inspection date unknown -> cannot establish temporal validity
        return TemporalStatus.UNKNOWN

    if effective_from is None and effective_to is None:
        # No explicit dates in statutory record -> preserve UNKNOWN per statutory constraint
        return TemporalStatus.UNKNOWN

    if effective_from is not None and as_of_date < effective_from:
        return TemporalStatus.HISTORICAL

    if effective_to is not None and as_of_date > effective_to:
        return TemporalStatus.SUPERSEDED

    # When effective_from is known and satisfied, and effective_to is not exceeded
    if effective_from is not None:
        if effective_to is None or as_of_date <= effective_to:
            return TemporalStatus.CURRENT

    # When effective_to is known and as_of_date <= effective_to, but effective_from is None
    # We cannot know if it was in force prior to effective_to without an effective_from
    return TemporalStatus.UNKNOWN

