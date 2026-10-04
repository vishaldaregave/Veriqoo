"""Repository abstractions and implementations for Consumer Issue Reporting."""

from __future__ import annotations

import abc
from datetime import datetime, timezone
import logging
import threading
from typing import Any

import requests

from backend.app.config import Settings, get_settings
from backend.app.services.consumer_issues.errors import (
    DuplicateConsumerIssueError,
    InvalidIssueStateError,
)
from backend.app.services.consumer_issues.models import ConsumerIssue, IssueStatus

logger = logging.getLogger(__name__)


class ConsumerIssueRepository(abc.ABC):
    """Abstract repository for persisting consumer issue reports."""

    @abc.abstractmethod
    def create_issue(self, issue: ConsumerIssue) -> ConsumerIssue:
        """Create a new consumer issue record. Raises DuplicateConsumerIssueError if duplicate exists."""
        pass

    @abc.abstractmethod
    def get_by_id(self, issue_id: str) -> ConsumerIssue | None:
        """Retrieve a consumer issue record by ID."""
        pass

    @abc.abstractmethod
    def get_by_user_and_inspection_and_type(
        self, user_id: str, inspection_id: str | None, issue_type: str
    ) -> ConsumerIssue | None:
        """Retrieve an issue matching user ID, inspection ID, and issue type."""
        pass

    @abc.abstractmethod
    def list_by_user(
        self, user_id: str, limit: int = 20, offset: int = 0, status_filter: str | None = None
    ) -> tuple[list[ConsumerIssue], int]:
        """List paginated consumer issues for a specific user with optional status filter."""
        pass

    @abc.abstractmethod
    def delete_by_id(self, issue_id: str, user_id: str) -> bool:
        """Delete a consumer issue record if owned by user_id and in SUBMITTED status."""
        pass


class InMemoryConsumerIssueRepository(ConsumerIssueRepository):
    """Thread-safe in-memory repository for unit testing and development."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: dict[str, ConsumerIssue] = {}

    def create_issue(self, issue: ConsumerIssue) -> ConsumerIssue:
        with self._lock:
            if issue.inspection_id is not None:
                existing = self.get_by_user_and_inspection_and_type(
                    user_id=issue.user_id,
                    inspection_id=issue.inspection_id,
                    issue_type=issue.issue_type,
                )
                if existing:
                    raise DuplicateConsumerIssueError(
                        f"A complaint of type '{issue.issue_type}' has already been submitted for this inspection.",
                        details={"inspection_id": issue.inspection_id, "issue_type": issue.issue_type},
                    )

            self._items[issue.id] = issue
            return issue

    def get_by_id(self, issue_id: str) -> ConsumerIssue | None:
        with self._lock:
            return self._items.get(issue_id)

    def get_by_user_and_inspection_and_type(
        self, user_id: str, inspection_id: str | None, issue_type: str
    ) -> ConsumerIssue | None:
        with self._lock:
            if inspection_id is None:
                return None
            for item in self._items.values():
                if (
                    item.user_id == user_id
                    and item.inspection_id == inspection_id
                    and item.issue_type == issue_type
                ):
                    return item
            return None

    def list_by_user(
        self, user_id: str, limit: int = 20, offset: int = 0, status_filter: str | None = None
    ) -> tuple[list[ConsumerIssue], int]:
        with self._lock:
            matched = [item for item in self._items.values() if item.user_id == user_id]
            if status_filter:
                matched = [item for item in matched if item.status == status_filter]
            matched.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matched)
            paginated = matched[offset : offset + limit]
            return paginated, total

    def delete_by_id(self, issue_id: str, user_id: str) -> bool:
        with self._lock:
            item = self._items.get(issue_id)
            if not item or item.user_id != user_id:
                return False
            if item.status != IssueStatus.SUBMITTED.value:
                raise InvalidIssueStateError(
                    f"Cannot withdraw complaint '{issue_id}' in status '{item.status}'.",
                    details={"issue_id": issue_id, "status": item.status},
                )
            del self._items[issue_id]
            return True

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class SupabaseConsumerIssueRepository(ConsumerIssueRepository):
    """Supabase REST API implementation for consumer issues persistence."""

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
        if resp.status_code == 409:
            return 409, []
        if resp.status_code == 400:
            try:
                err_data = resp.json()
                if isinstance(err_data, dict) and (
                    err_data.get("code") == "23505"
                    or "unique" in err_data.get("message", "").lower()
                ):
                    return 409, []
            except Exception:
                pass
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

    def _map_row(self, r: dict[str, Any]) -> ConsumerIssue:
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

    def create_issue(self, issue: ConsumerIssue) -> ConsumerIssue:
        if issue.inspection_id is not None:
            existing = self.get_by_user_and_inspection_and_type(
                user_id=issue.user_id,
                inspection_id=issue.inspection_id,
                issue_type=issue.issue_type,
            )
            if existing:
                raise DuplicateConsumerIssueError(
                    f"A complaint of type '{issue.issue_type}' has already been submitted for this inspection.",
                    details={"inspection_id": issue.inspection_id, "issue_type": issue.issue_type},
                )

        payload = {
            "id": issue.id,
            "user_id": issue.user_id,
            "inspection_id": issue.inspection_id,
            "saved_product_id": issue.saved_product_id,
            "issue_type": issue.issue_type,
            "title": issue.title,
            "description": issue.description,
            "status": issue.status,
            "resolution_notes": issue.resolution_notes,
            "evidence_images": issue.evidence_images,
            "department": issue.department,
            "state_code": issue.state_code,
            "district_code": issue.district_code,
            "jurisdiction_verified": issue.jurisdiction_verified,
            "establishment_id": issue.establishment_id,
            "jurisdiction_provenance": issue.jurisdiction_provenance,
            "jurisdiction_verified_at": issue.jurisdiction_verified_at.isoformat() if issue.jurisdiction_verified_at else None,
            "jurisdiction_verified_by": issue.jurisdiction_verified_by,
        }

        status_code, rows = self._request(
            "post",
            "consumer_issues",
            headers=self._headers(prefer="return=representation"),
            json=payload,
        )

        if status_code in (409, 23505):
            raise DuplicateConsumerIssueError(
                f"A complaint of type '{issue.issue_type}' has already been submitted for this inspection.",
                details={"inspection_id": issue.inspection_id, "issue_type": issue.issue_type},
            )

        if rows:
            return self._map_row(rows[0])
        return issue

    def get_by_id(self, issue_id: str) -> ConsumerIssue | None:
        _, rows = self._request(
            "get",
            "consumer_issues",
            headers=self._headers(),
            params={"id": f"eq.{issue_id}", "limit": "1"},
        )
        if not rows:
            return None
        return self._map_row(rows[0])

    def get_by_user_and_inspection_and_type(
        self, user_id: str, inspection_id: str | None, issue_type: str
    ) -> ConsumerIssue | None:
        if inspection_id is None:
            return None
        _, rows = self._request(
            "get",
            "consumer_issues",
            headers=self._headers(),
            params={
                "user_id": f"eq.{user_id}",
                "inspection_id": f"eq.{inspection_id}",
                "issue_type": f"eq.{issue_type}",
                "limit": "1",
            },
        )
        if not rows:
            return None
        return self._map_row(rows[0])

    def list_by_user(
        self, user_id: str, limit: int = 20, offset: int = 0, status_filter: str | None = None
    ) -> tuple[list[ConsumerIssue], int]:
        params = {
            "user_id": f"eq.{user_id}",
            "order": "created_at.desc",
            "offset": str(offset),
            "limit": str(limit),
        }
        if status_filter:
            params["status"] = f"eq.{status_filter}"

        _, rows = self._request(
            "get",
            "consumer_issues",
            headers=self._headers(),
            params=params,
        )
        items = [self._map_row(r) for r in rows]
        return items, len(items)

    def delete_by_id(self, issue_id: str, user_id: str) -> bool:
        item = self.get_by_id(issue_id)
        if not item or item.user_id != user_id:
            return False
        if item.status != IssueStatus.SUBMITTED.value:
            raise InvalidIssueStateError(
                f"Cannot withdraw complaint '{issue_id}' in status '{item.status}'.",
                details={"issue_id": issue_id, "status": item.status},
            )
        self._request(
            "delete",
            "consumer_issues",
            headers=self._headers(),
            params={"id": f"eq.{issue_id}", "user_id": f"eq.{user_id}"},
        )
        return True
