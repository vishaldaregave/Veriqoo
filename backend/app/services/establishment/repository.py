"""Repository abstractions and implementations for Retail Establishment Registry."""

from __future__ import annotations

import abc
import copy
from datetime import datetime, timezone
import logging
import threading
from typing import Any

import requests

import uuid

from backend.app.config import Settings, get_settings
from backend.app.services.authority.errors import (
    AuthorityInactiveError,
    AuthorityJurisdictionDeniedError,
)
from backend.app.services.establishment.errors import (
    DuplicateEstablishmentError,
    EstablishmentConcurrencyError,
    EstablishmentNotFoundError,
    EstablishmentRepositoryError,
    InvalidEstablishmentDataError,
)
from backend.app.services.establishment.models import (
    EstablishmentVerificationProvenance,
    EstablishmentVerificationStatus,
    RetailEstablishment,
)

logger = logging.getLogger(__name__)


class EstablishmentRepository(abc.ABC):
    """Abstract repository for persisting and querying retail establishments."""

    @abc.abstractmethod
    def save_establishment(self, establishment: RetailEstablishment) -> RetailEstablishment:
        """Create or update a retail establishment record."""
        pass

    @abc.abstractmethod
    def get_by_id(self, establishment_id: str) -> RetailEstablishment | None:
        """Retrieve an establishment by its unique identifier."""
        pass

    @abc.abstractmethod
    def get_by_gstin(self, gstin: str) -> RetailEstablishment | None:
        """Retrieve an establishment by its 15-character GSTIN."""
        pass

    @abc.abstractmethod
    def list_by_jurisdiction(
        self,
        state_code: str,
        district_code: str | None = None,
        verification_status: str | None = None,
        is_active: bool | None = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RetailEstablishment], int]:
        """List establishments filtered by jurisdiction, verification status, and active state."""
        pass

    @abc.abstractmethod
    def review_establishment_atomic(
        self,
        establishment_id: str,
        action: str,
        actor_id: str,
        expected_status: str,
        notes: str | None = None,
        provenance: str = "MANUAL",
    ) -> tuple[RetailEstablishment, dict[str, Any]]:
        """Atomically review establishment with concurrency locking and audit logging."""
        pass

    @abc.abstractmethod
    def get_audit_events(self, establishment_id: str) -> list[dict[str, Any]]:
        """Retrieve audit history entries for a retail establishment."""
        pass

    @abc.abstractmethod
    def clear(self) -> None:
        """Reset repository state (testing only)."""
        pass


class InMemoryEstablishmentRepository(EstablishmentRepository):
    """Thread-safe in-memory repository for unit testing and local development."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: dict[str, RetailEstablishment] = {}
        self._audit_events: list[dict[str, Any]] = []
        self.simulate_db_error: bool = False
        self.simulate_audit_failure: bool = False

    def save_establishment(self, establishment: RetailEstablishment) -> RetailEstablishment:
        with self._lock:
            if self.simulate_db_error:
                raise EstablishmentRepositoryError("Simulated database failure in establishment repository.")
            if not establishment.trade_name or not establishment.trade_name.strip():
                raise InvalidEstablishmentDataError("Establishment trade_name cannot be empty.")
            if not establishment.state_code or not establishment.district_code:
                raise InvalidEstablishmentDataError("Establishment requires state_code and district_code.")

            # Validate GSTIN uniqueness against other records
            if establishment.gstin and establishment.gstin.strip():
                clean_gstin = establishment.gstin.strip().upper()
                for other_id, other_est in self._items.items():
                    if other_id != establishment.id and other_est.gstin and other_est.gstin.strip().upper() == clean_gstin:
                        raise DuplicateEstablishmentError(
                            f"An establishment with GSTIN '{clean_gstin}' is already registered.",
                            details={"gstin": clean_gstin, "existing_id": other_id},
                        )

            now = datetime.now(timezone.utc)
            establishment.updated_at = now
            self._items[establishment.id] = copy.deepcopy(establishment)
            return copy.deepcopy(establishment)

    def get_by_id(self, establishment_id: str) -> RetailEstablishment | None:
        with self._lock:
            item = self._items.get(establishment_id)
            return copy.deepcopy(item) if item else None

    def get_by_gstin(self, gstin: str) -> RetailEstablishment | None:
        if not gstin:
            return None
        clean_gstin = gstin.strip().upper()
        with self._lock:
            for item in self._items.values():
                if item.gstin and item.gstin.strip().upper() == clean_gstin:
                    return copy.deepcopy(item)
            return None

    def list_by_jurisdiction(
        self,
        state_code: str,
        district_code: str | None = None,
        verification_status: str | None = None,
        is_active: bool | None = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RetailEstablishment], int]:
        clean_state = state_code.strip().upper() if state_code else ""
        clean_dist = district_code.strip().upper() if district_code else None

        with self._lock:
            matched: list[RetailEstablishment] = []
            for item in self._items.values():
                if item.state_code != clean_state:
                    continue
                if clean_dist and item.district_code != clean_dist:
                    continue
                if verification_status and item.verification_status != verification_status:
                    continue
                if is_active is not None and item.is_active != is_active:
                    continue
                matched.append(copy.deepcopy(item))

            matched.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matched)
            paginated = matched[offset : offset + limit]
            return paginated, total

    def review_establishment_atomic(
        self,
        establishment_id: str,
        action: str,
        actor_id: str,
        expected_status: str,
        notes: str | None = None,
        provenance: str = "MANUAL",
    ) -> tuple[RetailEstablishment, dict[str, Any]]:
        with self._lock:
            if self.simulate_db_error:
                raise EstablishmentRepositoryError("Simulated database failure in establishment repository.")

            clean_expected = (expected_status or "").strip().upper()
            if not clean_expected:
                raise InvalidEstablishmentDataError(
                    "CONCURRENCY_TOKEN_REQUIRED: expected_status token is mandatory for establishment review.",
                    details={"code": "CONCURRENCY_TOKEN_REQUIRED"},
                )

            clean_action = (action or "").strip().upper()
            if clean_action not in ("VERIFY", "SUSPEND", "REVOKE"):
                raise InvalidEstablishmentDataError(
                    f"INVALID_REVIEW_ACTION: Action '{action}' is not valid (must be VERIFY, SUSPEND, or REVOKE).",
                    details={"action": action},
                )

            est = self._items.get(establishment_id)
            if not est:
                raise EstablishmentNotFoundError(
                    f"ESTABLISHMENT_NOT_FOUND: Establishment '{establishment_id}' was not found.",
                    details={"establishment_id": establishment_id},
                )

            # Concurrency check: optimistic lock
            if est.verification_status != clean_expected:
                raise EstablishmentConcurrencyError(
                    f"CONCURRENT_UPDATE_CONFLICT: Establishment status is '{est.verification_status}' but expected '{clean_expected}'.",
                    details={
                        "code": "CONCURRENT_UPDATE_CONFLICT",
                        "current_status": est.verification_status,
                        "expected_status": clean_expected,
                        "conflict": True,
                    },
                )

            # Terminal state check
            if est.verification_status == EstablishmentVerificationStatus.REVOKED.value:
                raise InvalidEstablishmentDataError(
                    f"TERMINAL_ESTABLISHMENT_STATE: Establishment '{establishment_id}' is permanently revoked and cannot be transitioned.",
                    details={"code": "TERMINAL_ESTABLISHMENT_STATE"},
                )

            # Lifecycle transition check
            if est.verification_status == EstablishmentVerificationStatus.PENDING.value and clean_action == "SUSPEND":
                raise InvalidEstablishmentDataError(
                    f"INVALID_LIFECYCLE_TRANSITION: Cannot suspend establishment '{establishment_id}' from PENDING status.",
                    details={"code": "INVALID_LIFECYCLE_TRANSITION"},
                )

            now = datetime.now(timezone.utc)
            updated_est = copy.deepcopy(est)
            prev_status = est.verification_status
            prev_active = est.is_active

            if clean_action == "VERIFY":
                updated_est.verification_status = EstablishmentVerificationStatus.VERIFIED.value
                updated_est.is_active = True
                updated_est.verification_provenance = provenance.strip().upper() if provenance else "MANUAL"
                updated_est.verification_authority_id = actor_id
                updated_est.verification_date = now
            elif clean_action == "SUSPEND":
                updated_est.verification_status = EstablishmentVerificationStatus.SUSPENDED.value
                updated_est.is_active = False
            elif clean_action == "REVOKE":
                updated_est.verification_status = EstablishmentVerificationStatus.REVOKED.value
                updated_est.is_active = False

            updated_est.updated_by = actor_id
            updated_est.updated_at = now
            if notes is not None:
                updated_est.verification_notes = notes.strip() if notes else None

            event_id = str(uuid.uuid4())
            audit_event = {
                "id": event_id,
                "establishment_id": establishment_id,
                "actor_id": actor_id,
                "actor_role": "authority",
                "action": clean_action,
                "event_type": f"ESTABLISHMENT_{clean_action}",
                "previous_status": prev_status,
                "new_status": updated_est.verification_status,
                "previous_is_active": prev_active,
                "new_is_active": updated_est.is_active,
                "notes": updated_est.verification_notes,
                "provenance": updated_est.verification_provenance,
                "metadata": {
                    "actor_id": actor_id,
                    "action": clean_action,
                    "previous_status": prev_status,
                    "new_status": updated_est.verification_status,
                    "previous_is_active": prev_active,
                    "new_is_active": updated_est.is_active,
                    "notes": updated_est.verification_notes,
                    "provenance": updated_est.verification_provenance,
                    "timestamp": now.isoformat(),
                },
                "created_at": now.isoformat(),
            }

            # Transactional behavior: simulate rollback on audit persistence failure
            if self.simulate_audit_failure:
                raise EstablishmentRepositoryError("Simulated audit event persistence failure - rolling back.")

            self._items[establishment_id] = updated_est
            self._audit_events.append(audit_event)
            return copy.deepcopy(updated_est), audit_event

    def get_audit_events(self, establishment_id: str) -> list[dict[str, Any]]:
        with self._lock:
            matched = [
                copy.deepcopy(e)
                for e in self._audit_events
                if e.get("establishment_id") == establishment_id
            ]
            matched.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return matched

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._audit_events.clear()


class SupabaseEstablishmentRepository(EstablishmentRepository):
    """Supabase REST API implementation for retail establishments."""

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
        try:
            resp = requests.request(method, url, timeout=10, **kwargs)
        except Exception as exc:
            logger.error("Supabase API connection error on %s %s: %s", method, url, exc)
            raise EstablishmentRepositoryError(f"Database connection error: {exc}") from exc

        if resp.status_code >= 400:
            err_text = resp.text
            logger.error("Supabase API error %d on %s %s: %s", resp.status_code, method, url, err_text)
            if resp.status_code == 409 or "retail_establishments_gstin_key" in err_text or "23505" in err_text or "duplicate key" in err_text:
                raise DuplicateEstablishmentError(
                    "An establishment with this GSTIN is already registered.",
                    details={"db_error": err_text, "status_code": resp.status_code},
                )
            if resp.status_code >= 500:
                raise EstablishmentRepositoryError(
                    f"Database failure ({resp.status_code}): {err_text}",
                    details={"db_error": err_text, "status_code": resp.status_code},
                )
            resp.raise_for_status()
        if not resp.text or resp.text.strip() == "":
            return resp.status_code, []
        try:
            data = resp.json()
            items = data if isinstance(data, list) else [data]
            return resp.status_code, items
        except Exception:
            return resp.status_code, []

    def _map_row(self, r: dict[str, Any]) -> RetailEstablishment:
        return RetailEstablishment(
            id=str(r["id"]),
            trade_name=r["trade_name"],
            legal_name=r.get("legal_name"),
            gstin=r.get("gstin"),
            lm_license_number=r.get("lm_license_number"),
            shop_establishment_number=r.get("shop_establishment_number"),
            state_code=str(r.get("state_code", "")),
            district_code=str(r.get("district_code", "")),
            pincode=r.get("pincode"),
            physical_address=r.get("physical_address"),
            verification_status=r.get("verification_status", EstablishmentVerificationStatus.PENDING.value),
            verification_provenance=r.get("verification_provenance", EstablishmentVerificationProvenance.MANUAL.value),
            verification_authority_id=str(r["verification_authority_id"]) if r.get("verification_authority_id") else None,
            verification_date=datetime.fromisoformat(r["verification_date"].replace("Z", "+00:00")) if r.get("verification_date") else None,
            verification_notes=r.get("verification_notes"),
            is_active=bool(r.get("is_active", True)),
            created_by=str(r["created_by"]) if r.get("created_by") else None,
            updated_by=str(r["updated_by"]) if r.get("updated_by") else None,
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
        )

    def save_establishment(self, establishment: RetailEstablishment) -> RetailEstablishment:
        existing = self.get_by_id(establishment.id)
        is_update = existing is not None

        payload = {
            "id": establishment.id,
            "trade_name": establishment.trade_name,
            "legal_name": establishment.legal_name,
            "gstin": establishment.gstin,
            "lm_license_number": establishment.lm_license_number,
            "shop_establishment_number": establishment.shop_establishment_number,
            "state_code": establishment.state_code,
            "district_code": establishment.district_code,
            "pincode": establishment.pincode,
            "physical_address": establishment.physical_address,
            "verification_status": establishment.verification_status,
            "verification_provenance": establishment.verification_provenance,
            "verification_authority_id": establishment.verification_authority_id,
            "verification_date": establishment.verification_date.isoformat() if establishment.verification_date else None,
            "verification_notes": establishment.verification_notes,
            "is_active": establishment.is_active,
            "created_by": establishment.created_by,
            "updated_by": establishment.updated_by,
        }

        if is_update:
            # Explicit UPDATE targeting record by primary key (preserves unique constraints, no blind merge)
            status_code, rows = self._request(
                "patch",
                "retail_establishments",
                headers=self._headers(prefer="return=representation"),
                params={"id": f"eq.{establishment.id}"},
                json=payload,
            )
        else:
            # Explicit CREATE inserting new record
            status_code, rows = self._request(
                "post",
                "retail_establishments",
                headers=self._headers(prefer="return=representation"),
                json=payload,
            )

        if rows:
            return self._map_row(rows[0])
        return establishment

    def get_by_id(self, establishment_id: str) -> RetailEstablishment | None:
        _, rows = self._request(
            "get",
            "retail_establishments",
            headers=self._headers(),
            params={"id": f"eq.{establishment_id}", "limit": "1"},
        )
        if not rows:
            return None
        return self._map_row(rows[0])

    def get_by_gstin(self, gstin: str) -> RetailEstablishment | None:
        if not gstin:
            return None
        clean_gstin = gstin.strip().upper()
        _, rows = self._request(
            "get",
            "retail_establishments",
            headers=self._headers(),
            params={"gstin": f"eq.{clean_gstin}", "limit": "1"},
        )
        if not rows:
            return None
        return self._map_row(rows[0])

    def list_by_jurisdiction(
        self,
        state_code: str,
        district_code: str | None = None,
        verification_status: str | None = None,
        is_active: bool | None = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RetailEstablishment], int]:
        params = {
            "state_code": f"eq.{state_code.strip().upper()}",
            "order": "created_at.desc",
            "offset": str(offset),
            "limit": str(limit),
        }
        if district_code:
            params["district_code"] = f"eq.{district_code.strip().upper()}"
        if verification_status:
            params["verification_status"] = f"eq.{verification_status}"
        if is_active is not None:
            params["is_active"] = f"eq.{str(is_active).lower()}"

        _, rows = self._request(
            "get",
            "retail_establishments",
            headers=self._headers(),
            params=params,
        )
        items = [self._map_row(r) for r in rows]
        return items, len(items)

    def _rpc(self, function_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a Supabase database RPC function over REST."""
        url = f"{self.base_url}/rpc/{function_name}"
        try:
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=10)
        except Exception as exc:
            logger.error("Supabase API connection error on RPC %s: %s", function_name, exc)
            raise EstablishmentRepositoryError(f"Database connection error: {exc}") from exc

        if resp.status_code >= 400:
            err_msg = ""
            try:
                err_data = resp.json()
                err_msg = err_data.get("message") or err_data.get("details") or resp.text
            except Exception:
                err_msg = resp.text

            logger.error("Supabase RPC error %d on %s: %s", resp.status_code, function_name, err_msg)

            if "ESTABLISHMENT_NOT_FOUND" in err_msg:
                raise EstablishmentNotFoundError(err_msg)
            elif "ACTOR_JURISDICTION_DENIED" in err_msg:
                raise AuthorityJurisdictionDeniedError(err_msg)
            elif "ACTOR_UNAUTHORIZED" in err_msg or "ACTOR_ROLE_DENIED" in err_msg:
                raise AuthorityInactiveError(err_msg)
            elif "CONCURRENCY_TOKEN_REQUIRED" in err_msg:
                raise InvalidEstablishmentDataError(err_msg, details={"code": "CONCURRENCY_TOKEN_REQUIRED"})
            elif "CONCURRENT_UPDATE_CONFLICT" in err_msg:
                raise EstablishmentConcurrencyError(err_msg, details={"code": "CONCURRENT_UPDATE_CONFLICT", "conflict": True})
            elif "TERMINAL_ESTABLISHMENT_STATE" in err_msg or "INVALID_LIFECYCLE_TRANSITION" in err_msg or "INVALID_REVIEW_ACTION" in err_msg:
                raise InvalidEstablishmentDataError(err_msg)
            elif resp.status_code >= 500:
                raise EstablishmentRepositoryError(f"Database failure ({resp.status_code}): {err_msg}")
            else:
                resp.raise_for_status()

        return resp.json()

    def review_establishment_atomic(
        self,
        establishment_id: str,
        action: str,
        actor_id: str,
        expected_status: str,
        notes: str | None = None,
        provenance: str = "MANUAL",
    ) -> tuple[RetailEstablishment, dict[str, Any]]:
        clean_expected = (expected_status or "").strip().upper()
        if not clean_expected:
            raise InvalidEstablishmentDataError(
                "CONCURRENCY_TOKEN_REQUIRED: expected_status token is mandatory for establishment review.",
                details={"code": "CONCURRENCY_TOKEN_REQUIRED"},
            )
        payload = {
            "p_establishment_id": establishment_id,
            "p_action": (action or "").strip().upper(),
            "p_actor_id": actor_id,
            "p_expected_status": clean_expected,
            "p_notes": notes.strip() if notes else None,
            "p_provenance": (provenance or "MANUAL").strip().upper(),
        }
        res = self._rpc("authority_review_establishment", payload)
        est = self._map_row(res["establishment"])
        audit_event = res["audit_event"]
        return est, audit_event

    def get_audit_events(self, establishment_id: str) -> list[dict[str, Any]]:
        params = {
            "establishment_id": f"eq.{establishment_id}",
            "order": "created_at.desc",
        }
        _, rows = self._request(
            "get",
            "retail_establishment_audit_events",
            headers=self._headers(),
            params=params,
        )
        return rows

    def clear(self) -> None:
        pass
