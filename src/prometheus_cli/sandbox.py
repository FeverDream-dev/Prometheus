"""OS-level sandbox enforcement for PROMETHEUS command execution.

Detects available sandbox tools (bubblewrap on Linux, sandbox-exec on macOS)
and wraps commands to confine filesystem access to the workspace and system
read-only paths. When no sandbox tool is available, logs a persistent warning
so the user knows execution is unsandboxed.

This implements SECURITY.md sandbox tiers:
  Tier 1: native restricted process (no shell — already enforced by arg arrays)
  Tier 3: platform sandbox (bwrap / sandbox-exec — this module)
  Tier 4: unsandboxed with explicit warning

Container isolation (Tier 2) and Windows Job Objects are future work.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def docker_available() -> bool:
    return shutil.which("docker") is not None


def tier_available(tier: str) -> tuple[bool, str]:
    """Report whether a sandbox tier can actually enforce on this host."""
    if tier == "off":
        return True, "no enforcement requested"
    if tier == "basic":
        return True, "path + command policy enforced in-process"
    if tier == "native":
        broker = SandboxBroker(Path("."), enabled=True)
        if broker.tool is not None:
            return True, f"native confinement via {broker.tool}"
        return False, broker.warning or "no native sandbox tool found"
    if tier == "docker":
        if docker_available():
            return True, "docker present; disposable-container enforcement available"
        return False, "docker not installed; install docker or use 'native'/'basic'"
    return False, f"unknown sandbox tier: {tier}"


class SandboxBroker:
    def __init__(
        self,
        workspace: Path,
        enabled: bool = True,
        allow_network: bool = True,
    ):
        self.workspace = workspace.resolve()
        self.enabled = enabled
        self.allow_network = allow_network
        self.tool = self._detect_tool()
        self._ro_bind_dirs = self._system_ro_dirs()

    def _detect_tool(self) -> str | None:
        if sys.platform.startswith("linux") and shutil.which("bwrap"):
            return "bwrap"
        if sys.platform == "darwin" and shutil.which("sandbox-exec"):
            return "sandbox-exec"
        return None

    def _system_ro_dirs(self) -> list[str]:
        candidates = ["/usr", "/lib", "/lib32", "/lib64", "/bin", "/sbin", "/etc", "/opt"]
        if sys.platform == "darwin":
            candidates = ["/usr", "/bin", "/sbin", "/etc", "/System", "/Library", "/opt"]
        return [d for d in candidates if Path(d).exists()]

    @property
    def active(self) -> bool:
        return self.enabled and self.tool is not None

    @property
    def tier(self) -> str:
        if not self.enabled:
            return "unsandboxed"
        if self.tool is None:
            return "unsandboxed-warning"
        return f"sandboxed-{self.tool}"

    @property
    def warning(self) -> str | None:
        if self.enabled and self.tool is None:
            if sys.platform.startswith("linux"):
                return "Sandbox enabled but bubblewrap (bwrap) not found. Install: apt install bubblewrap"
            if sys.platform == "darwin":
                return "Sandbox enabled but sandbox-exec not found."
            return f"Sandbox enabled but no tool available on {sys.platform}."
        return None

    def wrap(self, command: list[str]) -> list[str]:
        if not self.enabled or self.tool is None:
            return command
        if self.tool == "bwrap":
            return self._bwrap_command(command)
        if self.tool == "sandbox-exec":
            return self._sandbox_exec_command(command)
        return command

    def _bwrap_command(self, command: list[str]) -> list[str]:
        parts: list[str] = ["bwrap"]
        for d in self._ro_bind_dirs:
            parts.extend(["--ro-bind", d, d])
        parts.extend(["--bind", str(self.workspace), str(self.workspace)])
        parts.extend(["--tmpfs", "/tmp"])
        parts.extend(["--dev", "/dev"])
        parts.extend(["--proc", "/proc"])
        if not self.allow_network:
            parts.append("--unshare-net")
        parts.extend(["--die-with-parent", "--"])
        parts.extend(command)
        return parts

    def _sandbox_exec_command(self, command: list[str]) -> list[str]:
        workspace_policy = f'(allow file-write* (subpath "{self.workspace}"))'
        net_policy = "" if self.allow_network else "(deny network*)"
        policy = f"(version 1)(allow default)(deny file-write*){workspace_policy}{net_policy}"
        return ["sandbox-exec", "-p", policy, "--"] + command
