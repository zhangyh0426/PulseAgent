from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .events import events_after, read_events, scan_for_changes
from .models import InterruptDecision, PulseEvent, ReplanAckDecision
from .protocol import ensure_pulse_dir, hash_file, load_state, save_state

INVALIDATING_EVENT_PATHS = {".pulse/guidance.md", ".pulse/constraints.md"}


def _is_plan_invalidating(event: PulseEvent) -> bool:
    return event.path in INVALIDATING_EVENT_PATHS


def _event_by_id(events: list[PulseEvent], event_id: str) -> PulseEvent | None:
    for event in events:
        if event.id == event_id:
            return event
    return None


def _pending_replan_events(
    events: list[PulseEvent],
    acknowledged_event_id: str | None,
) -> list[PulseEvent]:
    start_index = 0
    if acknowledged_event_id is not None:
        for index, event in enumerate(events):
            if event.id == acknowledged_event_id:
                start_index = index + 1
                break
    return [event for event in events[start_index:] if _is_plan_invalidating(event)]


def _pending_replan_event(
    events: list[PulseEvent],
    acknowledged_event_id: str | None,
) -> PulseEvent | None:
    pending_events = _pending_replan_events(events, acknowledged_event_id)
    return pending_events[-1] if pending_events else None


def _pending_replan_files(pending_events: list[PulseEvent]) -> list[str]:
    return list(dict.fromkeys(event.path for event in pending_events))


def should_interrupt(
    project: str | Path | None = None,
    last_seen_event_id: str | None = None,
) -> InterruptDecision:
    ensure_pulse_dir(project)
    scan_for_changes(project)
    events = read_events(project)
    state = load_state(project)
    latest_event_id = events[-1].id if events else None
    new_events = events_after(events, last_seen_event_id)
    pending_events = _pending_replan_events(events, state.last_acknowledged_event_id)
    pending_event = pending_events[-1] if pending_events else None
    pending_files = _pending_replan_files(pending_events)

    if pending_event is not None:
        reason = (
            "User guidance or constraints changed and have not been acknowledged. "
            "The agent should review PulseAgent context, update the plan, and call "
            "pulse_ack_replan before continuing."
        )
    elif new_events:
        reason = (
            "PulseAgent saw new events, but there is no pending guidance or constraints "
            "change requiring replan."
        )
    else:
        reason = "No new PulseAgent events and no pending replan acknowledgement."

    return InterruptDecision(
        needs_replan=pending_event is not None,
        latest_event_id=latest_event_id,
        has_new_events=bool(new_events),
        changed_files=[event.path for event in new_events],
        pending_replan_event_id=pending_event.id if pending_event is not None else None,
        pending_replan_files=pending_files,
        last_acknowledged_event_id=state.last_acknowledged_event_id,
        last_acknowledged_plan_sha256=state.last_acknowledged_plan_sha256,
        reason=reason,
    )


def ack_replan(project: str | Path | None = None, event_id: str | None = None) -> ReplanAckDecision:
    paths = ensure_pulse_dir(project)
    scan_for_changes(project)
    events = read_events(project)
    state = load_state(project)
    pending_event = _pending_replan_event(events, state.last_acknowledged_event_id)

    if event_id is None or not event_id.strip():
        return ReplanAckDecision(
            accepted=False,
            reason="A pending replan event id is required.",
        )

    event = _event_by_id(events, event_id)
    if event is None:
        return ReplanAckDecision(
            accepted=False,
            reason=f"Event {event_id} was not found.",
        )

    if not _is_plan_invalidating(event):
        return ReplanAckDecision(
            accepted=False,
            reason=f"Event {event_id} is not a guidance or constraints event.",
        )

    if pending_event is None:
        return ReplanAckDecision(
            accepted=False,
            reason="There is no pending guidance or constraints change to acknowledge.",
        )

    if event.id != pending_event.id:
        return ReplanAckDecision(
            accepted=False,
            acknowledged_event_id=state.last_acknowledged_event_id,
            plan_sha256=state.last_acknowledged_plan_sha256,
            reason=(
                f"Event {event_id} is stale. Acknowledge the latest pending replan event "
                f"{pending_event.id} instead."
            ),
        )

    plan_sha256 = hash_file(paths.plan)
    state.last_acknowledged_event_id = event.id
    state.last_acknowledged_plan_sha256 = plan_sha256
    state.last_acknowledged_at = datetime.now(UTC)
    save_state(project, state)

    return ReplanAckDecision(
        accepted=True,
        acknowledged_event_id=event.id,
        plan_sha256=plan_sha256,
        reason="Replan acknowledged for the latest guidance or constraints event.",
    )
