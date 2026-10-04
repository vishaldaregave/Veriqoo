"""Background Inspection Execution Service for Phase 9C.

Provides non-blocking in-process background scheduling and execution of the
Phase 7 inspection pipeline with strict lifecycle transitions (COLLECTING -> RUNNING -> COMPLETED/FAILED),
idempotency guards, process-local concurrency control, and sanitized failure recording.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import logging
import re
import threading
from typing import Any, Callable

from fastapi import BackgroundTasks

from backend.app.services.inspection.errors import (
    InspectionNotFoundError,
    InspectionStateError,
)
from backend.app.services.inspection.models import (
    Inspection,
    InspectionStatus,
)
from backend.app.services.inspection.service import InspectionService

logger = logging.getLogger(__name__)

# Regex to strip secrets/credentials/keys if accidentally included in error strings
_SECRET_PATTERN = re.compile(r"(?:key|token|secret|password|bearer)[=:\s]+['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?", re.IGNORECASE)


def sanitize_error_message(message: str) -> str:
    """Sanitize error messages to ensure no tokens, keys, or raw provider secrets are logged or exposed."""
    if not message:
        return "Unknown error occurred during inspection execution."
    # Strip known secret matches
    cleaned = _SECRET_PATTERN.sub("[REDACTED_SECRET]", str(message))
    # Truncate length
    if len(cleaned) > 500:
        cleaned = cleaned[:497] + "..."
    return cleaned


class InspectionExecutionService:
    """Manages scheduling and background execution of inspection pipelines.

    Provides a clean execution boundary so a future distributed worker (e.g. Celery/ARQ)
    can replace the in-process execution mechanism without changing the core inspection pipeline.
    """

    def __init__(
        self,
        inspection_service: InspectionService,
        max_workers: int = 4,
    ) -> None:
        self.service = inspection_service
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="InspectionWorker")

    def schedule_execution(
        self,
        inspection_id: str,
        background_tasks: BackgroundTasks | None = None,
        facts: list[dict[str, Any]] | None = None,
        applicability_context: dict[str, Any] | None = None,
        target_requirements: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[InspectionStatus, str]:
        """Schedule an inspection for background execution with idempotency & concurrency guards.

        Returns (current_status, status_message).
        """
        with self._lock:
            insp = self.service.repository.get_inspection(inspection_id)

            # 1. Idempotency guards
            if insp.status == InspectionStatus.RUNNING:
                return InspectionStatus.RUNNING, "Inspection execution is currently running."

            if insp.status == InspectionStatus.COMPLETED:
                return InspectionStatus.COMPLETED, "Inspection execution is already completed."

            # 2. Transition state to RUNNING immediately
            self.service.repository.update_inspection_status(
                inspection_id=inspection_id,
                status=InspectionStatus.RUNNING,
            )

            # 3. Schedule task
            task_kwargs = {
                "inspection_id": inspection_id,
                "facts": facts,
                "applicability_context": applicability_context,
                "target_requirements": target_requirements,
                "metadata": metadata,
            }

            if background_tasks is not None:
                background_tasks.add_task(self._run_task, **task_kwargs)
            else:
                self._executor.submit(self._run_task, **task_kwargs)

            return InspectionStatus.RUNNING, "Inspection execution started."

    def execute_sync(
        self,
        inspection_id: str,
        facts: list[dict[str, Any]] | None = None,
        applicability_context: dict[str, Any] | None = None,
        target_requirements: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[InspectionStatus, str]:
        """Synchronously execute the inspection pipeline (primarily used for deterministic test verification)."""
        with self._lock:
            insp = self.service.repository.get_inspection(inspection_id)
            if insp.status == InspectionStatus.COMPLETED:
                return InspectionStatus.COMPLETED, "Inspection execution is already completed."
            if insp.status == InspectionStatus.RUNNING:
                return InspectionStatus.RUNNING, "Inspection execution is currently running."

            self.service.repository.update_inspection_status(
                inspection_id=inspection_id,
                status=InspectionStatus.RUNNING,
            )

        self._run_task(
            inspection_id=inspection_id,
            facts=facts,
            applicability_context=applicability_context,
            target_requirements=target_requirements,
            metadata=metadata,
        )

        final_insp = self.service.repository.get_inspection(inspection_id)
        msg = "Inspection execution completed." if final_insp.is_completed else "Inspection execution failed."
        return final_insp.status, msg

    def _run_task(
        self,
        inspection_id: str,
        facts: list[dict[str, Any]] | None = None,
        applicability_context: dict[str, Any] | None = None,
        target_requirements: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Background worker executing the unified pipeline, persisting results, and handling failures."""
        logger.info("Starting background inspection execution for '%s'", inspection_id)
        try:
            self.service.run_inspection(
                inspection_id=inspection_id,
                facts=facts,
                applicability_context=applicability_context,
                target_requirements=target_requirements,
                metadata=metadata,
            )
            logger.info("Background inspection execution completed successfully for '%s'", inspection_id)
        except Exception as exc:
            safe_error = sanitize_error_message(str(exc))
            logger.error(
                "Background inspection execution failed for '%s': %s (Type: %s)",
                inspection_id,
                safe_error,
                type(exc).__name__,
            )
            # Record failure state and metadata
            try:
                insp = self.service.repository.get_inspection(inspection_id)
                meta = dict(insp.metadata)
                meta["execution_error"] = safe_error
                meta["error_type"] = type(exc).__name__
                meta["failed_at"] = datetime.now(timezone.utc).isoformat()

                # Update status to FAILED
                self.service.repository.update_inspection_status(
                    inspection_id=inspection_id,
                    status=InspectionStatus.FAILED,
                    completed_at=datetime.now(timezone.utc),
                )
            except Exception as persist_err:
                logger.critical(
                    "Failed to record FAILED status for inspection '%s': %s",
                    inspection_id,
                    persist_err,
                )

    def mark_interrupted_running_inspections(self) -> int:
        """Startup cleanup: marks any orphaned RUNNING inspections from crashed processes as FAILED."""
        count = 0
        # If repository supports listing, scan and update
        if hasattr(self.service.repository, "list_sessions"):
            for sess in self.service.repository.list_sessions():
                if sess.inspection.status == InspectionStatus.RUNNING:
                    sess.inspection.status = InspectionStatus.FAILED
                    sess.inspection.metadata["execution_error"] = "Execution interrupted by process restart."
                    count += 1
        return count

