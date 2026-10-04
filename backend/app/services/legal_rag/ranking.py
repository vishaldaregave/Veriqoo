"""Deterministic ranking contract for Legal RAG (Phase 4A).

Establishes a reproducible ordering across retrieved legal entities based on:
1. Requirement priority tier
2. Provenance specificity
3. Relevance score
4. Entity type hierarchy
5. Stable entity ID tie-breaker
"""

from __future__ import annotations

from typing import Sequence

from backend.app.services.legal_rag.models import (
    LegalEntityType,
    LegalSearchResult,
)

ENTITY_TYPE_PRIORITY: dict[LegalEntityType, int] = {
    LegalEntityType.REQUIREMENT: 1,
    LegalEntityType.PROVISION: 2,
    LegalEntityType.SCHEDULE_ENTRY: 3,
    LegalEntityType.TABLE: 4,
    LegalEntityType.AMENDMENT: 5,
}


def rank_key(res: LegalSearchResult) -> tuple[int, float, float, int, str]:
    """Deterministic comparison key for sorting search results.

    Tuple components:
    1. requirement_priority (ascending, 1 is highest priority)
    2. provenance_specificity (descending, higher specificity first -> negated)
    3. score (descending, higher score first -> negated)
    4. entity_type_priority (ascending, requirements first)
    5. entity_id (ascending string, deterministic tie-breaker)
    """
    priority = res.ranking.requirement_priority
    specificity = -float(res.ranking.provenance_specificity)
    score = -float(res.ranking.score)
    type_prio = ENTITY_TYPE_PRIORITY.get(res.entity_type, 99)
    tie_breaker = str(res.entity_id)

    return (priority, specificity, score, type_prio, tie_breaker)


def rank_results(results: Sequence[LegalSearchResult]) -> list[LegalSearchResult]:
    """Sort legal search results using the deterministic multi-criteria ranking contract."""
    return sorted(results, key=rank_key)


def apply_provisional_threshold(
    results: Sequence[LegalSearchResult],
    threshold: float,
    allow_fallback: bool = False,
) -> tuple[list[LegalSearchResult], bool]:
    """Apply a provisional semantic/relevance threshold.

    Returns:
        (filtered_results, fallback_triggered)
    If no results pass the threshold:
    - If allow_fallback is False, returns empty list with fallback_triggered=True.
    - If allow_fallback is True, returns top-K with fallback_triggered=True (provisional fallback).
    """
    passed = [r for r in results if r.ranking.score >= threshold]
    if passed:
        return rank_results(passed), False

    if not results:
        return [], False

    # All results below threshold
    if allow_fallback:
        # Fallback retains results but signals low confidence
        return rank_results(results), True
    return [], True

