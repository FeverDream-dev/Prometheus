from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1
MAX_WORKING_WORDS = 1024


class FactConfidence(str, Enum):
    USER_EXPLICIT = "user_explicit"
    OBSERVED = "observed"
    DECIDED = "decided"
    INFERRED = "inferred"
    STALE = "stale"
    CONFLICTED = "conflicted"


CERTAIN = {FactConfidence.USER_EXPLICIT, FactConfidence.OBSERVED, FactConfidence.DECIDED}


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: int | None = None
    source: Literal["user", "tool", "test", "build", "browser", "model", "git"] = "model"
    ref: str = ""


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    summary: str
    confidence: FactConfidence = FactConfidence.INFERRED
    provenance: Provenance = Field(default_factory=Provenance)
    created_at: str = ""
    superseded_by: str | None = None

    @property
    def is_certain(self) -> bool:
        return self.confidence in CERTAIN


class Constraint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    statement: str
    source_event_id: int | None = None
    active: bool = True


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = SCHEMA_VERSION
    objective: str
    success_criteria: list[str] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    approvals: list[str] = Field(default_factory=list)
    rejections: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def add_constraint(self, constraint: Constraint) -> None:
        for existing in self.constraints:
            if existing.statement == constraint.statement:
                return
        self.constraints.append(constraint)

    def record_conflict(self, description: str) -> None:
        if description not in self.conflicts:
            self.conflicts.append(description)


TaskStatus = Literal["pending", "active", "passing", "failing", "blocked", "superseded"]


class TaskNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    description: str
    status: TaskStatus = "pending"
    depends_on: list[str] = Field(default_factory=list)
    acceptance: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    micro_step: str = ""


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    question: str
    choice: str
    alternatives: list[str] = Field(default_factory=list)
    rationale: str = ""
    author: str = "system"
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: str = ""


class FailureSignature(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    signature: str
    hypothesis: str = ""
    count: int = 0
    last_seen: str = ""
    superseded: bool = False


SeatName = Literal["envoy", "forge", "argus"]


class Handoff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = SCHEMA_VERSION
    task_id: str
    from_seat: SeatName
    to_seat: SeatName
    objective: str = ""
    acceptance: list[str] = Field(default_factory=list)
    verified_facts: list[dict[str, str]] = Field(default_factory=list)
    changes: list[dict[str, str]] = Field(default_factory=list)
    evidence: list[dict[str, str]] = Field(default_factory=list)
    failure_signature: str | None = None
    next_action: str = ""
    prohibited_actions: list[str] = Field(default_factory=list)
    created_at: str = ""


class MemoryRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    checksum: str
    word_count: int
    created_at: str
    path: str = ""


class WorkingMemoryStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool
    word_count: int
    limit: int = MAX_WORKING_WORDS
    version: int
    checksum: str
    last_updated: str = ""
    recovered: bool = False
    error: str = ""


__all__ = [
    "CERTAIN",
    "Constraint",
    "Decision",
    "Fact",
    "FactConfidence",
    "FailureSignature",
    "Handoff",
    "Intent",
    "MAX_WORKING_WORDS",
    "MemoryRevision",
    "Provenance",
    "SCHEMA_VERSION",
    "TaskNode",
    "WorkingMemoryStatus",
]
