from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

from ..models import SandboxTier, Settings
from ..sandbox import SandboxBroker

_CATASTROPHIC = re.compile(
    r"(?:^|\s)(?:rm\s+-rf?\s*[/%~]|rm\s+-[a-z]*r[a-z]*\s*[/%~]|mkfs|dd\s+.*of=/dev/|"
    r":\(\)\s*\{|>\s*/dev/sd|shutdown|halt|reboot|chmod\s+-R\s+777\s*[/%~]|"
    r"chown\s+-R\s+\S+\s*[/%~])",
    re.IGNORECASE,
)
_REQUIRES_NETWORK = re.compile(r"(?:^|\s|/)(?:curl|wget|nc|netcat|ssh|scp|ftp|telnet)\b", re.IGNORECASE)
_REQUIRES_INSTALL = re.compile(
    r"(?:^|\s|/)(?:pip|pip3|pipx|uv\s+pip|apt|apt-get|brew|npm|yarn|pnpm|gem\s+install|"
    r"cargo\s+install|go\s+install|winget)\b",
    re.IGNORECASE,
)
_REQUIRES_PRIVILEGE = re.compile(r"(?:^|\s)(?:sudo|su\b|doas)\b", re.IGNORECASE)
_PIPE_TO_SHELL = re.compile(r"\|\s*(?:sh|bash|zsh)\b", re.IGNORECASE)
_SECRET_ENV_RE = re.compile(
    r"(?:API.?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|PRIVATE.?KEY|AUTH)",
    re.IGNORECASE,
)


class WorkspaceTools:
    def __init__(self, root: Path, sandbox: SandboxBroker | None = None):
        self.root = root.resolve()
        self.sandbox = sandbox or SandboxBroker(self.root, enabled=False)
        self.tier = SandboxTier.OFF
        self.allow_network = True
        self.allow_package_install = False

    @classmethod
    def from_settings(cls, root: Path, settings: Settings) -> WorkspaceTools:
        tier = settings.effective_sandbox_tier()
        tools = cls(root)
        tools.tier = tier
        tools.allow_network = settings.allow_network
        tools.allow_package_install = settings.allow_package_install
        if tier == SandboxTier.NATIVE:
            tools.sandbox = SandboxBroker(tools.root, enabled=True)
        else:
            tools.sandbox = SandboxBroker(tools.root, enabled=False)
        return tools

    def _resolve(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise PermissionError(f"Path escapes workspace: {relative}")
        return candidate

    def read_file(self, path: str, max_chars: int = 100_000) -> str:
        return self._resolve(path).read_text(encoding="utf-8")[:max_chars]

    def write_file(self, path: str, content: str) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".prometheus_write_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
        except BaseException:
            os.unlink(tmp)
            raise
        return f"wrote {path} ({len(content)} chars)"

    def list_files(self, pattern: str = "*") -> str:
        return "\n".join(
            str(path.relative_to(self.root))
            for path in sorted(self.root.rglob(pattern))
            if path.is_file() and ".git" not in path.parts
        )[:100_000]

    def _policy_block(self, command: list[str]) -> str | None:
        if self.tier == SandboxTier.OFF:
            return None
        rendered = " ".join(command)
        if _CATASTROPHIC.search(rendered):
            return ("catastrophic command",
                    "hard-deny pattern (rm -rf /, mkfs, dd to device, chmod -R 777 /, fork bomb, etc.)")
        if _REQUIRES_PRIVILEGE.search(rendered):
            return ("privilege escalation", "sudo/su/doas is blocked under sandbox")
        if _PIPE_TO_SHELL.search(rendered):
            return ("pipe-to-shell", "piping untrusted output to a shell is blocked under sandbox")
        if _REQUIRES_INSTALL.search(rendered) and not self.allow_package_install:
            return ("package install", "package install disabled (set allow_package_install=True to permit)")
        if _REQUIRES_NETWORK.search(rendered) and not self.allow_network:
            return ("network", "network command disabled (set allow_network=True to permit)")
        return None

    def run_command(self, command: list[str], timeout: int = 120) -> str:
        if not command:
            raise ValueError("command cannot be empty")
        block = self._policy_block(command)
        if block is not None:
            label, reason = block
            return (
                f"[sandbox:{self.tier.value}] BLOCKED {label}\n"
                f"{reason}.\nRe-run with an explicit, scoped command or adjust policy if this was intended."
            )
        wrapped = self.sandbox.wrap(command)
        run_env = None
        if self.tier != SandboxTier.OFF:
            run_env = {
                k: v for k, v in os.environ.items()
                if not _SECRET_ENV_RE.search(k)
            }
        result = subprocess.run(
            wrapped,
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=run_env,
        )
        sandbox_note = f"[sandbox:{self.sandbox.tier}]\n" if self.sandbox.active else ""
        return (
            f"{sandbox_note}exit_code={result.returncode}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )[-100_000:]

    def _git(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
        if not (self.root / ".git").exists():
            subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def git_checkpoint(self, message: str) -> str:
        self._git(["add", "-A"])
        result = self._git(["commit", "-m", message])
        if result.returncode != 0 and "nothing to commit" in (result.stdout + result.stderr):
            return "nothing to commit"
        return result.stdout + result.stderr

    def git_log(self, limit: int = 10) -> str:
        result = self._git(["log", f"-{limit}", "--oneline"])
        return result.stdout if result.returncode == 0 else result.stderr

    def git_current_sha(self) -> str | None:
        result = self._git(["rev-parse", "HEAD"])
        return result.stdout.strip() if result.returncode == 0 else None

    def git_diff(self, path: str | None = None) -> str:
        args = ["diff", "HEAD"]
        if path:
            self._resolve(path)
            args.extend(["--", path])
        result = self._git(args)
        return result.stdout[:100_000]

    def git_rollback(self, commit_sha: str) -> str:
        if not commit_sha or not all(c in "0123456789abcdef" for c in commit_sha.lower()):
            raise ValueError("invalid commit SHA")
        result = self._git(["reset", "--hard", commit_sha])
        return result.stdout + result.stderr

