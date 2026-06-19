from __future__ import annotations

import subprocess
from pathlib import Path


class WorkspaceTools:
    def __init__(self, root: Path):
        self.root = root.resolve()

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
        target.write_text(content, encoding="utf-8")
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
        result = subprocess.run(
            command,
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return (
            f"exit_code={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )[-100_000:]

    def git_checkpoint(self, message: str) -> str:
        if not (self.root / ".git").exists():
            subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout + result.stderr

