from __future__ import annotations

import os
import queue
import threading
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Footer,
    Header,
    Input,
    RichLog,
    Static,
)

from .config import ensure_home, load_bundle, load_settings
from .hardware import detect_hardware
from .models import Risk, ToolCall
from .orchestrator import Orchestrator
from .session import SessionStore

BUNDLES_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "bundles"
TELEMETRY_REFRESH_S = 1.5


class StatusBar(Static):
    mode: reactive[str] = reactive("pilot")
    completion: reactive[float] = reactive(0.0)
    status: reactive[str] = reactive("idle")

    def render(self) -> Text:
        return Text(
            f" Mode: {self.mode}  |  Completion: {self.completion:.0f}%  |  Status: {self.status} ",
            style="bold white on #1f6f8c",
        )


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


class PrometheusApp(App):
    CSS = """
    Screen {
        layout: vertical;
        background: #0e0f13;
    }
    Header {
        background: #1f6f8c 70%;
    }
    #workspace {
        height: 1fr;
        layout: horizontal;
    }
    .sidebar {
        background: #14161c;
        border: solid #2a2e3a;
        padding: 0 1;
        overflow: auto auto;
        color: #cfd3dc;
    }
    #sidebar-left {
        width: 22;
        min-width: 18;
    }
    #telemetry-right {
        width: 30;
        min-width: 24;
    }
    #main-center {
        width: 1fr;
        layout: vertical;
    }
    #hardware-panel {
        height: auto;
        padding: 0 1;
        background: #14161c;
        border: solid #2a2e3a;
        margin-bottom: 0;
        color: #e2e5ea;
    }
    #log-panel {
        height: 1fr;
        border: solid #2a2e3a;
        padding: 0 1;
        background: #0e0f13;
        margin-bottom: 0;
    }
    #approval-panel {
        height: auto;
        padding: 0 1;
        background: #3a2a00;
        border: solid #ffcf5c;
    }
    #input-bar {
        height: 3;
        dock: bottom;
        background: #14161c;
        border: solid #2a2e3a;
    }
    StatusBar {
        dock: bottom;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("y", "approve", "Approve"),
        Binding("n", "deny", "Deny"),
    ]

    completion: reactive[float] = reactive(0.0)
    status: reactive[str] = reactive("idle")

    def __init__(
        self,
        bundle_path: Path | None = None,
        workspace: Path | None = None,
        no_animation: bool = False,
    ):
        super().__init__()
        self.bundle_path = bundle_path
        self.workspace = workspace or Path.cwd()
        self.no_animation = no_animation
        self._approval = ApprovalPrompt()
        self._session_id: str | None = None
        self._store: SessionStore | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"):
            yield Vertical(id="sidebar-left", classes="sidebar")
            with Vertical(id="main-center"):
                yield Static(id="hardware-panel")
                yield RichLog(id="log-panel")
                yield self._approval
            yield Vertical(id="telemetry-right", classes="sidebar")
        yield Input(
            placeholder="Enter an objective or /command and press Enter…",
            id="input-bar",
        )
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        from . import tui_commands

        self._render_sidebar()
        self._render_hardware()
        for line in tui_commands.first_run_banner(load_settings()):
            self._log(line)
        self._refresh_telemetry()
        self.status = "ready"
        settings = load_settings()
        if settings.tui_telemetry_panel:
            self.set_interval(TELEMETRY_REFRESH_S, self._refresh_telemetry)

    def _render_sidebar(self) -> None:
        from . import tui_commands

        lines: list[str] = ["[bold cyan]Commands[/bold cyan]", ""]
        for cmd, desc in tui_commands.SLASH_COMMANDS.items():
            lines.append(f"[bold]{cmd}[/bold]")
            if len(desc) > 22:
                lines.append(f"  [dim]{desc[:21]}…[/dim]")
            else:
                lines.append(f"  [dim]{desc}[/dim]")
        lines.extend(["", "[dim]Ctrl+C / q to exit[/dim]"])
        widget = self.query_one("#sidebar-left", Static)
        widget.update("\n".join(lines))
        if self.size.width < 90:
            widget.styles.display = False

    def _render_hardware(self) -> None:
        report = detect_hardware()
        settings = load_settings()
        bundle_id = settings.active_bundle_id or "(none — /setup)"
        provider = "ollama-only" if settings.local_only else "ollama + cloud-capable"
        mode = settings.mode.value
        lines = [
            "[bold cyan]PROMETHEUS[/bold cyan] · [dim]local-first coding agent[/dim]",
            f"project: [bold]{self.workspace.name}[/bold]  ·  mode: [bold]{mode}[/bold]"
            f"  ·  provider: {provider}",
            f"bundle: [bold]{bundle_id}[/bold]"
            f"  ·  GPU: {report.gpu_name or 'CPU mode'}"
            f"  ·  RAM: {report.ram_gb:.0f} GB",
        ]
        self.query_one("#hardware-panel", Static).update("\n".join(lines))

    def _refresh_telemetry(self) -> None:
        try:
            widget = self.query_one("#telemetry-right", Static)
        except Exception:
            return
        if self.size.width < 110:
            widget.styles.display = False
            return
        widget.styles.display = True
        try:
            from .telemetry import collect_snapshot, render_telemetry_lines

            snapshot = collect_snapshot(
                workspace=str(self.workspace), gpu_timeout_s=1.0, cpu_interval_s=0.0,
            )
            compact = render_telemetry_lines(snapshot)[:14]
            widget.update("\n".join(compact))
        except Exception as exc:
            widget.update(f"[dim]telemetry error: {str(exc)[:80]}[/dim]")

    def _log(self, message: str) -> None:
        self.query_one("#log-panel", RichLog).write(message)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        if self._approval.visible:
            return

        if text.lower() in {"y", "yes"}:
            self._approval.respond(True)
            self._log("[green]Approved[/green]")
            return
        if text.lower() in {"n", "no"}:
            self._approval.respond(False)
            self._log("[red]Denied[/red]")
            return

        if text.startswith("/"):
            event.input.value = ""
            self._handle_slash(text)
            return

        self._run_objective(text)
        event.input.value = ""

    def _handle_slash(self, text: str) -> None:
        from . import tui_commands
        from .bundles import classify_registry, load_registry
        from .hardware import detect_hardware
        from .onboarding import check_ollama

        parts = text.split()
        cmd = parts[0].lower()
        log = self.query_one("#log-panel", RichLog)

        def _emit(lines):
            for line in lines:
                log.write(line)

        if cmd in ("/help", "/?"):
            _emit(tui_commands.help_lines())
            return
        if cmd == "/clear":
            log.clear()
            return
        if cmd in ("/doctor", "/models", "/modes", "/tools", "/mcp", "/provider", "/providers", "/permissions", "/sessions", "/telemetry", "/logo", "/diagnose"):
            if cmd == "/doctor":
                _emit(tui_commands.doctor_lines(detect_hardware(), check_ollama()))
            elif cmd == "/models":
                _emit(tui_commands.models_lines(check_ollama()))
            elif cmd == "/modes":
                _emit(tui_commands.modes_lines())
            elif cmd == "/tools":
                _emit(tui_commands.tools_lines())
            elif cmd == "/mcp":
                _emit(tui_commands.mcp_lines())
            elif cmd in ("/provider", "/providers"):
                _emit(tui_commands.provider_lines(load_settings()))
            elif cmd == "/permissions":
                _emit(tui_commands.permissions_lines(load_settings()))
            elif cmd == "/telemetry":
                _emit(tui_commands.telemetry_lines())
            elif cmd == "/logo":
                _emit(tui_commands.logo_lines())
            elif cmd == "/diagnose":
                _emit(tui_commands.diagnose_lines())
            else:
                _emit(tui_commands.sessions_lines())
            return
        if cmd in ("/settings", "/bundles"):
            ollama = check_ollama()
            classified = classify_registry(load_registry(), detect_hardware(), ollama.models)
            _emit(tui_commands.settings_lines(load_settings(), classified, ollama.models))
            return
        if cmd == "/mode":
            _emit(tui_commands.mode_switch_lines(load_settings(), parts[1] if len(parts) > 1 else ""))
            return
        if cmd == "/resume":
            _emit(tui_commands.resume_lines(parts[1] if len(parts) > 1 else ""))
            return
        if cmd in ("/exit", "/quit"):
            self.exit()
            return
        if cmd == "/qualify":
            self.run_worker(self._run_qualify, parts[1] if len(parts) > 1 else None)
            return
        if cmd == "/use":
            if len(parts) < 2:
                _emit(["[yellow]Usage:[/yellow] /use <bundle-id>  (e.g. /use spark-cpu-8gb)"])
                return
            self.run_worker(self._run_use, parts[1])
            return
        if cmd == "/memory":
            self.run_worker(self._run_memory, parts[1] if len(parts) > 1 else "status",
                            parts[2] if len(parts) > 2 else None)
            return
        if cmd == "/sandbox":
            _emit(tui_commands.sandbox_lines())
            return
        if cmd == "/vision":
            _emit(tui_commands.vision_lines())
            return
        if cmd == "/assets":
            _emit(tui_commands.assets_lines())
            return
        if cmd == "/astronaut":
            _emit(tui_commands.astronaut_lines(self.workspace))
            return
        if cmd == "/setup":
            ollama = check_ollama()
            classified = classify_registry(load_registry(), detect_hardware(), ollama.models)
            _emit(tui_commands.setup_lines(load_settings(), classified))
            return
        _emit(tui_commands.unknown_command_lines(cmd))

    def _run_memory(self, action: str, arg: str | None) -> None:
        from .memory import ProjectMemoryStore

        def emit(line: str) -> None:
            self.call_from_thread(self._log, line)

        store = ProjectMemoryStore(self.workspace)
        if action == "status":
            st = store.status()
            emit(f"Working memory: {'OK' if st.ok else 'NOT OK'} — {st.word_count}/{st.limit} words "
                 f"(v{st.version}){' [recovered]' if st.recovered else ''}")
        elif action == "inspect":
            facts = store.list_facts()
            emit(f"Tasks: {len(store.get_tasks())} · Decisions: {len(store.list_decisions())} · Facts: {len(facts)}")
            for f in facts[-8:]:
                emit(f"  ({f.confidence.value}/{f.provenance.source}) {f.summary}")
        elif action == "why" and arg:
            fact = store.why(arg)
            emit(f"{fact.summary} — {fact.confidence.value}/{fact.provenance.source}" if fact else f"no fact '{arg}'")
        elif action == "rebuild":
            st = store.rebuild()
            emit(f"Rebuilt: v{st.version}, {st.word_count} words")
        else:
            emit(f"/memory {action} — use: status|inspect|why <id>|rebuild|export|reset")

    def _run_use(self, bundle_id: str) -> None:
        import yaml

        from .bundles import find_bundle, load_registry
        from .config import ensure_home, save_settings

        def emit(line: str) -> None:
            self.call_from_thread(self._log, line)

        match = find_bundle(bundle_id, load_registry())
        if match is None:
            emit(f"[red]No package '{bundle_id}'.[/red]")
            return
        if match.is_add_on:
            emit(f"[red]'{bundle_id}' is an add-on; cannot be the active package.[/red]")
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
        emit(f"[green]Active package:[/green] {match.name} ({match.id}) — controller {match.controller_spec().model}")

    def _run_qualify(self, bundle_id: str | None) -> None:
        from .bundles import load_registry
        from .onboarding import check_ollama
        from .qualification import qualify_bundle, qualify_model

        def emit(line: str) -> None:
            self.call_from_thread(self._log, line)

        if not check_ollama().running:
            emit("[red]Ollama service is not running.[/red]")
            return
        if bundle_id:
            registry = load_registry()
            target = next((b for b in registry if b.id == bundle_id), None)
            if target is None:
                emit(f"[red]No bundle '{bundle_id}'.[/red]")
                return
            emit(f"Qualifying [bold]{target.id}[/bold] (controller {target.controller_spec().model})…")
            report = qualify_bundle(target)
        else:
            ollama = check_ollama()
            if not ollama.models:
                emit("[red]No installed models to qualify.[/red]")
                return
            model = ollama.models[0]
            emit(f"Qualifying model [bold]{model}[/bold]…")
            report = qualify_model(model)
        for r in report.results:
            mark = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
            emit(f"  {mark} {r.name} — {r.detail}")
        verdict = "QUALIFIED" if report.passed else "PARTIAL"
        emit(f"[bold]{verdict}[/bold]: {report.passed_count}/{len(report.results)}")

    def action_approve(self) -> None:
        if self._approval.visible:
            self._approval.respond(True)
            self._log("[green]Approved (y)[/green]")

    def action_deny(self) -> None:
        if self._approval.visible:
            self._approval.respond(False)
            self._log("[red]Denied (n)[/red]")

    def _run_objective(self, objective: str) -> None:
        if not self.bundle_path:
            self._log("[red]No bundle configured. Run: prometheus setup[/red]")
            return
        settings = load_settings()
        settings.workspace = self.workspace.resolve()
        home = ensure_home()
        self._store = SessionStore(home / "sessions" / "prometheus.db")
        bundle = load_bundle(self.bundle_path)
        self._log(f"[cyan]Starting: {objective}[/cyan]")
        self._log(f"Bundle: {bundle.name} | Mode: {settings.mode.value}")
        self.status = "running"
        self.run_worker(self._orchestrate, objective, settings, bundle)

    def run_worker(self, fn, *args) -> None:
        thread = threading.Thread(target=fn, args=args, daemon=True)
        thread.start()
        self.set_interval(0.1, self._poll_approvals)

    def _poll_approvals(self) -> None:
        pending = self._approval.pop_pending()
        if pending and not self._approval.visible:
            call, risk = pending
            self._approval.visible = True
            self.call_from_thread(
                self._approval.update,
                f"[bold]{risk.value.upper()}[/bold] approval needed:\n"
                f"Tool: {call.tool}\nArgs: {call.arguments}\nReason: {call.reason}\n"
                f"Press [bold]y[/bold] to approve or [bold]n[/bold] to deny.",
            )

    def _orchestrate(self, objective: str, settings, bundle) -> None:
        def on_update(line: str) -> None:
            self.call_from_thread(self._log, line)

        def approve(call: ToolCall, risk: Risk) -> bool:
            return self._approval.request(call, risk)

        try:
            orchestrator = Orchestrator(
                settings, bundle, approve=approve, session_store=self._store,
            )
            result = orchestrator.run(objective, on_update=on_update)
            self.call_from_thread(self._on_complete, result)
        except Exception as exc:
            self.call_from_thread(self._log, f"[red]ERROR: {exc}[/red]")
            self.call_from_thread(self._set_error_status)

    def _set_error_status(self) -> None:
        self.status = "error"

    def _on_complete(self, result) -> None:
        self._log(f"\n[bold {'green' if result.status == 'complete' else 'yellow'}]"
                  f"{result.status.upper()} — {result.completion_percent}%[/bold {'green' if result.status == 'complete' else 'yellow'}]")
        self._log(result.message)
        self.completion = result.completion_percent
        self.status = result.status
        if self._store:
            self._store.close()

    def watch_completion(self, value: float) -> None:
        try:
            bar = self.query_one(StatusBar)
            bar.completion = value
        except Exception:
            pass

    def watch_status(self, value: str) -> None:
        try:
            bar = self.query_one(StatusBar)
            bar.status = value
            bar.mode = load_settings().mode.value
        except Exception:
            pass


def launch_tui(
    bundle_path: Path | None = None,
    workspace: Path | None = None,
    no_animation: bool = False,
) -> None:
    app = PrometheusApp(
        bundle_path=bundle_path, workspace=workspace, no_animation=no_animation,
    )
    app.run()
