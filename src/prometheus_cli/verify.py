"""Deterministic workspace verification — no model opinion."""

from __future__ import annotations

from pathlib import Path


def _skip_part(path: Path) -> bool:
    parts = set(path.parts)
    return ".git" in parts or ".prometheus" in parts


_ARTIFACT_GLOBS = ("**/*.html", "**/*.css", "**/*.js", "**/*.py", "**/*.md", "**/*.json", "**/*.txt")
_SKIP_SUFFIXES = {".log"}


def nonempty_artifact_count(root: Path, *, min_bytes: int = 10) -> int:
    """Count workspace deliverable files (excludes .git / .prometheus / logs)."""
    if not root.is_dir():
        return 0
    seen: set[Path] = set()
    for pattern in _ARTIFACT_GLOBS:
        for path in root.glob(pattern):
            if not path.is_file() or path in seen or _skip_part(path.relative_to(root)):
                continue
            if path.suffix.lower() in _SKIP_SUFFIXES:
                continue
            try:
                if path.stat().st_size >= min_bytes:
                    seen.add(path)
            except OSError:
                continue
    return len(seen)


def verify_workspace_progress(tools, *, min_bytes: int = 1) -> tuple[bool, str]:
    """True when tests pass, git shows change, or non-empty artifacts exist."""
    root = Path(getattr(tools, "root", Path.cwd()))
    test_cmd = None
    try:
        from .agent.arena import detect_test_command

        test_cmd = detect_test_command(root)
    except Exception:
        test_cmd = None

    if test_cmd and hasattr(tools, "run_command"):
        out = tools.run_command(test_cmd, timeout=180)
        passed = "passed" in out and (" failed" not in out.lower())
        if passed:
            return True, _last_meaningful_line(out)
        return False, _last_meaningful_line(out)

    porcelain = ""
    if hasattr(tools, "git_status_porcelain"):
        porcelain = tools.git_status_porcelain().strip()

    diff = ""
    if hasattr(tools, "git_diff"):
        diff = tools.git_diff().strip()

    artifacts = nonempty_artifact_count(root, min_bytes=min_bytes)
    if artifacts > 0:
        detail = f"{artifacts} non-empty file(s) in workspace"
        if porcelain:
            detail += f"; git: {porcelain[:100]}"
        return True, detail

    if porcelain:
        return False, f"git shows changes but files are empty or too small: {porcelain[:120]}"

    if diff and "fatal" not in diff.lower():
        return True, "patch applied (tracked diff)"

    return False, "no change made"


def self_check_write(tools, path: str, *, min_bytes: int = 10) -> str:
    """Read back a path after write_file; return evidence for the model."""
    if not path or not hasattr(tools, "read_file"):
        return "SELF-CHECK: skipped (no path)"
    try:
        body = tools.read_file(path, max_chars=500)
        size = len(body.strip())
        if size < min_bytes:
            return (
                f"SELF-CHECK FAIL: {path} has only {size} chars after write. "
                "Rewrite with full content, then read_file to confirm."
            )
        preview = body.strip()[:120].replace("\n", " ")
        return f"SELF-CHECK OK: {path} ({size} chars). Preview: {preview!r}"
    except Exception as exc:
        return f"SELF-CHECK FAIL: could not read {path}: {exc}"


def _last_meaningful_line(output: str) -> str:
    import re

    for line in output.splitlines():
        if re.search(r"FAILED|AssertionError|assert\b|Error:|Exception", line):
            return line.strip()[:160]
    lines = [s.strip() for s in output.splitlines() if s.strip()]
    return lines[-1] if lines else "(no output)"


__all__ = ["nonempty_artifact_count", "self_check_write", "verify_workspace_progress"]
