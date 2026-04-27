from __future__ import annotations

from pulse_agent.events import read_events, scan_for_changes
from pulse_agent.policy import ack_replan, should_interrupt
from pulse_agent.protocol import ensure_pulse_dir, hash_file


def test_guidance_change_requires_ack_even_after_plan_update(tmp_path):
    paths = ensure_pulse_dir(tmp_path)
    paths.guidance.write_text("# Guidance\n\nUse the MCP sidecar design.\n", encoding="utf-8")

    decision = should_interrupt(tmp_path)

    assert decision.needs_replan is True
    assert decision.pending_replan_event_id is not None
    assert decision.pending_replan_files == [".pulse/guidance.md"]

    pending_event_id = decision.pending_replan_event_id
    paths.plan.write_text("# Plan\n\nHandle the latest guidance.\n", encoding="utf-8")

    decision = should_interrupt(tmp_path)

    assert decision.needs_replan is True
    assert decision.pending_replan_event_id == pending_event_id


def test_ack_replan_clears_pending_replan_and_records_plan_hash(tmp_path):
    paths = ensure_pulse_dir(tmp_path)
    paths.constraints.write_text(
        "# Constraints\n\nDo not execute shell commands.\n",
        encoding="utf-8",
    )
    decision = should_interrupt(tmp_path)
    assert decision.pending_replan_event_id is not None

    paths.plan.write_text("# Plan\n\nRespect the latest constraints.\n", encoding="utf-8")
    ack = ack_replan(tmp_path, decision.pending_replan_event_id)
    next_decision = should_interrupt(tmp_path, last_seen_event_id=decision.latest_event_id)

    assert ack.accepted is True
    assert ack.acknowledged_event_id == decision.pending_replan_event_id
    assert ack.plan_sha256 == hash_file(paths.plan)
    assert next_decision.needs_replan is False
    assert next_decision.pending_replan_event_id is None
    assert next_decision.last_acknowledged_event_id == decision.pending_replan_event_id
    assert next_decision.last_acknowledged_plan_sha256 == ack.plan_sha256


def test_new_guidance_after_ack_requires_replan_again(tmp_path):
    paths = ensure_pulse_dir(tmp_path)
    paths.guidance.write_text("# Guidance\n\nFirst change.\n", encoding="utf-8")
    first_decision = should_interrupt(tmp_path)
    assert first_decision.pending_replan_event_id is not None
    assert ack_replan(tmp_path, first_decision.pending_replan_event_id).accepted is True

    paths.guidance.write_text("# Guidance\n\nSecond change.\n", encoding="utf-8")
    second_decision = should_interrupt(tmp_path)

    assert second_decision.needs_replan is True
    assert second_decision.pending_replan_event_id is not None
    assert second_decision.pending_replan_event_id != first_decision.pending_replan_event_id


def test_ack_rejects_missing_stale_and_non_invalidating_events(tmp_path):
    paths = ensure_pulse_dir(tmp_path)

    paths.task.write_text("# Task\n\nInitial task.\n", encoding="utf-8")
    scan_for_changes(tmp_path)
    task_event = read_events(tmp_path)[-1]
    non_invalidating = ack_replan(tmp_path, task_event.id)
    assert non_invalidating.accepted is False
    assert "not a guidance or constraints event" in non_invalidating.reason

    paths.guidance.write_text("# Guidance\n\nFirst change.\n", encoding="utf-8")
    first_event_id = should_interrupt(tmp_path).pending_replan_event_id
    assert first_event_id is not None

    paths.constraints.write_text("# Constraints\n\nSecond change.\n", encoding="utf-8")
    second_decision = should_interrupt(tmp_path)
    second_event_id = second_decision.pending_replan_event_id
    assert second_event_id is not None
    assert second_event_id != first_event_id
    assert second_decision.pending_replan_files == [
        ".pulse/guidance.md",
        ".pulse/constraints.md",
    ]

    stale = ack_replan(tmp_path, first_event_id)
    missing = ack_replan(tmp_path, "evt_missing")

    assert stale.accepted is False
    assert "stale" in stale.reason
    assert missing.accepted is False
    assert "was not found" in missing.reason
    assert should_interrupt(tmp_path).pending_replan_event_id == second_event_id


def test_ack_rejects_when_no_pending_replan_exists(tmp_path):
    paths = ensure_pulse_dir(tmp_path)
    paths.guidance.write_text("# Guidance\n\nUse the MCP sidecar design.\n", encoding="utf-8")
    event_id = should_interrupt(tmp_path).pending_replan_event_id
    assert event_id is not None
    assert ack_replan(tmp_path, event_id).accepted is True

    rejected = ack_replan(tmp_path, event_id)

    assert rejected.accepted is False
    assert "no pending" in rejected.reason


def test_last_seen_event_id_tracks_new_events_separately_from_replan(tmp_path):
    paths = ensure_pulse_dir(tmp_path)

    paths.task.write_text("# Task\n\nInitial task.\n", encoding="utf-8")
    scan_for_changes(tmp_path)
    first_event = read_events(tmp_path)[-1]

    paths.plan.write_text("# Plan\n\nUpdate the plan.\n", encoding="utf-8")
    scan_for_changes(tmp_path)
    decision = should_interrupt(tmp_path, last_seen_event_id=first_event.id)

    assert decision.latest_event_id != first_event.id
    assert decision.has_new_events is True
    assert decision.changed_files == [".pulse/plan.md"]
    assert decision.needs_replan is False
