from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .models import PulseEvent
from .protocol import ensure_pulse_dir, hash_file, load_state, save_state


def _event_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"evt_{timestamp}_{uuid4().hex[:8]}"


def append_event(project: str | Path | None, event: PulseEvent) -> PulseEvent:
    paths = ensure_pulse_dir(project)
    with paths.events.open("a", encoding="utf-8") as handle:
        handle.write(event.model_dump_json() + "\n")
    return event


def read_events(project: str | Path | None = None, limit: int | None = None) -> list[PulseEvent]:
    paths = ensure_pulse_dir(project)
    rows: list[PulseEvent] = []
    for line in paths.events.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(PulseEvent.model_validate(json.loads(line)))
    if limit is not None:
        return rows[-limit:]
    return rows


def events_after(events: list[PulseEvent], event_id: str | None) -> list[PulseEvent]:
    if event_id is None:
        return events
    for index, event in enumerate(events):
        if event.id == event_id:
            return events[index + 1 :]
    return events


def scan_for_changes(project: str | Path | None = None) -> list[PulseEvent]:
    paths = ensure_pulse_dir(project)
    state = load_state(project)
    emitted: list[PulseEvent] = []

    for name, path in paths.watched_paths().items():
        old_hash = state.last_hashes.get(name)
        new_hash = hash_file(path)
        if old_hash == new_hash:
            continue

        if old_hash is None and new_hash is not None:
            kind = "created"
        elif old_hash is not None and new_hash is None:
            kind = "deleted"
        else:
            kind = "modified"

        event = PulseEvent(
            id=_event_id(),
            kind=kind,
            path=f".pulse/{name}",
            sha256=new_hash,
            size=path.stat().st_size if path.exists() else None,
        )
        append_event(project, event)
        emitted.append(event)
        state.last_hashes[name] = new_hash

    save_state(project, state)
    return emitted
