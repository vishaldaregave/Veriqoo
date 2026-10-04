"""Repository abstractions and implementations for User Profiles."""

from __future__ import annotations

import abc
from datetime import datetime, timezone
import logging
import threading
from typing import Any

import requests

from backend.app.config import Settings, get_settings
from backend.app.services.user_profile.models import UserProfile

logger = logging.getLogger(__name__)


class UserProfileRepository(abc.ABC):
    """Abstract repository for persisting user profiles."""

    @abc.abstractmethod
    def get_by_user_id(self, user_id: str) -> UserProfile | None:
        """Retrieve user profile by Supabase user UUID."""
        pass

    @abc.abstractmethod
    def create_profile(self, profile: UserProfile) -> UserProfile:
        """Create a new user profile record."""
        pass

    @abc.abstractmethod
    def update_profile(self, user_id: str, updates: dict[str, Any]) -> UserProfile | None:
        """Update fields of an existing user profile."""
        pass


class InMemoryUserProfileRepository(UserProfileRepository):
    """Thread-safe in-memory user profile repository for testing and development."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._profiles_by_user_id: dict[str, UserProfile] = {}

    def get_by_user_id(self, user_id: str) -> UserProfile | None:
        with self._lock:
            return self._profiles_by_user_id.get(user_id)

    def create_profile(self, profile: UserProfile) -> UserProfile:
        with self._lock:
            self._profiles_by_user_id[profile.user_id] = profile
            return profile

    def update_profile(self, user_id: str, updates: dict[str, Any]) -> UserProfile | None:
        with self._lock:
            profile = self._profiles_by_user_id.get(user_id)
            if not profile:
                return None
            if "display_name" in updates:
                profile.display_name = updates["display_name"]
            if "language_preference" in updates and updates["language_preference"] is not None:
                profile.language_preference = updates["language_preference"]
            profile.updated_at = datetime.now(timezone.utc)
            return profile

    def clear(self) -> None:
        with self._lock:
            self._profiles_by_user_id.clear()


class SupabaseUserProfileRepository(UserProfileRepository):
    """Supabase REST API implementation for user profile persistence."""

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

    def _request(self, method: str, table: str, **kwargs: Any) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{table}"
        resp = requests.request(method, url, timeout=10, **kwargs)
        if resp.status_code >= 400:
            logger.error("Supabase API error %d on %s %s: %s", resp.status_code, method, url, resp.text)
            resp.raise_for_status()
        if not resp.text or resp.text.strip() == "":
            return []
        try:
            data = resp.json()
            return data if isinstance(data, list) else [data]
        except Exception:
            return []

    def get_by_user_id(self, user_id: str) -> UserProfile | None:
        rows = self._request(
            "get",
            "user_profiles",
            headers=self._headers(),
            params={"user_id": f"eq.{user_id}", "limit": "1"},
        )
        if not rows:
            return None
        r = rows[0]
        return UserProfile(
            id=str(r["id"]),
            user_id=str(r["user_id"]),
            display_name=r.get("display_name"),
            language_preference=r.get("language_preference", "en"),
            app_role=r.get("app_role", "consumer"),
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
        )

    def create_profile(self, profile: UserProfile) -> UserProfile:
        payload = {
            "user_id": profile.user_id,
            "display_name": profile.display_name,
            "language_preference": profile.language_preference,
            "app_role": profile.app_role,
        }
        res = self._request(
            "post",
            "user_profiles",
            headers=self._headers(prefer="return=representation"),
            json=payload,
        )
        if res:
            r = res[0]
            profile.id = str(r["id"])
            if "created_at" in r:
                profile.created_at = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
            if "updated_at" in r:
                profile.updated_at = datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
        return profile

    def update_profile(self, user_id: str, updates: dict[str, Any]) -> UserProfile | None:
        payload: dict[str, Any] = {}
        if "display_name" in updates:
            payload["display_name"] = updates["display_name"]
        if "language_preference" in updates and updates["language_preference"] is not None:
            payload["language_preference"] = updates["language_preference"]
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()

        res = self._request(
            "patch",
            "user_profiles",
            headers=self._headers(prefer="return=representation"),
            params={"user_id": f"eq.{user_id}"},
            json=payload,
        )
        if not res:
            return None
        r = res[0]
        return UserProfile(
            id=str(r["id"]),
            user_id=str(r["user_id"]),
            display_name=r.get("display_name"),
            language_preference=r.get("language_preference", "en"),
            app_role=r.get("app_role", "consumer"),
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
        )
