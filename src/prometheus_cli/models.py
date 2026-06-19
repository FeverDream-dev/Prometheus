from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class AutonomyMode(str, Enum):
    COPILOT = "copilot"
    PILOT = "pilot"
    ASTRONAUT = "astronaut"


class Risk(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    DESTRUCTIVE = "destructive"


class ModelSpec(BaseModel):
    provider: str = "ollama"
    model: str
    role: Literal["controller", "coder", "reasoner", "reviewer", "vision"]
    base_url: str | None = None
    api_key_env: str | None = None
    context_window: int = 32768
    keep_alive: int | str = "5m"
    tool_capable: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class ModelBundle(BaseModel):
    name: str
    description: str = ""
    minimum_ram_gb: int = 8
    minimum_vram_gb: int = 0
    sequential_loading: bool = True
    models: list[ModelSpec]

    def for_role(self, role: str) -> ModelSpec:
        for model in self.models:
            if model.role == role:
                return model
        if role in {"coder", "reviewer", "reasoner"}:
            return self.for_role("controller")
        raise KeyError(f"No model configured for role: {role}")


class Settings(BaseModel):
    workspace: Path = Field(default_factory=Path.cwd)
    mode: AutonomyMode = AutonomyMode.PILOT
    bundle_file: Path | None = None
    sandbox: bool = True
    allow_package_install: bool = False
    allow_network: bool = True
    telemetry: bool = False
    sounds: bool = True
    multi_agent_review: bool = True
    target_completion: int = Field(default=95, ge=1, le=100)
    attempts_before_escalation: int = Field(default=5, ge=1, le=20)
    max_steps: int = Field(default=50, ge=1)
    max_runtime_minutes: int = Field(default=240, ge=1)


class ToolCall(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class AgentTurn(BaseModel):
    thought_summary: str = ""
    status: Literal["working", "needs_user", "complete", "blocked"] = "working"
    message: str = ""
    completion_percent: int = Field(default=0, ge=0, le=100)
    calls: list[ToolCall] = Field(default_factory=list)

