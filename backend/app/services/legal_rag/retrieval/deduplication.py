"""Deterministic legal context deduplication (Phase 4C).

Grounded in authoritative corpus:
- Deduplication is keyed strictly by (entity_type, entity_id).
- NEVER merges distinct legal entities merely because their text is similar.
- Preserves:
  * original entity identity
  * strongest retrieval score (and lowest ranking tier)
  * all applicable retrieval methods
  * combined provenance and relationship links
"""

from __future__ import annotations

from backend.app.services.legal_rag.models import RetrievalMethod
from backend.app.services.legal_rag.retrieval.models import RetrievedEntityContext


class DeterministicDeduplicator:
    """Deduplicates retrieved legal entities while preserving comprehensive provenance."""

    @staticmethod
    def deduplicate(entities: list[RetrievedEntityContext]) -> list[RetrievedEntityContext]:
        """Deduplicate entities by (entity_type, entity_id), preserving best score and all methods."""
        if not entities:
            return []

        grouped: dict[tuple[str, str], list[RetrievedEntityContext]] = {}
        for ent in entities:
            key = (ent.entity_type.value, str(ent.entity_id))
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(ent)

        deduped: list[RetrievedEntityContext] = []

        for key, instances in grouped.items():
            if len(instances) == 1:
                deduped.append(instances[0])
                continue

            # Pick primary instance with best ranking tier (1: Direct > 2: Expansion > 3: Semantic)
            # If tiers are equal, choose highest similarity score
            best = min(
                instances,
                key=lambda x: (
                    x.ranking_tier,
                    -(x.similarity_score if x.similarity_score is not None else 0.0),
                ),
            )

            # Collect all retrieval methods without duplicates
            all_methods: list[RetrievalMethod] = []
            for inst in instances:
                for m in inst.retrieval_methods:
                    if m not in all_methods:
                        all_methods.append(m)

            # Merge linked relationships
            linked_reqs = list(dict.fromkeys([rid for inst in instances for rid in inst.linked_requirement_ids]))
            linked_provs = list(dict.fromkeys([pid for inst in instances for pid in inst.linked_provision_ids]))
            linked_scheds = list(dict.fromkeys([sid for inst in instances for sid in inst.linked_schedule_entry_ids]))
            linked_tables = list(dict.fromkeys([tid for inst in instances for tid in inst.linked_table_ids]))
            linked_amends = list(dict.fromkeys([aid for inst in instances for aid in inst.linked_amendment_ids]))

            # Highest score
            scores = [inst.similarity_score for inst in instances if inst.similarity_score is not None]
            best_score = max(scores) if scores else None

            # Lowest ranking tier
            min_tier = min(inst.ranking_tier for inst in instances)

            merged = RetrievedEntityContext(
                entity_type=best.entity_type,
                entity_id=best.entity_id,
                source_identifier=best.source_identifier,
                source_reference=best.source_reference,
                legal_text=best.legal_text,
                source_quote=best.source_quote,
                similarity_score=best_score,
                retrieval_method=best.retrieval_method,
                retrieval_methods=all_methods,
                provenance=best.provenance,
                linked_requirement_ids=linked_reqs,
                linked_provision_ids=linked_provs,
                linked_schedule_entry_ids=linked_scheds,
                linked_table_ids=linked_tables,
                linked_amendment_ids=linked_amends,
                deduplicated=True,
                deduplication_notes=[
                    f"Merged {len(instances)} retrieval paths: {', '.join(m.value for m in all_methods)}"
                ],
                ranking_tier=min_tier,
                title=best.title,
                commodity_text=best.commodity_text,
                quantity_text=best.quantity_text,
                temporal_status=best.temporal_status,
                effective_from=best.effective_from,
                effective_to=best.effective_to,
                metadata=best.metadata,
            )
            deduped.append(merged)

        return deduped

