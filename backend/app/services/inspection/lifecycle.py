"""Explicit lifecycle state transitions and validation rules for inspections."""

from __future__ import annotations

from backend.app.services.inspection.errors import (
    InspectionStateError,
    InvalidLifecycleTransitionError,
)
from backend.app.services.inspection.models import Inspection, InspectionStatus

# Define valid state transition graph
VALID_TRANSITIONS: dict[InspectionStatus, set[InspectionStatus]] = {
    InspectionStatus.COLLECTING: {InspectionStatus.READY},
    InspectionStatus.READY: {InspectionStatus.COLLECTING},
}


class InspectionLifecycleValidator:
    """Validates lifecycle transitions and mutation permissions for inspections."""

    @staticmethod
    def validate_transition(current_status: InspectionStatus, new_status: InspectionStatus) -> None:
        """Validate if a state transition is legal."""
        if current_status == new_status:
            return

        allowed = VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            cur_val = getattr(current_status, "value", str(current_status))
            new_val = getattr(new_status, "value", str(new_status))
            raise InvalidLifecycleTransitionError(
                f"Invalid lifecycle transition from '{cur_val}' to '{new_val}'.",
                details={
                    "current_status": cur_val,
                    "target_status": new_val,
                    "allowed_transitions": [getattr(s, "value", str(s)) for s in allowed],
                },
            )

    @staticmethod
    def assert_can_mutate(inspection: Inspection, operation: str = "modify") -> None:
        """Ensure inspection is in a state that permits adding or removing image references."""
        if not inspection.is_collecting:
            raise InspectionStateError(
                f"Cannot {operation} inspection '{inspection.inspection_id}' because it is in '{inspection.status.value}' state. "
                f"Mutations are only permitted when in '{InspectionStatus.COLLECTING.value}' state.",
                details={
                    "inspection_id": inspection.inspection_id,
                    "current_status": inspection.status.value,
                    "operation": operation,
                },
            )
