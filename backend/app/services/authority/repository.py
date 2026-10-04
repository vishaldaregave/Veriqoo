"""Repository interface and in-memory implementation for authority profiles (T3-4 Phase 2)."""

from __future__ import annotations

from abc import ABC, abstractmethod
import threading
from typing import Any

from backend.app.services.authority.models import AuthorityProfile


class AuthorityRepository(ABC):
    """Abstract persistence interface for authority profiles."""

    @abstractmethod
    def get_by_user_id(self, user_id: str) -> AuthorityProfile | None:
        """Retrieve authority profile by Supabase user UUID."""
        raise NotImplementedError

    @abstractmethod
    def save(self, profile: AuthorityProfile) -> AuthorityProfile:
        """Persist or update an authority profile."""
        raise NotImplementedError

    @abstractmethod
    def delete_by_user_id(self, user_id: str) -> bool:
        """Delete an authority profile."""
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """Reset repository state (primarily used in testing)."""
        raise NotImplementedError


class InMemoryAuthorityRepository(AuthorityRepository):
    """Thread-safe in-memory implementation of AuthorityRepository."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._profiles: dict[str, AuthorityProfile] = {}

    def get_by_user_id(self, user_id: str) -> AuthorityProfile | None:
        with self._lock:
            return self._profiles.get(user_id)

    def save(self, profile: AuthorityProfile) -> AuthorityProfile:
        with self._lock:
            self._profiles[profile.user_id] = profile
            return profile

    def delete_by_user_id(self, user_id: str) -> bool:
        with self._lock:
            if user_id in self._profiles:
                del self._profiles[user_id]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._profiles.clear()


class SupabaseAuthorityRepository(AuthorityRepository):
    """Supabase REST API implementation for authority profiles persistence."""

    def __init__(self, settings: Any | None = None) -> None:
        from backend.app.config import get_settings
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

    def _request(self, method: str, table: str, **kwargs: Any) -> list[dict[str, Any]]:
        import requests
        import logging
        url = f"{self.base_url}/{table}"
        resp = requests.request(method, url, timeout=10, **kwargs)
        if resp.status_code >= 400:
            logging.getLogger(__name__).error("Supabase API error %d on %s %s: %s", resp.status_code, method, url, resp.text)
            resp.raise_for_status()
        if not resp.text or resp.text.strip() == "":
            return []
        try:
            data = resp.json()
            return data if isinstance(data, list) else [data]
        except Exception:
            return []

    def _map_row(self, r: dict[str, Any]) -> AuthorityProfile:
        from datetime import datetime
        from backend.app.services.authority.models import (
            JurisdictionLevel,
            JurisdictionScope,
        )
        try:
            scope = JurisdictionScope(
                state_code=str(r["state_code"]),
                level=str(r.get("jurisdiction_level", JurisdictionLevel.DISTRICT.value)),
                authorized_district_codes=r.get("authorized_district_codes", []),
            )
            return AuthorityProfile(
                id=str(r["id"]),
                user_id=str(r["user_id"]),
                department=str(r["department"]),
                designation=str(r["designation"]),
                badge_number=r.get("badge_number"),
                jurisdiction=scope,
                is_active=bool(r.get("is_active", True)),
                created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Failed to map authority profile row: %s", exc)
            raise ValueError(f"Malformed authority profile data in database: {exc}") from exc

    def get_by_user_id(self, user_id: str) -> AuthorityProfile | None:
        rows = self._request(
            "get",
            "authority_profiles",
            headers=self._headers(),
            params={"user_id": f"eq.{user_id}", "limit": "1"},
        )
        if not rows:
            return None
        return self._map_row(rows[0])

    def save(self, profile: AuthorityProfile) -> AuthorityProfile:
        payload = {
            "id": profile.id,
            "user_id": profile.user_id,
            "department": profile.department,
            "designation": profile.designation,
            "badge_number": profile.badge_number,
            "state_code": profile.jurisdiction.state_code,
            "jurisdiction_level": profile.jurisdiction.level.value,
            "authorized_district_codes": sorted(profile.jurisdiction.authorized_district_codes),
            "is_active": profile.is_active,
        }
        res = self._request(
            "post",
            "authority_profiles",
            headers=self._headers(prefer="resolution=merge-duplicates,return=representation"),
            json=payload,
        )
        if res:
            return self._map_row(res[0])
        return profile

    def delete_by_user_id(self, user_id: str) -> bool:
        self._request(
            "delete",
            "authority_profiles",
            headers=self._headers(),
            params={"user_id": f"eq.{user_id}"},
        )
        return True

    def clear(self) -> None:
        pass

