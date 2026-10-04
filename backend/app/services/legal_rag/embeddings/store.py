"""Vector embedding storage interfaces and implementations (Phase 4B).

Provides:
- EmbeddingStore (abstract interface)
- InMemoryEmbeddingStore (in-memory storage for unit tests and local execution)
- SupabaseEmbeddingStore (PostgREST / pgvector storage for public.legal_corpus_embeddings)
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Sequence

import requests

from backend.app.services.legal_rag.embeddings.models import EntityEmbeddingRecord
from backend.app.services.legal_rag.models import LegalEntityType

TABLE_NAME = "legal_corpus_embeddings"


class EmbeddingStore(ABC):
    """Abstract storage interface for legal corpus embeddings."""

    @abstractmethod
    def save_embeddings(self, records: Sequence[EntityEmbeddingRecord]) -> int:
        """Persist a batch of embedding records idempotently. Returns count saved."""
        raise NotImplementedError

    @abstractmethod
    def get_embedding(
        self,
        entity_type: LegalEntityType | str,
        entity_id: str,
        model: str = "gemini-embedding-001",
        version: str = "v1",
    ) -> EntityEmbeddingRecord | None:
        """Retrieve a specific embedding record by entity locator and model version."""
        raise NotImplementedError

    @abstractmethod
    def count_embeddings(
        self,
        entity_type: LegalEntityType | str | None = None,
        model: str | None = None,
    ) -> int:
        """Count persistent embeddings, optionally filtered by entity type or model."""
        raise NotImplementedError

    def get_existing_hashes(
        self,
        model: str = "gemini-embedding-001",
        version: str = "v1",
    ) -> dict[tuple[str, str], str]:
        """Fetch mapping of (entity_type, entity_id) -> embedding_text_hash for bulk idempotency check."""
        return {}


class InMemoryEmbeddingStore(EmbeddingStore):
    """Fast, deterministic in-memory store for unit testing and offline runs."""

    def __init__(self) -> None:
        # Key: (entity_type_str, entity_id, model, version)
        self._records: dict[tuple[str, str, str, str], EntityEmbeddingRecord] = {}

    def get_existing_hashes(
        self,
        model: str = "gemini-embedding-001",
        version: str = "v1",
    ) -> dict[tuple[str, str], str]:
        hashes = {}
        for (etype_str, eid, mdl, ver), rec in self._records.items():
            if mdl == model and ver == version:
                hashes[(etype_str, eid)] = rec.embedding_text_hash
        return hashes


    def save_embeddings(self, records: Sequence[EntityEmbeddingRecord]) -> int:
        count = 0
        for rec in records:
            etype_str = rec.entity_type.value if isinstance(rec.entity_type, LegalEntityType) else str(rec.entity_type)
            key = (etype_str, str(rec.entity_id), rec.model, rec.embedding_text_version)
            self._records[key] = rec
            count += 1
        return count

    def get_embedding(
        self,
        entity_type: LegalEntityType | str,
        entity_id: str,
        model: str = "gemini-embedding-001",
        version: str = "v1",
    ) -> EntityEmbeddingRecord | None:
        etype_str = entity_type.value if isinstance(entity_type, LegalEntityType) else str(entity_type)
        key = (etype_str, str(entity_id), model, version)
        return self._records.get(key)

    def count_embeddings(
        self,
        entity_type: LegalEntityType | str | None = None,
        model: str | None = None,
    ) -> int:
        count = 0
        etype_filter = (
            entity_type.value if isinstance(entity_type, LegalEntityType) else str(entity_type)
            if entity_type is not None
            else None
        )
        for (etype, _eid, mdl, _ver) in self._records.keys():
            if etype_filter is not None and etype != etype_filter:
                continue
            if model is not None and mdl != model:
                continue
            count += 1
        return count


class SupabaseEmbeddingStore(EmbeddingStore):
    """Supabase / PostgREST persistent store targeting public.legal_corpus_embeddings."""

    def __init__(self, url: str, key: str) -> None:
        self.url = url.rstrip("/")
        self.key = key
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def save_embeddings(self, records: Sequence[EntityEmbeddingRecord]) -> int:
        if not records:
            return 0

        endpoint = f"{self.url}/rest/v1/{TABLE_NAME}?on_conflict=entity_type,entity_id,model,embedding_text_version"
        headers = {**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"}

        payload = []
        for r in records:
            etype_str = r.entity_type.value if isinstance(r.entity_type, LegalEntityType) else str(r.entity_type)
            payload.append({
                "id": str(r.id),
                "entity_type": etype_str,
                "entity_id": str(r.entity_id),
                "source_identifier": r.source_identifier,
                "provider": r.provider,
                "model": r.model,
                "dimension": r.dimension,
                "embedding_text_version": r.embedding_text_version,
                "embedding_text": r.embedding_text,
                "embedding_text_hash": r.embedding_text_hash,
                "embedding": r.embedding,
                "metadata": r.metadata,
            })

        # Send in batches of 50 to avoid request size limits
        total_saved = 0
        batch_size = 50
        for i in range(0, len(payload), batch_size):
            chunk = payload[i : i + batch_size]
            resp = requests.post(endpoint, headers=headers, json=chunk, timeout=120)
            if not resp.ok:
                raise RuntimeError(
                    f"Supabase embedding persistence failed ({resp.status_code}): {resp.text}"
                )
            data = resp.json()
            total_saved += len(data) if isinstance(data, list) else len(chunk)

        return total_saved

    def get_embedding(
        self,
        entity_type: LegalEntityType | str,
        entity_id: str,
        model: str = "gemini-embedding-001",
        version: str = "v1",
    ) -> EntityEmbeddingRecord | None:
        etype_str = entity_type.value if isinstance(entity_type, LegalEntityType) else str(entity_type)
        endpoint = f"{self.url}/rest/v1/{TABLE_NAME}"
        params = [
            ("entity_type", f"eq.{etype_str}"),
            ("entity_id", f"eq.{entity_id}"),
            ("model", f"eq.{model}"),
            ("embedding_text_version", f"eq.{version}"),
            ("limit", "1"),
        ]
        resp = requests.get(endpoint, headers=self.headers, params=params, timeout=30)
        if not resp.ok:
            return None
        data = resp.json()
        if not data or not isinstance(data, list):
            return None
        row = data[0]
        return EntityEmbeddingRecord(
            id=row["id"],
            entity_type=LegalEntityType(row["entity_type"]),
            entity_id=row["entity_id"],
            source_identifier=row["source_identifier"],
            provider=row.get("provider", "gemini"),
            model=row.get("model", model),
            dimension=row.get("dimension", 3072),
            embedding_text_version=row.get("embedding_text_version", version),
            embedding_text=row.get("embedding_text", ""),
            embedding_text_hash=row.get("embedding_text_hash", ""),
            embedding=row.get("embedding", []),
            metadata=row.get("metadata", {}),
        )

    def count_embeddings(
        self,
        entity_type: LegalEntityType | str | None = None,
        model: str | None = None,
    ) -> int:
        endpoint = f"{self.url}/rest/v1/{TABLE_NAME}"
        headers = {**self.headers, "Range": "0-0", "Prefer": "count=exact"}
        params = [("select", "id")]
        if entity_type is not None:
            etype_str = entity_type.value if isinstance(entity_type, LegalEntityType) else str(entity_type)
            params.append(("entity_type", f"eq.{etype_str}"))
        if model is not None:
            params.append(("model", f"eq.{model}"))

        resp = requests.get(endpoint, headers=headers, params=params, timeout=30)
        if not resp.ok:
            return 0
        content_range = resp.headers.get("content-range", "")
        if "/" in content_range:
            try:
                return int(content_range.split("/")[-1])
            except ValueError:
                return 0
        return 0

    def get_existing_hashes(
        self,
        model: str = "gemini-embedding-001",
        version: str = "v1",
    ) -> dict[tuple[str, str], str]:
        endpoint = f"{self.url}/rest/v1/{TABLE_NAME}"
        params = [
            ("select", "entity_type,entity_id,embedding_text_hash"),
            ("model", f"eq.{model}"),
            ("embedding_text_version", f"eq.{version}"),
            ("limit", "5000"),
        ]
        resp = requests.get(endpoint, headers=self.headers, params=params, timeout=30)
        if not resp.ok:
            return {}
        data = resp.json()
        if not isinstance(data, list):
            return {}
        return {(str(r["entity_type"]), str(r["entity_id"])): str(r["embedding_text_hash"]) for r in data}

