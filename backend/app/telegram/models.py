"""Data models and identity representations for Telegram Bot Integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TelegramWorkflowState(str, Enum):
    """Conversation state of a Telegram user session."""
    IDLE = "IDLE"
    COLLECTING = "COLLECTING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class TelegramUserIdentity:
    """Isolated representation of a Telegram caller's identity."""
    telegram_user_id: int
    chat_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    @property
    def display_name(self) -> str:
        """User-friendly display name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        if self.first_name:
            return self.first_name
        if self.username:
            return f"@{self.username}"
        return f"User {self.telegram_user_id}"


@dataclass
class TelegramConversation:
    """Tracks the active inspection reference for a Telegram chat."""
    chat_id: int
    telegram_user_id: int
    active_inspection_id: str | None = None
    state: TelegramWorkflowState = TelegramWorkflowState.IDLE
    last_interaction: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

