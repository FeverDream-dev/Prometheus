from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from ..sandbox import SandboxBroker


class WorkspaceTools:
    def __init__(self, root: Path, sandbox: SandboxBroker | None = None):
        self.root = root.resolve()
        self.sandbox = sandbox or SandboxBroker(self.root, enabled=False)

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

    def run_command(self, command: list[str], timeout: int = 120) -> str:
        if not command:
            raise ValueError("command cannot be empty")
        wrapped = self.sandbox.wrap(command)
        result = subprocess.run(
            wrapped,
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
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

