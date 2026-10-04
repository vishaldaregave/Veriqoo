"""Service coordinator for Consumer Issue Reporting (T3-3)."""

from __future__ import annotations

import logging
from typing import Any

from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.services.consumer_issues.errors import (
    ConsumerIssueNotFoundError,
    InvalidConsumerIssueError,
    InvalidImageReferenceError,
    InvalidIssueStateError,
)
from backend.app.services.consumer_issues.jurisdiction import (
    DefaultTrustedJurisdictionResolver,
    TrustedJurisdictionResolver,
)
from backend.app.services.consumer_issues.models import ConsumerIssue, IssueStatus
from backend.app.services.consumer_issues.repository import ConsumerIssueRepository
from backend.app.services.consumer_issues.schemas import CreateConsumerIssueRequest
from backend.app.services.inspection.errors import InspectionNotFoundError
from backend.app.services.saved_products.errors import SavedProductNotFoundError
from backend.app.services.saved_products.repository import SavedProductRepository

logger = logging.getLogger(__name__)


class ConsumerIssueService:
    """Service coordinator handling consumer issue domain validation and persistence."""

    def __init__(
        self,
        repository: ConsumerIssueRepository,
        session_store: InMemoryInspectionStore,
        saved_product_repository: SavedProductRepository | None = None,
        jurisdiction_resolver: TrustedJurisdictionResolver | None = None,
    ) -> None:
        self.repository = repository
        self.session_store = session_store
        self.saved_product_repository = saved_product_repository
        self.jurisdiction_resolver = jurisdiction_resolver or DefaultTrustedJurisdictionResolver()

    def create_issue(
        self,
        user_id: str,
        request: CreateConsumerIssueRequest,
    ) -> ConsumerIssue:
        """Submit a consumer issue complaint after ownership and evidence validation."""
        # 1. Validate inspection existence and ownership
        try:
            session = self.session_store.get_session(request.inspection_id)
        except InspectionNotFoundError as exc:
            raise InspectionNotFoundError(
                f"Inspection session '{request.inspection_id}' not found.",
                details={"inspection_id": request.inspection_id},
            ) from exc

        # Mandatory service-layer ownership check
        insp_owner = session.inspection.owner_id or session.inspection.metadata.get("owner_id")
        if insp_owner and insp_owner != user_id:
            raise InspectionNotFoundError(
                f"Inspection session '{request.inspection_id}' not found.",
                details={"inspection_id": request.inspection_id},
            )

        # 2. Validate saved_product ownership and inspection consistency if provided
        if request.saved_product_id:
            if self.saved_product_repository is None:
                raise InvalidConsumerIssueError(
                    "Saved product repository is not configured on service.",
                    details={"saved_product_id": request.saved_product_id},
                )
            saved_prod = self.saved_product_repository.get_by_id(request.saved_product_id)
            if not saved_prod or saved_prod.user_id != user_id:
                raise SavedProductNotFoundError(request.saved_product_id)
            if saved_prod.inspection_id != request.inspection_id:
                raise InvalidConsumerIssueError(
                    f"Saved product '{request.saved_product_id}' is linked to inspection '{saved_prod.inspection_id}', which does not match complaint inspection '{request.inspection_id}'.",
                    details={
                        "saved_product_id": request.saved_product_id,
                        "saved_product_inspection_id": saved_prod.inspection_id,
                        "inspection_id": request.inspection_id,
                    },
                )

        # 3. Validate evidence image references against session images
        valid_images = {img.image_id: img for img in session.inspection.images}
        evidence_payload: list[dict[str, Any]] = []

        for img_id in request.evidence_image_ids:
            if img_id not in valid_images:
                raise InvalidImageReferenceError(
                    f"Image '{img_id}' does not belong to inspection '{request.inspection_id}'.",
                    details={"invalid_image_id": img_id, "inspection_id": request.inspection_id},
                )
            img_ref = valid_images[img_id]
            evidence_payload.append({
                "image_id": img_ref.image_id,
                "sequence": img_ref.sequence,
                "source_hash": img_ref.source_hash,
                "storage_path": img_ref.storage_path,
            })

        # 4. Resolve trusted jurisdiction via authoritative server-controlled path
        state_code, district_code, jurisdiction_verified = (
            self.jurisdiction_resolver.resolve_jurisdiction(
                inspection_id=request.inspection_id,
                session=session,
                untrusted_payload={
                    "state_code": getattr(request, "state_code", None),
                    "district_code": getattr(request, "district_code", None),
                },
            )
        )

        # Enforce fail-closed state invariants:
        # If jurisdiction is not verified, state_code and district_code must only reflect trusted sources.
        if not jurisdiction_verified:
            if not state_code:
                state_code = None
            if not district_code:
                district_code = None
        else:
            if not state_code or not district_code:
                jurisdiction_verified = False
                state_code = None
                district_code = None

        # 5. Create consumer issue domain model with enforced SUBMITTED status
        issue = ConsumerIssue(
            user_id=user_id,
            inspection_id=request.inspection_id,
            saved_product_id=request.saved_product_id,
            issue_type=request.issue_type.value,
            title=request.title.strip(),
            description=request.description.strip(),
            status=IssueStatus.SUBMITTED.value,
            resolution_notes=None,
            evidence_images=evidence_payload,
            department="LEGAL_METROLOGY",
            state_code=state_code,
            district_code=district_code,
            jurisdiction_verified=jurisdiction_verified,
        )

        # 6. Save to repository (raises DuplicateConsumerIssueError if conflict exists)
        return self.repository.create_issue(issue)

    def get_issue(self, user_id: str, issue_id: str) -> ConsumerIssue:
        """Retrieve consumer issue details if owned by caller."""
        issue = self.repository.get_by_id(issue_id)
        if not issue or issue.user_id != user_id:
            raise ConsumerIssueNotFoundError(
                f"Consumer issue with ID '{issue_id}' not found.",
                details={"issue_id": issue_id},
            )
        return issue

    def list_issues(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        status_filter: str | None = None,
    ) -> tuple[list[ConsumerIssue], int]:
        """List caller's reported issues with pagination and optional status filter."""
        return self.repository.list_by_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
            status_filter=status_filter,
        )

    def delete_issue(self, user_id: str, issue_id: str) -> bool:
        """Withdraw consumer issue complaint if owned by caller and still in SUBMITTED state."""
        issue = self.get_issue(user_id=user_id, issue_id=issue_id)
        if issue.status != IssueStatus.SUBMITTED.value:
            raise InvalidIssueStateError(
                f"Cannot withdraw complaint '{issue_id}' in status '{issue.status}'.",
                details={"issue_id": issue_id, "status": issue.status},
            )
        return self.repository.delete_by_id(issue_id=issue_id, user_id=user_id)
