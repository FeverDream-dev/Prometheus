"""TUI 2.0 screens — slash-command displays, setup wizard, command palette.

Every screen is a thin subclass of :class:`RichCommandScreen` (a base that renders
a title + structured body from markup-safe lines). The :func:`dispatch_slash`
entry point routes a ``/cmd`` to either a pushed screen or returns ``False`` so
the caller (the App) can handle it inline.

The :func:`render_screen_text` helper produces a deterministic plain-text dump
of any screen for golden-fixture tests — no Textual run required, no markup
brackets leaking into the snapshot.
"""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from .tui_state import TuiSnapshot
from .tui_theme import COMMAND_PALETTE

# ---------------------------------------------------------------------------
# Markup stripping (for golden text dumps — must not contain raw [tags])
# ---------------------------------------------------------------------------

import re

_MARKUP_TAG_RE = re.compile(r"\[/?[^\]]+\]")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_markup(text: str) -> str:
    """Remove Rich/Textual markup tags and ANSI escapes → plain text."""
    out = _ANSI_RE.sub("", text)
    out = _MARKUP_TAG_RE.sub("", out)
    return out


# ---------------------------------------------------------------------------
# Generic command screen — title + structured body
# ---------------------------------------------------------------------------

class RichCommandScreen(Screen):
    """Base for /help /models /sandbox etc. Title strip + scrollable body."""

    CSS = """
    RichCommandScreen { layout: vertical; }
    """

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Back", show=True),
    ]

    title: str = "PROMETHEUS"
    subtitle: str = ""

    def __init__(self, snapshot: TuiSnapshot | None = None) -> None:
        super().__init__()
        self.snapshot = snapshot

    # ---- Override these in subclasses ----
    def body_lines(self) -> list[str]:
        return ["[dim](no content)[/]"]

    # ---- Lifecycle ----
    def compose(self) -> ComposeResult:
        yield Static(f"[gold]{self.title}[/]", classes="title", markup=True)
        if self.subtitle:
            yield Static(self.subtitle, classes="subtitle", markup=True)
        body_text = "\n".join(self.body_lines())
        yield VerticalScroll(
            Static(body_text, markup=True, id="screen-body"),
            id="screen-scroll",
        )
        yield Static(
            "[dim]Esc to return[/]  [dim]·[/]  [dim]/help for commands[/]",
            classes="dim",
            markup=True,
        )

    def action_dismiss_screen(self) -> None:
        self.app.pop_screen()


# ---------------------------------------------------------------------------
# Concrete screens — each delegates to tui_commands.* helpers so the data
# pipeline stays single-source.
# ---------------------------------------------------------------------------

class HelpScreen(RichCommandScreen):
    title = "PROMETHEUS · Command Help"
    subtitle = "grouped command palette — Ctrl+P opens the visual palette"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        return tui_commands.help_lines()


class SettingsScreen(RichCommandScreen):
    title = "Settings"
    subtitle = "stored in ~/.prometheus/config.yaml"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        from .bundles import classify_registry, load_registry
        from .hardware import detect_hardware
        from .onboarding import check_ollama
        from .config import load_settings

        ollama = check_ollama()
        classified = classify_registry(load_registry(), detect_hardware(), ollama.models)
        return tui_commands.settings_lines(load_settings(), classified, ollama.models)


class ModelsScreen(RichCommandScreen):
    title = "Models"
    subtitle = "installed Ollama models · /models"

    def body_lines(self) -> list[str]:
        if self.snapshot is not None and self.snapshot.is_demo:
            lines = [f"[gold]Installed Ollama models ({len(self.snapshot.ollama_models)}):[/]"]
            for m in self.snapshot.ollama_models:
                lines.append(f"  • {m}")
            lines.append("")
            lines.append("[dim](demo data — run without --demo for real models)[/]")
            return lines
        from . import tui_commands
        from .onboarding import check_ollama
        return tui_commands.models_lines(check_ollama())


class BundlesScreen(RichCommandScreen):
    title = "Model Packages"
    subtitle = "hardware-aware bundles · /use <id>"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        from .bundles import classify_registry, load_registry
        from .hardware import detect_hardware
        from .onboarding import check_ollama
        from .config import load_settings
        ollama = check_ollama()
        classified = classify_registry(load_registry(), detect_hardware(), ollama.models)
        return tui_commands.settings_lines(load_settings(), classified, ollama.models)


class SandboxScreen(RichCommandScreen):
    title = "Sandbox"
    subtitle = "enforcement tiers + policy"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        return tui_commands.sandbox_lines()


class MemoryScreen(RichCommandScreen):
    title = "Memory"
    subtitle = "bounded project memory · /memory status|inspect|why|rebuild"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        # Snapshot carries memory info; show inline.
        lines = []
        if self.snapshot is not None:
            mem = self.snapshot.memory
            if mem.available:
                lines.append(
                    f"[k]Working memory[/] [v]{'OK' if mem.ok else 'OVERSIZE'}[/]"
                    f"  [k]words[/] [v]{mem.word_count}/{mem.limit}[/]"
                    f"  [k]version[/] [v]v{mem.version}[/]"
                    f"{'  [warn]recovered[/]' if mem.recovered else ''}"
                )
            else:
                lines.append("[dim]no memory file in this workspace[/]")
        lines.append("")
        lines.extend(tui_commands.tools_lines()[1:])  # brief
        lines.append("[dim]CLI: prometheus memory inspect|why|rebuild|export|reset[/]")
        return lines


class VisionScreen(RichCommandScreen):
    title = "Vision"
    subtitle = "CSS / a11y inspector · /vision inspect <selector>"

    def body_lines(self) -> list[str]:
        if self.snapshot is not None and self.snapshot.is_demo:
            return [
                "[gold]Vision inspector[/]",
                "  Playwright: [ok]available (demo)[/]",
                "  Browsers: chromium",
                "  Fixture UI: [ok]available[/]",
                "  Evidence dir: .prometheus/vision/",
                "",
                "[dim](demo data)[/]",
            ]
        from . import tui_commands
        return tui_commands.vision_lines()


class AssetsScreen(RichCommandScreen):
    title = "AssetForge"
    subtitle = "local image generation with provenance · /assets generate <kind>"

    def body_lines(self) -> list[str]:
        if self.snapshot is not None and self.snapshot.is_demo:
            return [
                "[gold]AssetForge[/]",
                "  torch:      [ok]available (demo)[/]",
                "  diffusers:  [ok]available (demo)[/]",
                "  rembg:      [warn]not installed[/]",
                "  image tests: disabled",
                "",
                "[dim](demo data)[/]",
            ]
        from . import tui_commands
        return tui_commands.assets_lines()


class AstronautScreen(RichCommandScreen):
    title = "Astronaut"
    subtitle = "long-run autonomous mode · /astronaut start|pause|stop|report"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        try:
            workspace = self.app.workspace  # type: ignore[attr-defined]
        except Exception:
            workspace = Path.cwd()
        if self.snapshot is not None and self.snapshot.is_demo:
            return [
                "[gold]Astronaut session[/]",
                "  status:    [ok]idle (demo)[/]",
                "  objective: add JWT auth to /api/login",
                "  macro attempts: 3 · checkpoints: 2",
                "",
                "[dim]CLI: prometheus astronaut start|pause|resume|stop|tick|report[/]",
                "[dim](demo data)[/]",
            ]
        return tui_commands.astronaut_lines(workspace)


class DoctorScreen(RichCommandScreen):
    title = "Doctor"
    subtitle = "hardware + Ollama service report"

    def body_lines(self) -> list[str]:
        if self.snapshot is not None and self.snapshot.is_demo:
            s = self.snapshot
            return [
                f"[k]OS[/]      [v]{s.os} {s.arch}[/]",
                f"[k]RAM[/]     [v]{s.ram_gb:.0f} GB[/]",
                f"[k]GPU[/]     [v]{s.gpu_name or 'CPU mode'}[/]",
                f"[k]VRAM[/]    [v]{s.vram_gb:.0f} GB[/]",
                f"[k]Disk[/]    [v]{s.disk_free_gb:.0f} GB free[/]",
                "",
                f"[k]Ollama[/]  [{'ok' if s.ollama_running else 'warn'}]{s.ollama_label}[/]",
                "",
                "[dim](demo data — run without --demo for the real report)[/]",
            ]
        from . import tui_commands
        from .hardware import detect_hardware
        from .onboarding import check_ollama
        return tui_commands.doctor_lines(detect_hardware(), check_ollama())


class ToolsScreen(RichCommandScreen):
    title = "Tools"
    subtitle = "built-in agent tools"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        return tui_commands.tools_lines()


class McpScreen(RichCommandScreen):
    title = "MCP"
    subtitle = "model context protocol servers"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        return tui_commands.mcp_lines()


class ModesScreen(RichCommandScreen):
    title = "Autonomy Modes"
    subtitle = "Copilot · Pilot · Astronaut"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        return tui_commands.modes_lines()


class SessionsScreen(RichCommandScreen):
    title = "Sessions"
    subtitle = "recent coding sessions"

    def body_lines(self) -> list[str]:
        if self.snapshot is not None and self.snapshot.is_demo:
            lines = ["[gold]Recent sessions[/]"]
            for s in self.snapshot.recent_sessions:
                lines.append(f"  {s}")
            lines.append("")
            lines.append("[dim](demo data — run without --demo for real sessions)[/]")
            return lines
        from . import tui_commands
        return tui_commands.sessions_lines()


class PermissionsScreen(RichCommandScreen):
    title = "Permissions"
    subtitle = "autonomy policy"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        from .config import load_settings
        return tui_commands.permissions_lines(load_settings())


class ProvidersScreen(RichCommandScreen):
    title = "Providers"
    subtitle = "configured backends"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        from .config import load_settings
        return tui_commands.provider_lines(load_settings())


class TelemetryScreen(RichCommandScreen):
    title = "Telemetry"
    subtitle = "live CPU/RAM/GPU/disk snapshot"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        return tui_commands.telemetry_lines()


class LogoScreen(RichCommandScreen):
    title = "PROMETHEUS"
    subtitle = "brand mark"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        return tui_commands.logo_lines()


class DiagnoseScreen(RichCommandScreen):
    title = "Diagnose"
    subtitle = "sanitized diagnostics export"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        return tui_commands.diagnose_lines()


class PlanScreen(RichCommandScreen):
    title = "Plan"
    subtitle = "objective + acceptance criteria"

    def body_lines(self) -> list[str]:
        lines = [
            "[gold]Plan an objective[/]",
            "",
            "Type an objective in the input below and PROMETHEUS will draft a",
            "plan: tasks, acceptance criteria, and a checkpoint strategy.",
            "Press [gold]Enter[/] to submit (or [gold]/build <objective>[/]).",
            "",
            "[dim]Example:[/] [v]add JWT auth to /api/login with tests[/]",
        ]
        return lines


class SetupScreen(RichCommandScreen):
    """Static rendering of the full 7-step setup wizard.

    Renders all wizard steps as one scrollable screen — the MVP-friendly
    alternative to the interactive modal. The interactive :class:`SetupWizard`
    is kept available for callers that want step-by-step modal flow, but the
    ``/setup`` slash command dispatches here so the screen renders reliably
    under both interactive and headless-export paths.
    """

    title = "PROMETHEUS · First-run Setup"
    subtitle = "7-step setup wizard — type /use <bundle-id> to select"

    def body_lines(self) -> list[str]:
        snap = self.snapshot or TuiSnapshot()
        lines: list[str] = []
        for step in range(len(WIZARD_STEPS)):
            lines.append(f"[gold]Step {step + 1} · {WIZARD_STEPS[step]}[/]")
            lines.extend("  " + ln for ln in _setup_wizard_step_text(step, snap))
            lines.append("")
        lines.append("[dim]Interactive wizard: SetupWizard (pushed programmatically).[/]")
        return lines


# ---------------------------------------------------------------------------
# Screen registry — maps /command to screen class. Used by dispatch_slash.
# ---------------------------------------------------------------------------

SLASH_SCREEN_MAP: dict[str, type[RichCommandScreen]] = {
    "/help":        HelpScreen,
    "/?":           HelpScreen,
    "/settings":    SettingsScreen,
    "/models":      ModelsScreen,
    "/bundles":     BundlesScreen,
    "/sandbox":     SandboxScreen,
    "/memory":      MemoryScreen,
    "/vision":      VisionScreen,
    "/assets":      AssetsScreen,
    "/astronaut":   AstronautScreen,
    "/doctor":      DoctorScreen,
    "/tools":       ToolsScreen,
    "/mcp":         McpScreen,
    "/modes":       ModesScreen,
    "/sessions":    SessionsScreen,
    "/permissions": PermissionsScreen,
    "/provider":    ProvidersScreen,
    "/providers":   ProvidersScreen,
    "/telemetry":   TelemetryScreen,
    "/logo":        LogoScreen,
    "/diagnose":    DiagnoseScreen,
    "/plan":        PlanScreen,
    "/setup":       SetupScreen,
}


def dispatch_slash(app, cmd: str, snapshot: TuiSnapshot | None, rest: str = "") -> bool:
    """Route a display /command to its screen. Returns True if handled.

    The caller (PrometheusApp) already handles /exit /clear /mode /use /qualify
    /resume /memory /build inline because those mutate state. Everything that's
    purely display lives here.
    """
    if cmd == "/setup-wizard":
        app.push_screen(SetupWizard(snapshot, app=app))
        return True

    screen_cls = SLASH_SCREEN_MAP.get(cmd)
    if screen_cls is None:
        return False
    try:
        app.push_screen(screen_cls(snapshot))
    except Exception as exc:
        try:
            from .tui import PrometheusApp
            if isinstance(app, PrometheusApp):
                app._log(f"[err]screen error:[/] {exc}")
        except Exception:
            pass
        return False
    return True


# ---------------------------------------------------------------------------
# Render-to-text helper — used by golden tests + SVG snapshot script
# ---------------------------------------------------------------------------

def render_screen_text(cmd: str, snapshot: TuiSnapshot | None = None) -> str:
    """Return a deterministic plain-text dump of a command screen's body."""
    if cmd == "/setup-wizard":
        lines = _setup_wizard_step_text(0, snapshot)
    else:
        cls = SLASH_SCREEN_MAP.get(cmd, HelpScreen)
        screen = cls.__new__(cls)
        screen.snapshot = snapshot
        try:
            lines = screen.body_lines()
        except Exception as exc:
            lines = [f"(screen error: {exc})"]
    return "\n".join(strip_markup(str(line)) for line in lines)


# ---------------------------------------------------------------------------
# Setup wizard — modal screen, 7 steps per spec
# ---------------------------------------------------------------------------

WIZARD_STEPS = [
    "Welcome",
    "Hardware",
    "Ollama",
    "Recommended bundle",
    "Confirm bundle",
    "Pull / validate",
    "Start coding",
]


class SetupWizard(Screen):
    """Interactive multi-step setup wizard.

    Pushed via :func:`dispatch_slash` when ``cmd == '/setup-wizard'`` (an
    explicit, opt-in path). The default ``/setup`` routes to :class:`SetupScreen`
    for cross-mode rendering reliability.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("right", "next_step", "Next", show=False),
        Binding("left", "prev_step", "Back", show=False),
    ]

    def __init__(self, snapshot: TuiSnapshot | None = None, app=None) -> None:
        super().__init__()
        self.snapshot = snapshot
        self._app_ref = app
        self.step = 0
        self.total = len(WIZARD_STEPS)
        self.choice: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("[gold]PROMETHEUS · First-run Setup[/]", id="wizard-title", markup=True)
        yield Static("", id="wizard-step", markup=True)
        yield Static("", id="wizard-body", markup=True, classes="wizard-body-static")
        yield Button("Back", id="wiz-back", variant="default", classes="wiz-btn")
        yield Button("Next", id="wiz-next", variant="primary", classes="wiz-btn")
        yield Button("Cancel", id="wiz-cancel", variant="error", classes="wiz-btn")

    def on_mount(self) -> None:
        self._render()

    def _render(self) -> None:
        try:
            step_widget = self.query_one("#wizard-step", Static)
            body_widget = self.query_one("#wizard-body", Static)
        except Exception:
            return
        step_widget.update(
            f"[dim]step {self.step + 1} of {self.total} ·[/] [gold]{WIZARD_STEPS[self.step]}[/]"
        )
        body_widget.update("\n".join(_setup_wizard_step_text(self.step, self.snapshot)))
        # Button state
        try:
            self.query_one("#wiz-back", Button).disabled = self.step == 0
            self.query_one("#wiz-next", Button).label = (
                "Start coding" if self.step == self.total - 1 else "Next"
            )
        except Exception:
            pass

    def _advance(self, delta: int) -> None:
        new = max(0, min(self.total - 1, self.step + delta))
        if new == self.step:
            return
        self.step = new
        self._render()

    def action_next_step(self) -> None:
        if self.step == self.total - 1:
            self.dismiss({"bundle_id": self.choice})
        else:
            self._advance(+1)

    def action_prev_step(self) -> None:
        self._advance(-1)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "wiz-next":
            self.action_next_step()
        elif event.button.id == "wiz-back":
            self.action_prev_step()
        elif event.button.id == "wiz-cancel":
            self.action_cancel()


def _setup_wizard_step_text(step: int, snap: TuiSnapshot | None) -> list[str]:
    """Pure function — used by both the wizard UI and golden text tests."""
    snap = snap or TuiSnapshot()
    if step == 0:  # Welcome
        return [
            "[gold]Welcome to PROMETHEUS[/]",
            "",
            "A local-first, hardware-honest coding agent.",
            "This wizard picks a model bundle that fits your machine,",
            "checks Ollama, and gets you vibe-coding in under a minute.",
            "",
            "[dim]Next: detect your hardware.[/]",
        ]
    if step == 1:  # Hardware
        template = [
            "[k]OS[/]      [v]{os} {arch}[/]",
            "[k]CPU[/]     [v]{cpu}[/]",
            "[k]RAM[/]     [v]{ram:.0f} GB[/]",
            "[k]GPU[/]     [v]{gpu}[/]",
            "[k]VRAM[/]    [v]{vram:.0f} GB[/]",
            "[k]Disk[/]    [v]{disk:.0f} GB free[/]",
        ]
        return [
            line.format(
                os=snap.os, arch=snap.arch, cpu=snap.cpu_brand or "—",
                ram=snap.ram_gb, gpu=snap.gpu_name or "CPU mode",
                vram=snap.vram_gb, disk=snap.disk_free_gb,
            )
            for line in template
        ]
    if step == 2:  # Ollama
        ollama_state = "running" if snap.ollama_running else "[warn]not running[/]"
        return [
            "[k]Ollama[/]",
            f"  state:    {ollama_state}",
            f"  models:   {len(snap.ollama_models)} installed",
            "",
            "[dim]If not running, start it with:[/]",
            "[v]  ollama serve[/]",
        ]
    if step == 3:  # Recommended bundle
        try:
            from .hardware import detect_hardware, recommended_profile
            recommended = recommended_profile(detect_hardware())
        except Exception:
            recommended = "spark-cpu-8gb"
        return [
            "[gold]Recommended bundle[/]",
            "",
            f"  [v]{recommended}[/]",
            "",
            "[dim]Based on your detected hardware. You can confirm,[/]",
            "[dim]or browse alternatives in the next step.[/]",
        ]
    if step == 4:  # Confirm bundle
        try:
            from .bundles import classify_registry, load_registry
            from .hardware import detect_hardware
            from .onboarding import check_ollama
            classified = classify_registry(
                load_registry(), detect_hardware(), check_ollama().models,
            )
        except Exception:
            classified = []
        lines = ["[gold]Available bundles[/]", ""]
        for c in classified[:8]:
            tag = "ok" if c.status in ("recommended", "installed") else "dim"
            add_on = " (add-on)" if c.bundle.is_add_on else ""
            lines.append(
                f"  [{tag}]{c.bundle.id:<22}[/] {c.bundle.name}{add_on}"
            )
        lines.append("")
        lines.append("[dim]Type /use <id> to select one (in the main input).[/]")
        return lines
    if step == 5:  # Pull / validate
        return [
            "[gold]Pull / validate[/]",
            "",
            "Once you /use a bundle, PROMETHEUS will:",
            "  1. Verify each model is present in Ollama",
            "  2. Run a smoke test (chat + structured output)",
            "  3. Show qualification results inline",
            "",
            "[dim]Use /qualify <bundle-id> to qualify now.[/]",
        ]
    return [  # Start coding
        "[gold]Ready to code[/]",
        "",
        "[dim]Type an objective and press Enter:[/]",
        "[v]  add JWT auth to /api/login with tests[/]",
        "",
        "[dim]Or open the command palette with Ctrl+P.[/]",
    ]


# ---------------------------------------------------------------------------
# Command palette — custom MVP richer than the builtin
# ---------------------------------------------------------------------------

class CommandPaletteScreen(Screen[str | None]):
    """MVP command palette with metadata: name, description, shortcut, source."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("down", "cursor_down", show=False),
        Binding("up", "cursor_up", show=False),
        Binding("enter", "select_current", show=False),
    ]

    def __init__(self, snapshot: TuiSnapshot | None = None) -> None:
        super().__init__()
        self.snapshot = snapshot
        self._filter = ""
        self._rows: list[tuple[str, str, str, str, str]] = list(COMMAND_PALETTE)
        self._selected = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-card"):
            yield Input(id="palette-input", placeholder="filter commands…")
            yield VerticalScroll(
                Static("", id="palette-list", markup=True),
                id="palette-scroll",
            )

    def on_mount(self) -> None:
        try:
            self.query_one("#palette-input", Input).focus()
        except Exception:
            pass
        self._render_rows()

    def _filtered(self) -> list[tuple[str, str, str, str, str]]:
        if not self._filter:
            return self._rows
        f = self._filter.lower()
        return [
            row for row in self._rows
            if f in row[0].lower() or f in row[1].lower()
        ]

    def _render_rows(self) -> None:
        rows = self._filtered()
        if not rows:
            self.query_one("#palette-list", Static).update(
                "[dim]no commands match[/]"
            )
            return
        if self._selected >= len(rows):
            self._selected = 0
        lines: list[str] = []
        for i, (cmd, desc, shortcut, avail, source) in enumerate(rows):
            marker = "[gold]▶[/]" if i == self._selected else " "
            sc = f"[dim]{shortcut}[/]" if shortcut else ""
            src_tag = {
                "local":    "[ok]local[/]",
                "cloud":    "[info]cloud[/]",
                "external": "[warn]ext[/]",
            }.get(source, f"[dim]{source}[/]")
            lines.append(
                f"{marker} [gold]{cmd:<13}[/] {desc}\n"
                f"    {sc} [dim]·[/] {src_tag} [dim]·[/] {avail}"
            )
        self.query_one("#palette-list", Static).update("\n".join(lines))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "palette-input":
            self._filter = event.value
            self._selected = 0
            self._render_rows()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_select_current()

    def action_cursor_down(self) -> None:
        rows = self._filtered()
        if rows:
            self._selected = (self._selected + 1) % len(rows)
            self._render_rows()

    def action_cursor_up(self) -> None:
        rows = self._filtered()
        if rows:
            self._selected = (self._selected - 1) % len(rows)
            self._render_rows()

    def action_select_current(self) -> None:
        rows = self._filtered()
        if not rows:
            return
        cmd = rows[self._selected][0]
        self.dismiss(cmd)

    def action_cancel(self) -> None:
        self.dismiss(None)


__all__ = [
    "AssetsScreen",
    "AstronautScreen",
    "BundlesScreen",
    "CommandPaletteScreen",
    "DiagnoseScreen",
    "DoctorScreen",
    "HelpScreen",
    "LogoScreen",
    "McpScreen",
    "MemoryScreen",
    "ModelsScreen",
    "ModesScreen",
    "PermissionsScreen",
    "PlanScreen",
    "ProvidersScreen",
    "RichCommandScreen",
    "SLASH_SCREEN_MAP",
    "SandboxScreen",
    "SessionsScreen",
    "SettingsScreen",
    "SetupWizard",
    "TelemetryScreen",
    "ToolsScreen",
    "VisionScreen",
    "WIZARD_STEPS",
    "dispatch_slash",
    "render_screen_text",
    "strip_markup",
]
