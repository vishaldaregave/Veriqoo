"""Multiple-image batch ingestion and duplicate tracking for Phase 5A."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.evidence.models import (
    BatchItem,
    ImageArtifact,
    ImageBatch,
    IngestionConfig,
)


class ImageBatchIngestionService:
    """Service for batch ingestion of package photographs with deterministic duplicate tracking."""

    def __init__(
        self,
        ingestion_service: ImageIngestionService | None = None,
        config: IngestionConfig | None = None,
    ) -> None:
        self.ingestion_service = ingestion_service or ImageIngestionService(config=config)

    def ingest_artifacts(self, artifacts: Sequence[ImageArtifact]) -> ImageBatch:
        """Construct an ImageBatch from already-ingested artifacts preserving order and tracking duplicates."""
        seen_hashes: dict[str, tuple[int, str]] = {}  # normalized_hash -> (first_index, image_id)
        batch_items: list[BatchItem] = []

        for idx, artifact in enumerate(artifacts):
            norm_hash = artifact.normalized_hash
            if norm_hash in seen_hashes:
                orig_idx, orig_id = seen_hashes[norm_hash]
                item = BatchItem(
                    index=idx,
                    artifact=artifact,
                    is_duplicate=True,
                    duplicate_of_index=orig_idx,
                    duplicate_of_id=orig_id,
                )
            else:
                seen_hashes[norm_hash] = (idx, artifact.image_id)
                item = BatchItem(
                    index=idx,
                    artifact=artifact,
                    is_duplicate=False,
                    duplicate_of_index=None,
                    duplicate_of_id=None,
                )
            batch_items.append(item)

        return ImageBatch(items=batch_items)

    def ingest_files(
        self,
        file_paths: Sequence[str | Path],
        base_metadata: dict[str, Any] | None = None,
    ) -> ImageBatch:
        """Ingest a sequence of image files in exact order and return an ImageBatch."""
        artifacts: list[ImageArtifact] = []
        for idx, path in enumerate(file_paths):
            meta = dict(base_metadata or {})
            meta["batch_index"] = idx
            artifact = self.ingestion_service.ingest_file(path, metadata=meta)
            artifacts.append(artifact)

        return self.ingest_artifacts(artifacts)

    def ingest_byte_list(
        self,
        byte_items: Sequence[tuple[bytes, str | None]],
        base_metadata: dict[str, Any] | None = None,
    ) -> ImageBatch:
        """Ingest a list of (raw_bytes, source_name) tuples in exact order and return an ImageBatch."""
        artifacts: list[ImageArtifact] = []
        for idx, (data, source_name) in enumerate(byte_items):
            meta = dict(base_metadata or {})
            meta["batch_index"] = idx
            artifact = self.ingestion_service.ingest_bytes(data, source_name=source_name, metadata=meta)
            artifacts.append(artifact)

        return self.ingest_artifacts(artifacts)

