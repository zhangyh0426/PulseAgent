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
    schema_version: int = 2
    project_root: str
    initialized_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_hashes: dict[str, str | None] = Field(default_factory=dict)
    last_acknowledged_event_id: str | None = None
    last_acknowledged_plan_sha256: str | None = None
    last_acknowledged_at: datetime | None = None


class InterruptDecision(BaseModel):
    needs_replan: bool
    latest_event_id: str | None
    has_new_events: bool
    changed_files: list[str] = Field(default_factory=list)
    pending_replan_event_id: str | None = None
    pending_replan_files: list[str] = Field(default_factory=list)
    last_acknowledged_event_id: str | None = None
    last_acknowledged_plan_sha256: str | None = None
    reason: str


class ReplanAckDecision(BaseModel):
    accepted: bool
    acknowledged_event_id: str | None = None
    plan_sha256: str | None = None
    reason: str
