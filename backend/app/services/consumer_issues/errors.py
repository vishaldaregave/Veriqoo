"""Domain exception classes for Consumer Issue Reporting (T3-3)."""

from __future__ import annotations

from typing import Any


class ConsumerIssueError(Exception):
    """Base domain exception for consumer issue reporting failures."""
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConsumerIssueNotFoundError(ConsumerIssueError):
    """Raised when a requested consumer issue is missing or unowned."""
    pass


class InvalidConsumerIssueError(ConsumerIssueError):
    """Raised when input parameters fail domain validation rules."""
    pass


class InvalidImageReferenceError(ConsumerIssueError):
    """Raised when an evidence image ID does not belong to the referenced inspection."""
    pass


class DuplicateConsumerIssueError(ConsumerIssueError):
    """Raised when a complaint of the same type already exists for the user and inspection."""
    pass


class InvalidIssueStateError(ConsumerIssueError):
    """Raised when an operation (such as withdrawal) is illegal in the issue's current status."""
    pass
