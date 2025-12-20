"""
Injection B: Operation Scheduling

Schedules operations and emits a deterministic event stream.
It does NOT change concentrations. It only feeds InjectionManager.

Design Philosophy:
- Scheduler owns WHEN and IN WHAT ORDER events occur
- InjectionManager owns WHAT HAPPENS (concentration changes)
- Biology owns HOW CELLS RESPOND (growth, death, stress)
- Clear separation of concerns, no backchannels

Last Updated: 2025-12-20
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ScheduledEvent:
    """
    A scheduled operation with deterministic ordering.

    Frozen to prevent accidental mutation after submission.
    """
    # Stable tie-breaker
    event_id: int

    # Where/what
    vessel_id: str
    event_type: str
    payload: Dict[str, Any]

    # When/how
    scheduled_time_h: float
    duration_h: float = 0.0
    priority: int = 50

    # Extra metadata (ignored by InjectionManager, but available for forensics)
    metadata: Dict[str, Any] = field(default_factory=dict)


class OperationScheduler:
    """
    Injection B: schedules operations and emits a deterministic event stream.

    Contract:
    - submit_intent(...) queues operations with explicit time and priority
    - flush_due_events(...) resolves pending events in deterministic order
    - Scheduler NEVER mutates concentrations (that's InjectionManager's job)
    - Scheduler NEVER reads biology state (that would create coupling)

    Deterministic ordering:
    1. scheduled_time_h (ascending)
    2. priority (ascending, lower = earlier)
    3. event_id (ascending, stable tie-breaker)

    Default priorities (from covenant):
    - SEED_VESSEL: 0 (first)
    - WASHOUT_COMPOUND: 10 (remove)
    - FEED_VESSEL: 20 (replenish)
    - TREAT_COMPOUND: 30 (add signal)
    - Other: 50 (default)
    """

    def __init__(self):
        self._next_event_id = 1
        self._pending: List[ScheduledEvent] = []

    def submit_intent(
        self,
        *,
        vessel_id: str,
        event_type: str,
        payload: Dict[str, Any],
        requested_time_h: float,
        duration_h: float = 0.0,
        priority: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScheduledEvent:
        """
        Queue an operation for future execution.

        Args:
            vessel_id: Target vessel identifier
            event_type: Event type (SEED_VESSEL, TREAT_COMPOUND, FEED_VESSEL, WASHOUT_COMPOUND)
            payload: Event payload (must match InjectionManager schema)
            requested_time_h: When this operation should occur
            duration_h: How long this operation takes (for future capacity modeling)
            priority: Explicit priority override (None = use default policy)
            metadata: Extra metadata for forensics (operator_id, instrument_id, etc.)

        Returns:
            ScheduledEvent with assigned event_id
        """
        if priority is None:
            priority = self._default_priority(event_type)

        ev = ScheduledEvent(
            event_id=self._next_event_id,
            vessel_id=str(vessel_id),
            event_type=str(event_type),
            payload=dict(payload),
            scheduled_time_h=float(requested_time_h),
            duration_h=float(duration_h),
            priority=int(priority),
            metadata=dict(metadata) if metadata else {},
        )
        self._next_event_id += 1
        self._pending.append(ev)
        return ev

    def flush_due_events(
        self,
        *,
        now_h: float,
        injection_mgr: Any,
    ) -> List[ScheduledEvent]:
        """
        Resolve all events with scheduled_time_h <= now_h in deterministic order,
        then push them into InjectionManager via add_event(...).

        This is the ONLY place where events move from Scheduler → InjectionManager.

        Args:
            now_h: Current simulated time
            injection_mgr: InjectionManager instance to receive events

        Returns:
            List of events that were delivered (in delivery order)
        """
        now_h = float(now_h)

        # Find due events
        due = [e for e in self._pending if e.scheduled_time_h <= now_h]
        if not due:
            return []

        # Keep the rest pending
        self._pending = [e for e in self._pending if e.scheduled_time_h > now_h]

        # Deterministic linearization (covenant Section 5):
        # 1) scheduled_time_h
        # 2) priority
        # 3) event_id (stable tie-break)
        due.sort(key=lambda e: (e.scheduled_time_h, e.priority, e.event_id))

        # Deliver to InjectionManager (the only concentration authority)
        for e in due:
            injection_mgr.add_event(
                {
                    "event_type": e.event_type,
                    "time_h": float(e.scheduled_time_h),
                    "vessel_id": e.vessel_id,
                    "payload": dict(e.payload),
                }
            )

        return due

    def _default_priority(self, event_type: str) -> int:
        """
        Default priority policy matching covenant Section 5.

        Lower priority = executed earlier.

        Policy: remove → replenish → add signal
        - SEED_VESSEL: 0 (initialize first)
        - WASHOUT_COMPOUND: 10 (remove compounds)
        - FEED_VESSEL: 20 (refresh nutrients)
        - TREAT_COMPOUND: 30 (add compounds)
        - Other: 50 (default)
        """
        if event_type == "SEED_VESSEL":
            return 0
        if event_type == "WASHOUT_COMPOUND":
            return 10
        if event_type == "FEED_VESSEL":
            return 20
        if event_type == "TREAT_COMPOUND":
            return 30
        return 50

    def get_pending_count(self) -> int:
        """Return number of pending events (for debugging)."""
        return len(self._pending)

    def get_pending_events(self) -> List[ScheduledEvent]:
        """Return copy of pending events (for inspection)."""
        return list(self._pending)
