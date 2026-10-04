"""Offline Inspection Bundle & Legal Snapshot Context for Phase U24-D.

Defines portable, strongly typed, and deterministically serializable contracts for:
1. OfflineInspectionBundle (carrying facts, observations, images, and candidates from device)
2. LegalSnapshotContext (approved in-memory legal data and rules bound to a deterministic SHA-256 snapshot)
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Sequence

from backend.app.services.offline_sync.models import (
    EvaluationMetadata,
    EvaluationMode,
    LegalSnapshotManifest,
)
from backend.app.services.offline_sync.snapshot import LegalSnapshotBuilder


def _canonical_json(data: Any) -> str:
    """Produce stable, deterministic JSON string."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class OfflineInspectionBundle:
    """Encapsulates the complete offline inspection payload produced on a mobile client.

    Guarantees:
    - Deterministic SHA-256 content hash across semantic content.
    - Zero cloud or auth secrets.
    - Strict isolation of image and OCR identifiers.
    - Preserves client legal_snapshot_id binding.
    """

    def __init__(
        self,
        inspection_id: str,
        legal_snapshot_id: str,
        bundle_id: str | None = None,
        schema_version: str = "1.0.0",
        inspection_facts: list[dict[str, Any]] | None = None,
        image_artifacts: list[dict[str, Any]] | None = None,
        ocr_results: list[dict[str, Any]] | None = None,
        evidence_candidates: list[dict[str, Any]] | None = None,
        target_requirements: list[str | dict[str, Any]] | None = None,
        evaluation_metadata: EvaluationMetadata | dict[str, Any] | None = None,
        sync_metadata: dict[str, Any] | None = None,
        created_at: str | None = None,
        content_hash: str | None = None,
    ) -> None:
        self.inspection_id = str(inspection_id).strip()
        self.legal_snapshot_id = str(legal_snapshot_id).strip()
        self.bundle_id = str(bundle_id).strip() if bundle_id else f"bundle-{self.inspection_id}"
        self.schema_version = str(schema_version)
        self.inspection_facts = list(inspection_facts or [])
        self.image_artifacts = list(image_artifacts or [])
        self.ocr_results = list(ocr_results or [])
        self.evidence_candidates = list(evidence_candidates or [])
        self.target_requirements = list(target_requirements or [])

        self.sync_metadata = dict(sync_metadata or {})
        self.created_at = str(created_at) if created_at else datetime.now(timezone.utc).isoformat()

        if isinstance(evaluation_metadata, EvaluationMetadata):
            self.evaluation_metadata = evaluation_metadata
        elif isinstance(evaluation_metadata, dict):
            self.evaluation_metadata = EvaluationMetadata.from_dict(evaluation_metadata)
        else:
            self.evaluation_metadata = EvaluationMetadata(
                evaluation_mode=EvaluationMode.OFFLINE_DETERMINISTIC,
                legal_snapshot_id=self.legal_snapshot_id,
                evaluated_at=self.created_at,
            )


        if content_hash:
            self.content_hash = str(content_hash).strip()
        else:
            self.content_hash = self.compute_content_hash()

    def compute_content_hash(self) -> str:
        """Compute deterministic SHA-256 hash over the semantic bundle content."""
        eval_meta_dict = {
            "evaluation_mode": self.evaluation_metadata.evaluation_mode.value,
            "revalidation_required": self.evaluation_metadata.revalidation_required,
            "engine_version": self.evaluation_metadata.engine_version,
            "legal_snapshot_id": self.evaluation_metadata.legal_snapshot_id,
        }
        semantic_dict = {
            "bundle_id": self.bundle_id,
            "inspection_id": self.inspection_id,
            "schema_version": self.schema_version,
            "legal_snapshot_id": self.legal_snapshot_id,
            "inspection_facts": self.inspection_facts,
            "image_artifacts": self.image_artifacts,
            "ocr_results": self.ocr_results,
            "evidence_candidates": self.evidence_candidates,
            "target_requirements": self.target_requirements,
            "evaluation_metadata": eval_meta_dict,
            "sync_metadata": self.sync_metadata,
        }
        canonical_str = _canonical_json(semantic_dict)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


    def validate_integrity(self) -> tuple[bool, str | None]:
        """Verify that the declared content hash matches computed content hash."""
        if not self.inspection_id:
            return False, "inspection_id cannot be empty."
        if not self.legal_snapshot_id:
            return False, "legal_snapshot_id cannot be empty."

        computed = self.compute_content_hash()
        if self.content_hash != computed:
            return False, f"Content hash mismatch: declared '{self.content_hash}' != computed '{computed}'"

        return True, None

    def to_dict(self) -> dict[str, Any]:
        """Serialize bundle to dictionary."""
        return {
            "bundle_id": self.bundle_id,
            "inspection_id": self.inspection_id,
            "schema_version": self.schema_version,
            "legal_snapshot_id": self.legal_snapshot_id,
            "inspection_facts": list(self.inspection_facts),
            "image_artifacts": list(self.image_artifacts),
            "ocr_results": list(self.ocr_results),
            "evidence_candidates": list(self.evidence_candidates),
            "target_requirements": list(self.target_requirements),
            "evaluation_metadata": self.evaluation_metadata.to_dict(),
            "sync_metadata": dict(self.sync_metadata),
            "created_at": self.created_at,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], verify_hash: bool = True) -> OfflineInspectionBundle:
        """Instantiate bundle from dictionary with optional integrity check."""
        bundle = cls(
            bundle_id=data.get("bundle_id"),
            inspection_id=data.get("inspection_id", ""),
            schema_version=data.get("schema_version", "1.0.0"),
            legal_snapshot_id=data.get("legal_snapshot_id", ""),
            inspection_facts=data.get("inspection_facts"),
            image_artifacts=data.get("image_artifacts"),
            ocr_results=data.get("ocr_results"),
            evidence_candidates=data.get("evidence_candidates"),
            target_requirements=data.get("target_requirements"),
            evaluation_metadata=data.get("evaluation_metadata"),
            sync_metadata=data.get("sync_metadata"),
            created_at=data.get("created_at"),
            content_hash=data.get("content_hash"),
        )
        if verify_hash:
            is_valid, err = bundle.validate_integrity()
            if not is_valid:
                raise ValueError(f"Invalid bundle integrity: {err}")
        return bundle

    def to_json(self) -> str:
        """Produce deterministic UTF-8 JSON representation."""
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str, verify_hash: bool = True) -> OfflineInspectionBundle:
        """Parse bundle from JSON string with validation."""
        data = json.loads(json_str)
        return cls.from_dict(data, verify_hash=verify_hash)


class LegalSnapshotContext:
    """In-memory collection of approved legal provisions, requirements, and rules for a snapshot."""

    def __init__(
        self,
        legal_snapshot_id: str,
        manifest: LegalSnapshotManifest | dict[str, Any] | None = None,
        documents: Sequence[Any] | None = None,
        provisions: Sequence[Any] | None = None,
        requirements: Sequence[Any] | None = None,
        schedules: Sequence[Any] | None = None,
        schedule_entries: Sequence[Any] | None = None,
        tables: Sequence[Any] | None = None,
        amendments: Sequence[Any] | None = None,
        applicability_rule_versions: Sequence[Any] | None = None,
        applicability_condition_groups: Sequence[Any] | None = None,
        applicability_conditions: Sequence[Any] | None = None,
        applicability_rules: Sequence[Any] | None = None,
        historical_snapshot_ids: Sequence[str] | set[str] | None = None,
        serialization_version: str = "1.0.0",
    ) -> None:
        self.legal_snapshot_id = str(legal_snapshot_id).strip()
        self.documents = list(documents or [])
        self.provisions = list(provisions or [])
        self.requirements = list(requirements or [])
        self.schedules = list(schedules or [])
        self.schedule_entries = list(schedule_entries or [])
        self.tables = list(tables or [])
        self.amendments = list(amendments or [])
        self.applicability_rule_versions = list(applicability_rule_versions or [])
        self.applicability_condition_groups = list(applicability_condition_groups or [])
        self.applicability_conditions = list(applicability_conditions or [])
        self.applicability_rules = list(applicability_rules or [])
        self.historical_snapshot_ids = list(historical_snapshot_ids or [])
        self.serialization_version = str(serialization_version)

        if isinstance(manifest, LegalSnapshotManifest):
            self.manifest = manifest
        elif isinstance(manifest, dict):
            self.manifest = LegalSnapshotManifest.from_dict(manifest)
        else:
            self.manifest = LegalSnapshotManifest(
                legal_snapshot_id=self.legal_snapshot_id,
                document_count=len(self.documents),
                provision_count=len(self.provisions),
                requirement_count=len(self.requirements),
                schedule_count=len(self.schedules),
                schedule_entry_count=len(self.schedule_entries),
                table_count=len(self.tables),
                amendment_count=len(self.amendments),
                approved_applicability_rule_version_count=len(self.applicability_rule_versions),
                approved_condition_group_count=len(self.applicability_condition_groups),
                approved_condition_count=len(self.applicability_conditions),
                serialization_version=self.serialization_version,
            )

    def verify_integrity(self) -> tuple[bool, str]:
        """Compute the deterministic snapshot identity from components and verify."""
        computed_id, _, _ = LegalSnapshotBuilder.build_snapshot(
            documents=self.documents,
            provisions=self.provisions,
            requirements=self.requirements,
            schedules=self.schedules,
            schedule_entries=self.schedule_entries,
            tables=self.tables,
            amendments=self.amendments,
            applicability_rule_versions=self.applicability_rule_versions,
            applicability_condition_groups=self.applicability_condition_groups,
            applicability_conditions=self.applicability_conditions,
            serialization_version=self.serialization_version,
        )
        is_valid = computed_id == self.legal_snapshot_id
        return is_valid, computed_id

    def to_dict(self) -> dict[str, Any]:
        """Serialize snapshot context to dictionary."""
        return {
            "legal_snapshot_id": self.legal_snapshot_id,
            "manifest": self.manifest.to_dict() if hasattr(self.manifest, "to_dict") else dict(self.manifest),
            "documents": list(self.documents),
            "provisions": list(self.provisions),
            "requirements": list(self.requirements),
            "schedules": list(self.schedules),
            "schedule_entries": list(self.schedule_entries),
            "tables": list(self.tables),
            "amendments": list(self.amendments),
            "applicability_rule_versions": list(self.applicability_rule_versions),
            "applicability_condition_groups": list(self.applicability_condition_groups),
            "applicability_conditions": list(self.applicability_conditions),
            "applicability_rules": list(self.applicability_rules),
            "serialization_version": self.serialization_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LegalSnapshotContext:
        """Instantiate snapshot context from dictionary."""
        return cls(
            legal_snapshot_id=data.get("legal_snapshot_id", ""),
            manifest=data.get("manifest"),
            documents=data.get("documents"),
            provisions=data.get("provisions"),
            requirements=data.get("requirements"),
            schedules=data.get("schedules"),
            schedule_entries=data.get("schedule_entries"),
            tables=data.get("tables"),
            amendments=data.get("amendments"),
            applicability_rule_versions=data.get("applicability_rule_versions"),
            applicability_condition_groups=data.get("applicability_condition_groups"),
            applicability_conditions=data.get("applicability_conditions"),
            applicability_rules=data.get("applicability_rules"),
            serialization_version=data.get("serialization_version", "1.0.0"),
        )
