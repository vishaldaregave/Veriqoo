"""Deterministic deduplication contract for Legal RAG (Phase 4A).

Handles overlapping legal entities:
- Multiple retrieval methods returning the same entity
- Requirement + linked provision
- Provision + schedule entry / table
Preserves full provenance and links related entities rather than discarding them.
"""

from __future__ import annotations

from typing import Iterable

from backend.app.services.legal_rag.models import (
    LegalEntityType,
    LegalSearchResult,
    RankingMetadata,
)
from backend.app.services.legal_rag.provenance import merge_provenance


def deduplicate_results(results: Iterable[LegalSearchResult]) -> list[LegalSearchResult]:
    """Deduplicate legal search results while preserving complete statutory provenance

    and establishing explicit hierarchical relationships.
    """
    seen: dict[tuple[LegalEntityType, str], LegalSearchResult] = {}

    for res in results:
        key = (res.entity_type, str(res.entity_id))

        if key not in seen:
            seen[key] = res
            continue

        # Existing entity retrieved again (e.g., exact ID lookup + semantic retrieval)
        existing = seen[key]

        # 1. Merge provenance
        if existing.provenance and res.provenance:
            existing.provenance = merge_provenance(existing.provenance, res.provenance)
        elif res.provenance and not existing.provenance:
            existing.provenance = res.provenance

        # 2. Merge ranking signals (take the maximum score, combine matched terms)
        max_score = max(existing.ranking.score, res.ranking.score)
        combined_terms = tuple(sorted(set(existing.ranking.matched_terms + res.ranking.matched_terms)))
        lexical = (
            max(existing.ranking.lexical_score or 0.0, res.ranking.lexical_score or 0.0)
            if (existing.ranking.lexical_score is not None or res.ranking.lexical_score is not None)
            else None
        )
        semantic = (
            max(existing.ranking.semantic_similarity or 0.0, res.ranking.semantic_similarity or 0.0)
            if (existing.ranking.semantic_similarity is not None or res.ranking.semantic_similarity is not None)
            else None
        )
        existing.ranking = RankingMetadata(
            score=max_score,
            lexical_score=lexical,
            semantic_similarity=semantic,
            provenance_specificity=max(
                existing.ranking.provenance_specificity,
                res.ranking.provenance_specificity,
            ),
            requirement_priority=min(
                existing.ranking.requirement_priority,
                res.ranking.requirement_priority,
            ),
            is_provisional_threshold=existing.ranking.is_provisional_threshold and res.ranking.is_provisional_threshold,
            matched_terms=combined_terms,
        )

        # 3. Merge linked entities
        for lid in res.linked_entity_ids:
            if lid not in existing.linked_entity_ids:
                existing.linked_entity_ids.append(lid)

        # 4. If new result has parent info and existing does not, adopt it
        if res.parent_entity_id and not existing.parent_entity_id:
            existing.parent_entity_id = res.parent_entity_id
            existing.parent_entity_type = res.parent_entity_type

    deduped = list(seen.values())

    # Establish cross-entity links between requirements and their parent provisions
    provision_ids = {
        str(r.entity_id): r
        for r in deduped
        if r.entity_type == LegalEntityType.PROVISION
    }

    for item in deduped:
        if item.entity_type == LegalEntityType.REQUIREMENT and item.provenance:
            prov_id = str(item.provenance.provision_id) if item.provenance.provision_id else None
            if prov_id:
                if prov_id not in item.linked_entity_ids:
                    item.linked_entity_ids.append(prov_id)
                item.parent_entity_id = prov_id
                item.parent_entity_type = LegalEntityType.PROVISION
                # Also link back on the provision if present
                if prov_id in provision_ids:
                    prov = provision_ids[prov_id]
                    if str(item.entity_id) not in prov.linked_entity_ids:
                        prov.linked_entity_ids.append(str(item.entity_id))

    return deduped

