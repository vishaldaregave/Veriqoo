"""Domain models and value objects for Authority Dashboard & Access Control (T3-4 Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class JurisdictionLevel(str, Enum):
    """Hierarchical level of authority jurisdiction."""
    DISTRICT = "DISTRICT"
    STATE = "STATE"


class DepartmentCode(str, Enum):
    """Standardized departmental identifiers."""
    LEGAL_METROLOGY = "LEGAL_METROLOGY"
    FOOD_SAFETY = "FOOD_SAFETY"
    CONSUMER_AFFAIRS = "CONSUMER_AFFAIRS"
    WEIGHTS_AND_MEASURES = "WEIGHTS_AND_MEASURES"


@dataclass(frozen=True)
class JurisdictionScope:
    """Geographic and departmental scope assigned to an authority principal.

    Represents explicit state and district boundaries.
    Wildcards and global access are strictly prohibited.
    """
    state_code: str
    level: JurisdictionLevel
    authorized_district_codes: frozenset[str]

    def __init__(
        self,
        state_code: str,
        level: JurisdictionLevel | str,
        authorized_district_codes: set[str] | list[str] | frozenset[str],
    ) -> None:
        clean_state = state_code.strip().upper() if state_code else ""
        if not clean_state:
            raise ValueError("JurisdictionScope requires a non-empty state_code.")

        resolved_level = JurisdictionLevel(level) if isinstance(level, str) else level

        clean_districts = {
            d.strip().upper()
            for d in authorized_district_codes
            if isinstance(d, str) and d.strip()
        }
        if not clean_districts:
            raise ValueError("JurisdictionScope requires at least one authorized district code.")

        object.__setattr__(self, "state_code", clean_state)
        object.__setattr__(self, "level", resolved_level)
        object.__setattr__(self, "authorized_district_codes", frozenset(clean_districts))


@dataclass(frozen=True)
class CaseJurisdiction:
    """Territorial and departmental location tags associated with an inspection or complaint."""
    department: str
    state_code: str
    district_code: str

    def __init__(self, department: str, state_code: str, district_code: str) -> None:
        clean_dept = department.strip().upper() if department else ""
        clean_state = state_code.strip().upper() if state_code else ""
        clean_dist = district_code.strip().upper() if district_code else ""

        object.__setattr__(self, "department", clean_dept)
        object.__setattr__(self, "state_code", clean_state)
        object.__setattr__(self, "district_code", clean_dist)

    def is_valid(self) -> bool:
        """Verify that case jurisdiction contains non-empty identifiers for all dimensions."""
        return bool(self.department and self.state_code and self.district_code)


@dataclass
class AuthorityProfile:
    """Authority officer profile entity representing administrative credentials and jurisdiction."""
    user_id: str
    department: str
    designation: str
    jurisdiction: JurisdictionScope
    is_active: bool = True
    badge_number: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.department = self.department.strip().upper()
        self.designation = self.designation.strip()


@dataclass(frozen=True)
class AuthorityPrincipal:
    """Authenticated and authorized authority context injected into API endpoints.

    Contains verified identity, role, department, and jurisdiction scope.
    """
    user_id: str
    email: str | None
    app_role: str
    department: str
    designation: str
    jurisdiction: JurisdictionScope
    is_active: bool = True
    badge_number: str | None = None


@dataclass
class InvestigationNote:
    """Confidential internal investigation note for an authority case."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issue_id: str = ""
    author_id: str = ""
    note_text: str = ""
    is_internal: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.created_at and self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.updated_at and self.updated_at.tzinfo is None:
            self.updated_at = self.updated_at.replace(tzinfo=timezone.utc)


class AuditEventType(str, Enum):
    """Event types recorded in case audit history."""
    CASE_ASSIGNED = "CASE_ASSIGNED"
    CASE_REASSIGNED = "CASE_REASSIGNED"
    NOTE_ADDED = "NOTE_ADDED"
    STATUS_CHANGED = "STATUS_CHANGED"
    JURISDICTION_VERIFIED = "JURISDICTION_VERIFIED"


@dataclass
class AuditEvent:
    """Case audit log entry for statutory and administrative traceability."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issue_id: str | None = None
    actor_id: str = ""
    actor_role: str = ""
    event_type: str = AuditEventType.STATUS_CHANGED.value
    previous_state: str | None = None
    new_state: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.created_at and self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
