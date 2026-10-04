"""Deterministic multi-tier ranking strategy (Phase 4C).

Grounded in authoritative corpus:
- Tier 1: Direct authoritative lookup (exact ID lookup requested by caller or applicability).
- Tier 2: Explicit statutory relationship expansion (parent provision, schedule, table, amendment).
- Tier 3: Semantic retrieval candidates (ordered by cosine similarity descending).
- Canonical tie-breaking: entity_type ASC, entity_id ASC.
- Explicit legal relationships are NEVER displaced by lower-tier semantic candidates.
"""

from __future__ import annotations

from backend.app.services.legal_rag.retrieval.models import RetrievedEntityContext


class DeterministicRanker:
    """Applies transparent, multi-tier ranking to retrieved legal entities."""

    @staticmethod
    def rank(entities: list[RetrievedEntityContext]) -> list[RetrievedEntityContext]:
        """Rank retrieved entities deterministically using statutory priority tiers."""
        if not entities:
            return []

        def sort_key(ent: RetrievedEntityContext) -> tuple[int, float, str, str]:
            # Tier: 1 (Direct) < 2 (Explicit Expansion) < 3 (Semantic Retrieval)
            tier = ent.ranking_tier if ent.ranking_tier in (1, 2, 3) else 3
            # Invert score for descending order
            score = -(ent.similarity_score if ent.similarity_score is not None else 0.0)
            etype = ent.entity_type.value
            eid = str(ent.entity_id)
            return (tier, score, etype, eid)

        return sorted(entities, key=sort_key)

