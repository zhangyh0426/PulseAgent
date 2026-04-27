from __future__ import annotations

import threading
from pathlib import Path

from watchfiles import watch

from .events import scan_for_changes
from .protocol import WATCHED_FILES, ensure_pulse_dir


def watch_project(project: str | Path | None = None) -> None:
    paths = ensure_pulse_dir(project)
    watched_names = set(WATCHED_FILES)
    scan_for_changes(paths.project_root)

    for changes in watch(paths.pulse_dir):
        if any(Path(change_path).name in watched_names for _, change_path in changes):
            scan_for_changes(paths.project_root)


def start_watcher_thread(project: str | Path | None = None) -> threading.Thread:
    thread = threading.Thread(
        target=watch_project,
        args=(project,),
        daemon=True,
        name="pulse-watcher",
    )
    thread.start()
    return thread
