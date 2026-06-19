from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .arena import MicroStepEngine
from .seats import SEATS


@dataclass
class CandidateResult:
    label: str
    worktree: Path
    passed: bool
    evidence: str = ""
    changed_files: list[str] = field(default_factory=list)
    score: tuple = ()


@dataclass
class DeepArenaResult:
    winner: CandidateResult | None = None
    candidates: list[CandidateResult] = field(default_factory=list)
    applied: bool = False
    reason: str = ""


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)


def _changed_files(worktree: Path) -> list[str]:
    res = _run_git(["diff", "--name-only"], worktree)
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def deep_arena(
    store,
    workspace: Path,
    forge_provider_factory: Callable[[int, Path], object],
    verify_in: Callable[[object], tuple[bool, str]],
    engine: MicroStepEngine,
    *,
    n: int = 2,
    base_ref: str = "HEAD",
    on_update: Callable[[str], None] = lambda _m: None,
) -> DeepArenaResult:
    worktree_root = workspace / ".prometheus" / "worktrees"
    worktree_root.mkdir(parents=True, exist_ok=True)
    candidates: list[CandidateResult] = []
    on_update(f"Deep arena: spawning {n} isolated candidates from {base_ref}.")
    for i in range(n):
        wt = worktree_root / f"cand-{i}"
        if wt.exists():
            shutil.rmtree(wt, ignore_errors=True)
        res = _run_git(["worktree", "add", "--detach", str(wt), base_ref], workspace)
        if res.returncode != 0:
            on_update(f"worktree add failed for cand-{i}: {res.stderr.strip()}")
            continue
        wt_tools = _WorkspaceToolsAt(wt)
        wt_engine = MicroStepEngine(store=store, tools=wt_tools, settings=engine.settings, approve=engine.approve)
        provider = forge_provider_factory(i, wt)
        try:
            wt_engine.run_seat(SEATS["forge"], provider)
        except Exception as exc:
            on_update(f"cand-{i} forge error: {exc}")
        passed, evidence = verify_in(wt_tools)
        changed = _changed_files(wt)
        score = (1 if passed else 0, -len(changed), -len(evidence))
        cand = CandidateResult(label=f"cand-{i}", worktree=wt, passed=passed, evidence=evidence, changed_files=changed, score=score)
        candidates.append(cand)
        on_update(f"cand-{i}: {'PASS' if passed else 'FAIL'} ({len(changed)} file(s) changed)")
    if not candidates:
        return DeepArenaResult(reason="no candidates could be created")
    winner = max(candidates, key=lambda c: c.score)
    result = DeepArenaResult(winner=winner, candidates=candidates)
    if winner.passed:
        for rel in winner.changed_files:
            src = winner.worktree / rel
            dst = workspace / rel
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        result.applied = True
        result.reason = f"applied {winner.label} ({len(winner.changed_files)} file(s))"
        on_update(f"Deep arena winner: {winner.label}; applied to workspace.")
    else:
        result.reason = "no candidate passed; discarded all"
        on_update("Deep arena: no candidate passed; all discarded.")
    for cand in candidates:
        _run_git(["worktree", "remove", "--force", str(cand.worktree)], workspace)
    return result


class _WorkspaceToolsAt:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _resolve(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise PermissionError(f"Path escapes worktree: {relative}")
        return candidate

    def read_file(self, path: str, max_chars: int = 100_000) -> str:
        p = self._resolve(path)
        return p.read_text(encoding="utf-8")[:max_chars] if p.exists() else f"(missing) {path}"

    def write_file(self, path: str, content: str) -> str:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(p)
        return f"wrote {len(content)} chars to {path}"

    def list_files(self, pattern: str = "*") -> str:
        from fnmatch import fnmatch

        rows = [str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file()
                and ".prometheus" not in p.parts and fnmatch(str(p.name), pattern)]
        return "\n".join(sorted(rows))

    def run_command(self, command: list[str], timeout: int = 120) -> str:
        try:
            res = subprocess.run(command, cwd=str(self.root), capture_output=True, text=True, timeout=timeout, check=False)
            return (res.stdout + res.stderr).strip()[-4000:]
        except (subprocess.SubprocessError, OSError) as exc:
            return f"command failed: {exc}"


__all__ = ["CandidateResult", "DeepArenaResult", "deep_arena"]
