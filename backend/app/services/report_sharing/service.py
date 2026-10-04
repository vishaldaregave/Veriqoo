"""Core service implementation for Phase U4 QR Report Sharing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
from typing import Any

from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.config import Settings, get_settings
from backend.app.localization.service import (
    LocalizationService,
    SupportedLanguage,
    get_localization_service,
)
from backend.app.services.inspection.errors import (
    InspectionNotFoundError,
    InspectionStateError,
)
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.report_sharing.models import (
    PublicInspectionReport,
    QRPayload,
    ReportShare,
    ShareStatus,
)

logger = logging.getLogger(__name__)


class ReportShareError(Exception):
    """Base exception for report sharing errors."""
    def __init__(self, message: str, code: str = "SHARE_ERROR", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class ReportShareNotFoundError(ReportShareError):
    """Raised when a share token cannot be found."""
    def __init__(self, message: str = "Share reference not found or invalid.", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="SHARE_NOT_FOUND", details=details)


class ReportShareExpiredError(ReportShareError):
    """Raised when a share token has expired."""
    def __init__(self, message: str = "Share reference has expired.", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="SHARE_EXPIRED", details=details)


class ReportShareRevokedError(ReportShareError):
    """Raised when a share token has been revoked."""
    def __init__(self, message: str = "Share reference has been revoked.", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="SHARE_REVOKED", details=details)


class ReportShareStateError(ReportShareError):
    """Raised when the underlying inspection is not in COMPLETED state."""
    def __init__(self, message: str = "Inspection report is not available for sharing.", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="SHARE_INVALID_STATE", details=details)


class ReportSharePermissionError(ReportShareError):
    """Raised when user lacks permission to manage a share."""
    def __init__(self, message: str = "Permission denied to manage share reference.", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="SHARE_FORBIDDEN", details=details)


class ReportSharingService:
    """Service managing generation, resolution, and revocation of shareable QR report tokens."""

    def __init__(
        self,
        store: InMemoryInspectionStore,
        settings: Settings | None = None,
        localization: LocalizationService | None = None,
    ) -> None:
        self._store = store
        self._settings = settings or get_settings()
        self._localization = localization or get_localization_service()

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Compute deterministic SHA-256 hash of a share token."""
        return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()

    def create_share(
        self,
        inspection_id: str,
        created_by: str | None = None,
        expires_in_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[ReportShare, str, QRPayload]:
        """Generate a new secure report share reference and QR payload for a completed inspection.

        Returns:
            tuple of (ReportShare, raw_token, QRPayload)
        """
        # Validate inspection existence and ownership
        session = self._store.get_session(inspection_id)
        insp = session.inspection

        if created_by and insp.owner_id and insp.owner_id != created_by:
            raise ReportSharePermissionError(
                f"User does not own inspection '{inspection_id}'.",
                details={"inspection_id": inspection_id},
            )

        if insp.status != InspectionStatus.COMPLETED:
            raise ReportShareStateError(
                f"Cannot create share for inspection in status '{insp.status.value}'. Must be COMPLETED.",
                details={"inspection_id": inspection_id, "status": insp.status.value},
            )

        report = self._store.get_report(inspection_id)
        if report is None:
            raise ReportShareStateError(
                f"Inspection report does not exist for inspection '{inspection_id}'.",
                details={"inspection_id": inspection_id},
            )

        # Generate high-entropy unguessable token
        raw_token = f"vqr_{secrets.token_urlsafe(32)}"
        token_hash = self.hash_token(raw_token)

        now = datetime.now(timezone.utc)
        expires_at: datetime | None = None
        if expires_in_seconds is not None and expires_in_seconds > 0:
            expires_at = now + timedelta(seconds=expires_in_seconds)

        meta = dict(metadata or {})
        share = ReportShare(
            inspection_id=inspection_id,
            token_hash=token_hash,
            created_at=now,
            expires_at=expires_at,
            revoked_at=None,
            created_by=created_by,
            metadata=meta,
        )

        self._store.save_share(share)

        # Construct public QR URL using configured base URL
        base_url = (self._settings.public_report_base_url or "http://localhost:8000/r").rstrip("/")
        qr_url = f"{base_url}/{raw_token}"

        qr_payload = QRPayload(
            url=qr_url,
            token_id=share.id,
            format="url",
            version=1,
        )

        return share, raw_token, qr_payload

    def resolve_share(
        self,
        raw_token: str,
        lang: str | None = None,
        accept_language: str | None = None,
    ) -> PublicInspectionReport:
        """Resolve a public share token to a safe, localized public report projection."""
        if not raw_token or not raw_token.strip():
            raise ReportShareNotFoundError()

        token_hash = self.hash_token(raw_token)
        share: ReportShare | None = self._store.get_share_by_token_hash(token_hash)

        if share is None:
            raise ReportShareNotFoundError()

        if share.is_revoked:
            raise ReportShareRevokedError()

        if share.is_expired():
            raise ReportShareExpiredError()

        try:
            session = self._store.get_session(share.inspection_id)
        except InspectionNotFoundError:
            raise ReportShareNotFoundError()

        if session.inspection.status != InspectionStatus.COMPLETED or session.inspection.is_failed:
            raise ReportShareStateError()

        report = self._store.get_report(share.inspection_id)
        if report is None:
            raise ReportShareStateError()

        # Language negotiation using U3 LocalizationService
        target_lang = self._localization.resolve_language(
            explicit_lang=lang,
            inspection_meta=session.inspection.metadata,
            accept_language_header=accept_language,
        )

        # Generate localized presentation dictionary from report
        report_dict = report.to_dict(lang=target_lang.value)

        # Sanitize evidence annotations: preserve IDs, geometry, but omit internal storage paths
        sanitized_annotations = []
        for ann in report_dict.get("evidence_annotations", []):
            safe_ann = {
                "annotation_id": ann.get("annotation_id"),
                "image_id": ann.get("image_id"),
                "requirement_id": ann.get("requirement_id"),
                "evidence_id": ann.get("evidence_id"),
                "status": ann.get("status"),
                "annotation_type": ann.get("annotation_type"),
                "polygon": ann.get("polygon", []),
                "bounding_box": ann.get("bounding_box", {}),
                "normalized_box": ann.get("normalized_box", {}),
                "label": ann.get("label", ""),
                "reason": ann.get("reason", ""),
                "confidence": ann.get("confidence"),
                "is_locatable": ann.get("is_locatable", True),
                "metadata": {k: v for k, v in ann.get("metadata", {}).items() if not k.startswith("_") and k != "storage_path"},
            }
            sanitized_annotations.append(safe_ann)

        # Sanitize verification results: preserve canonical requirement IDs, status, localized reason
        sanitized_results = []
        for res in report_dict.get("verification_results", []):
            safe_res = {
                "verification_id": res.get("verification_id"),
                "requirement_id": res.get("requirement_id"),
                "applicability_decision_id": res.get("applicability_decision_id"),
                "status": res.get("status"),
                "reason": res.get("reason"),
                "confidence": res.get("confidence"),
                "review_required": res.get("review_required", False),
                "evidence_ids": res.get("evidence_ids", []),
                "source_observation_ids": res.get("source_observation_ids", []),
                "image_ids": res.get("image_ids", []),
                "metadata": {k: v for k, v in res.get("metadata", {}).items() if not k.startswith("_")},
                "created_at": res.get("created_at"),
            }
            sanitized_results.append(safe_res)

        return PublicInspectionReport(
            report_id=f"rep_{share.inspection_id[:8]}",
            inspection_id=share.inspection_id,
            overall_status=report_dict.get("overall_status", "REVIEW_REQUIRED"),
            language=target_lang.value,
            summary=report_dict.get("summary", ""),
            counts=report_dict.get("counts", {}),
            verification_results=sanitized_results,
            evidence_annotations=sanitized_annotations,
            created_at=report_dict.get("created_at", datetime.now(timezone.utc).isoformat()),
            share_metadata={
                "share_id": share.id,
                "share_status": share.status().value,
                "expires_at": share.expires_at.isoformat() if share.expires_at else None,
            },
        )

    def revoke_share(
        self,
        inspection_id: str,
        share_id: str,
        current_user_id: str,
    ) -> ReportShare:
        """Revoke a share reference immediately if owned by current user."""
        session = self._store.get_session(inspection_id)
        insp = session.inspection

        if current_user_id and insp.owner_id and insp.owner_id != current_user_id:
            raise ReportSharePermissionError(
                f"User does not own inspection '{inspection_id}'.",
                details={"inspection_id": inspection_id},
            )

        share = self._store.get_share(share_id)
        if share is None or share.inspection_id != inspection_id:
            raise ReportShareNotFoundError(
                f"Share reference '{share_id}' not found for inspection '{inspection_id}'.",
                details={"share_id": share_id, "inspection_id": inspection_id},
            )

        revoked_share = self._store.revoke_share(share_id)
        return revoked_share or share

    def list_shares(
        self,
        inspection_id: str,
        current_user_id: str,
    ) -> list[ReportShare]:
        """List all shares generated for an inspection session owned by user."""
        session = self._store.get_session(inspection_id)
        insp = session.inspection

        if current_user_id and insp.owner_id and insp.owner_id != current_user_id:
            raise ReportSharePermissionError(
                f"User does not own inspection '{inspection_id}'.",
                details={"inspection_id": inspection_id},
            )

        return self._store.list_shares(inspection_id)


_GLOBAL_REPORT_SHARING_SERVICE: ReportSharingService | None = None


def get_report_sharing_service(
    store: InMemoryInspectionStore | None = None,
    settings: Settings | None = None,
) -> ReportSharingService:
    """Provide singleton ReportSharingService instance."""
    global _GLOBAL_REPORT_SHARING_SERVICE
    if _GLOBAL_REPORT_SHARING_SERVICE is None:
        from backend.app.api.dependencies import get_session_store
        s = store or get_session_store()
        cfg = settings or get_settings()
        _GLOBAL_REPORT_SHARING_SERVICE = ReportSharingService(store=s, settings=cfg)
    return _GLOBAL_REPORT_SHARING_SERVICE
