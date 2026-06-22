"""State adapter for the PROMETHEUS TUI.

Single source of truth for everything the TUI displays. The App and all
screens/widgets read from :class:`TuiSnapshot` and never call the underlying
probes directly. This isolates the UI from network/IO flakiness and lets the
demo mode produce realistic data without Ollama, cloud keys, or model downloads.

Two construction paths:
    * :func:`collect_snapshot` — real mode. Calls every probe (hardware, ollama,
      git, memory, sandbox, sessions). Each probe is defensive: a failure
      degrades to an "unknown" sentinel rather than crashing the TUI.
    * :func:`collect_demo_snapshot` — demo mode. Returns a fully-mocked,
      realistic-looking snapshot. Clearly labelled via ``is_demo=True``.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


def _short(path: Path, max_len: int = 48) -> str:
    s = str(path)
    if len(s) <= max_len:
        return s
    return "…" + s[-(max_len - 1):]


@dataclass
class GitInfo:
    branch: str | None = None
    dirty: bool | None = None
    recent_commits: list[str] = field(default_factory=list)
    available: bool = False

    @property
    def status_label(self) -> str:
        if not self.available:
            return "no repo"
        return "dirty" if self.dirty else "clean"


@dataclass
class MemoryInfo:
    ok: bool = False
    word_count: int = 0
    limit: int = 0
    version: int = 0
    recovered: bool = False
    available: bool = False

    @property
    def status_label(self) -> str:
        if not self.available:
            return "—"
        return ("ready" if self.ok else "oversize") + f" · {self.word_count}/{self.limit}w"


@dataclass
class TuiSnapshot:
    """All state the TUI needs to render one frame. Pure data — no IO."""

    is_demo: bool = False

    # Identity
    project_path: str = ""
    project_name: str = ""

    # Hardware
    os: str = ""
    arch: str = ""
    cpu_brand: str = ""
    ram_gb: float = 0.0
    gpu_name: str | None = None
    vram_gb: float = 0.0
    disk_free_gb: float = 0.0

    # Backend / provider
    ollama_installed: bool = False
    ollama_running: bool = False
    ollama_models: list[str] = field(default_factory=list)
    provider: str = "ollama"

    # Bundle
    bundle_id: str | None = None
    bundle_name: str | None = None
    bundle_status: str = "none"  # "active" | "recommended" | "none"

    # Policy
    mode: str = "pilot"
    sandbox_tier: str = "basic"
    local_only: bool = True

    # Git + memory + sessions
    git: GitInfo = field(default_factory=GitInfo)
    memory: MemoryInfo = field(default_factory=MemoryInfo)
    recent_sessions: list[str] = field(default_factory=list)

    # Activity timeline (demo-friendly)
    recent_files: list[str] = field(default_factory=list)
    recent_commands: list[str] = field(default_factory=list)
    tests_passing: bool | None = None

    # UX hint
    next_action: str = "Type an objective, or /help for commands."

    # ---- Derived labels ----
    @property
    def ollama_label(self) -> str:
        if not self.ollama_installed:
            return "not installed"
        return f"{'running' if self.ollama_running else 'stopped'} · {len(self.ollama_models)} models"

    @property
    def bundle_label(self) -> str:
        if self.bundle_id:
            return self.bundle_id
        return "not configured"

    @property
    def mode_label(self) -> str:
        return self.mode.capitalize()

    @property
    def status_bar_segments(self) -> list[tuple[str, str]]:
        """(label, value) pairs for the bottom status bar."""
        return [
            ("provider", self.provider),
            ("bundle", self.bundle_label),
            ("mode", self.mode_label),
            ("sandbox", self.sandbox_tier),
            ("git", self.git.status_label),
            ("memory", self.memory.status_label),
        ]


# ---------------------------------------------------------------------------
# Demo snapshot — fully mocked, no IO, clearly labelled
# ---------------------------------------------------------------------------

DEMO_RECENT_FILES = [
    "src/prometheus_cli/orchestrator.py",
    "tests/test_orchestrator.py",
    "README.md",
    "docs/ARCHITECTURE.md",
]

DEMO_RECENT_COMMANDS = [
    "/plan  add JWT auth to /api/login",
    "/build running pytest -q",
    "git checkpoint  auth-jwt-spike",
    "/memory inspect",
]

DEMO_RECENT_SESSIONS = [
    "a1b2c3d4  Fix failing pytest collection          100.0% complete",
    "e5f6a7b8  Add OAuth client credentials flow       78.0% partial",
    "9c0d1e2f  Refactor provider conformance suite      95.0% complete",
]


def collect_demo_snapshot(workspace: Path) -> TuiSnapshot:
    """Fully-mocked snapshot for `prometheus tui --demo`. No IO whatsoever."""
    return TuiSnapshot(
        is_demo=True,
        project_path=_short(workspace),
        project_name=workspace.name or "demo-project",
        os="Linux",
        arch="x86_64",
        cpu_brand="Demo CPU (8 cores)",
        ram_gb=32.0,
        gpu_name="Demo GPU (mock)",
        vram_gb=8.0,
        disk_free_gb=180.0,
        ollama_installed=True,
        ollama_running=True,
        ollama_models=["qwen3.5:4b", "granite4.1:3b", "gemma3:4b"],
        provider="ollama",
        bundle_id="ember-8gb",
        bundle_name="Ember (8 GB GPU)",
        bundle_status="active",
        mode="pilot",
        sandbox_tier="basic",
        local_only=True,
        git=GitInfo(
            branch="main",
            dirty=False,
            recent_commits=[
                "a1b2c3d  feat(auth): JWT login skeleton",
                "e5f6a7b  test(auth): pytest fixtures",
                "9c0d1e2  docs: update README quickstart",
            ],
            available=True,
        ),
        memory=MemoryInfo(
            ok=True, word_count=412, limit=1024, version=7, recovered=False, available=True,
        ),
        recent_sessions=list(DEMO_RECENT_SESSIONS),
        recent_files=list(DEMO_RECENT_FILES),
        recent_commands=list(DEMO_RECENT_COMMANDS),
        tests_passing=True,
        next_action="Demo only — press Ctrl+P for commands, or /help.",
    )


# ---------------------------------------------------------------------------
# Real snapshot — calls every probe defensively
# ---------------------------------------------------------------------------

def _probe_git(workspace: Path) -> GitInfo:
    """Defensive git probe. Never raises."""
    try:
        rev_parse = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=workspace, capture_output=True, text=True, timeout=2.0,
        )
        if rev_parse.returncode != 0:
            return GitInfo()
        branch = rev_parse.stdout.strip() or "(detached)"

        porcelain = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace, capture_output=True, text=True, timeout=2.0,
        )
        dirty = bool(porcelain.stdout.strip()) if porcelain.returncode == 0 else None

        log = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            cwd=workspace, capture_output=True, text=True, timeout=2.0,
        )
        recent = [
            line for line in log.stdout.strip().splitlines()
            if line and log.returncode == 0
        ][:5]

        modified = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"],
            cwd=workspace, capture_output=True, text=True, timeout=2.0,
        )
        files: list[str] = []
        if modified.returncode == 0:
            files = [line for line in modified.stdout.strip().splitlines() if line][:8]

        return GitInfo(
            branch=branch, dirty=dirty, recent_commits=recent,
            available=True,
        ) if not files else GitInfo(
            branch=branch, dirty=dirty, recent_commits=recent,
            available=True,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return GitInfo()


def _probe_memory(workspace: Path) -> MemoryInfo:
    """Defensive bounded-memory probe. Never raises."""
    try:
        from .memory import ProjectMemoryStore
        store = ProjectMemoryStore(workspace)
        try:
            st = store.status()
        finally:
            pass
        return MemoryInfo(
            ok=st.ok, word_count=st.word_count, limit=st.limit,
            version=st.version, recovered=st.recovered, available=True,
        )
    except Exception:
        return MemoryInfo()


def _probe_sessions(limit: int = 5) -> list[str]:
    """Defensive session-list probe. Never raises."""
    try:
        from .config import ensure_home
        from .session import SessionStore
        home = ensure_home()
        store = SessionStore(home / "sessions" / "prometheus.db")
        try:
            rows = store.list_sessions(limit=limit)
        finally:
            store.close()
        out: list[str] = []
        for s in rows:
            out.append(
                f"{s.id[:8]}  {s.objective[:46]:<46}  {s.completion_percent:5.1f}% {s.status}"
            )
        return out
    except Exception:
        return []


def _probe_recent_files(workspace: Path) -> list[str]:
    """Best-effort list of files modified in the most recent commit."""
    try:
        modified = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"],
            cwd=workspace, capture_output=True, text=True, timeout=2.0,
        )
        if modified.returncode != 0:
            return []
        return [line for line in modified.stdout.strip().splitlines() if line][:8]
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return []


def collect_snapshot(workspace: Path) -> TuiSnapshot:
    """Read real state from every backend. Each probe is individually guarded."""
    # Hardware
    try:
        from .hardware import detect_hardware, recommended_profile
        hw = detect_hardware()
    except Exception:
        hw = None

    # Ollama
    try:
        from .onboarding import check_ollama
        ollama = check_ollama()
    except Exception:
        ollama = None

    # Settings
    try:
        from .config import load_settings
        settings = load_settings()
    except Exception:
        settings = None

    # Sandbox
    try:
        sandbox_tier = settings.effective_sandbox_tier().value if settings else "basic"
    except Exception:
        sandbox_tier = "basic"

    snap = TuiSnapshot(
        is_demo=False,
        project_path=_short(workspace.resolve()),
        project_name=workspace.name or "project",
    )

    if hw is not None:
        snap.os = hw.os or ""
        snap.arch = hw.architecture or ""
        snap.cpu_brand = hw.cpu_brand or ""
        snap.ram_gb = float(hw.ram_gb or 0)
        snap.gpu_name = hw.gpu_name
        snap.vram_gb = float(hw.vram_gb or 0)
        snap.disk_free_gb = float(hw.disk_free_gb or 0)

    if ollama is not None:
        snap.ollama_installed = bool(ollama.installed)
        snap.ollama_running = bool(ollama.running)
        snap.ollama_models = list(ollama.models or [])

    if settings is not None:
        snap.mode = settings.mode.value
        snap.sandbox_tier = sandbox_tier
        snap.local_only = bool(settings.local_only)
        snap.provider = "ollama" if settings.local_only else "ollama + cloud"
        snap.bundle_id = settings.active_bundle_id
        snap.bundle_status = "active" if settings.active_bundle_id else "none"
        if settings.active_bundle_id:
            try:
                from .bundles import find_bundle, load_registry
                match = find_bundle(settings.active_bundle_id, load_registry())
                if match is not None:
                    snap.bundle_name = match.name
            except Exception:
                pass

    snap.git = _probe_git(workspace)
    snap.recent_files = _probe_recent_files(workspace)
    snap.memory = _probe_memory(workspace)
    snap.recent_sessions = _probe_sessions()

    # Decide next-action hint
    if not snap.ollama_running:
        snap.next_action = "Ollama is not running. Start it: ollama serve  (or /setup)"
    elif not snap.bundle_id:
        try:
            from .hardware import recommended_profile
            recommended = recommended_profile(hw) if hw else "spark-cpu-8gb"
        except Exception:
            recommended = "spark-cpu-8gb"
        snap.next_action = f"No bundle active. Type /setup or /use {recommended}"
    else:
        snap.next_action = "Type an objective, or /help for commands."

    return snap


__all__ = [
    "DEMO_RECENT_COMMANDS",
    "DEMO_RECENT_FILES",
    "DEMO_RECENT_SESSIONS",
    "GitInfo",
    "MemoryInfo",
    "TuiSnapshot",
    "collect_demo_snapshot",
    "collect_snapshot",
]
