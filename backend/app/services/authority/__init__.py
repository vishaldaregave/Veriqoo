"""Authority Dashboard & Access Control Module (T3-4 Phase 2)."""

from backend.app.services.authority.errors import (
    AuthorityAccessDeniedError,
    AuthorityError,
    AuthorityInactiveError,
    AuthorityJurisdictionDeniedError,
    AuthorityNotProvisionedError,
    InvalidJurisdictionScopeError,
)
from backend.app.services.authority.models import (
    AuthorityPrincipal,
    AuthorityProfile,
    CaseJurisdiction,
    DepartmentCode,
    JurisdictionLevel,
    JurisdictionScope,
)
from backend.app.services.authority.policy import AuthorityAccessPolicy
from backend.app.services.authority.repository import (
    AuthorityRepository,
    InMemoryAuthorityRepository,
)
from backend.app.services.authority.service import AuthorityService

__all__ = [
    "AuthorityAccessDeniedError",
    "AuthorityError",
    "AuthorityInactiveError",
    "AuthorityJurisdictionDeniedError",
    "AuthorityNotProvisionedError",
    "InvalidJurisdictionScopeError",
    "AuthorityPrincipal",
    "AuthorityProfile",
    "CaseJurisdiction",
    "DepartmentCode",
    "JurisdictionLevel",
    "JurisdictionScope",
    "AuthorityAccessPolicy",
    "AuthorityRepository",
    "InMemoryAuthorityRepository",
    "AuthorityService",
]
