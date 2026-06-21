"""Sanitized diagnostics collection for PROMETHEUS.

Used by ``prometheus diagnose`` and the ``/diagnose`` TUI command. Collects
versions, config status, recent session errors, recent TUI/output errors,
installer logs (if present), Ollama status, git status, and test command
suggestions. Output is always passed through ``redaction.redact`` so secrets
(API keys, bearer tokens, password assignments) are stripped before anything
is written to disk or shown in the TUI.

Nothing here reads or copies: ``.env`` files, model weights, private project
source, or anything under ``.prometheus/memory/`` (project memory is
user-owned). Only operational metadata is collected.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .redaction import redact

_SECRET_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "credentials.json", "secrets.yaml", "secrets.yml", "id_rsa", "id_ed25519",
}
_TEST_HINTS = [
    ("Python unit/integration tests", "pytest -q"),
    ("Lint and style", "ruff check src tests"),
    ("Bytecode compiles", "python -m compileall src"),
    ("Sandbox enforcement suite", "prometheus sandbox test --workspace <dir> --all"),
    ("TUI smoke (manual)", "prometheus tui"),
]


def _redact(text: str) -> str:
    try:
        return redact(text)
    except Exception:
        return _fallback_redact(text)


def _fallback_redact(text: str) -> str:
    patterns = [
        (r"(sk-[a-zA-Z0-9]{20,})", "[REDACTED]"),
        (r"(?i)(password|secret|token|api[_-]?key)\s*[=:]\s*\S+", r"\1=[REDACTED]"),
        (r"(Bearer\s+[A-Za-z0-9._~+/=-]{20,})", "Bearer [REDACTED]"),
        (r"(gh[pousr]_[A-Za-z0-9]{36})", "[REDACTED]"),
    ]
    out = text
    for pat, repl in patterns:
        out = re.sub(pat, repl, out)
    return out


def _safe(path: Path) -> bool:
    name = path.name.lower()
    if name in _SECRET_FILENAMES:
        return False
    if name.endswith((".gguf", ".safetensors", ".bin", ".pt", ".ckpt", ".onnx")):
        return False
    if name.endswith((".env", ".pem", ".key")):
        return False
    return True


def _parse_since(since_str: str | None) -> datetime | None:
    if not since_str:
        return None
    m = re.match(r"^(\d+)\s*(m|h|d|w)?$", since_str.strip().lower())
    if not m:
        return None
    value = int(m.group(1))
    unit = m.group(2) or "m"
    multiplier = {"m": 1, "h": 60, "d": 60 * 24, "w": 60 * 24 * 7}[unit]
    return datetime.now(timezone.utc) - timedelta(minutes=value * multiplier)


def collect_python_env() -> dict:
    return {
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "os_name": os.name,
    }


def collect_prometheus_version() -> dict:
    try:
        from importlib.metadata import version
        v = version("prometheus-local-agent")
    except Exception:
        v = "unknown"
    return {
        "package_version": v,
        "cli_entry": "prometheus_cli.cli:app",
        "git_branch": _git_branch(),
    }


def _git_branch() -> str | None:
    r = _run(["git", "-C", os.getcwd(), "rev-parse", "--abbrev-ref", "HEAD"], timeout=1.0)
    if r and r.returncode == 0:
        return r.stdout.strip()
    return None


def collect_config_status() -> dict:
    try:
        from .config import CONFIG_HOME, load_settings
        settings = load_settings()
        return {
            "config_home": str(CONFIG_HOME),
            "config_exists": (CONFIG_HOME / "config.yaml").exists(),
            "active_bundle_id": settings.active_bundle_id,
            "mode": settings.mode.value,
            "sandbox_tier": settings.effective_sandbox_tier().value,
            "local_only": settings.local_only,
            "reduced_motion": settings.reduced_motion,
            "multi_agent_review": settings.multi_agent_review,
        }
    except Exception as exc:
        return {"error": _redact(str(exc))[:200]}


def collect_recent_session_errors(since: datetime | None = None, limit: int = 20) -> list[dict]:
    try:
        from .config import ensure_home
        from .session import SessionStore
        home = ensure_home()
        store = SessionStore(home / "sessions" / "prometheus.db")
        try:
            rows = store.list_sessions(limit=limit)
        finally:
            store.close()
        out: list[dict] = []
        for r in rows:
            out.append({
                "id": r.id,
                "objective": _redact(r.objective)[:120],
                "status": r.status,
                "completion_percent": r.completion_percent,
            })
        return out
    except Exception as exc:
        return [{"error": _redact(str(exc))[:200]}]


def collect_recent_output_logs(limit: int = 40) -> list[str]:
    candidates = [
        Path.cwd() / ".prometheus" / "astronaut" / "events.jsonl",
        Path.home() / ".prometheus" / "prometheus.log",
    ]
    out: list[str] = []
    for path in candidates:
        if path.exists() and _safe(path):
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                out.extend(lines[-limit:])
            except OSError:
                pass
    return [_redact(ln)[:300] for ln in out[-limit:]]


def collect_installer_logs() -> list[str]:
    out: list[str] = []
    for path in (
        Path.home() / ".local" / "share" / "prometheus" / "install.log",
        Path.home() / ".local" / "share" / "prometheus" / "installer.log",
    ):
        if path.exists() and _safe(path):
            try:
                out.extend(path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:])
            except OSError:
                pass
    return [_redact(ln)[:300] for ln in out[-40:]]


def collect_ollama_status() -> dict:
    try:
        from .onboarding import check_ollama
        status = check_ollama()
        return {
            "installed": status.installed,
            "running": status.running,
            "model_count": len(status.models),
            "models_sample": status.models[:6],
        }
    except Exception as exc:
        return {"error": _redact(str(exc))[:200]}


def collect_git_status() -> dict:
    ws = Path.cwd()
    if not (ws / ".git").exists():
        return {"available": False}
    branch = _run(["git", "-C", str(ws), "rev-parse", "--abbrev-ref", "HEAD"], timeout=1.0)
    status = _run(["git", "-C", str(ws), "status", "--porcelain"], timeout=1.0)
    return {
        "available": True,
        "branch": branch.stdout.strip() if branch and branch.returncode == 0 else None,
        "modified_files": (
            len([ln for ln in status.stdout.splitlines() if ln.strip()])
            if status and status.returncode == 0 else None
        ),
    }


def collect_test_hints() -> list[dict]:
    return [{"label": lbl, "command": cmd} for lbl, cmd in _TEST_HINTS]


def _run(cmd: list[str], timeout: float = 2.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None


def collect_diagnostics(since_str: str | None = None) -> dict:
    since = _parse_since(since_str)
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "since": since.isoformat() if since else None,
        "python_env": collect_python_env(),
        "prometheus": collect_prometheus_version(),
        "config": collect_config_status(),
        "recent_sessions": collect_recent_session_errors(since=since),
        "recent_output_logs": collect_recent_output_logs(),
        "installer_logs": collect_installer_logs(),
        "ollama": collect_ollama_status(),
        "git": collect_git_status(),
        "test_hints": collect_test_hints(),
        "secret_redaction": "applied via prometheus_cli.redaction.redact",
    }


def render_diagnostics_lines(diag: dict) -> list[str]:
    out: list[str] = [
        "[bold cyan]PROMETHEUS diagnostics[/bold cyan]"
        f"  [dim]{diag.get('collected_at', '?')}[/dim]",
        "",
    ]
    py = diag.get("python_env", {})
    out.append(f"  Python: {py.get('python_version', '?')} on {py.get('platform', '?')}")
    prom = diag.get("prometheus", {})
    out.append(f"  Prometheus: {prom.get('package_version', '?')} · branch {prom.get('git_branch', '?')}")
    cfg = diag.get("config", {})
    if cfg.get("active_bundle_id"):
        out.append(f"  Bundle: {cfg['active_bundle_id']} · mode: {cfg.get('mode')}")
    else:
        out.append("  Bundle: [yellow]none configured[/yellow]")
    out.append(f"  Sandbox: {cfg.get('sandbox_tier', '?')} · local_only: {cfg.get('local_only')}")

    ollama = diag.get("ollama", {})
    ollama_state = "OK" if ollama.get("running") else "[red]down[/red]"
    out.append(f"  Ollama: {ollama_state} ({ollama.get('model_count', 0)} models)")

    git = diag.get("git", {})
    if git.get("available"):
        dirty = git.get("modified_files", 0) > 0
        tag = "[yellow]dirty[/yellow]" if dirty else "[green]clean[/green]"
        out.append(f"  Git: {git.get('branch', '?')} · {tag} · {git.get('modified_files', 0)} changes")

    out.append("")
    out.append("[bold]Recent sessions:[/bold]")
    sessions = diag.get("recent_sessions", [])
    if not sessions:
        out.append("  [dim]none[/dim]")
    for s in sessions[:5]:
        if "error" in s:
            out.append(f"  [red]err: {s['error']}[/red]")
        else:
            out.append(f"  {s.get('id', '?')[:12]}  {s.get('completion_percent', 0):>5.1f}%  "
                       f"{s.get('status', '?'):<10}  {s.get('objective', '')[:50]}")

    out.append("")
    out.append("[bold]Try:[/bold]")
    for hint in diag.get("test_hints", []):
        out.append(f"  {hint.get('label'):<32}  {hint.get('command')}")

    out.append("")
    out.append(f"[dim]{diag.get('secret_redaction', 'redaction applied')}[/dim]")
    return out


def _redact_recursive(value):
    if isinstance(value, str):
        return _redact(value)
    if isinstance(value, list):
        return [_redact_recursive(v) for v in value]
    if isinstance(value, dict):
        return {k: _redact_recursive(v) for k, v in value.items()}
    return value


def export_zip(diag: dict, out_path: Path | str) -> Path:
    import zipfile

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    safe = _redact_recursive(diag)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("diagnostics.json", json.dumps(safe, indent=2, default=str))
        zf.writestr(
            "README.txt",
            "PROMETHEUS diagnostics export.\n"
            "Secrets stripped via prometheus_cli.redaction.redact before export.\n"
            "No model weights, .env files, or private project source included.\n",
        )
    return out_path


__all__ = [
    "collect_config_status",
    "collect_diagnostics",
    "collect_git_status",
    "collect_installer_logs",
    "collect_ollama_status",
    "collect_prometheus_version",
    "collect_python_env",
    "collect_recent_output_logs",
    "collect_recent_session_errors",
    "collect_test_hints",
    "export_zip",
    "render_diagnostics_lines",
]
