from __future__ import annotations

import json

from pulse_agent.events import read_events, scan_for_changes
from pulse_agent.protocol import WATCHED_FILES, ensure_pulse_dir


def test_initializes_pulse_directory(tmp_path):
    paths = ensure_pulse_dir(tmp_path)

    assert paths.pulse_dir.is_dir()
    for name in WATCHED_FILES:
        assert (paths.pulse_dir / name).is_file()
    assert paths.events.is_file()
    assert paths.state.is_file()

    state = json.loads(paths.state.read_text(encoding="utf-8"))
    assert state["schema_version"] == 1
    assert set(state["last_hashes"]) == set(WATCHED_FILES)


def test_scan_logs_file_changes_as_jsonl(tmp_path):
    paths = ensure_pulse_dir(tmp_path)

    paths.guidance.write_text("# Guidance\n\nUse the MCP sidecar design.\n", encoding="utf-8")
    emitted = scan_for_changes(tmp_path)

    assert len(emitted) == 1
    assert emitted[0].kind == "modified"
    assert emitted[0].path == ".pulse/guidance.md"

    lines = paths.events.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["id"].startswith("evt_")
    assert row["path"] == ".pulse/guidance.md"
    assert row["sha256"]

    events = read_events(tmp_path)
    assert events[0].id == emitted[0].id
