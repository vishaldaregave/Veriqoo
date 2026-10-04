"""Data models for legal corpus embeddings (Phase 4B).

Defines types for:
- EntityEmbeddingRecord
- EmbeddingBatchResult
- EmbeddingProviderConfig
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from backend.app.services.legal_rag.models import LegalEntityType


@dataclass(frozen=True)
class EntityEmbeddingRecord:
    """A persistent vector embedding record for a normalized legal corpus entity."""

    id: str | UUID
    entity_type: LegalEntityType
    entity_id: str
    source_identifier: str
    provider: str = "gemini"
    model: str = "gemini-embedding-001"
    dimension: int = 3072
    embedding_text_version: str = "v1"
    embedding_text: str = ""
    embedding_text_hash: str = ""
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class EmbeddingBatchResult:
    """Summary result of a batch embedding generation operation."""

    total_processed: int = 0
    successful: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    records: list[EntityEmbeddingRecord] = field(default_factory=list)
    entity_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    """Configuration for embedding client operations."""

    provider: str = "gemini"
    model: str = "gemini-embedding-001"
    dimension: int = 3072
    batch_size: int = 20
    max_retries: int = 3
    base_retry_delay: float = 1.0
    text_version: str = "v1"
