from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

WatchedFile = Literal["task.md", "guidance.md", "constraints.md", "plan.md"]
EventKind = Literal["created", "modified", "deleted"]


class PulseEvent(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    kind: EventKind
    path: str
    sha256: str | None = None
    size: int | None = None


class PulseState(BaseModel):
    schema_version: int = 1
    project_root: str
    initialized_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_hashes: dict[str, str | None] = Field(default_factory=dict)


class InterruptDecision(BaseModel):
    needs_replan: bool
    latest_event_id: str | None
    has_new_events: bool
    changed_files: list[str] = Field(default_factory=list)
    reason: str
