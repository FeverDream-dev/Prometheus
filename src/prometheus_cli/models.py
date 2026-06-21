from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class AutonomyMode(str, Enum):
    COPILOT = "copilot"
    PILOT = "pilot"
    ASTRONAUT = "astronaut"


class SandboxTier(str, Enum):
    OFF = "off"
    BASIC = "basic"
    DOCKER = "docker"
    NATIVE = "native"


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
    active_bundle_id: str | None = None
    sandbox: bool = True
    sandbox_tier: SandboxTier = SandboxTier.OFF
    allow_package_install: bool = False
    allow_network: bool = True
    telemetry: bool = False
    sounds: bool = True
    multi_agent_review: bool = True
    target_completion: int = Field(default=95, ge=1, le=100)
    attempts_before_escalation: int = Field(default=5, ge=1, le=20)
    max_steps: int = Field(default=0, ge=0)
    max_runtime_minutes: int = Field(default=0, ge=0)
    unlimited_local_sessions: bool = True
    local_only: bool = False
    max_context_tokens: int = Field(default=0, ge=0)
    max_output_tokens: int = Field(default=0, ge=0)
    keep_alive_minutes: int = Field(default=0, ge=0)
    sequential_loading: bool | None = None
    disk_safety_floor_gb: int = Field(default=8, ge=0)
    memory_safety_floor_gb: float = Field(default=2.0, ge=0)
    cloud_monthly_budget_usd: float | None = Field(default=None, ge=0)
    checkpoint_interval_steps: int = Field(default=10, ge=1)
    reduced_motion: bool = False
    tui_telemetry_panel: bool = True

    def step_limit(self) -> int | None:
        return None if self.max_steps == 0 else self.max_steps

    def runtime_limit_minutes(self) -> int | None:
        return None if self.max_runtime_minutes == 0 else self.max_runtime_minutes

    def effective_sandbox_tier(self) -> SandboxTier:
        if self.sandbox_tier != SandboxTier.OFF:
            return self.sandbox_tier
        if self.sandbox:
            return SandboxTier.NATIVE
        return SandboxTier.OFF


class ToolCall(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class Criterion(BaseModel):
    description: str
    weight: int = Field(default=1, ge=1, le=100)
    critical: bool = False


class AgentTurn(BaseModel):
    thought_summary: str = ""
    status: Literal["working", "needs_user", "complete", "blocked"] = "working"
    message: str = ""
    completion_percent: int = Field(default=0, ge=0, le=100)
    calls: list[ToolCall] = Field(default_factory=list)
    criteria_proposed: list[Criterion] = Field(default_factory=list)
    criteria_met: list[str] = Field(default_factory=list)

