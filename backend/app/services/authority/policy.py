"""Authority access control and jurisdiction evaluation policy (T3-4 Phase 2)."""

from __future__ import annotations

import logging
from backend.app.services.authority.errors import (
    AuthorityInactiveError,
    AuthorityJurisdictionDeniedError,
    InvalidJurisdictionScopeError,
)
from backend.app.services.authority.models import AuthorityPrincipal, CaseJurisdiction

logger = logging.getLogger(__name__)


class AuthorityAccessPolicy:
    """Enforces jurisdiction boundaries and department isolation for authority actions.

    Follows a strict default-deny evaluation order:
    1. Active status check
    2. Valid case jurisdiction structure check
    3. Department match check
    4. State match check
    5. Authorized district membership check
    """

    @staticmethod
    def can_access_case(
        authority: AuthorityPrincipal,
        case_jurisdiction: CaseJurisdiction | None,
    ) -> bool:
        """Evaluate whether the given authority principal is authorized to access the case."""
        if not authority or not authority.is_active:
            logger.warning("Access denied: Authority principal is missing or inactive (%s).", getattr(authority, "user_id", None))
            return False

        if case_jurisdiction is None or not case_jurisdiction.is_valid():
            logger.warning("Access denied: Case jurisdiction is missing or malformed.")
            return False

        # 1. Department Isolation Check
        if case_jurisdiction.department != authority.department:
            logger.warning(
                "Access denied: Department mismatch. Authority='%s', Case='%s'.",
                authority.department,
                case_jurisdiction.department,
            )
            return False

        # 2. State-level Scope Check
        if case_jurisdiction.state_code != authority.jurisdiction.state_code:
            logger.warning(
                "Access denied: State mismatch. Authority State='%s', Case State='%s'.",
                authority.jurisdiction.state_code,
                case_jurisdiction.state_code,
            )
            return False

        # 3. Explicit District Authorization Check
        if case_jurisdiction.district_code not in authority.jurisdiction.authorized_district_codes:
            logger.warning(
                "Access denied: District '%s' not in authorized districts %s for authority '%s'.",
                case_jurisdiction.district_code,
                sorted(authority.jurisdiction.authorized_district_codes),
                authority.user_id,
            )
            return False

        return True

    @staticmethod
    def enforce_case_access(
        authority: AuthorityPrincipal,
        case_jurisdiction: CaseJurisdiction | None,
    ) -> None:
        """Assert authority case access; raises specific AuthorityError on denial."""
        if not authority or not authority.is_active:
            raise AuthorityInactiveError(
                f"Authority user '{getattr(authority, 'user_id', 'unknown')}' is inactive or unprovisioned.",
                details={"user_id": getattr(authority, "user_id", None)},
            )

        if case_jurisdiction is None or not case_jurisdiction.is_valid():
            raise InvalidJurisdictionScopeError(
                "Case jurisdiction is missing, empty, or malformed.",
                details={"case_jurisdiction": str(case_jurisdiction)},
            )

        if case_jurisdiction.department != authority.department:
            raise AuthorityJurisdictionDeniedError(
                f"Authority in department '{authority.department}' cannot access case in department '{case_jurisdiction.department}'.",
                details={
                    "authority_department": authority.department,
                    "case_department": case_jurisdiction.department,
                },
            )

        if case_jurisdiction.state_code != authority.jurisdiction.state_code:
            raise AuthorityJurisdictionDeniedError(
                f"Authority in state '{authority.jurisdiction.state_code}' cannot access case in state '{case_jurisdiction.state_code}'.",
                details={
                    "authority_state": authority.jurisdiction.state_code,
                    "case_state": case_jurisdiction.state_code,
                },
            )

        if case_jurisdiction.district_code not in authority.jurisdiction.authorized_district_codes:
            raise AuthorityJurisdictionDeniedError(
                f"Authority is not authorized for district '{case_jurisdiction.district_code}'.",
                details={
                    "district_code": case_jurisdiction.district_code,
                    "authorized_districts": sorted(authority.jurisdiction.authorized_district_codes),
                },
            )
