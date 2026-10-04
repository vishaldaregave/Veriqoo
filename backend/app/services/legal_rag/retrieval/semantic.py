"""Semantic vector search resolver using legal_corpus_embeddings (Phase 4C).

Reuses Phase 4B EmbeddingClient abstraction:
- Converts query text to 3072-dimensional embedding using EmbeddingClient.
- Queries public.legal_corpus_embeddings via repository vector search RPC.
- Converts matched embedding records into complete, provenance-preserving legal entities.
- Gracefully handles empty embedding corpus without claiming false completeness.
"""

from __future__ import annotations

from typing import Any

from backend.app.services.legal_rag.embeddings.client import EmbeddingClient
from backend.app.services.legal_rag.models import (
    LegalEntityType,
    LegalProvenance,
    RetrievalMethod,
    TemporalStatus,
)
from backend.app.services.legal_rag.retrieval.models import (
    RetrievalRequest,
    RetrievedEntityContext,
)
from backend.app.services.legal_rag.retrieval.repository import LegalCorpusRepository


class SemanticSearchResolver:
    """Performs semantic similarity search against legal_corpus_embeddings."""

    def __init__(
        self,
        repository: LegalCorpusRepository,
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        self.repository = repository
        self.embedding_client = embedding_client

    def search(self, request: RetrievalRequest) -> list[RetrievedEntityContext]:
        """Execute semantic search against legal corpus embeddings."""
        if not request.query_text or not request.query_text.strip():
            return []

        if not self.embedding_client:
            return []

        # Generate query embedding with task_type RETRIEVAL_QUERY
        try:
            query_vector = self.embedding_client.embed_query(request.query_text.strip())
        except Exception:
            return []

        # Optional entity type filter
        filter_type_str = None
        if request.entity_types and len(request.entity_types) == 1:
            filter_type_str = request.entity_types[0].value

        matches = self.repository.search_embeddings(
            query_embedding=query_vector,
            limit=request.limit,
            filter_entity_type=filter_type_str,
        )

        results: list[RetrievedEntityContext] = []
        for m in matches:
            sim = float(m.get("similarity", 0.0))
            if sim < request.min_similarity_threshold:
                continue

            etype_str = m.get("entity_type")
            eid = str(m.get("entity_id"))

            ctx = self._resolve_entity_from_match(etype_str, eid, sim, m)
            if ctx:
                results.append(ctx)

        return results

    def _resolve_entity_from_match(
        self,
        entity_type_str: str,
        entity_id: str,
        similarity: float,
        embedding_match: dict[str, Any],
    ) -> RetrievedEntityContext | None:
        """Resolve full authoritative entity from repository to attach provenance."""
        try:
            etype = LegalEntityType(entity_type_str)
        except ValueError:
            return None

        if etype == LegalEntityType.REQUIREMENT:
            req = self.repository.get_requirement(entity_id)
            if not req:
                return None
            norm = req.get("normalized_requirement") or ""
            text = req.get("requirement_text") or norm
            src_id = str(req.get("source_identifier") or f"requirement_{entity_id}")
            src_quote = req.get("source_quote") or ""
            src_ref = req.get("source_reference") or {}
            prov_id = req.get("provision_id")
            subject = req.get("subject") or ""

            prov = LegalProvenance(
                source_identifier=src_id,
                document_id=src_ref.get("document_id", 1),
                provision_id=int(prov_id) if prov_id is not None else None,
                source_quote=src_quote,
                source_reference=src_ref,
            )
            return RetrievedEntityContext(
                entity_type=LegalEntityType.REQUIREMENT,
                entity_id=entity_id,
                source_identifier=src_id,
                source_reference=src_ref,
                legal_text=text,
                source_quote=src_quote,
                similarity_score=similarity,
                retrieval_method=RetrievalMethod.SEMANTIC_VECTOR,
                ranking_tier=3,
                title=f"Requirement: {subject}" if subject else f"Requirement {entity_id}",
                provenance=prov,
                linked_provision_ids=[int(prov_id)] if prov_id is not None else [],
                metadata={"subject": subject, "normalized_requirement": norm},
            )

        elif etype == LegalEntityType.PROVISION:
            try:
                pid = int(entity_id)
            except ValueError:
                return None
            prov_data = self.repository.get_provision(pid)
            if not prov_data:
                return None
            content = prov_data.get("content") or ""
            raw = prov_data.get("raw_content") or content
            src_id = str(prov_data.get("source_identifier") or f"provision_{pid}")
            rule_num = prov_data.get("rule_number")

            provenance = LegalProvenance(
                source_identifier=src_id,
                document_id=prov_data.get("document_id", 1),
                provision_id=pid,
                rule_number=rule_num,
                source_quote=raw,
            )
            return RetrievedEntityContext(
                entity_type=LegalEntityType.PROVISION,
                entity_id=str(pid),
                source_identifier=src_id,
                source_reference={"rule_number": rule_num},
                legal_text=content or raw,
                source_quote=raw,
                similarity_score=similarity,
                retrieval_method=RetrievalMethod.SEMANTIC_VECTOR,
                ranking_tier=3,
                title=f"Rule {rule_num}" if rule_num else f"Provision {pid}",
                provenance=provenance,
            )

        elif etype == LegalEntityType.SCHEDULE_ENTRY:
            entry = self.repository.get_schedule_entry(entity_id)
            if not entry:
                return None
            raw = entry.get("raw_content") or ""
            norm = entry.get("normalized_content") or raw
            commodity = entry.get("commodity_text")
            quantity = entry.get("quantity_text")

            provenance = LegalProvenance(
                source_identifier=str(entry.get("source_identifier") or f"schedule_entry_{entity_id}"),
                document_id=1,
                schedule_id=str(entry.get("schedule_id", "")),
                schedule_entry_id=entity_id,
                source_quote=raw or norm,
            )
            return RetrievedEntityContext(
                entity_type=LegalEntityType.SCHEDULE_ENTRY,
                entity_id=entity_id,
                source_identifier=str(entry.get("source_identifier") or f"schedule_entry_{entity_id}"),
                source_reference={"schedule_id": entry.get("schedule_id")},
                legal_text=raw or norm,
                source_quote=raw or norm,
                similarity_score=similarity,
                retrieval_method=RetrievalMethod.SEMANTIC_VECTOR,
                ranking_tier=3,
                title=f"Schedule Entry: {commodity}" if commodity else f"Schedule Entry {entity_id}",
                commodity_text=commodity,
                quantity_text=quantity,
                provenance=provenance,
            )

        elif etype == LegalEntityType.TABLE:
            tbl = self.repository.get_table(entity_id)
            if not tbl:
                return None
            raw = tbl.get("raw_content") or ""
            norm = tbl.get("normalized_content") or raw
            ident = tbl.get("table_identifier") or entity_id

            provenance = LegalProvenance(
                source_identifier=str(tbl.get("source_identifier") or f"table_{entity_id}"),
                document_id=1,
                table_id=entity_id,
                source_quote=raw or norm,
            )
            return RetrievedEntityContext(
                entity_type=LegalEntityType.TABLE,
                entity_id=entity_id,
                source_identifier=str(tbl.get("source_identifier") or f"table_{entity_id}"),
                source_reference={"table_identifier": ident},
                legal_text=raw or norm,
                source_quote=raw or norm,
                similarity_score=similarity,
                retrieval_method=RetrievalMethod.SEMANTIC_VECTOR,
                ranking_tier=3,
                title=tbl.get("title") or f"Table: {ident}",
                provenance=provenance,
            )

        elif etype == LegalEntityType.AMENDMENT:
            amd = self.repository.get_amendment(entity_id)
            if not amd:
                return None
            raw = amd.get("raw_content") or ""
            norm = amd.get("normalized_content") or raw
            ident = amd.get("amendment_identifier") or entity_id

            provenance = LegalProvenance(
                source_identifier=str(amd.get("source_identifier") or f"amendment_{entity_id}"),
                document_id=1,
                amendment_id=entity_id,
                source_quote=raw or norm,
            )
            return RetrievedEntityContext(
                entity_type=LegalEntityType.AMENDMENT,
                entity_id=entity_id,
                source_identifier=str(amd.get("source_identifier") or f"amendment_{entity_id}"),
                source_reference={"amendment_identifier": ident},
                legal_text=raw or norm,
                source_quote=raw or norm,
                similarity_score=similarity,
                retrieval_method=RetrievalMethod.SEMANTIC_VECTOR,
                ranking_tier=3,
                title=f"Amendment: {ident}",
                provenance=provenance,
            )

        return None

