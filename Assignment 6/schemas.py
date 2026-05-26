"""
schemas.py
Pydantic v2 typed contracts for every role boundary in the agent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    kind: Literal["fact", "preference", "tool_outcome", "scratchpad"]
    keywords: list[str]
    descriptor: str
    value: dict
    artifact_id: str | None = None
    source: str
    run_id: str
    goal_id: str | None = None
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Artifact(BaseModel):
    id: str               # "art:<sha256-prefix>"
    content_type: str
    size_bytes: int
    source: str
    descriptor: str


class Goal(BaseModel):
    id: str
    text: str
    done: bool = False
    attach_artifact_id: str | None = None


class Observation(BaseModel):
    goals: list[Goal]

    @property
    def all_done(self) -> bool:
        return len(self.goals) > 0 and all(g.done for g in self.goals)

    def next_unfinished(self) -> Goal | None:
        return next((g for g in self.goals if not g.done), None)


class ToolCall(BaseModel):
    name: str
    arguments: dict


class DecisionOutput(BaseModel):
    answer: str | None = None
    tool_call: ToolCall | None = None

    @property
    def is_answer(self) -> bool:
        return self.answer is not None
