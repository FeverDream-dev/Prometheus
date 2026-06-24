"""PROMETHEUS TUI 2.0 — local-first coding agent application shell.

OpenCode/Claude-Code/LazyGit-style chrome: persistent top brand header, left
command rail, main work area, right inspector, bottom input, dense status bar.
Slash commands push rich screens; the setup wizard and command palette are
modal overlays. Demo mode renders fully-mocked state for preview and tests.

The raw-markup leak that plagued the previous TUI is fixed structurally: every
markup-bearing widget is a ``Static`` (markup ON by default) or a ``RichLog``
constructed with ``markup=True``. The ``tui_state.TuiSnapshot`` dataclass is
the single read-only contract for all displayed values, so probes never crash
the UI and demo mode is a drop-in replacement.
"""
from __future__ import annotations

import datetime
import os
import queue
import threading
import traceback
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Footer, Input, RichLog, Static

from .config import ensure_home, load_bundle, load_settings, save_settings
from .models import Risk, ToolCall
from .orchestrator import Orchestrator
from .session import SessionStore
from .tui_state import TuiSnapshot, collect_demo_snapshot, collect_snapshot
from .tui_theme import APP_CSS
from .tui_widgets import (
    BrandBadges,
    BrandHeader,
    CommandRail,
    DemoRibbon,
    InspectorPanel,
    NextAction,
    SectionTitle,
    StatusBar,
)

TELEMETRY_REFRESH_S = 2.0


# ---------------------------------------------------------------------------
# Inline approval prompt for risky tool calls (preserved from v1)
# ---------------------------------------------------------------------------

class ApprovalPrompt(Static):
    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue[tuple[ToolCall, Risk] | None] = queue.Queue()
        self._response: queue.Queue[bool] = queue.Queue()
        self.visible = False

    def request(self, call: ToolCall, risk: Risk) -> bool:
        self._queue.put((call, risk))
        return self._response.get()

    def pop_pending(self) -> tuple[ToolCall, Risk] | None:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def respond(self, approved: bool) -> None:
        self._response.put(approved)
        self.visible = False
        self.update("")


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class PrometheusApp(App):
    """The PROMETHEUS application shell."""

    CSS = APP_CSS

    # App-level keybindings. Per-screen bindings live on the Screen subclasses.
    BINDINGS = [
        Binding("ctrl+p", "command_palette", "Commands", show=True),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=True),
        Binding("ctrl+i", "toggle_inspector", "Inspector", show=True),
        Binding("ctrl+l", "clear_transcript", "Clear", show=False),
        Binding("escape", "back", "Back", show=False),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    # Whether the builtin Ctrl+P command palette is enabled. We provide our own
    # richer palette via tui_screens.CommandPaletteScreen, so disable the builtin.
    ENABLE_COMMAND_PALETTE = False

    completion: reactive[float] = reactive(0.0)
    status: reactive[str] = reactive("idle")

    def __init__(
        self,
        bundle_path: Path | None = None,
        workspace: Path | None = None,
        no_animation: bool = False,
        demo: bool = False,
        initial_screen: str | None = None,
        submit_objective: str | None = None,
    ):
        super().__init__()
        self.bundle_path = bundle_path
        self.workspace = workspace or Path.cwd()
        self.no_animation = no_animation
        self.demo = demo
        self.initial_screen = initial_screen
        self.submit_objective = submit_objective
        self._approval = ApprovalPrompt()
        self._session_id: str | None = None
        self._store: SessionStore | None = None
        self._snapshot: TuiSnapshot | None = None

    # ------------------------------------------------------------------
    # Compose the shell
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        # Top brand header (replaces built-in Header)
        with Horizontal(id="brand-header"):
            yield BrandHeader(id="brand-mark")
            yield BrandBadges(id="brand-badges")
        yield DemoRibbon(id="demo-ribbon")

        # 3-column workspace
        with Horizontal(id="workspace"):
            yield CommandRail(id="sidebar")
            with VerticalScroll(id="main"):
                with VerticalScroll(id="dashboard-view"):
                    yield SectionTitle(Static("[section]OBJECTIVE[/]", id="obj-title"),
                                       classes="section-title")
                    yield Static(
                        "Ask PROMETHEUS to build, fix, test, explain, or inspect this project…",
                        id="obj-body", classes="section-body", markup=True,
                    )
                    yield SectionTitle(Static("[section]PLAN[/]", id="plan-title"),
                                       classes="section-title")
                    yield Static(
                        "[dim]No active plan. Type an objective to draft one.[/]",
                        id="plan-body", classes="section-body", markup=True,
                    )
                    yield SectionTitle(Static("[section]ACTIVITY[/]", id="act-title"),
                                       classes="section-title")
                    yield RichLog(id="transcript", markup=True, highlight=False, wrap=True)
                    yield SectionTitle(Static("[section]RECENT FILES[/]", id="files-title"),
                                       classes="section-title")
                    yield Static("[dim]—[/]", id="files-body", classes="section-body", markup=True)
                    yield NextAction("", id="next-action", markup=True)
                with VerticalScroll(id="command-view"):
                    yield Static("", id="command-content", markup=True)
            yield InspectorPanel(id="inspector", markup=True)

        # Bottom: input + status + footer
        yield Input(
            placeholder="Ask PROMETHEUS to build, fix, test, explain, or inspect this project…  (/"
            " for commands, Ctrl+P for palette)",
            id="cmd-input",
        )
        yield StatusBar(id="status-bar", markup=True)
        yield Footer()

    # ------------------------------------------------------------------
    # Mount: load snapshot, render, wire telemetry
    # ------------------------------------------------------------------

    async def on_mount(self) -> None:
        self._snapshot = self._collect_snapshot()
        self._refresh_all(self._snapshot)
        self._apply_responsive_layout()
        self.status = "ready"
        if self._snapshot.is_demo:
            self._populate_demo_transcript()
        else:
            from . import tui_commands
            for line in tui_commands.first_run_banner(load_settings()):
                # Render via RichLog with markup=True so the brackets don't leak.
                self._log(line)
        # Push initial screen if requested (e.g. --screen setup).
        if self.initial_screen:
            cmd = self.initial_screen if self.initial_screen.startswith("/") else f"/{self.initial_screen}"
            self._dispatch_slash_text(cmd)
        if self.submit_objective:
            self._run_objective(self.submit_objective)
        # Periodic telemetry refresh (only in real mode — demo is static).
        if not self._snapshot.is_demo:
            try:
                if load_settings().tui_telemetry_panel:
                    self.set_interval(TELEMETRY_REFRESH_S, self._tick_telemetry)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Snapshot collection
    # ------------------------------------------------------------------

    def _collect_snapshot(self) -> TuiSnapshot:
        if self.demo:
            return collect_demo_snapshot(self.workspace)
        return collect_snapshot(self.workspace)

    def _refresh_all(self, snap: TuiSnapshot) -> None:
        """Push snapshot into every chrome widget."""
        self.query_one("#brand-mark", BrandHeader).update_snapshot(snap)
        self.query_one("#brand-badges", BrandBadges).update_snapshot(snap)
        self.query_one("#demo-ribbon", DemoRibbon).update_snapshot(snap)
        self.query_one("#sidebar", CommandRail).update_snapshot(snap)
        self.query_one("#inspector", InspectorPanel).update_snapshot(snap)
        self.query_one("#status-bar", StatusBar).update_snapshot(snap)
        # Recent files panel
        files = snap.recent_files or [c for c in snap.git.recent_commits[:3]]
        files_widget = self.query_one("#files-body", Static)
        if files:
            body = "\n".join(f"[dim]•[/] {f}" for f in files[:8])
        else:
            body = "[dim]no recent changes[/]"
        files_widget.update(body)
        # Next-action hint
        self.query_one("#next-action", NextAction).update(
            f"[k]next[/] [v]{snap.next_action}[/]"
        )

    def _tick_telemetry(self) -> None:
        """Re-read live state and refresh widgets. Cheap; runs on interval."""
        try:
            snap = collect_snapshot(self.workspace)
            self._snapshot = snap
            self._refresh_all(snap)
        except Exception:
            pass

    def _update_inspector_for_screen(self) -> None:
        try:
            from .tui_widgets import InspectorPanel
            inspector = self.query_one("#inspector", InspectorPanel)
            screen = self.screen
            lines = getattr(screen, "inspector_lines", lambda: None)()
            inspector.set_context(lines)
        except Exception:
            pass

    _current_view: str = "dashboard"

    def _show_command_view(self, cmd: str, title: str, subtitle: str,
                           body_lines: list[str],
                           inspector_lines: list[str] | None = None) -> None:
        try:
            self.query_one("#dashboard-view").styles.display = "none"
            cv = self.query_one("#command-view")
            cv.styles.display = "block"
            content = self.query_one("#command-content", Static)
            parts = [f"[gold]{title}[/]"]
            if subtitle:
                parts.append(f"[dim]{subtitle}[/]")
            parts.append("")
            parts.extend(body_lines)
            parts.append("")
            parts.append("[dim]Esc to return  \u00b7  /help for commands[/]")
            content.update("\n".join(parts))
            self._current_view = "command"
            try:
                cv.scroll_y = 0
            except Exception:
                pass
            from .tui_widgets import SidebarEntry, InspectorPanel, BrandHeader
            for entry in self.query(SidebarEntry):
                if entry.sidebar_cmd == cmd:
                    entry.add_class("active")
                else:
                    entry.remove_class("active")
            self.query_one("#brand-mark", BrandHeader).set_breadcrumb(title.split("\u00b7")[0].strip())
            if inspector_lines:
                self.query_one("#inspector", InspectorPanel).set_context(inspector_lines)
        except Exception:
            pass

    def _show_dashboard(self) -> None:
        try:
            self.query_one("#command-view").styles.display = "none"
            self.query_one("#dashboard-view").styles.display = "block"
            self._current_view = "dashboard"
            from .tui_widgets import InspectorPanel, SidebarEntry, BrandHeader
            self.query_one("#inspector", InspectorPanel).set_context(None)
            for entry in self.query(SidebarEntry):
                entry.remove_class("active")
            self.query_one("#brand-mark", BrandHeader).clear_breadcrumb()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Transcript log (markup-safe)
    # ------------------------------------------------------------------

    def _log(self, message: str) -> None:
        try:
            self.query_one("#transcript", RichLog).write(message)
        except Exception:
            pass

    def _log_user(self, text: str) -> None:
        """Render a user objective with a distinct visual block."""
        self._log("[dim]────────────────────────────────────────────────[/]")
        self._log("[bold #5a8aa0]  You[/]")
        for line in (text.splitlines() or [text]):
            self._log(f"[#c8dce8]  {line}[/]")
        self._log("[dim]────────────────────────────────────────────────[/]")

    def _log_agent(self, text: str, *, prefix: str | None = None) -> None:
        """Render agent/orchestrator output with PROMETHEUS styling."""
        label = prefix or "PROMETHEUS"
        if prefix is None and text.startswith(("step ", "PLAN", "BUILD", "TEST")):
            label = "PROMETHEUS"
        self._log(f"[bold #d4a02a]  ◆ {label}[/]  [#e6e2d8]{text}[/]")

    def _log_system(self, text: str) -> None:
        """Render system guidance (cards, hints) without looking like agent chat."""
        self._log(f"[dim]{text}[/]")

    def _populate_demo_transcript(self) -> None:
        for line in [
            "[gold]▸[/] add JWT auth to /api/login with tests",
            "[dim]─────────────────────────────────────────────[/]",
            "[info]PLAN[/] drafting acceptance criteria…",
            "  [ok]task[/] implement JWT issuance (envoy, 2 subtasks)",
            "  [ok]task[/] write pytest fixtures (forge, 3 subtasks)",
            "  [ok]task[/] wire /api/login endpoint (forge, 1 subtask)",
            "[info]BUILD[/] forge executing…",
            "  [dim]edit[/] src/auth/jwt.py (+47 lines)",
            "  [dim]edit[/] src/api/routes/login.py (+28 lines)",
            "  [dim]edit[/] tests/test_auth_jwt.py (+63 lines)",
            "[ok]git[/] checkpoint auth-jwt-skeleton (sha a1b2c3d)",
            "[info]TEST[/] pytest tests/test_auth_jwt.py",
            "  [ok]PASS[/] test_jwt_issue_expired_token",
            "  [ok]PASS[/] test_jwt_verify_valid_signature",
            "  [ok]PASS[/] test_login_returns_200_with_token",
            "  [ok]PASS[/] test_login_rejects_wrong_password",
            "[ok]result[/] 4/4 passed — [gold]100.0%[/]",
            "[info]memory[/] +1 decision, +2 facts (419/1024 words)",
            "[gold]▸ DONE[/] JWT auth added. Type next objective or /help.",
        ]:
            self._log(line)

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = (event.value or "").strip()
        if not text:
            return
        if self._approval.visible:
            return

        # Approval-flow shortcuts (preserved from v1)
        if text.lower() in {"y", "yes"}:
            self._approval.respond(True)
            self._log("[ok]Approved[/]")
            return
        if text.lower() in {"n", "no"}:
            self._approval.respond(False)
            self._log("[err]Denied[/]")
            return

        if text.startswith("/"):
            event.input.value = ""
            self._dispatch_slash_text(text)
            return

        # Echo the objective into the transcript and run.
        self._log_user(text)
        event.input.value = ""
        self._run_objective(text)

    def _dispatch_slash_text(self, text: str) -> None:
        """Route a /command to a screen push or an inline handler."""
        from . import tui_screens

        parts = text.split()
        cmd = parts[0].lower()
        rest = " ".join(parts[1:])

        # Inline handlers first (these mutate state, not just display).
        if cmd in ("/exit", "/quit"):
            self.exit()
            return
        if cmd == "/clear":
            try:
                self.query_one("#transcript", RichLog).clear()
            except Exception:
                pass
            self._log("[dim]transcript cleared[/]")
            return
        if cmd == "/mode":
            self._inline_mode_switch(rest)
            return
        if cmd == "/use":
            self.run_worker(self._run_use, rest)
            return
        if cmd == "/qualify":
            self.run_worker(self._run_qualify, rest or None)
            return
        if cmd == "/resume":
            self._inline_resume(rest)
            return
        if cmd == "/memory" and rest:
            self.run_worker(
                self._run_memory,
                (rest.split()[0] if rest else "status"),
                (rest.split()[1] if len(rest.split()) > 1 else None),
            )
            return
        if cmd == "/build" and rest:
            self._run_objective(rest)
            return

        handled = tui_screens.dispatch_slash(self, cmd, self._snapshot, rest)
        if not handled:
            self._log(f"[warn]Unknown command:[/] [gold]{cmd}[/]  (try /help)")

    # ------------------------------------------------------------------
    # Inline command implementations
    # ------------------------------------------------------------------

    def _inline_mode_switch(self, arg: str) -> None:
        from .models import AutonomyMode
        arg = arg.strip().lower()
        valid = {m.value for m in AutonomyMode}
        if arg not in valid:
            self._log(
                f"[warn]Unknown mode '{arg}'.[/] Use one of: [gold]{', '.join(sorted(valid))}[/]"
            )
            return
        settings = load_settings()
        settings.mode = AutonomyMode(arg)
        save_settings(settings)
        self._log(f"[ok]Mode →[/] [gold]{arg}[/]. Saved to ~/.prometheus/config.yaml")
        # Refresh chrome so the new mode shows in header/status.
        if self._snapshot is not None:
            self._snapshot.mode = arg
            self._refresh_all(self._snapshot)

    def _inline_resume(self, session_id: str) -> None:
        sid = (session_id or "").strip()
        if not sid:
            self._log("[warn]/resume needs a session id.[/] Try /sessions.")
            return
        self._log(f"[dim]Resume in a terminal:[/] prometheus resume {sid}")

    # ------------------------------------------------------------------
    # Worker-bound inline commands (bundle/memory/qualify)
    # ------------------------------------------------------------------

    def _run_use(self, bundle_id: str) -> None:
        import yaml
        from .bundles import find_bundle, load_registry

        def emit(line: str) -> None:
            self.call_from_thread(self._log, line)

        match = find_bundle(bundle_id, load_registry())
        if match is None:
            emit(f"[err]No package '{bundle_id}'.[/]")
            return
        if match.is_add_on:
            emit(f"[err]'{bundle_id}' is an add-on; cannot be active.[/]")
            return
        settings = load_settings()
        home = ensure_home()
        active_dir = home / "bundles"
        active_dir.mkdir(exist_ok=True)
        active_path = active_dir / f"active-{match.id}.yaml"
        active_path.write_text(
            yaml.safe_dump(match.to_v1_bundle().model_dump(mode="json"), sort_keys=False),
            encoding="utf-8",
        )
        settings.active_bundle_id = match.id
        settings.bundle_file = active_path
        save_settings(settings)
        self.bundle_path = active_path
        emit(f"[ok]Active package:[/] [gold]{match.name}[/] ({match.id})")
        # Refresh snapshot + chrome so the new bundle shows immediately.
        if not self.demo:
            self.call_from_thread(self._tick_telemetry)

    def _run_memory(self, action: str, arg: str | None) -> None:
        from .memory import ProjectMemoryStore

        def emit(line: str) -> None:
            self.call_from_thread(self._log, line)

        store = ProjectMemoryStore(self.workspace)
        if action == "status":
            st = store.status()
            emit(
                f"Working memory: {'OK' if st.ok else 'OVERSIZE'} — "
                f"{st.word_count}/{st.limit} words (v{st.version})"
                f"{' [recovered]' if st.recovered else ''}"
            )
        elif action == "inspect":
            facts = store.list_facts()
            emit(
                f"Tasks: {len(store.get_tasks())} · Decisions: {len(store.list_decisions())}"
                f" · Facts: {len(facts)}"
            )
            for f in facts[-8:]:
                emit(f"  ({f.confidence.value}/{f.provenance.source}) {f.summary}")
        elif action == "why" and arg:
            fact = store.why(arg)
            emit(f"{fact.summary} — {fact.confidence.value}/{fact.provenance.source}"
                 if fact else f"no fact '{arg}'")
        elif action == "rebuild":
            st = store.rebuild()
            emit(f"Rebuilt: v{st.version}, {st.word_count} words")
        else:
            emit("/memory status|inspect|why <id>|rebuild|export|reset")

    def _run_qualify(self, bundle_id: str | None) -> None:
        from .bundles import load_registry
        from .onboarding import check_ollama
        from .qualification import qualify_bundle, qualify_model

        def emit(line: str) -> None:
            self.call_from_thread(self._log, line)

        if not check_ollama().running:
            emit("[err]Ollama service is not running.[/]")
            return
        if bundle_id:
            target = next((b for b in load_registry() if b.id == bundle_id), None)
            if target is None:
                emit(f"[err]No bundle '{bundle_id}'.[/]")
                return
            emit(f"Qualifying [gold]{target.id}[/]…")
            report = qualify_bundle(target)
        else:
            ollama = check_ollama()
            if not ollama.models:
                emit("[err]No installed models to qualify.[/]")
                return
            model = ollama.models[0]
            emit(f"Qualifying [gold]{model}[/]…")
            report = qualify_model(model)
        for r in report.results:
            mark = "[ok]PASS[/]" if r.passed else "[err]FAIL[/]"
            emit(f"  {mark} {r.name} — {r.detail}")
        verdict = "QUALIFIED" if report.passed else "PARTIAL"
        emit(f"[gold]{verdict}[/]: {report.passed_count}/{len(report.results)}")

    # ------------------------------------------------------------------
    # Objective execution (preserved threading + approval flow)
    # ------------------------------------------------------------------

    def _run_objective(self, objective: str) -> None:
        if self.demo:
            self._log("[dim](demo mode — objective would be sent to the orchestrator)[/]")
            self._log(f"[gold]▸ {objective}[/]")
            return

        settings = load_settings()
        if not self._has_active_bundle(settings):
            self._render_no_bundle_card(settings)
            return

        ollama = self._check_ollama_models(settings)
        if ollama is not None:
            self._render_missing_models_card(settings, ollama)
            return

        settings.workspace = self.workspace.resolve()
        bundle_path = self.bundle_path or settings.bundle_file
        if not bundle_path:
            self._render_no_bundle_card(settings)
            return
        home = ensure_home()
        try:
            bundle = load_bundle(bundle_path)
        except Exception as exc:
            self._log("")
            self._log("[err]┌─ Bundle could not be loaded ────────────────────────────┐[/]")
            self._log(f"[err]│[/]  {type(exc).__name__}: {str(exc)[:72]}")
            self._log("[err]│[/]  Run [gold]/setup[/] or [gold]/use <bundle-id>[/] to reconfigure. [err]│[/]")
            self._log("[err]└──────────────────────────────────────────────────────────┘[/]")
            self._log("")
            return
        self._log(f"[info]Bundle:[/] {bundle.name}  [info]Mode:[/] {settings.mode.value}")
        self.status = "running"
        self.run_worker(self._orchestrate, objective, settings, bundle, home)

    def _has_active_bundle(self, settings) -> bool:
        """True only when a bundle is explicitly active (matches header chrome)."""
        if getattr(settings, "active_bundle_id", None):
            return True
        # Stale bundle_file on disk without active_bundle_id is not configured.
        return False

    def _check_ollama_models(self, settings):
        try:
            from .onboarding import check_ollama
            status = check_ollama()
        except Exception:
            return ("ollama_check_failed", [])
        if not status.running:
            return ("not_running", [])
        if not status.models:
            return ("no_models", [])
        bundle_path = self.bundle_path or settings.bundle_file
        if not bundle_path:
            return ("no_bundle_file", [])
        try:
            bundle = load_bundle(bundle_path)
            required = [m.model for m in bundle.models]
        except Exception:
            return ("bundle_load_failed", [])
        installed = set(status.models)
        missing = [m for m in required if m not in installed]
        if missing:
            return ("missing_models", missing)
        return None

    def _render_no_bundle_card(self, settings) -> None:
        rec = "spark-cpu-8gb"
        try:
            from .hardware import detect_hardware, recommended_profile
            rec = recommended_profile(detect_hardware()) or rec
        except Exception:
            pass
        self._log("")
        self._log("[err]┌─ No active bundle configured ─────────────────────────────┐[/]")
        self._log("[err]│[/]  PROMETHEUS needs a model bundle to run objectives.  [err]│[/]")
        self._log("[err]│[/]                                                          [err]│[/]")
        self._log(f"[err]│[/]  Recommended:  [gold]{rec}[/]")
        self._log("[err]│[/]                                                          [err]│[/]")
        self._log("[err]│[/]  Next steps:                                              [err]│[/]")
        self._log("[err]│[/]    [gold]/setup[/]     — run the 7-step setup wizard       [err]│[/]")
        self._log("[err]│[/]    [gold]/bundles[/]   — browse available bundles         [err]│[/]")
        self._log(f"[err]│[/]    [gold]/use {rec}[/] — select the recommended bundle   [err]│[/]")
        self._log("[err]└──────────────────────────────────────────────────────────┘[/]")
        self._log("")

    def _render_missing_models_card(self, settings, ollama_info) -> None:
        kind, missing = ollama_info
        if kind == "not_running":
            self._log("")
            self._log("[err]┌─ Ollama not running ─────────────────────────────────────┐[/]")
            self._log("[err]│[/]  Start it with:  [gold]ollama serve[/]                    [err]│[/]")
            self._log("[err]│[/]  Then run:       [gold]/setup[/] or [gold]/models pull <bundle>[/]  [err]│[/]")
            self._log("[err]└──────────────────────────────────────────────────────────┘[/]")
            self._log("")
            return
        if kind in {"bundle_load_failed", "no_bundle_file", "ollama_check_failed"}:
            self._log("")
            self._log("[err]┌─ Bundle not ready ───────────────────────────────────────┐[/]")
            self._log("[err]│[/]  Could not verify models for the active bundle.        [err]│[/]")
            self._log("[err]│[/]  Run [gold]/setup[/] or [gold]/use <bundle-id>[/] to fix.   [err]│[/]")
            self._log("[err]└──────────────────────────────────────────────────────────┘[/]")
            self._log("")
            return
        label = (
            "Ollama is running, but no required models are installed"
            if kind == "no_models"
            else "Some required models are missing"
        )
        bundle_id = getattr(settings, "active_bundle_id", None) or "your bundle"
        self._log("")
        self._log("[err]┌─ " + label + " ──────────────────────┐[/]")
        if missing:
            self._log("[err]│[/]  Missing models:                                          [err]│[/]")
            for m in missing:
                self._log(f"[err]│[/]    [warn]•[/] {m}")
        else:
            self._log("[err]│[/]  Ollama has 0 models installed.                        [err]│[/]")
        self._log("[err]│[/]                                                          [err]│[/]")
        self._log("[err]│[/]  Pull required models:                                   [err]│[/]")
        self._log(f"[err]│[/]    [gold]/models pull {bundle_id}[/]")
        self._log("[err]│[/]    [gold]/setup[/]")
        self._log("[err]└──────────────────────────────────────────────────────────┘[/]")
        self._log("")

    def run_worker(self, fn, *args) -> None:
        thread = threading.Thread(target=fn, args=args, daemon=True)
        thread.start()
        self.set_interval(0.2, self._poll_approvals)

    def _poll_approvals(self) -> None:
        pending = self._approval.pop_pending()
        if pending and not self._approval.visible:
            call, risk = pending
            self._approval.visible = True
            self.call_from_thread(
                self._approval.update,
                f"[warn]{risk.value.upper()}[/] approval needed:\n"
                f"[k]Tool[/] [v]{call.tool}[/]\n"
                f"[k]Args[/] [v]{call.arguments}[/]\n"
                f"[k]Reason[/] [v]{call.reason}[/]\n"
                f"[dim]Press [gold]y[/] to approve or [err]n[/] to deny.[/]",
            )

    def _orchestrate(self, objective: str, settings, bundle, home: Path) -> None:
        def on_update(line: str) -> None:
            self.call_from_thread(self._log_agent, line)

        def approve(call: ToolCall, risk: Risk) -> bool:
            return self._approval.request(call, risk)

        try:
            self._store = SessionStore(home / "sessions" / "prometheus.db")
            orchestrator = Orchestrator(
                settings, bundle, approve=approve, session_store=self._store,
            )
            result = orchestrator.run(objective, on_update=on_update)
            self.call_from_thread(self._on_complete, result)
        except Exception as exc:
            self._safe_call_from_thread(self._log_worker_error, exc)

    def _log_worker_error(self, exc: Exception) -> None:
        tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb = "".join(tb_lines)
        if "NoneType: None" in tb:
            current = traceback.format_exc()
            if "NoneType: None" not in current:
                tb = current
        try:
            home = ensure_home()
            log_dir = home / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = log_dir / f"tui_worker_error_{stamp}.log"
            log_path.write_text(
                f"TUI worker error\nObjective path\nTimestamp: {stamp}\n\n{tb}\n",
                encoding="utf-8",
            )
            log_ref = str(log_path)
        except Exception:
            log_ref = "(log write failed)"

        exc_type = type(exc).__name__
        short = str(exc)[:120]
        if len(str(exc)) > 120:
            short += "…"

        self._safe_call_from_thread(self._render_error_card, exc_type, short, log_ref)
        self._safe_call_from_thread(self._set_error_status)

    def _safe_call_from_thread(self, fn, *args) -> None:
        try:
            self.call_from_thread(fn, *args)
        except RuntimeError:
            fn(*args)

    def _render_error_card(self, exc_type: str, short_msg: str, log_ref: str) -> None:
        self._log("")
        self._log("[err]┌─ Objective failed ────────────────────────────────────────┐[/]")
        self._log(f"[err]│[/]  [warn]{exc_type}[/]")
        self._log(f"[err]│[/]  {short_msg}")
        self._log("[err]│[/]                                                          [err]│[/]")
        self._log(f"[err]│[/]  Details logged: [dim]{log_ref}[/]")
        self._log("[err]│[/]  You can retry, type /help, or /setup to reconfigure.   [err]│[/]")
        self._log("[err]└──────────────────────────────────────────────────────────┘[/]")
        self._log("")

    def _set_error_status(self) -> None:
        self.status = "error"

    def _on_complete(self, result) -> None:
        self._log_agent(f"{result.status.upper()} — {result.completion_percent}%", prefix="Result")
        if result.message:
            self._log_agent(result.message)
        self.completion = result.completion_percent
        self.status = result.status
        if self._store:
            self._store.close()

    # ------------------------------------------------------------------
    # Reactive watchers — keep StatusBar in sync
    # ------------------------------------------------------------------

    def watch_completion(self, value: float) -> None:
        pass  # status bar reads from snapshot

    def watch_status(self, value: str) -> None:
        pass  # status bar reads from snapshot

    # ------------------------------------------------------------------
    # Responsive layout — collapse rails at narrow widths.
    # textual 1.0.0 has no HORIZONTAL_BREAKPOINTS, so we watch ``size``.
    # ------------------------------------------------------------------

    def watch_size(self, size) -> None:
        self._apply_responsive_layout(size)

    def _apply_responsive_layout(self, size=None) -> None:
        try:
            sidebar = self.query_one("#sidebar")
            inspector = self.query_one("#inspector")
        except Exception:
            return
        if size is None:
            size = self.size
        w = size.width if hasattr(size, "width") else size[0]
        # At the minimum supported width (80 cols) and below, collapse both
        # rails to give the main area full width. Inspector collapses earlier
        # (under 100) since it's the lower-priority panel.
        if w <= 80:
            sidebar.styles.display = "none"
            inspector.styles.display = "none"
        elif w <= 100:
            sidebar.styles.display = "block"
            inspector.styles.display = "none"
        else:
            sidebar.styles.display = "block"
            inspector.styles.display = "block"

    # ------------------------------------------------------------------
    # Bound actions
    # ------------------------------------------------------------------

    def action_command_palette(self) -> None:
        """Open the rich command palette (overrides builtin)."""
        from .tui_screens import CommandPaletteScreen
        self.push_screen(CommandPaletteScreen(self._snapshot))

    def action_toggle_sidebar(self) -> None:
        try:
            sb = self.query_one("#sidebar")
            sb.styles.display = "none" if sb.styles.display != "none" else "block"
        except Exception:
            pass

    def action_toggle_inspector(self) -> None:
        try:
            insp = self.query_one("#inspector")
            insp.styles.display = "none" if insp.styles.display != "none" else "block"
        except Exception:
            pass

    def action_clear_transcript(self) -> None:
        try:
            self.query_one("#transcript", RichLog).clear()
        except Exception:
            pass

    def action_back(self) -> None:
        if len(self._screen_stack) > 1:
            self.pop_screen()
            return
        if self._current_view == "command":
            self._show_dashboard()


# ---------------------------------------------------------------------------
# Launch entrypoint (called by cli.py)
# ---------------------------------------------------------------------------

def launch_tui(
    bundle_path: Path | None = None,
    workspace: Path | None = None,
    no_animation: bool = False,
    demo: bool = False,
    screenshot_path: Path | None = None,
    initial_screen: str | None = None,
    exit_after_render: bool = False,
    submit_objective: str | None = None,
) -> None:
    """Launch the PROMETHEUS TUI.

    If ``screenshot_path`` is set the app runs headless, composes once, exports
    an SVG, writes it to disk, and returns without entering the event loop.
    If ``exit_after_render`` is set, the app runs headless, composes once, and
    exits — for CI smoke tests where no SVG file is needed.
    """
    app = PrometheusApp(
        bundle_path=bundle_path,
        workspace=workspace or Path.cwd(),
        no_animation=no_animation,
        demo=demo,
        initial_screen=initial_screen,
        submit_objective=submit_objective,
    )

    if screenshot_path is not None:
        _export_screenshot(app, screenshot_path, initial_screen=initial_screen)
        return

    if exit_after_render:
        _exit_after_render(app, initial_screen=initial_screen)
        return

    app.run()


def _exit_after_render(app: PrometheusApp, initial_screen: str | None) -> None:
    import asyncio

    async def _run() -> None:
        async with app.run_test(headless=True, size=(120, 36)) as pilot:
            await pilot.pause(0.05)
            if initial_screen:
                cmd = initial_screen if initial_screen.startswith("/") else f"/{initial_screen}"
                app._dispatch_slash_text(cmd)
                await pilot.pause(0.05)

    asyncio.run(_run())


def _export_screenshot(app: PrometheusApp, path: Path, initial_screen: str | None) -> None:
    """Run the app headless, push the requested screen, export SVG to ``path``."""
    import asyncio

    async def _run() -> None:
        async with app.run_test(headless=True, size=(120, 36)) as pilot:
            # Allow one paint so the snapshot finishes loading.
            await pilot.pause(0.05)
            if initial_screen:
                cmd = initial_screen if initial_screen.startswith("/") else f"/{initial_screen}"
                # Dispatch and let the screen settle.
                app._dispatch_slash_text(cmd)
                await pilot.pause(0.05)
            svg = app.export_screenshot(title=f"PROMETHEUS — {initial_screen or 'dashboard'}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(svg, encoding="utf-8")

    asyncio.run(_run())


__all__ = ["ApprovalPrompt", "PrometheusApp", "launch_tui"]
