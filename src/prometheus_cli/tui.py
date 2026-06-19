from __future__ import annotations

import queue
import threading
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import (
    Footer,
    Header,
    Input,
    Log,
    Static,
)

from .config import ensure_home, load_bundle, load_settings
from .hardware import detect_hardware, recommended_profile
from .models import Risk, ToolCall
from .orchestrator import Orchestrator
from .session import SessionStore

BUNDLES_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "bundles"


class StatusBar(Static):
    mode: reactive[str] = reactive("pilot")
    completion: reactive[float] = reactive(0.0)
    status: reactive[str] = reactive("idle")

    def render(self) -> Text:
        return Text(
            f" Mode: {self.mode}  |  Completion: {self.completion:.0f}%  |  Status: {self.status} ",
            style="bold white on blue",
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


class PrometheusApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #hardware-panel {
        height: auto;
        padding: 0 1;
        background: $surface;
        border: solid $primary;
        margin-bottom: 1;
    }
    #main-area {
        height: 1fr;
    }
    #log-panel {
        border: solid $accent;
        padding: 0 1;
    }
    #approval-panel {
        height: auto;
        padding: 0 1;
        background: $warning-background;
        border: solid $warning;
    }
    #input-bar {
        height: 3;
        dock: bottom;
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

    def __init__(self, bundle_path: Path | None = None, workspace: Path | None = None):
        super().__init__()
        self.bundle_path = bundle_path
        self.workspace = workspace or Path.cwd()
        self._approval = ApprovalPrompt()
        self._session_id: str | None = None
        self._store: SessionStore | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="hardware-panel")
        with Vertical(id="main-area"):
            yield Log(id="log-panel", highlight=True, markup=True)
            yield self._approval
        yield Input(placeholder="Enter an objective and press Enter…", id="input-bar")
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        self._render_hardware()
        self.status = "ready"

    def _render_hardware(self) -> None:
        report = detect_hardware()
        lines = [
            "[bold]PROMETHEUS[/bold] — local-first coding agent",
            f"OS: {report.os} {report.architecture}" + (" (WSL)" if report.wsl else ""),
            f"RAM: {report.ram_gb} GB | GPU: {report.gpu_name or 'CPU mode'}",
            f"Recommended bundle: [bold]{recommended_profile(report)}[/bold]",
        ]
        self.query_one("#hardware-panel", Static).update("\n".join(lines))

    def _log(self, message: str) -> None:
        log = self.query_one("#log-panel", Log)
        log.write_line(message)

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

        self._run_objective(text)
        event.input.value = ""

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


def launch_tui(bundle_path: Path | None = None, workspace: Path | None = None) -> None:
    app = PrometheusApp(bundle_path=bundle_path, workspace=workspace)
    app.run()
