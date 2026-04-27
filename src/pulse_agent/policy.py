from __future__ import annotations

from pathlib import Path

from .events import events_after, read_events, scan_for_changes
from .models import InterruptDecision
from .protocol import ensure_pulse_dir


def _mtime_ns(path: Path) -> int:
    if not path.exists():
        return 0
    return path.stat().st_mtime_ns


def should_interrupt(
    project: str | Path | None = None,
    last_seen_event_id: str | None = None,
) -> InterruptDecision:
    paths = ensure_pulse_dir(project)
    scan_for_changes(project)
    events = read_events(project)
    latest_event_id = events[-1].id if events else None
    new_events = events_after(events, last_seen_event_id)

    guidance_mtime = _mtime_ns(paths.guidance)
    constraints_mtime = _mtime_ns(paths.constraints)
    plan_mtime = _mtime_ns(paths.plan)
    changed_since_plan = [
        name
        for name, mtime in (
            ("guidance.md", guidance_mtime),
            ("constraints.md", constraints_mtime),
        )
        if mtime > plan_mtime
    ]

    if changed_since_plan:
        reason = (
            "User guidance or constraints changed after the current plan. "
            "The agent should review PulseAgent context and replan before continuing."
        )
    elif new_events:
        reason = (
            "PulseAgent saw new events, but the current plan is not older than guidance "
            "or constraints."
        )
    else:
        reason = "No new PulseAgent events and the current plan is up to date."

    return InterruptDecision(
        needs_replan=bool(changed_since_plan),
        latest_event_id=latest_event_id,
        has_new_events=bool(new_events),
        changed_files=[event.path for event in new_events],
        reason=reason,
    )
