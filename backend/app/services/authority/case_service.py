"""Service layer coordinating Authority Case Management workflows (T3-4 Phase 4)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from backend.app.services.authority.case_repository import AuthorityCaseRepository
from backend.app.services.authority.errors import (
    AuthorityInactiveError,
    AuthorityJurisdictionDeniedError,
    CaseNotFoundError,
    InvalidAssignmentError,
    InvalidCaseNoteError,
    InvalidJurisdictionScopeError,
    InvalidStatusTransitionError,
)
from backend.app.services.authority.models import (
    AuditEvent,
    AuditEventType,
    AuthorityPrincipal,
    CaseJurisdiction,
    InvestigationNote,
)
from backend.app.services.authority.policy import AuthorityAccessPolicy
from backend.app.services.authority.repository import AuthorityRepository
from backend.app.services.consumer_issues.models import ConsumerIssue, IssueStatus
from backend.app.services.establishment.errors import (
    EstablishmentInactiveError,
    EstablishmentNotFoundError,
    EstablishmentUnverifiedError,
)

logger = logging.getLogger(__name__)

# Strict state transition matrix for statutory case lifecycle
VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    IssueStatus.SUBMITTED.value: {
        IssueStatus.UNDER_REVIEW.value,
        IssueStatus.REJECTED.value,
    },
    IssueStatus.UNDER_REVIEW.value: {
        IssueStatus.ACTION_TAKEN.value,
        IssueStatus.RESOLVED.value,
        IssueStatus.REJECTED.value,
    },
    IssueStatus.ACTION_TAKEN.value: {
        IssueStatus.RESOLVED.value,
        IssueStatus.REJECTED.value,
    },
    IssueStatus.RESOLVED.value: set(),  # Terminal state
    IssueStatus.REJECTED.value: set(),  # Terminal state
}

# Statuses requiring substantive resolution/investigation notes
STATUSES_REQUIRING_NOTES: set[str] = {
    IssueStatus.ACTION_TAKEN.value,
    IssueStatus.RESOLVED.value,
    IssueStatus.REJECTED.value,
}


class AuthorityCaseService:
    """Business logic coordinator for authority complaint queues, assignment, notes, and lifecycle."""

    def __init__(
        self,
        case_repository: AuthorityCaseRepository,
        authority_repository: AuthorityRepository,
        establishment_repository: Any | None = None,
    ) -> None:
        self.case_repo = case_repository
        self.auth_repo = authority_repository
        self.est_repo = establishment_repository

    def _enforce_authority_case_access(
        self,
        authority: AuthorityPrincipal,
        case: ConsumerIssue,
    ) -> None:
        """Validate that authority has active credentials and explicit jurisdiction access to the case."""
        if not authority or not authority.is_active:
            raise AuthorityInactiveError(
                f"Authority user '{getattr(authority, 'user_id', 'unknown')}' is inactive or unprovisioned.",
                details={"user_id": getattr(authority, "user_id", None)},
            )

        # Jurisdiction must be verified; unresolved jurisdiction fails closed
        if not case.jurisdiction_verified or not case.state_code or not case.district_code:
            logger.warning("Access denied: Case '%s' has unresolved or unverified jurisdiction.", case.id)
            raise AuthorityJurisdictionDeniedError(
                f"Case '{case.id}' jurisdiction is unverified or unresolved. Access denied.",
                details={"case_id": case.id, "jurisdiction_verified": case.jurisdiction_verified},
            )

        case_jurisdiction = CaseJurisdiction(
            department=case.department,
            state_code=case.state_code,
            district_code=case.district_code,
        )
        AuthorityAccessPolicy.enforce_case_access(authority, case_jurisdiction)

    def list_cases(
        self,
        authority: AuthorityPrincipal,
        status: str | None = None,
        issue_type: str | None = None,
        assigned: bool | None = None,
        my_cases: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ConsumerIssue], int]:
        """List cases bounded strictly by the authority's assigned department and authorized districts."""
        if not authority.is_active:
            raise AuthorityInactiveError(f"Authority user '{authority.user_id}' is inactive.")

        if not authority.jurisdiction or not authority.jurisdiction.state_code or not authority.jurisdiction.authorized_district_codes:
            raise InvalidJurisdictionScopeError("Authority jurisdiction scope is incomplete or missing.")

        assigned_to_user_id = authority.user_id if my_cases else None

        return self.case_repo.list_cases(
            department=authority.department,
            state_code=authority.jurisdiction.state_code,
            authorized_district_codes=authority.jurisdiction.authorized_district_codes,
            status_filter=status,
            issue_type_filter=issue_type,
            assigned_filter=assigned,
            assigned_to_user_id=assigned_to_user_id,
            limit=limit,
            offset=offset,
        )

    def get_case_details(
        self,
        authority: AuthorityPrincipal,
        case_id: str,
    ) -> ConsumerIssue:
        """Retrieve authorized case details, enforcing jurisdiction boundaries."""
        case = self.case_repo.get_case_by_id(case_id)
        if not case:
            raise CaseNotFoundError(f"Case '{case_id}' was not found.", details={"case_id": case_id})

        self._enforce_authority_case_access(authority, case)
        return case

    def assign_officer(
        self,
        authority: AuthorityPrincipal,
        case_id: str,
        target_officer_id: str | None = None,
        expected_assigned_officer_id: str | None = None,
        expect_unassigned: bool = False,
        enforce_concurrency: bool | None = None,
    ) -> tuple[ConsumerIssue, AuditEvent]:
        """Assign or reassign primary investigating officer to a complaint.

        If target_officer_id is None, assigns the case to the acting authority principal (self-assignment).
        In Phase 5.2, without an established supervisor hierarchy, cross-officer assignment is denied;
        officers may only self-assign cases within their jurisdiction.
        """
        case = self.get_case_details(authority, case_id)

        # Mandatory concurrency enforcement
        if expect_unassigned:
            if case.assigned_officer_id is not None:
                raise InvalidAssignmentError(
                    f"Concurrent update conflict: expected case to be unassigned, but current is '{case.assigned_officer_id}'.",
                    details={
                        "conflict": True,
                        "current_officer": case.assigned_officer_id,
                        "expected_officer": None,
                    },
                )
        else:
            if expected_assigned_officer_id is None:
                raise InvalidAssignmentError(
                    "CONCURRENCY_TOKEN_REQUIRED: Expected assignment state must be explicitly provided.",
                    details={"code": "CONCURRENCY_TOKEN_REQUIRED"},
                )
            if case.assigned_officer_id != expected_assigned_officer_id:
                raise InvalidAssignmentError(
                    f"Concurrent update conflict: expected assigned officer '{expected_assigned_officer_id}', but current is '{case.assigned_officer_id}'.",
                    details={
                        "conflict": True,
                        "current_officer": case.assigned_officer_id,
                        "expected_officer": expected_assigned_officer_id,
                    },
                )

        assigned_officer_id = target_officer_id or authority.user_id

        if assigned_officer_id != authority.user_id:
            raise AuthorityJurisdictionDeniedError(
                "CROSS_OFFICER_ASSIGNMENT_DENIED: Cross-officer reassignment is disabled. Officers may only self-assign cases.",
                details={"target_officer_id": assigned_officer_id, "actor_id": authority.user_id},
            )

        saved_case, saved_event = self.case_repo.atomic_assign_officer(
            case_id=case.id,
            actor_id=authority.user_id,
            actor_role=authority.app_role,
            target_officer_id=assigned_officer_id,
            expected_assigned_officer_id=expected_assigned_officer_id,
            expect_unassigned=expect_unassigned,
        )

        logger.info(
            "Case '%s' assigned to officer '%s' by authority '%s' (event: %s).",
            case.id,
            assigned_officer_id,
            authority.user_id,
            saved_event.event_type,
        )
        return saved_case, saved_event

    def add_investigation_note(
        self,
        authority: AuthorityPrincipal,
        case_id: str,
        note_text: str,
    ) -> tuple[InvestigationNote, AuditEvent]:
        """Add a confidential internal investigation note to an active case atomically."""
        case = self.get_case_details(authority, case_id)

        clean_text = (note_text or "").strip()
        if not clean_text:
            raise InvalidCaseNoteError("Investigation note text cannot be empty or whitespace.")
        if len(clean_text) > 5000:
            raise InvalidCaseNoteError("Investigation note exceeds maximum allowed length of 5000 characters.")

        saved_note, saved_event = self.case_repo.atomic_create_note(
            case_id=case.id,
            actor_id=authority.user_id,
            actor_role=authority.app_role,
            note_text=clean_text,
        )

        logger.info("Confidential note added to case '%s' by authority '%s'.", case.id, authority.user_id)
        return saved_note, saved_event

    def list_investigation_notes(
        self,
        authority: AuthorityPrincipal,
        case_id: str,
    ) -> list[InvestigationNote]:
        """List confidential investigation notes for an authorized case."""
        # get_case_details enforces jurisdiction boundary check
        self.get_case_details(authority, case_id)
        return self.case_repo.list_notes(case_id)

    def transition_status(
        self,
        authority: AuthorityPrincipal,
        case_id: str,
        new_status: str,
        resolution_notes: str | None = None,
        expected_status: str | None = None,
    ) -> tuple[ConsumerIssue, AuditEvent]:
        """Perform validated lifecycle status transition on a case with audit tracking."""
        case = self.get_case_details(authority, case_id)

        # Concurrency protection: mandatory token
        clean_expected = (expected_status or "").strip()
        if not clean_expected:
            raise InvalidStatusTransitionError(
                "expected_status concurrency token is mandatory for status transitions.",
                details={"expected_status": expected_status},
            )

        if case.status != clean_expected:
            raise InvalidStatusTransitionError(
                f"Concurrent update conflict: expected status '{clean_expected}', but current status is '{case.status}'.",
                details={"conflict": True, "current_status": case.status, "expected_status": clean_expected},
            )

        # Validate valid enum
        valid_status_values = {s.value for s in IssueStatus}
        if new_status not in valid_status_values:
            raise InvalidStatusTransitionError(
                f"Invalid status '{new_status}'. Allowed statuses: {sorted(valid_status_values)}.",
                details={"new_status": new_status, "allowed": sorted(valid_status_values)},
            )

        # Validate transition matrix
        allowed_next = VALID_STATUS_TRANSITIONS.get(case.status, set())
        if new_status not in allowed_next:
            raise InvalidStatusTransitionError(
                f"Cannot transition case from status '{case.status}' to '{new_status}'. Allowed next statuses: {sorted(allowed_next) or 'None (terminal state)'}.",
                details={"current_status": case.status, "requested_status": new_status, "allowed_next": sorted(allowed_next)},
            )

        # Validate required resolution notes
        if new_status in STATUSES_REQUIRING_NOTES:
            clean_notes = (resolution_notes or "").strip()
            if len(clean_notes) < 5:
                raise InvalidStatusTransitionError(
                    f"Transition to status '{new_status}' requires substantive resolution notes (minimum 5 characters).",
                    details={"new_status": new_status, "provided_length": len(clean_notes)},
                )

        saved_case, saved_event = self.case_repo.atomic_transition_status(
            case_id=case.id,
            actor_id=authority.user_id,
            actor_role=authority.app_role,
            new_status=new_status,
            resolution_notes=resolution_notes,
            expected_status=expected_status,
        )

        logger.info(
            "Case '%s' status transitioned from '%s' to '%s' by authority '%s'.",
            case.id,
            saved_event.previous_state,
            new_status,
            authority.user_id,
        )
        return saved_case, saved_event

    def list_audit_events(
        self,
        authority: AuthorityPrincipal,
        case_id: str,
    ) -> list[AuditEvent]:
        """Retrieve audit timeline for a case, enforcing jurisdiction."""
        self.get_case_details(authority, case_id)
        return self.case_repo.list_audit_events(case_id)

    def verify_case_jurisdiction(
        self,
        authority: AuthorityPrincipal,
        case_id: str,
        establishment_id: str,
        provenance: str = "ADMIN_TRIAGE_VERIFICATION",
        verification_notes: str | None = None,
    ) -> tuple[ConsumerIssue, AuditEvent]:
        """Atomically verify a consumer complaint's jurisdiction against a verified retail establishment."""
        if not authority or not authority.is_active:
            raise AuthorityInactiveError(
                f"Authority user '{getattr(authority, 'user_id', 'unknown')}' is inactive or unprovisioned.",
                details={"user_id": getattr(authority, "user_id", None)},
            )

        if not authority.jurisdiction or not authority.jurisdiction.state_code or not authority.jurisdiction.authorized_district_codes:
            raise InvalidJurisdictionScopeError("Authority jurisdiction scope is incomplete or missing.")

        case = self.case_repo.get_case_by_id(case_id)
        if not case:
            raise CaseNotFoundError(f"Case '{case_id}' was not found.", details={"case_id": case_id})

        # Terminal case check
        if case.status in (IssueStatus.RESOLVED.value, IssueStatus.REJECTED.value):
            raise InvalidStatusTransitionError(
                f"INVALID_CASE_STATUS: Terminal case '{case_id}' in status '{case.status}' cannot have jurisdiction verified.",
                details={"case_id": case_id, "status": case.status},
            )

        # Department check
        if case.department != authority.department:
            raise AuthorityJurisdictionDeniedError(
                f"DEPARTMENT_MISMATCH: Case department '{case.department}' does not match authority department '{authority.department}'.",
                details={"authority_department": authority.department, "case_department": case.department},
            )

        # Pre-validate establishment if repo is available
        if self.est_repo:
            est = self.est_repo.get_by_id(establishment_id)
            if not est:
                raise EstablishmentNotFoundError(f"Establishment '{establishment_id}' was not found.")
            if not est.is_active:
                raise EstablishmentInactiveError(f"Establishment '{establishment_id}' is inactive.")
            if est.verification_status != "VERIFIED":
                raise EstablishmentUnverifiedError(
                    f"Establishment '{establishment_id}' is not verified (status: {est.verification_status})."
                )
            if authority.jurisdiction.state_code != est.state_code:
                raise AuthorityJurisdictionDeniedError(
                    f"State mismatch: Authority State='{authority.jurisdiction.state_code}', Establishment State='{est.state_code}'.",
                    details={"authority_state": authority.jurisdiction.state_code, "establishment_state": est.state_code},
                )
            if est.district_code not in authority.jurisdiction.authorized_district_codes:
                raise AuthorityJurisdictionDeniedError(
                    f"District '{est.district_code}' not in authorized districts for authority '{authority.user_id}'.",
                    details={"establishment_district": est.district_code, "authorized_districts": list(authority.jurisdiction.authorized_district_codes)},
                )

        clean_prov = (provenance or "").strip().upper()
        if clean_prov not in ("ESTABLISHMENT_QR", "VERIFIED_GSTIN_INVOICE", "ADMIN_TRIAGE_VERIFICATION"):
            raise InvalidJurisdictionScopeError(f"INVALID_PROVENANCE: Provenance '{provenance}' is not valid.")

        saved_case, audit_event = self.case_repo.atomic_verify_jurisdiction(
            case_id=case.id,
            establishment_id=establishment_id,
            actor_id=authority.user_id,
            actor_role=authority.app_role,
            provenance=clean_prov,
            verification_notes=verification_notes,
            establishment_repo=self.est_repo,
            authority_repo=self.auth_repo,
        )

        logger.info(
            "Case '%s' jurisdiction verified against establishment '%s' by authority '%s'.",
            case.id,
            establishment_id,
            authority.user_id,
        )
        return saved_case, audit_event

