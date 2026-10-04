"""Repository abstractions and implementations for Authority Case Management (T3-4 Phase 4)."""

from __future__ import annotations

import abc
import copy
from datetime import datetime, timezone
import logging
import threading
from typing import Any
import uuid

import requests

from backend.app.config import Settings, get_settings
from backend.app.services.authority.errors import (
    AuthorityInactiveError,
    AuthorityJurisdictionDeniedError,
    AuthorityRoleDeniedError,
    CaseNotFoundError,
    InvalidAssignmentError,
    InvalidCaseNoteError,
    InvalidJurisdictionScopeError,
    InvalidStatusTransitionError,
)
from backend.app.services.establishment.errors import (
    EstablishmentInactiveError,
    EstablishmentNotFoundError,
    EstablishmentUnverifiedError,
)
from backend.app.services.authority.models import (
    AuditEvent,
    AuditEventType,
    InvestigationNote,
)
from backend.app.services.consumer_issues.models import ConsumerIssue, IssueStatus

logger = logging.getLogger(__name__)


class AuthorityCaseRepository(abc.ABC):
    """Abstract persistence interface for authority case investigation and workflow."""

    @abc.abstractmethod
    def list_cases(
        self,
        department: str,
        state_code: str,
        authorized_district_codes: set[str] | frozenset[str],
        status_filter: str | None = None,
        issue_type_filter: str | None = None,
        assigned_filter: bool | None = None,
        assigned_to_user_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ConsumerIssue], int]:
        """List cases bounded strictly by department, state, and authorized districts."""
        pass

    @abc.abstractmethod
    def get_case_by_id(self, case_id: str) -> ConsumerIssue | None:
        """Fetch a single case by ID."""
        pass

    @abc.abstractmethod
    def save_case(self, case: ConsumerIssue) -> ConsumerIssue:
        """Persist updates to an existing case."""
        pass

    @abc.abstractmethod
    def atomic_assign_officer(
        self,
        case_id: str,
        actor_id: str,
        actor_role: str,
        target_officer_id: str,
        expected_assigned_officer_id: str | None = None,
        expect_unassigned: bool = False,
        enforce_concurrency: bool | None = None,
    ) -> tuple[ConsumerIssue, AuditEvent]:
        """Atomically assign officer and insert audit record, guaranteeing transactional consistency."""
        pass

    @abc.abstractmethod
    def atomic_transition_status(
        self,
        case_id: str,
        actor_id: str,
        actor_role: str,
        new_status: str,
        resolution_notes: str | None = None,
        expected_status: str | None = None,
    ) -> tuple[ConsumerIssue, AuditEvent]:
        """Atomically update case status and insert audit record, guaranteeing transactional consistency."""
        pass

    @abc.abstractmethod
    def atomic_create_note(
        self,
        case_id: str,
        actor_id: str,
        actor_role: str,
        note_text: str,
    ) -> tuple[InvestigationNote, AuditEvent]:
        """Atomically insert confidential investigation note and NOTE_ADDED audit record."""
        pass

    @abc.abstractmethod
    def atomic_verify_jurisdiction(
        self,
        case_id: str,
        establishment_id: str,
        actor_id: str,
        actor_role: str,
        provenance: str,
        verification_notes: str | None = None,
        establishment_repo: Any = None,
        authority_repo: Any = None,
    ) -> tuple[ConsumerIssue, AuditEvent]:
        """Atomically verify complaint jurisdiction against a verified establishment."""
        pass

    @abc.abstractmethod
    def create_note(self, note: InvestigationNote) -> InvestigationNote:
        """Store a confidential internal investigation note."""
        pass

    @abc.abstractmethod
    def list_notes(self, case_id: str) -> list[InvestigationNote]:
        """Retrieve confidential internal notes for a case."""
        pass

    @abc.abstractmethod
    def record_audit_event(self, event: AuditEvent) -> AuditEvent:
        """Append an immutable case audit record."""
        pass

    @abc.abstractmethod
    def list_audit_events(self, case_id: str) -> list[AuditEvent]:
        """Retrieve audit timeline for a case."""
        pass

    @abc.abstractmethod
    def clear(self) -> None:
        """Reset repository state (testing only)."""
        pass


class InMemoryAuthorityCaseRepository(AuthorityCaseRepository):
    """Thread-safe in-memory case repository for unit testing and local development."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cases: dict[str, ConsumerIssue] = {}
        self._notes: dict[str, list[InvestigationNote]] = {}
        self._audit_events: dict[str, list[AuditEvent]] = {}
        self.simulate_audit_failure: bool = False
        self.simulate_case_failure: bool = False

    def list_cases(
        self,
        department: str,
        state_code: str,
        authorized_district_codes: set[str] | frozenset[str],
        status_filter: str | None = None,
        issue_type_filter: str | None = None,
        assigned_filter: bool | None = None,
        assigned_to_user_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ConsumerIssue], int]:
        with self._lock:
            districts = set(authorized_district_codes)
            candidates = []
            for c in self._cases.values():
                # Enforce fail-closed jurisdiction gating
                if not c.jurisdiction_verified:
                    continue
                if c.department != department:
                    continue
                if c.state_code != state_code:
                    continue
                if not c.district_code or c.district_code not in districts:
                    continue

                # Filters
                if status_filter and c.status != status_filter:
                    continue
                if issue_type_filter and c.issue_type != issue_type_filter:
                    continue
                if assigned_filter is True and not c.assigned_officer_id:
                    continue
                if assigned_filter is False and c.assigned_officer_id:
                    continue
                if assigned_to_user_id and c.assigned_officer_id != assigned_to_user_id:
                    continue

                candidates.append(c)

            candidates.sort(key=lambda x: x.created_at, reverse=True)
            total = len(candidates)
            paginated = candidates[offset : offset + limit]
            return paginated, total

    def get_case_by_id(self, case_id: str) -> ConsumerIssue | None:
        with self._lock:
            return self._cases.get(case_id)

    def save_case(self, case: ConsumerIssue) -> ConsumerIssue:
        with self._lock:
            self._cases[case.id] = case
            return case

    def atomic_assign_officer(
        self,
        case_id: str,
        actor_id: str,
        actor_role: str,
        target_officer_id: str,
        expected_assigned_officer_id: str | None = None,
        expect_unassigned: bool = False,
        enforce_concurrency: bool | None = None,
    ) -> tuple[ConsumerIssue, AuditEvent]:
        with self._lock:
            case = self._cases.get(case_id)
            if not case:
                raise CaseNotFoundError(f"Case '{case_id}' was not found.", details={"case_id": case_id})

            if target_officer_id != actor_id:
                raise AuthorityJurisdictionDeniedError(
                    "CROSS_OFFICER_ASSIGNMENT_DENIED: Cross-officer reassignment is disabled. Officers may only self-assign cases."
                )

            if expect_unassigned:
                if case.assigned_officer_id is not None:
                    raise InvalidAssignmentError(
                        f"CONCURRENT_UPDATE_CONFLICT: Case expected to be unassigned, but currently assigned to '{case.assigned_officer_id}'.",
                        details={"conflict": True, "current_officer": case.assigned_officer_id, "expected_officer": None},
                    )
            else:
                if expected_assigned_officer_id is None:
                    raise InvalidAssignmentError(
                        "CONCURRENCY_TOKEN_REQUIRED: expected assignment state must be explicitly provided.",
                        details={"code": "CONCURRENCY_TOKEN_REQUIRED"},
                    )
                if case.assigned_officer_id != expected_assigned_officer_id:
                    raise InvalidAssignmentError(
                        f"CONCURRENT_UPDATE_CONFLICT: expected assigned officer '{expected_assigned_officer_id}', but current is '{case.assigned_officer_id}'.",
                        details={"conflict": True, "current_officer": case.assigned_officer_id, "expected_officer": expected_assigned_officer_id},
                    )

            if self.simulate_case_failure:
                raise RuntimeError("Simulated database failure during case assignment.")

            # Snapshot previous state for rollback guarantee
            prev_officer = case.assigned_officer_id
            prev_assigned_by = case.assigned_by
            prev_assigned_at = case.assigned_at
            prev_updated_at = case.updated_at

            now = datetime.now(timezone.utc)
            case.assigned_officer_id = target_officer_id
            case.assigned_by = actor_id
            case.assigned_at = now
            case.updated_at = now

            if self.simulate_audit_failure:
                # Rollback case assignment to prove atomic transaction boundary
                case.assigned_officer_id = prev_officer
                case.assigned_by = prev_assigned_by
                case.assigned_at = prev_assigned_at
                case.updated_at = prev_updated_at
                raise RuntimeError("Simulated database failure during audit event insertion. Assignment rolled back.")

            event_type = (
                AuditEventType.CASE_REASSIGNED.value
                if prev_officer
                else AuditEventType.CASE_ASSIGNED.value
            )
            audit_event = AuditEvent(
                issue_id=case.id,
                actor_id=actor_id,
                actor_role=actor_role,
                event_type=event_type,
                previous_state=prev_officer,
                new_state=target_officer_id,
                metadata={
                    "assigned_by": actor_id,
                    "assigned_officer_id": target_officer_id,
                    "previous_officer_id": prev_officer,
                    "assigned_at": now.isoformat(),
                },
                created_at=now,
            )
            self._audit_events.setdefault(case.id, []).append(audit_event)
            return copy.deepcopy(case), audit_event

    def atomic_transition_status(
        self,
        case_id: str,
        actor_id: str,
        actor_role: str,
        new_status: str,
        resolution_notes: str | None = None,
        expected_status: str | None = None,
    ) -> tuple[ConsumerIssue, AuditEvent]:
        with self._lock:
            case = self._cases.get(case_id)
            if not case:
                raise CaseNotFoundError(f"Case '{case_id}' was not found.", details={"case_id": case_id})

            clean_expected = (expected_status or "").strip()
            if not clean_expected:
                raise InvalidStatusTransitionError(
                    "CONCURRENCY_TOKEN_REQUIRED: expected_status token is mandatory for status transitions.",
                    details={"code": "CONCURRENCY_TOKEN_REQUIRED"},
                )

            if case.status != clean_expected:
                raise InvalidStatusTransitionError(
                    f"Concurrent update conflict: expected status '{clean_expected}', but current status is '{case.status}'.",
                    details={"conflict": True, "current_status": case.status, "expected_status": clean_expected},
                )

            if self.simulate_case_failure:
                raise RuntimeError("Simulated database failure during status update.")

            # Snapshot previous state for rollback guarantee
            prev_status = case.status
            prev_notes = case.resolution_notes
            prev_updated_at = case.updated_at

            now = datetime.now(timezone.utc)
            case.status = new_status
            if resolution_notes:
                case.resolution_notes = resolution_notes.strip()
            case.updated_at = now

            if self.simulate_audit_failure:
                # Rollback case status update to prove atomic transaction boundary
                case.status = prev_status
                case.resolution_notes = prev_notes
                case.updated_at = prev_updated_at
                raise RuntimeError("Simulated database failure during audit event insertion. Status update rolled back.")

            audit_event = AuditEvent(
                issue_id=case.id,
                actor_id=actor_id,
                actor_role=actor_role,
                event_type=AuditEventType.STATUS_CHANGED.value,
                previous_state=prev_status,
                new_state=new_status,
                metadata={
                    "actor_id": actor_id,
                    "actor_role": actor_role,
                    "previous_status": prev_status,
                    "new_status": new_status,
                    "resolution_notes": case.resolution_notes,
                },
                created_at=now,
            )
            self._audit_events.setdefault(case.id, []).append(audit_event)
            return copy.deepcopy(case), audit_event

    def atomic_create_note(
        self,
        case_id: str,
        actor_id: str,
        actor_role: str,
        note_text: str,
    ) -> tuple[InvestigationNote, AuditEvent]:
        with self._lock:
            case = self._cases.get(case_id)
            if not case:
                raise CaseNotFoundError(f"Case '{case_id}' was not found.", details={"case_id": case_id})

            clean_text = (note_text or "").strip()
            if not clean_text:
                raise InvalidCaseNoteError("NOTE_EMPTY: Note text cannot be empty.")
            if len(clean_text) > 5000:
                raise InvalidCaseNoteError("NOTE_TOO_LONG: Note text cannot exceed 5000 characters.")

            if self.simulate_case_failure:
                raise RuntimeError("Simulated database failure during note creation.")

            now = datetime.now(timezone.utc)
            note = InvestigationNote(
                id=str(uuid.uuid4()),
                issue_id=case_id,
                author_id=actor_id,
                note_text=clean_text,
                is_internal=True,
                created_at=now,
                updated_at=now,
            )

            # Insert note
            self._notes.setdefault(case_id, []).append(note)

            if self.simulate_audit_failure:
                # Rollback note insertion to prove atomic transaction boundary
                self._notes[case_id].remove(note)
                raise RuntimeError("Simulated database failure during audit event insertion. Note creation rolled back.")

            audit_event = AuditEvent(
                issue_id=case_id,
                actor_id=actor_id,
                actor_role=actor_role,
                event_type=AuditEventType.NOTE_ADDED.value,
                previous_state=None,
                new_state="CONFIDENTIAL_NOTE",
                metadata={
                    "note_id": note.id,
                    "author_id": actor_id,
                    "note_length": len(clean_text),
                },
                created_at=now,
            )
            self._audit_events.setdefault(case_id, []).append(audit_event)
            return copy.deepcopy(note), audit_event

    def atomic_verify_jurisdiction(
        self,
        case_id: str,
        establishment_id: str,
        actor_id: str,
        actor_role: str,
        provenance: str,
        verification_notes: str | None = None,
        establishment_repo: Any = None,
        authority_repo: Any = None,
    ) -> tuple[ConsumerIssue, AuditEvent]:
        with self._lock:
            if not actor_id:
                raise AuthorityInactiveError("ACTOR_REQUIRED: Actor ID cannot be null.")

            if actor_role not in ("authority", "admin"):
                raise AuthorityRoleDeniedError(
                    f"ACTOR_ROLE_DENIED: Actor {actor_id} does not have an authority or admin role (role: {actor_role})"
                )

            case = self._cases.get(case_id)
            if not case:
                raise CaseNotFoundError(f"Case '{case_id}' was not found.", details={"case_id": case_id})

            if case.status in (IssueStatus.RESOLVED.value, IssueStatus.REJECTED.value):
                raise InvalidStatusTransitionError(
                    f"INVALID_CASE_STATUS: Terminal case '{case_id}' in status '{case.status}' cannot have jurisdiction verified."
                )

            if not establishment_id:
                raise InvalidJurisdictionScopeError("ESTABLISHMENT_REQUIRED: Establishment ID cannot be null.")

            est = None
            if establishment_repo:
                est = establishment_repo.get_by_id(establishment_id)

            if not est:
                raise EstablishmentNotFoundError(f"Establishment '{establishment_id}' was not found.")

            if not est.is_active:
                raise EstablishmentInactiveError(f"Establishment '{establishment_id}' is inactive.")

            if est.verification_status != "VERIFIED":
                raise EstablishmentUnverifiedError(
                    f"Establishment '{establishment_id}' is not verified (status: {est.verification_status})."
                )

            if authority_repo:
                actor_profile = (
                    authority_repo.get_by_user_id(actor_id)
                    if hasattr(authority_repo, "get_by_user_id")
                    else authority_repo.get_profile_by_user_id(actor_id)
                )
                if not actor_profile or not actor_profile.is_active:
                    raise AuthorityInactiveError(f"Authority account for user '{actor_id}' is inactive or not provisioned.")

                if actor_profile.department != case.department:
                    raise AuthorityJurisdictionDeniedError(
                        f"Department mismatch. Authority='{actor_profile.department}', Case='{case.department}'."
                    )

                profile_state = getattr(actor_profile, "state_code", None) or (
                    actor_profile.jurisdiction.state_code if hasattr(actor_profile, "jurisdiction") else None
                )
                profile_districts = getattr(actor_profile, "authorized_district_codes", None) or (
                    actor_profile.jurisdiction.authorized_district_codes if hasattr(actor_profile, "jurisdiction") else set()
                )

                if profile_state != est.state_code:
                    raise AuthorityJurisdictionDeniedError(
                        f"State mismatch. Authority State='{profile_state}', Establishment State='{est.state_code}'."
                    )

                if est.district_code not in profile_districts:
                    raise AuthorityJurisdictionDeniedError(
                        f"District '{est.district_code}' not in authorized districts for authority '{actor_id}'."
                    )

            clean_prov = (provenance or "").strip()
            if clean_prov not in ("ESTABLISHMENT_QR", "VERIFIED_GSTIN_INVOICE", "ADMIN_TRIAGE_VERIFICATION"):
                raise InvalidJurisdictionScopeError(f"INVALID_PROVENANCE: Provenance '{provenance}' is not valid.")

            if self.simulate_case_failure:
                raise RuntimeError("Simulated database failure during jurisdiction verification.")

            prev_verified = case.jurisdiction_verified
            prev_state = case.state_code
            prev_district = case.district_code
            prev_est_id = case.establishment_id
            prev_prov = case.jurisdiction_provenance
            prev_verified_at = case.jurisdiction_verified_at
            prev_verified_by = case.jurisdiction_verified_by
            prev_updated_at = case.updated_at

            now = datetime.now(timezone.utc)
            case.jurisdiction_verified = True
            case.state_code = est.state_code
            case.district_code = est.district_code
            case.establishment_id = est.id
            case.jurisdiction_provenance = clean_prov
            case.jurisdiction_verified_at = now
            case.jurisdiction_verified_by = actor_id
            case.updated_at = now

            if self.simulate_audit_failure:
                case.jurisdiction_verified = prev_verified
                case.state_code = prev_state
                case.district_code = prev_district
                case.establishment_id = prev_est_id
                case.jurisdiction_provenance = prev_prov
                case.jurisdiction_verified_at = prev_verified_at
                case.jurisdiction_verified_by = prev_verified_by
                case.updated_at = prev_updated_at
                raise RuntimeError("Simulated database failure during audit event insertion. Jurisdiction verification rolled back.")

            audit_event = AuditEvent(
                issue_id=case.id,
                actor_id=actor_id,
                actor_role=actor_role,
                event_type=AuditEventType.JURISDICTION_VERIFIED.value,
                previous_state="VERIFIED" if prev_verified else "UNVERIFIED",
                new_state="VERIFIED",
                metadata={
                    "establishment_id": est.id,
                    "trade_name": est.trade_name,
                    "state_code": est.state_code,
                    "district_code": est.district_code,
                    "provenance": clean_prov,
                    "verification_notes": verification_notes or "",
                },
                created_at=now,
            )
            self._audit_events.setdefault(case.id, []).append(audit_event)
            return copy.deepcopy(case), audit_event

    def create_note(self, note: InvestigationNote) -> InvestigationNote:
        with self._lock:
            self._notes.setdefault(note.issue_id, []).append(note)
            return note

    def list_notes(self, case_id: str) -> list[InvestigationNote]:
        with self._lock:
            notes = list(self._notes.get(case_id, []))
            notes.sort(key=lambda x: x.created_at, reverse=True)
            return notes

    def record_audit_event(self, event: AuditEvent) -> AuditEvent:
        with self._lock:
            key = event.issue_id or "unassigned"
            self._audit_events.setdefault(key, []).append(event)
            return event

    def list_audit_events(self, case_id: str) -> list[AuditEvent]:
        with self._lock:
            events = list(self._audit_events.get(case_id, []))
            events.sort(key=lambda x: x.created_at, reverse=True)
            return events

    def clear(self) -> None:
        with self._lock:
            self._cases.clear()
            self._notes.clear()
            self._audit_events.clear()


class SupabaseAuthorityCaseRepository(AuthorityCaseRepository):
    """Supabase REST API implementation for authority cases, notes, and audit events."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = f"{self.settings.supabase_url.rstrip('/')}/rest/v1"

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        key = self.settings.supabase_service_role_key or self.settings.supabase_anon_key
        h = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        if prefer:
            h["Prefer"] = prefer
        return h

    def _request(self, method: str, table: str, **kwargs: Any) -> tuple[int, list[dict[str, Any]]]:
        url = f"{self.base_url}/{table}"
        resp = requests.request(method, url, timeout=10, **kwargs)
        if resp.status_code >= 400:
            logger.error("Supabase API error %d on %s %s: %s", resp.status_code, method, url, resp.text)
            resp.raise_for_status()
        if not resp.text or resp.text.strip() == "":
            return resp.status_code, []
        try:
            data = resp.json()
            items = data if isinstance(data, list) else [data]
            return resp.status_code, items
        except Exception:
            return resp.status_code, []

    def _map_case_row(self, r: dict[str, Any]) -> ConsumerIssue:
        return ConsumerIssue(
            id=str(r["id"]),
            user_id=str(r["user_id"]),
            inspection_id=str(r["inspection_id"]) if r.get("inspection_id") else None,
            saved_product_id=str(r["saved_product_id"]) if r.get("saved_product_id") else None,
            issue_type=r["issue_type"],
            title=r["title"],
            description=r["description"],
            status=r.get("status", IssueStatus.SUBMITTED.value),
            resolution_notes=r.get("resolution_notes"),
            evidence_images=r.get("evidence_images", []),
            department=str(r.get("department", "LEGAL_METROLOGY")),
            state_code=str(r["state_code"]) if r.get("state_code") else None,
            district_code=str(r["district_code"]) if r.get("district_code") else None,
            jurisdiction_verified=bool(r.get("jurisdiction_verified", False)),
            establishment_id=str(r["establishment_id"]) if r.get("establishment_id") else None,
            jurisdiction_provenance=str(r.get("jurisdiction_provenance", "UNVERIFIED")),
            jurisdiction_verified_at=datetime.fromisoformat(r["jurisdiction_verified_at"].replace("Z", "+00:00")) if r.get("jurisdiction_verified_at") else None,
            jurisdiction_verified_by=str(r["jurisdiction_verified_by"]) if r.get("jurisdiction_verified_by") else None,
            assigned_officer_id=str(r["assigned_officer_id"]) if r.get("assigned_officer_id") else None,
            assigned_at=datetime.fromisoformat(r["assigned_at"].replace("Z", "+00:00")) if r.get("assigned_at") else None,
            assigned_by=str(r["assigned_by"]) if r.get("assigned_by") else None,
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
        )

    def _map_note_row(self, r: dict[str, Any]) -> InvestigationNote:
        return InvestigationNote(
            id=str(r["id"]),
            issue_id=str(r["issue_id"]),
            author_id=str(r["author_id"]),
            note_text=str(r["note_text"]),
            is_internal=bool(r.get("is_internal", True)),
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
        )

    def _map_audit_row(self, r: dict[str, Any]) -> AuditEvent:
        return AuditEvent(
            id=str(r["id"]),
            issue_id=str(r["issue_id"]) if r.get("issue_id") else None,
            actor_id=str(r["actor_id"]),
            actor_role=str(r.get("actor_role", "authority")),
            event_type=str(r["event_type"]),
            previous_state=str(r["previous_state"]) if r.get("previous_state") else None,
            new_state=str(r["new_state"]) if r.get("new_state") else None,
            metadata=r.get("metadata", {}),
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
        )

    def list_cases(
        self,
        department: str,
        state_code: str,
        authorized_district_codes: set[str] | frozenset[str],
        status_filter: str | None = None,
        issue_type_filter: str | None = None,
        assigned_filter: bool | None = None,
        assigned_to_user_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ConsumerIssue], int]:
        districts = sorted(authorized_district_codes)
        if not districts:
            return [], 0

        params: dict[str, str] = {
            "department": f"eq.{department}",
            "state_code": f"eq.{state_code}",
            "jurisdiction_verified": "eq.true",
            "order": "created_at.desc",
            "offset": str(offset),
            "limit": str(limit),
        }

        if len(districts) == 1:
            params["district_code"] = f"eq.{districts[0]}"
        else:
            params["district_code"] = f"in.({','.join(districts)})"

        if status_filter:
            params["status"] = f"eq.{status_filter}"
        if issue_type_filter:
            params["issue_type"] = f"eq.{issue_type_filter}"
        if assigned_filter is True:
            params["assigned_officer_id"] = "not.is.null"
        elif assigned_filter is False:
            params["assigned_officer_id"] = "is.null"
        if assigned_to_user_id:
            params["assigned_officer_id"] = f"eq.{assigned_to_user_id}"

        _, rows = self._request("get", "consumer_issues", headers=self._headers(), params=params)
        cases = [self._map_case_row(r) for r in rows]
        return cases, len(cases)

    def get_case_by_id(self, case_id: str) -> ConsumerIssue | None:
        _, rows = self._request(
            "get",
            "consumer_issues",
            headers=self._headers(),
            params={"id": f"eq.{case_id}", "limit": "1"},
        )
        if not rows:
            return None
        return self._map_case_row(rows[0])

    def save_case(self, case: ConsumerIssue) -> ConsumerIssue:
        payload = {
            "status": case.status,
            "resolution_notes": case.resolution_notes,
            "assigned_officer_id": case.assigned_officer_id,
            "assigned_at": case.assigned_at.isoformat() if case.assigned_at else None,
            "assigned_by": case.assigned_by,
        }
        _, rows = self._request(
            "patch",
            "consumer_issues",
            headers=self._headers(prefer="return=representation"),
            params={"id": f"eq.{case.id}"},
            json=payload,
        )
        if rows:
            return self._map_case_row(rows[0])
        return case

    def _rpc(self, function_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a Supabase database RPC function over REST."""
        url = f"{self.base_url}/rpc/{function_name}"
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=10)
        if resp.status_code >= 400:
            err_msg = ""
            try:
                err_data = resp.json()
                err_msg = err_data.get("message") or err_data.get("details") or resp.text
            except Exception:
                err_msg = resp.text

            logger.error("Supabase RPC error %d on %s: %s", resp.status_code, function_name, err_msg)

            if "CASE_NOT_FOUND" in err_msg:
                raise CaseNotFoundError(err_msg)
            elif "CROSS_OFFICER_ASSIGNMENT_DENIED" in err_msg:
                raise AuthorityJurisdictionDeniedError(err_msg)
            elif "CONCURRENCY_TOKEN_REQUIRED" in err_msg:
                if "status" in err_msg.lower():
                    raise InvalidStatusTransitionError(err_msg, details={"code": "CONCURRENCY_TOKEN_REQUIRED"})
                else:
                    raise InvalidAssignmentError(err_msg, details={"code": "CONCURRENCY_TOKEN_REQUIRED"})
            elif "CONCURRENT_UPDATE_CONFLICT" in err_msg:
                if "status" in err_msg.lower():
                    raise InvalidStatusTransitionError(err_msg, details={"conflict": True})
                else:
                    raise InvalidAssignmentError(err_msg, details={"conflict": True})
            elif "NOTE_EMPTY" in err_msg or "NOTE_TOO_LONG" in err_msg:
                raise InvalidCaseNoteError(err_msg)
            elif "ESTABLISHMENT_NOT_FOUND" in err_msg:
                raise EstablishmentNotFoundError(err_msg)
            elif "ESTABLISHMENT_INACTIVE" in err_msg:
                raise EstablishmentInactiveError(err_msg)
            elif "ESTABLISHMENT_UNVERIFIED" in err_msg:
                raise EstablishmentUnverifiedError(err_msg)
            elif "INVALID_CASE_STATUS" in err_msg:
                raise InvalidStatusTransitionError(err_msg)
            elif "INVALID_PROVENANCE" in err_msg:
                raise InvalidJurisdictionScopeError(err_msg)
            elif "DEPARTMENT_MISMATCH" in err_msg:
                raise AuthorityJurisdictionDeniedError(err_msg)
            elif "ACTOR_JURISDICTION_DENIED" in err_msg or "JURISDICTION_UNVERIFIED" in err_msg or "MALFORMED_JURISDICTION" in err_msg:
                raise AuthorityJurisdictionDeniedError(err_msg)
            elif "ACTOR_UNAUTHORIZED" in err_msg or "ACTOR_MISMATCH" in err_msg:
                raise AuthorityInactiveError(err_msg)
            elif "ACTOR_ROLE_DENIED" in err_msg:
                raise AuthorityRoleDeniedError(err_msg)
            elif "TARGET_" in err_msg:
                raise InvalidAssignmentError(err_msg)
            elif "INVALID_STATUS" in err_msg or "RESOLUTION_NOTES_REQUIRED" in err_msg:
                raise InvalidStatusTransitionError(err_msg)
            resp.raise_for_status()

        try:
            data = resp.json()
            if isinstance(data, dict):
                return data
            return {"data": data}
        except Exception as exc:
            raise RuntimeError(f"Malformed RPC response from {function_name}: {exc}") from exc

    def atomic_assign_officer(
        self,
        case_id: str,
        actor_id: str,
        actor_role: str,
        target_officer_id: str,
        expected_assigned_officer_id: str | None = None,
        expect_unassigned: bool = False,
        enforce_concurrency: bool | None = None,
    ) -> tuple[ConsumerIssue, AuditEvent]:
        payload = {
            "p_case_id": case_id,
            "p_target_officer_id": target_officer_id,
            "p_actor_id": actor_id,
            "p_expected_assigned_officer_id": expected_assigned_officer_id,
            "p_expect_unassigned": bool(expect_unassigned),
        }
        res = self._rpc("authority_assign_case", payload)
        case = self._map_case_row(res["case"])
        audit_event = self._map_audit_row(res["audit_event"])
        return case, audit_event

    def atomic_create_note(
        self,
        case_id: str,
        actor_id: str,
        actor_role: str,
        note_text: str,
    ) -> tuple[InvestigationNote, AuditEvent]:
        payload = {
            "p_case_id": case_id,
            "p_actor_id": actor_id,
            "p_note_text": note_text,
            "p_metadata": {},
        }
        res = self._rpc("authority_create_case_note", payload)
        note = self._map_note_row(res["note"])
        audit_event = self._map_audit_row(res["audit_event"])
        return note, audit_event

    def atomic_transition_status(
        self,
        case_id: str,
        actor_id: str,
        actor_role: str,
        new_status: str,
        resolution_notes: str | None = None,
        expected_status: str | None = None,
    ) -> tuple[ConsumerIssue, AuditEvent]:
        clean_expected = (expected_status or "").strip()
        if not clean_expected:
            raise InvalidStatusTransitionError(
                "CONCURRENCY_TOKEN_REQUIRED: expected_status token is mandatory for status transitions.",
                details={"code": "CONCURRENCY_TOKEN_REQUIRED"},
            )
        payload = {
            "p_case_id": case_id,
            "p_new_status": new_status,
            "p_actor_id": actor_id,
            "p_resolution_notes": resolution_notes,
            "p_expected_status": clean_expected,
        }
        res = self._rpc("authority_transition_status", payload)
        case = self._map_case_row(res["case"])
        audit_event = self._map_audit_row(res["audit_event"])
        return case, audit_event

    def atomic_verify_jurisdiction(
        self,
        case_id: str,
        establishment_id: str,
        actor_id: str,
        actor_role: str,
        provenance: str,
        verification_notes: str | None = None,
        establishment_repo: Any = None,
        authority_repo: Any = None,
    ) -> tuple[ConsumerIssue, AuditEvent]:
        payload = {
            "p_case_id": case_id,
            "p_establishment_id": establishment_id,
            "p_actor_id": actor_id,
            "p_provenance": provenance,
            "p_verification_notes": verification_notes,
        }
        res = self._rpc("authority_verify_complaint_jurisdiction", payload)
        case = self._map_case_row(res["case"])
        audit_event = self._map_audit_row(res["audit_event"])
        return case, audit_event

    def create_note(self, note: InvestigationNote) -> InvestigationNote:
        payload = {
            "id": note.id,
            "issue_id": note.issue_id,
            "author_id": note.author_id,
            "note_text": note.note_text,
            "is_internal": note.is_internal,
        }
        _, rows = self._request(
            "post",
            "consumer_issue_notes",
            headers=self._headers(prefer="return=representation"),
            json=payload,
        )
        if rows:
            return self._map_note_row(rows[0])
        return note

    def list_notes(self, case_id: str) -> list[InvestigationNote]:
        _, rows = self._request(
            "get",
            "consumer_issue_notes",
            headers=self._headers(),
            params={"issue_id": f"eq.{case_id}", "order": "created_at.desc"},
        )
        return [self._map_note_row(r) for r in rows]

    def record_audit_event(self, event: AuditEvent) -> AuditEvent:
        payload = {
            "id": event.id,
            "issue_id": event.issue_id,
            "actor_id": event.actor_id,
            "actor_role": event.actor_role,
            "event_type": event.event_type,
            "previous_state": event.previous_state,
            "new_state": event.new_state,
            "metadata": event.metadata,
        }
        _, rows = self._request(
            "post",
            "consumer_issue_audit_events",
            headers=self._headers(prefer="return=representation"),
            json=payload,
        )
        if rows:
            return self._map_audit_row(rows[0])
        return event

    def list_audit_events(self, case_id: str) -> list[AuditEvent]:
        _, rows = self._request(
            "get",
            "consumer_issue_audit_events",
            headers=self._headers(),
            params={"issue_id": f"eq.{case_id}", "order": "created_at.desc"},
        )
        return [self._map_audit_row(r) for r in rows]

    def clear(self) -> None:
        pass
