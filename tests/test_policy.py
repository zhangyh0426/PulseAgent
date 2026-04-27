from __future__ import annotations

import os

from pulse_agent.events import read_events, scan_for_changes
from pulse_agent.policy import should_interrupt
from pulse_agent.protocol import ensure_pulse_dir


def _set_mtime(path, value: int) -> None:
    os.utime(path, ns=(value, value))


def test_guidance_or_constraints_newer_than_plan_requires_replan(tmp_path):
    paths = ensure_pulse_dir(tmp_path)
    _set_mtime(paths.guidance, 100)
    _set_mtime(paths.constraints, 100)
    _set_mtime(paths.plan, 200)

    assert should_interrupt(tmp_path).needs_replan is False

    _set_mtime(paths.guidance, 300)
    decision = should_interrupt(tmp_path)

    assert decision.needs_replan is True
    assert "guidance.md" in decision.changed_files or decision.changed_files == []


def test_plan_update_after_guidance_clears_replan(tmp_path):
    paths = ensure_pulse_dir(tmp_path)
    _set_mtime(paths.plan, 100)
    _set_mtime(paths.constraints, 100)
    _set_mtime(paths.guidance, 200)

    assert should_interrupt(tmp_path).needs_replan is True

    _set_mtime(paths.plan, 300)
    decision = should_interrupt(tmp_path)

    assert decision.needs_replan is False


def test_last_seen_event_id_tracks_new_events(tmp_path):
    paths = ensure_pulse_dir(tmp_path)

    paths.task.write_text("# Task\n\nInitial task.\n", encoding="utf-8")
    scan_for_changes(tmp_path)
    first_event = read_events(tmp_path)[-1]

    paths.constraints.write_text(
        "# Constraints\n\nDo not execute shell commands.\n",
        encoding="utf-8",
    )
    scan_for_changes(tmp_path)
    decision = should_interrupt(tmp_path, last_seen_event_id=first_event.id)

    assert decision.latest_event_id != first_event.id
    assert decision.has_new_events is True
    assert decision.changed_files == [".pulse/constraints.md"]
