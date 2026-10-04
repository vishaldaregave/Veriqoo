"""Service layer coordinating Retail Establishment onboarding and administrative review (Phase 7.4.2)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from backend.app.services.authority.errors import (
    AuthorityInactiveError,
    AuthorityJurisdictionDeniedError,
)
from backend.app.services.authority.models import AuthorityPrincipal
from backend.app.services.consumer_issues.jurisdiction import validate_canonical_jurisdiction
from backend.app.services.establishment.errors import (
    DuplicateEstablishmentError,
    EstablishmentInactiveError,
    EstablishmentNotFoundError,
    EstablishmentUnverifiedError,
    InvalidEstablishmentDataError,
)
from backend.app.services.establishment.models import (
    EstablishmentVerificationProvenance,
    EstablishmentVerificationStatus,
    RetailEstablishment,
)
from backend.app.services.establishment.repository import EstablishmentRepository
from backend.app.services.establishment.schemas import CreateEstablishmentRequest

logger = logging.getLogger(__name__)


class EstablishmentService:
    """Business logic coordinator for retail establishment registration, review, and lookup."""

    def __init__(self, repository: EstablishmentRepository) -> None:
        self.repo = repository

    def _enforce_active_authority(self, authority: AuthorityPrincipal) -> None:
        if not authority or not authority.is_active:
            raise AuthorityInactiveError(
                f"Authority user '{getattr(authority, 'user_id', 'unknown')}' is inactive or unprovisioned.",
                details={"user_id": getattr(authority, "user_id", None)},
            )

    def create_establishment(
        self,
        authority: AuthorityPrincipal,
        data: CreateEstablishmentRequest,
    ) -> RetailEstablishment:
        """Onboard a new commercial premises in PENDING status."""
        self._enforce_active_authority(authority)

        # 1. Canonical state and LGD district validation
        can_state, can_dist, is_valid = validate_canonical_jurisdiction(
            state_code=data.state_code,
            district_code=data.district_code,
        )
        if not is_valid or not can_state or not can_dist:
            raise InvalidEstablishmentDataError(
                f"Invalid or non-canonical jurisdiction: state='{data.state_code}', district='{data.district_code}'.",
                details={"state_code": data.state_code, "district_code": data.district_code},
            )

        # 2. Strict jurisdiction boundary: officer can only onboard within their jurisdiction
        if authority.jurisdiction.state_code != can_state:
            raise AuthorityJurisdictionDeniedError(
                f"Officer state '{authority.jurisdiction.state_code}' does not match establishment state '{can_state}'.",
                details={"officer_state": authority.jurisdiction.state_code, "target_state": can_state},
            )

        if can_dist not in authority.jurisdiction.authorized_district_codes:
            raise AuthorityJurisdictionDeniedError(
                f"District '{can_dist}' is not in officer's authorized districts {set(authority.jurisdiction.authorized_district_codes)}.",
                details={"target_district": can_dist, "authorized_districts": list(authority.jurisdiction.authorized_district_codes)},
            )

        # 3. Check for existing GSTIN conflict
        if data.gstin and data.gstin.strip():
            clean_gstin = data.gstin.strip().upper()
            existing = self.repo.get_by_gstin(clean_gstin)
            if existing:
                raise DuplicateEstablishmentError(
                    f"An establishment with GSTIN '{clean_gstin}' is already registered.",
                    details={"gstin": clean_gstin, "existing_id": existing.id},
                )

        est = RetailEstablishment(
            trade_name=data.trade_name.strip(),
            legal_name=data.legal_name.strip() if data.legal_name else None,
            gstin=data.gstin.strip().upper() if data.gstin else None,
            lm_license_number=data.lm_license_number.strip() if data.lm_license_number else None,
            shop_establishment_number=data.shop_establishment_number.strip() if data.shop_establishment_number else None,
            state_code=can_state,
            district_code=can_dist,
            pincode=data.pincode.strip() if data.pincode else None,
            physical_address=data.physical_address.strip() if data.physical_address else None,
            verification_status=EstablishmentVerificationStatus.PENDING.value,
            verification_provenance=EstablishmentVerificationProvenance.MANUAL.value,
            is_active=True,
            created_by=authority.user_id,
        )

        return self.repo.save_establishment(est)

    def review_establishment(
        self,
        authority: AuthorityPrincipal,
        establishment_id: str,
        action: str,
        expected_status: str | None = None,
        notes: str | None = None,
        provenance: str = "MANUAL",
    ) -> tuple[RetailEstablishment, dict[str, Any]]:
        """Administrative review action to VERIFY, SUSPEND, or REVOKE an establishment with atomic concurrency and audit logging."""
        self._enforce_active_authority(authority)

        clean_expected = (expected_status or "").strip().upper()
        if not clean_expected:
            raise InvalidEstablishmentDataError(
                "CONCURRENCY_TOKEN_REQUIRED: expected_status token is mandatory for establishment review.",
                details={"code": "CONCURRENCY_TOKEN_REQUIRED"},
            )

        est = self.repo.get_by_id(establishment_id)
        if not est:
            raise EstablishmentNotFoundError(
                f"Establishment '{establishment_id}' was not found.",
                details={"establishment_id": establishment_id},
            )

        # Enforce jurisdiction scope
        if authority.jurisdiction.state_code != est.state_code or est.district_code not in authority.jurisdiction.authorized_district_codes:
            raise AuthorityJurisdictionDeniedError(
                f"Officer is not authorized to review establishment in {est.state_code}/{est.district_code}.",
                details={"establishment_id": establishment_id, "establishment_state": est.state_code, "establishment_district": est.district_code},
            )

        clean_action = (action or "").strip().upper()
        if clean_action not in ("VERIFY", "SUSPEND", "REVOKE"):
            raise InvalidEstablishmentDataError(
                f"Invalid review action '{action}'. Must be VERIFY, SUSPEND, or REVOKE.",
                details={"action": action},
            )

        return self.repo.review_establishment_atomic(
            establishment_id=establishment_id,
            action=clean_action,
            actor_id=authority.user_id,
            expected_status=clean_expected,
            notes=notes.strip() if notes else None,
            provenance=provenance,
        )

    def get_establishment(
        self,
        authority: AuthorityPrincipal,
        establishment_id: str,
    ) -> RetailEstablishment:
        """Retrieve establishment details bounded by authority jurisdiction."""
        self._enforce_active_authority(authority)

        est = self.repo.get_by_id(establishment_id)
        if not est:
            raise EstablishmentNotFoundError(
                f"Establishment '{establishment_id}' was not found.",
                details={"establishment_id": establishment_id},
            )

        # Officer can view if in jurisdiction OR if verified and active
        if authority.jurisdiction.state_code == est.state_code and est.district_code in authority.jurisdiction.authorized_district_codes:
            return est

        if est.verification_status == EstablishmentVerificationStatus.VERIFIED.value and est.is_active:
            return est

        raise AuthorityJurisdictionDeniedError(
            f"Officer is not authorized to view establishment '{establishment_id}'.",
            details={"establishment_id": establishment_id},
        )

    def list_establishments(
        self,
        authority: AuthorityPrincipal,
        district_code: str | None = None,
        verification_status: str | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RetailEstablishment], int]:
        """List establishments bounded by officer's authorized state and districts."""
        self._enforce_active_authority(authority)

        clean_dist = district_code.strip().upper() if district_code else None
        if clean_dist and clean_dist not in authority.jurisdiction.authorized_district_codes:
            raise AuthorityJurisdictionDeniedError(
                f"District '{clean_dist}' is not in officer's authorized districts.",
                details={"requested_district": clean_dist},
            )

        items, total = self.repo.list_by_jurisdiction(
            state_code=authority.jurisdiction.state_code,
            district_code=clean_dist,
            verification_status=verification_status,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )

        # Filter to only authorized districts if no specific district requested
        if not clean_dist:
            items = [
                i for i in items
                if i.district_code in authority.jurisdiction.authorized_district_codes
            ]
            total = len(items)

        return items, total
