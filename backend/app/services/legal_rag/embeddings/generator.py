"""High-level embedding generation and persistence orchestrator (Phase 4B).

Coordinates:
- Extracting normalized statutory entities from legal corpus
- Building deterministic, provenance-preserving embedding texts
- Computing text hashes for idempotency and change detection
- Safe chunking and batching via EmbeddingClient
- Idempotent persistence via EmbeddingStore
- Exact count reporting across all 5 legal entity types
"""

from __future__ import annotations

import logging
import time
from typing import Any, Mapping, Sequence
from uuid import uuid4

from backend.app.services.legal_rag.embeddings.client import (
    EmbeddingClient,
    EmbeddingGenerationError,
)
from backend.app.services.legal_rag.embeddings.models import (
    EmbeddingBatchResult,
    EntityEmbeddingRecord,
)
from backend.app.services.legal_rag.embeddings.store import EmbeddingStore
from backend.app.services.legal_rag.embeddings.text_builder import (
    build_amendment_embedding_text,
    build_provision_embedding_text,
    build_requirement_embedding_text,
    build_schedule_entry_embedding_text,
    build_table_embedding_text,
    compute_embedding_text_hash,
)
from backend.app.services.legal_rag.models import LegalEntityType

logger = logging.getLogger(__name__)


class LegalEmbeddingGenerator:
    """Orchestrates embedding generation across the normalized legal corpus."""

    def __init__(
        self,
        client: EmbeddingClient,
        store: EmbeddingStore,
        text_version: str = "v1",
        batch_size: int = 20,
        inter_batch_delay: float = 4.0,
    ) -> None:
        self.client = client
        self.store = store
        self.text_version = text_version
        self.batch_size = batch_size
        self.inter_batch_delay = inter_batch_delay

    def generate_all(
        self,
        requirements: Sequence[Any] = (),
        provisions: Sequence[Any] = (),
        schedule_entries: Sequence[Any] = (),
        tables: Sequence[Any] = (),
        amendments: Sequence[Any] = (),
        skip_existing_hashes: bool = True,
    ) -> EmbeddingBatchResult:
        """Generate and persist embeddings for all provided legal corpus entities."""
        provisions_by_id = {
            getattr(p, "id", p.get("id") if isinstance(p, dict) else None): p
            for p in provisions
        }

        items_to_embed: list[dict[str, Any]] = []

        # 1. Requirements
        for req in requirements:
            p_id = getattr(req, "provision_id", req.get("provision_id") if isinstance(req, dict) else None)
            prov = provisions_by_id.get(p_id)
            text = build_requirement_embedding_text(req, provision=prov)
            items_to_embed.append({
                "entity_type": LegalEntityType.REQUIREMENT,
                "entity_id": str(getattr(req, "id", req.get("id"))),
                "source_identifier": str(getattr(req, "source_identifier", req.get("source_identifier"))),
                "text": text,
                "metadata": {"provision_id": p_id},
            })

        # 2. Provisions
        for prov in provisions:
            text = build_provision_embedding_text(prov)
            items_to_embed.append({
                "entity_type": LegalEntityType.PROVISION,
                "entity_id": str(getattr(prov, "id", prov.get("id"))),
                "source_identifier": str(getattr(prov, "source_identifier", prov.get("source_identifier", f"provision_{getattr(prov, 'id', prov.get('id'))}"))),
                "text": text,
                "metadata": {"rule_number": getattr(prov, "rule_number", prov.get("rule_number"))},
            })

        # 3. Schedule Entries
        for entry in schedule_entries:
            text = build_schedule_entry_embedding_text(entry)
            items_to_embed.append({
                "entity_type": LegalEntityType.SCHEDULE_ENTRY,
                "entity_id": str(getattr(entry, "id", entry.get("id"))),
                "source_identifier": str(getattr(entry, "source_identifier", entry.get("source_identifier"))),
                "text": text,
                "metadata": {"entry_key": getattr(entry, "entry_key", entry.get("entry_key"))},
            })

        # 4. Tables
        for tbl in tables:
            text = build_table_embedding_text(tbl)
            items_to_embed.append({
                "entity_type": LegalEntityType.TABLE,
                "entity_id": str(getattr(tbl, "id", tbl.get("id"))),
                "source_identifier": str(getattr(tbl, "source_identifier", tbl.get("source_identifier"))),
                "text": text,
                "metadata": {"table_identifier": getattr(tbl, "table_identifier", tbl.get("table_identifier"))},
            })

        # 5. Amendments
        for amd in amendments:
            aff_p_id = getattr(amd, "affected_provision_id", amd.get("affected_provision_id") if isinstance(amd, dict) else None)
            prov = provisions_by_id.get(aff_p_id)
            text = build_amendment_embedding_text(amd, affected_prov=prov)
            items_to_embed.append({
                "entity_type": LegalEntityType.AMENDMENT,
                "entity_id": str(getattr(amd, "id", amd.get("id"))),
                "source_identifier": str(getattr(amd, "source_identifier", amd.get("source_identifier"))),
                "text": text,
                "metadata": {"affected_provision_id": aff_p_id},
            })

        return self._process_items(items_to_embed, skip_existing_hashes=skip_existing_hashes)

    def _process_items(
        self,
        items: list[dict[str, Any]],
        skip_existing_hashes: bool = True,
    ) -> EmbeddingBatchResult:
        result = EmbeddingBatchResult(total_processed=len(items))
        counts: dict[str, int] = {
            LegalEntityType.REQUIREMENT.value: 0,
            LegalEntityType.PROVISION.value: 0,
            LegalEntityType.SCHEDULE_ENTRY.value: 0,
            LegalEntityType.TABLE.value: 0,
            LegalEntityType.AMENDMENT.value: 0,
        }

        # Filter items if skipping existing
        existing_hashes: dict[tuple[str, str], str] | None = None
        if skip_existing_hashes and hasattr(self.store, "get_existing_hashes"):
            existing_hashes = self.store.get_existing_hashes(
                model=self.client.model,
                version=self.text_version,
            )

        pending: list[dict[str, Any]] = []
        for item in items:
            text_hash = compute_embedding_text_hash(item["text"])
            item["hash"] = text_hash

            if skip_existing_hashes:
                etype_str = item["entity_type"].value if isinstance(item["entity_type"], LegalEntityType) else str(item["entity_type"])
                eid_str = str(item["entity_id"])

                if existing_hashes is not None:
                    stored_hash = existing_hashes.get((etype_str, eid_str))
                    if stored_hash == text_hash:
                        result.successful += 1
                        etype_key = item["entity_type"].value
                        counts[etype_key] = counts.get(etype_key, 0) + 1
                        continue
                else:
                    existing = self.store.get_embedding(
                        entity_type=item["entity_type"],
                        entity_id=item["entity_id"],
                        model=self.client.model,
                        version=self.text_version,
                    )
                    if existing and existing.embedding_text_hash == text_hash:
                        result.successful += 1
                        result.records.append(existing)
                        etype_key = item["entity_type"].value
                        counts[etype_key] = counts.get(etype_key, 0) + 1
                        continue

            pending.append(item)


        if not pending:
            result.entity_counts = counts
            return result

        # Batch embed pending items
        for i in range(0, len(pending), self.batch_size):
            chunk = pending[i : i + self.batch_size]
            texts = [c["text"] for c in chunk]
            try:
                embeddings = self.client.embed_batch(
                    texts,
                    task_type="RETRIEVAL_DOCUMENT",
                    batch_size=len(texts),
                )
                records_to_save: list[EntityEmbeddingRecord] = []
                for item, vector in zip(chunk, embeddings):
                    record = EntityEmbeddingRecord(
                        id=str(uuid4()),
                        entity_type=item["entity_type"],
                        entity_id=item["entity_id"],
                        source_identifier=item["source_identifier"],
                        provider=self.client.provider,
                        model=self.client.model,
                        dimension=self.client.dimension,
                        embedding_text_version=self.text_version,
                        embedding_text=item["text"],
                        embedding_text_hash=item["hash"],
                        embedding=vector,
                        metadata=item.get("metadata", {}),
                    )
                    records_to_save.append(record)
                    result.successful += 1
                    result.records.append(record)
                    etype_key = item["entity_type"].value
                    counts[etype_key] = counts.get(etype_key, 0) + 1

                # Persist to store
                self.store.save_embeddings(records_to_save)
                total_batches = (len(pending) + self.batch_size - 1) // self.batch_size
                current_batch = i // self.batch_size + 1
                print(f"  [Batch {current_batch}/{total_batches}] Successfully embedded and persisted {len(chunk)} items ({result.successful}/{len(items)} total).")
                if self.inter_batch_delay > 0:
                    time.sleep(self.inter_batch_delay)

            except EmbeddingGenerationError as exc:
                result.failed += len(chunk)
                err_msg = f"Batch embedding failed for items {i} to {i + len(chunk)}: {exc}"
                result.errors.append(err_msg)
                logger.error(err_msg)


        result.entity_counts = counts
        return result
