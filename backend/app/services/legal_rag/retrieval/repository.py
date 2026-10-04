"""Repository layer for accessing authoritative legal corpus entities and embeddings (Phase 4C).

Provides:
- LegalCorpusRepository: Abstract base repository interface
- InMemoryLegalCorpusRepository: Fast, deterministic in-memory store for unit tests
- SupabaseLegalCorpusRepository: Remote PostgreSQL/PostgREST repository connecting to Supabase
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any, Sequence

import requests

from backend.app.services.legal_rag.models import LegalEntityType


class LegalCorpusRepository(ABC):
    """Abstract interface for accessing normalized legal corpus entities and vector embeddings."""

    @abstractmethod
    def get_requirement(self, requirement_id: str) -> dict[str, Any] | None:
        """Retrieve a legal requirement by ID."""
        raise NotImplementedError

    @abstractmethod
    def get_provision(self, provision_id: int) -> dict[str, Any] | None:
        """Retrieve a legal provision by ID."""
        raise NotImplementedError

    @abstractmethod
    def get_schedule_entry(self, entry_id: str) -> dict[str, Any] | None:
        """Retrieve a legal schedule entry by ID."""
        raise NotImplementedError

    @abstractmethod
    def get_table(self, table_id: str) -> dict[str, Any] | None:
        """Retrieve a legal table by ID."""
        raise NotImplementedError

    @abstractmethod
    def get_amendment(self, amendment_id: str) -> dict[str, Any] | None:
        """Retrieve a legal amendment by ID."""
        raise NotImplementedError

    @abstractmethod
    def get_requirements_by_provision(self, provision_id: int) -> list[dict[str, Any]]:
        """Retrieve requirements derived from a parent provision."""
        raise NotImplementedError

    @abstractmethod
    def get_schedule_entries_by_schedule(self, schedule_id: str) -> list[dict[str, Any]]:
        """Retrieve schedule entries belonging to a schedule."""
        raise NotImplementedError

    @abstractmethod
    def get_tables_by_provision(self, provision_id: int) -> list[dict[str, Any]]:
        """Retrieve tables linked to a provision."""
        raise NotImplementedError

    @abstractmethod
    def get_tables_by_schedule(self, schedule_id: str) -> list[dict[str, Any]]:
        """Retrieve tables linked to a schedule."""
        raise NotImplementedError

    @abstractmethod
    def get_amendments_by_provision(self, provision_id: int) -> list[dict[str, Any]]:
        """Retrieve amendments that affected a provision."""
        raise NotImplementedError

    @abstractmethod
    def search_embeddings(
        self,
        query_embedding: list[float],
        limit: int = 10,
        filter_entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search legal_corpus_embeddings by cosine similarity."""
        raise NotImplementedError

    @abstractmethod
    def count_embeddings(self, entity_type: str | None = None) -> int:
        """Count rows in legal_corpus_embeddings, optionally by entity_type."""
        raise NotImplementedError

    @abstractmethod
    def count_legal_entities(self, entity_type: str) -> int:
        """Count authoritative legal corpus entities by entity_type."""
        raise NotImplementedError


class InMemoryLegalCorpusRepository(LegalCorpusRepository):
    """Deterministic in-memory repository for unit testing and offline retrieval verification."""

    def __init__(self) -> None:
        self.requirements: dict[str, dict[str, Any]] = {}
        self.provisions: dict[int, dict[str, Any]] = {}
        self.schedule_entries: dict[str, dict[str, Any]] = {}
        self.tables: dict[str, dict[str, Any]] = {}
        self.amendments: dict[str, dict[str, Any]] = {}
        self.embeddings: list[dict[str, Any]] = []

    def register_requirement(self, req: dict[str, Any]) -> None:
        self.requirements[str(req["id"])] = req

    def register_provision(self, prov: dict[str, Any]) -> None:
        self.provisions[int(prov["id"])] = prov

    def register_schedule_entry(self, entry: dict[str, Any]) -> None:
        self.schedule_entries[str(entry["id"])] = entry

    def register_table(self, tbl: dict[str, Any]) -> None:
        self.tables[str(tbl["id"])] = tbl

    def register_amendment(self, amd: dict[str, Any]) -> None:
        self.amendments[str(amd["id"])] = amd

    def register_embedding(self, emb: dict[str, Any]) -> None:
        self.embeddings.append(emb)

    def get_requirement(self, requirement_id: str) -> dict[str, Any] | None:
        return self.requirements.get(str(requirement_id))

    def get_provision(self, provision_id: int) -> dict[str, Any] | None:
        return self.provisions.get(int(provision_id))

    def get_schedule_entry(self, entry_id: str) -> dict[str, Any] | None:
        return self.schedule_entries.get(str(entry_id))

    def get_table(self, table_id: str) -> dict[str, Any] | None:
        return self.tables.get(str(table_id))

    def get_amendment(self, amendment_id: str) -> dict[str, Any] | None:
        return self.amendments.get(str(amendment_id))

    def get_requirements_by_provision(self, provision_id: int) -> list[dict[str, Any]]:
        return [r for r in self.requirements.values() if r.get("provision_id") == provision_id]

    def get_schedule_entries_by_schedule(self, schedule_id: str) -> list[dict[str, Any]]:
        return [e for e in self.schedule_entries.values() if str(e.get("schedule_id")) == str(schedule_id)]

    def get_tables_by_provision(self, provision_id: int) -> list[dict[str, Any]]:
        return [t for t in self.tables.values() if t.get("provision_id") == provision_id]

    def get_tables_by_schedule(self, schedule_id: str) -> list[dict[str, Any]]:
        return [t for t in self.tables.values() if str(t.get("schedule_id")) == str(schedule_id)]

    def get_amendments_by_provision(self, provision_id: int) -> list[dict[str, Any]]:
        return [a for a in self.amendments.values() if a.get("affected_provision_id") == provision_id]

    def search_embeddings(
        self,
        query_embedding: list[float],
        limit: int = 10,
        filter_entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.embeddings or not query_embedding:
            return []

        def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
            dot = sum(a * b for a, b in zip(v1, v2))
            norm1 = math.sqrt(sum(a * a for a in v1))
            norm2 = math.sqrt(sum(b * b for b in v2))
            if norm1 == 0.0 or norm2 == 0.0:
                return 0.0
            return dot / (norm1 * norm2)

        candidates = []
        for emb in self.embeddings:
            if filter_entity_type and emb.get("entity_type") != filter_entity_type:
                continue
            if "mock_similarity" in emb:
                sim = float(emb["mock_similarity"])
            elif "similarity" in emb and "embedding" not in emb:
                sim = float(emb["similarity"])
            elif "embedding" in emb:
                sim = cosine_similarity(query_embedding, emb["embedding"])
            else:
                sim = float(emb.get("similarity", 0.0))
            candidates.append({**emb, "similarity": sim})

        # Deterministic sort: similarity DESC, entity_type ASC, entity_id ASC
        candidates.sort(
            key=lambda x: (
                -x["similarity"],
                x.get("entity_type", ""),
                str(x.get("entity_id", "")),
            )
        )
        return candidates[: max(limit, 1)]

    def count_embeddings(self, entity_type: str | None = None) -> int:
        if entity_type is None:
            return len(self.embeddings)
        return sum(1 for e in self.embeddings if e.get("entity_type") == entity_type)

    def count_legal_entities(self, entity_type: str) -> int:
        if entity_type == "requirement":
            return len(self.requirements)
        elif entity_type == "provision":
            return len(self.provisions)
        elif entity_type == "schedule_entry":
            return len(self.schedule_entries)
        elif entity_type == "table":
            return len(self.tables)
        elif entity_type == "amendment":
            return len(self.amendments)
        return 0


class SupabaseLegalCorpusRepository(LegalCorpusRepository):
    """PostgREST / Supabase repository targeting authoritative legal tables and vector search RPC."""

    def __init__(self, url: str, key: str) -> None:
        self.url = url.rstrip("/")
        self.key = key
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def _get(self, endpoint: str, params: list[tuple[str, str]]) -> list[dict[str, Any]]:
        resp = requests.get(f"{self.url}/rest/v1/{endpoint}", headers=self.headers, params=params, timeout=30)
        if not resp.ok:
            return []
        data = resp.json()
        return data if isinstance(data, list) else []

    def get_requirement(self, requirement_id: str) -> dict[str, Any] | None:
        rows = self._get("legal_requirements", [("id", f"eq.{requirement_id}"), ("limit", "1")])
        return rows[0] if rows else None

    def get_provision(self, provision_id: int) -> dict[str, Any] | None:
        rows = self._get("legal_provisions", [("id", f"eq.{provision_id}"), ("limit", "1")])
        return rows[0] if rows else None

    def get_schedule_entry(self, entry_id: str) -> dict[str, Any] | None:
        rows = self._get("legal_schedule_entries", [("id", f"eq.{entry_id}"), ("limit", "1")])
        return rows[0] if rows else None

    def get_table(self, table_id: str) -> dict[str, Any] | None:
        rows = self._get("legal_tables", [("id", f"eq.{table_id}"), ("limit", "1")])
        return rows[0] if rows else None

    def get_amendment(self, amendment_id: str) -> dict[str, Any] | None:
        rows = self._get("legal_amendments", [("id", f"eq.{amendment_id}"), ("limit", "1")])
        return rows[0] if rows else None

    def get_requirements_by_provision(self, provision_id: int) -> list[dict[str, Any]]:
        return self._get("legal_requirements", [("provision_id", f"eq.{provision_id}")])

    def get_schedule_entries_by_schedule(self, schedule_id: str) -> list[dict[str, Any]]:
        return self._get("legal_schedule_entries", [("schedule_id", f"eq.{schedule_id}")])

    def get_tables_by_provision(self, provision_id: int) -> list[dict[str, Any]]:
        return self._get("legal_tables", [("provision_id", f"eq.{provision_id}")])

    def get_tables_by_schedule(self, schedule_id: str) -> list[dict[str, Any]]:
        return self._get("legal_tables", [("schedule_id", f"eq.{schedule_id}")])

    def get_amendments_by_provision(self, provision_id: int) -> list[dict[str, Any]]:
        return self._get("legal_amendments", [("affected_provision_id", f"eq.{provision_id}")])

    def search_embeddings(
        self,
        query_embedding: list[float],
        limit: int = 10,
        filter_entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Call public.match_legal_corpus_embeddings RPC."""
        rpc_url = f"{self.url}/rest/v1/rpc/match_legal_corpus_embeddings"
        payload = {
            "query_embedding": query_embedding,
            "match_count": limit,
            "filter_entity_type": filter_entity_type,
        }
        resp = requests.post(rpc_url, headers=self.headers, json=payload, timeout=30)
        if not resp.ok:
            return []
        data = resp.json()
        return data if isinstance(data, list) else []

    def count_embeddings(self, entity_type: str | None = None) -> int:
        headers = {**self.headers, "Range": "0-0", "Prefer": "count=exact"}
        params = [("select", "id")]
        if entity_type:
            params.append(("entity_type", f"eq.{entity_type}"))
        resp = requests.get(f"{self.url}/rest/v1/legal_corpus_embeddings", headers=headers, params=params, timeout=30)
        if not resp.ok:
            return 0
        content_range = resp.headers.get("content-range", "")
        if "/" in content_range:
            try:
                return int(content_range.split("/")[-1])
            except ValueError:
                return 0
        return 0

    def count_legal_entities(self, entity_type: str) -> int:
        table_map = {
            "requirement": "legal_requirements",
            "provision": "legal_provisions",
            "schedule_entry": "legal_schedule_entries",
            "table": "legal_tables",
            "amendment": "legal_amendments",
            "document": "legal_documents",
            "schedule": "legal_schedules",
        }
        tbl = table_map.get(entity_type)
        if not tbl:
            return 0
        headers = {**self.headers, "Range": "0-0", "Prefer": "count=exact"}
        resp = requests.get(f"{self.url}/rest/v1/{tbl}?select=id", headers=headers, timeout=30)
        if not resp.ok:
            return 0
        content_range = resp.headers.get("content-range", "")
        if "/" in content_range:
            try:
                return int(content_range.split("/")[-1])
            except ValueError:
                return 0
        return 0

