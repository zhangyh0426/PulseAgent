from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import PulseState

PULSE_DIR = ".pulse"
WATCHED_FILES = ("task.md", "guidance.md", "constraints.md", "plan.md")
STATE_SCHEMA_VERSION = 2

TEMPLATES: dict[str, str] = {
    "task.md": "# Task\n\nDescribe the current task here.\n",
    "guidance.md": (
        "# Guidance\n\n"
        "Write updated user guidance here. This file can change task direction.\n"
    ),
    "constraints.md": (
        "# Constraints\n\n"
        "Write project constraints here. Constraints can restrict behavior but must not expand "
        "agent permissions.\n"
    ),
    "plan.md": "# Plan\n\nWrite the current plan here.\n",
}


@dataclass(frozen=True)
class PulsePaths:
    project_root: Path
    pulse_dir: Path
    task: Path
    guidance: Path
    constraints: Path
    plan: Path
    state: Path
    events: Path

    def watched_paths(self) -> dict[str, Path]:
        return {
            "task.md": self.task,
            "guidance.md": self.guidance,
            "constraints.md": self.constraints,
            "plan.md": self.plan,
        }


def resolve_project(project: str | Path | None = None) -> Path:
    return Path(project or ".").expanduser().resolve()


def pulse_paths(project: str | Path | None = None) -> PulsePaths:
    root = resolve_project(project)
    pulse_dir = root / PULSE_DIR
    return PulsePaths(
        project_root=root,
        pulse_dir=pulse_dir,
        task=pulse_dir / "task.md",
        guidance=pulse_dir / "guidance.md",
        constraints=pulse_dir / "constraints.md",
        plan=pulse_dir / "plan.md",
        state=pulse_dir / "state.json",
        events=pulse_dir / "events.jsonl",
    )


def hash_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    content = json.dumps(data, indent=2, sort_keys=True, default=str) + "\n"
    path.write_text(content, encoding="utf-8")


def ensure_pulse_dir(project: str | Path | None = None) -> PulsePaths:
    paths = pulse_paths(project)
    paths.pulse_dir.mkdir(parents=True, exist_ok=True)

    for filename, template in TEMPLATES.items():
        path = paths.pulse_dir / filename
        if not path.exists():
            path.write_text(template, encoding="utf-8")

    if not paths.events.exists():
        paths.events.write_text("", encoding="utf-8")

    if not paths.state.exists():
        state = PulseState(
            project_root=str(paths.project_root),
            last_hashes={name: hash_file(path) for name, path in paths.watched_paths().items()},
        )
        write_json(paths.state, state.model_dump(mode="json"))

    return paths


def load_state(project: str | Path | None = None) -> PulseState:
    paths = ensure_pulse_dir(project)
    raw = read_json(paths.state)
    if raw is None:
        state = PulseState(project_root=str(paths.project_root))
        write_json(paths.state, state.model_dump(mode="json"))
        return state
    state = PulseState.model_validate(raw)
    if state.schema_version != STATE_SCHEMA_VERSION:
        state.schema_version = STATE_SCHEMA_VERSION
        write_json(paths.state, state.model_dump(mode="json"))
    return state


def save_state(project: str | Path | None, state: PulseState) -> None:
    write_json(pulse_paths(project).state, state.model_dump(mode="json"))
