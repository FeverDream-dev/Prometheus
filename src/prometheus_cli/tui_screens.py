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
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
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

    def inspector_lines(self) -> list[str] | None:
        s = self.snapshot
        if s is None:
            return None
        return [
            f"[section]{self.title}[/]",
            f"  [k]Mode[/]    [v]{s.mode_label}[/]",
            f"  [k]Bundle[/]  [v]{s.bundle_label}[/]",
            f"  [k]Sandbox[/] [v]{s.sandbox_tier}[/]",
            f"  [k]Git[/]     [v]{s.git.status_label}[/]",
            f"  [k]Memory[/]  [v]{s.memory.status_label}[/]",
        ]

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
    title = "PROMETHEUS \u00b7 Command Help"
    subtitle = "grouped command palette \u2014 Ctrl+P opens the visual palette"

    def body_lines(self) -> list[str]:
        from . import tui_commands
        return tui_commands.help_lines()

    def inspector_lines(self) -> list[str]:
        from .tui_theme import COMMAND_PALETTE
        return [
            "[section]Commands[/]",
            f"  [k]Total[/]     [v]{len(COMMAND_PALETTE)}[/]",
            "[section]Shortcuts[/]",
            "  [gold]Ctrl+P[/]  palette",
            "  [gold]Ctrl+B[/]  toggle sidebar",
            "  [gold]Ctrl+I[/]  toggle inspector",
            "  [gold]Esc[/]     back to dashboard",
        ]


class SettingsScreen(RichCommandScreen):
    title = "Settings"
    subtitle = "stored in ~/.prometheus/config.yaml"

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        return [
            "[section]Config[/]",
            "  [k]Path[/]      [v]~/.prometheus/[/]",
            f"  [k]Mode[/]      [v]{s.mode_label}[/]",
            f"  [k]Sandbox[/]   [v]{s.sandbox_tier}[/]",
            f"  [k]Local-only[/] [v]{'on' if s.local_only else 'off'}[/]",
            f"  [k]Provider[/]   [v]{s.provider}[/]",
        ]

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

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        lines = ["[section]GPU fit[/]",
                 f"  [k]RAM[/]  [v]{s.ram_gb:.0f} GB[/]",
                 f"  [k]VRAM[/] [v]{s.vram_gb:.0f} GB[/]",
                 f"  [k]Disk[/] [v]{s.disk_free_gb:.0f} GB[/]",
                 "",
                 "[section]Models[/]"]
        for m in s.ollama_models[:6]:
            lines.append(f"  [dim]• {m}[/]")
        return lines


class BundlesScreen(RichCommandScreen):
    title = "Model Packages"
    subtitle = "hardware-aware bundles · /use <id>"

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        return [
            "[section]Hardware fit[/]",
            f"  [k]RAM[/]   [v]{s.ram_gb:.0f} GB[/]",
            f"  [k]VRAM[/]  [v]{s.vram_gb:.0f} GB[/]",
            f"  [k]Disk[/]  [v]{s.disk_free_gb:.0f} GB[/]",
            "",
            "[section]Active[/]",
            f"  [gold]{s.bundle_label}[/]",
        ]

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

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        return [
            "[section]Active tier[/]",
            f"  [gold]{s.sandbox_tier}[/]",
            "",
            "[section]Policy[/]",
            f"  [k]Network[/]  [{'ok' if not s.local_only else 'warn'}]{'allowed' if not s.local_only else 'denied'}[/]",
            f"  [k]Mode[/]     [v]{s.mode_label}[/]",
            "",
            "[dim]CLI: prometheus sandbox test --all[/]",
        ]


class MemoryScreen(RichCommandScreen):
    title = "Memory"
    subtitle = "bounded project memory · /memory status|inspect|why|rebuild"

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        m = s.memory
        if not m.available:
            return ["[section]Memory[/]", "  [dim]no file[/]"]
        return [
            "[section]Memory[/]",
            f"  [k]Status[/]   [{'ok' if m.ok else 'warn'}]{m.status_label}[/]",
            f"  [k]Words[/]    [v]{m.word_count}/{m.limit}[/]",
            f"  [k]Version[/]  [v]v{m.version}[/]",
            f"  [k]Recovered[/] [v]{'yes' if m.recovered else 'no'}[/]",
        ]

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
    subtitle = "CSS / a11y inspector \u00b7 /vision inspect <selector>"

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        pw = "available (demo)" if s.is_demo else "check /doctor"
        return [
            "[section]Playwright[/]",
            f"  [{'ok' if s.is_demo else 'warn'}]{pw}[/]",
            "[section]Fixtures[/]",
            f"  [k]Web UI[/]    [v]{'available' if s.is_demo else 'check'}[/]",
            "[section]Evidence[/]",
            "  [k]Dir[/]  [v].prometheus/vision/[/]",
        ]

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
    subtitle = "local image generation with provenance \u00b7 /assets generate <kind>"

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        status = "available (demo)" if s.is_demo else "check /doctor"
        return [
            "[section]Backends[/]",
            f"  [k]torch[/]       [{'ok'}]{status}[/]",
            f"  [k]diffusers[/]   [{'ok'}]{status}[/]",
            f"  [k]rembg[/]       [{'warn'}]not installed[/]",
            "[section]Policy[/]",
            "  [k]Commercial[/]  [v]per-license[/]",
        ]

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
    subtitle = "long-run autonomous mode \u00b7 /astronaut start|pause|stop|report"

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        if s.is_demo:
            return [
                "[section]Session[/]",
                "  [k]Status[/]    [ok]idle[/]",
                "  [k]Attempts[/]  [v]3[/]",
                "  [k]Checks[/]    [v]2[/]",
                "[section]Control[/]",
                "  [gold]start | pause | stop[/]",
            ]
        return [
            "[section]Control files[/]",
            "  [k]STOP[/]    [dim].prometheus/STOP[/]",
            "  [k]PAUSE[/]   [dim].prometheus/PAUSE[/]",
        ]

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

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        return [
            "[section]Health[/]",
            f"  [k]OS[/]      [v]{s.os} {s.arch}[/]",
            f"  [k]RAM[/]     [v]{s.ram_gb:.0f} GB[/]",
            f"  [k]GPU[/]     [v]{s.gpu_name or 'CPU'}[/]",
            f"  [k]Ollama[/]  [{'ok' if s.ollama_running else 'warn'}]{s.ollama_label}[/]",
            f"  [k]Models[/]  [v]{len(s.ollama_models)}[/]",
        ]

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

    def inspector_lines(self) -> list[str]:
        return [
            "[section]Categories[/]",
            "  [k]Repository[/]  [v]6 tools[/]",
            "  [k]Process[/]     [v]run, supervise[/]",
            "  [k]Git[/]         [v]5 tools[/]",
            "  [k]Browser[/]     [v]Playwright[/]",
            "  [k]Web[/]         [v]fetch (bounded)[/]",
            "  [k]MCP[/]         [v]per-server[/]",
        ]

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
    subtitle = "Copilot \u00b7 Pilot \u00b7 Astronaut"

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        return [
            "[section]Modes[/]",
            f"  [{'gold' if s.mode == 'copilot' else 'dim'}]Copilot[/]    suggestive",
            f"  [{'gold' if s.mode == 'pilot' else 'dim'}]Pilot[/]      balanced",
            f"  [{'gold' if s.mode == 'astronaut' else 'dim'}]Astronaut[/]  autonomous",
            "",
            f"[k]Active[/] [gold]{s.mode_label}[/]",
        ]

    def body_lines(self) -> list[str]:
        from . import tui_commands
        return tui_commands.modes_lines()


class SessionsScreen(RichCommandScreen):
    title = "Sessions"
    subtitle = "recent coding sessions"

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        count = len(s.recent_sessions) if s.is_demo else 0
        latest = s.recent_sessions[0][:40] if s.recent_sessions else "(none)"
        return [
            "[section]History[/]",
            f"  [k]Total[/]     [v]{count}[/]",
            f"  [k]Latest[/]    [v]{latest}[/]",
            "[section]Storage[/]",
            "  [k]DB[/]  [v]~/.prometheus/sessions/[/]",
        ]

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

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        return [
            "[section]Policy[/]",
            f"  [k]Mode[/]        [v]{s.mode_label}[/]",
            f"  [k]Sandbox[/]     [v]{s.sandbox_tier}[/]",
            f"  [k]Network[/]     [{'ok' if not s.local_only else 'warn'}]{'allowed' if not s.local_only else 'denied'}[/]",
            f"  [k]Local-only[/]  [v]{'on' if s.local_only else 'off'}[/]",
        ]

    def body_lines(self) -> list[str]:
        from . import tui_commands
        from .config import load_settings
        return tui_commands.permissions_lines(load_settings())


class ProvidersScreen(RichCommandScreen):
    title = "Providers"
    subtitle = "configured backends"

    def inspector_lines(self) -> list[str]:
        s = self.snapshot or TuiSnapshot()
        return [
            "[section]Ollama[/]",
            "  [k]URL[/]     [v]http://127.0.0.1:11434[/]",
            f"  [k]Status[/]  [{'ok' if s.ollama_running else 'warn'}]{s.ollama_label}[/]",
            "[section]Cloud[/]",
            f"  [k]Status[/]  [v]{'disabled (local-only)' if s.local_only else 'configured per-bundle'}[/]",
        ]

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

    def inspector_lines(self) -> list[str]:
        return [
            "[section]Workflow[/]",
            "  [gold]1[/] type an objective",
            "  [gold]2[/] PROMETHEUS drafts a plan",
            "  [gold]3[/] acceptance criteria listed",
            "  [gold]4[/] checkpoints at each step",
        ]

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


class BundleForgeScreen(RichCommandScreen):
    title = "BundleForge"
    subtitle = "create custom bundles from templates"

    def inspector_lines(self) -> list[str]:
        try:
            from .bundleforge import list_templates, load_catalog
            cat = load_catalog()
            return [
                "[section]Catalog[/]",
                f"  [k]Models[/]    [v]{len(cat.models)}[/]",
                f"  [k]Templates[/] [v]{len(list_templates())}[/]",
                "[section]CLI[/]",
                "  [dim]bundleforge recommend[/]",
                "  [dim]bundleforge create[/]",
                "  [dim]bundleforge install[/]",
            ]
        except Exception:
            return ["[section]BundleForge[/]", "  [dim]catalog unavailable[/]"]

    def body_lines(self) -> list[str]:
        try:
            from .bundleforge import list_templates, load_template, load_catalog
        except Exception:
            return ["[dim]BundleForge not available.[/]"]
        lines = ["[gold]BundleForge templates[/]", ""]
        for tid in list_templates():
            try:
                bundle = load_template(tid)
                req = bundle.requirements
                lines.append(
                    f"  [k]{tid:<28}[/] [v]{bundle.name}[/]"
                )
                lines.append(
                    f"    [dim]{req.min_ram_gb} GB RAM, {req.min_vram_gb} GB VRAM"
                    f"  ({bundle.use_case})[/]"
                )
            except Exception:
                pass
        lines.append("")
        try:
            cat = load_catalog()
            lines.append(f"[gold]Model catalog[/]: {len(cat.models)} models")
            lines.append(f"  [dim]families: {', '.join(sorted({m.family for m in cat.models}))}[/]")
        except Exception:
            pass
        lines.append("")
        lines.append("[dim]CLI: prometheus bundleforge recommend \"<your use case>\"[/]")
        return lines


class SetupScreen(RichCommandScreen):
    """Static rendering of the full setup wizard (all steps on one screen).

    Renders every wizard step as one scrollable view for headless export and
    ``/setup`` slash dispatch. Interactive bundle pull uses ``/setup-wizard``.
    """

    title = "PROMETHEUS · First-run Setup"
    subtitle = "9-step setup wizard — type /use <bundle-id> to select"

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
    "/setup":       SetupScreen,
    "/settings":    SettingsScreen,
    "/models":      ModelsScreen,
    "/bundles":     BundlesScreen,
    "/bundleforge": BundleForgeScreen,
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
}


def dispatch_slash(app, cmd: str, snapshot: TuiSnapshot | None, rest: str = "") -> bool:
    """Route a display /command to an in-panel view. Returns True if handled.

    Command views render in the main area (sidebar/inspector/status bar stay
    visible). The palette and wizard are still pushed as modal Screen overlays.
    """
    if cmd == "/setup-wizard":
        app.push_screen(InteractiveSetupScreen(snapshot, app=app))
        return True

    screen_cls = SLASH_SCREEN_MAP.get(cmd)
    if screen_cls is None:
        return False
    try:
        view = screen_cls.__new__(screen_cls)
        view.snapshot = snapshot
        body = view.body_lines()
        insp = getattr(view, "inspector_lines", lambda: None)()
        app._show_command_view(cmd, view.title, view.subtitle, body, insp)
    except Exception as exc:
        try:
            from .tui import PrometheusApp
            if isinstance(app, PrometheusApp):
                app._log(f"[err]view error:[/] {exc}")
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
    elif cmd == "/setup":
        screen = SetupScreen.__new__(SetupScreen)
        screen.snapshot = snapshot
        try:
            lines = screen.body_lines()
        except Exception as exc:
            lines = [f"(screen error: {exc})"]
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
    "Project folder",
    "Hardware scan",
    "Ollama status",
    "Bundle recommendation",
    "Bundle choice",
    "Model pull / validate",
    "Git & memory setup",
    "Ready to code",
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
    snap = snap or TuiSnapshot()

    def _wizard_hardware():
        from .hardware import HardwareReport, detect_hardware

        if snap.is_demo or snap.ram_gb > 0:
            return HardwareReport(
                os=snap.os or "Linux",
                architecture=snap.arch or "x86_64",
                ram_gb=snap.ram_gb,
                cpu_brand=snap.cpu_brand,
                gpu_name=snap.gpu_name,
                vram_gb=snap.vram_gb,
                disk_free_gb=snap.disk_free_gb,
                ollama_installed=snap.ollama_installed,
                ollama_running=snap.ollama_running,
            )
        return detect_hardware()

    def _wizard_models() -> list[str]:
        if snap.is_demo or snap.ollama_models:
            return list(snap.ollama_models)
        from .onboarding import check_ollama
        return check_ollama().models

    if step == 0:
        return [
            "[gold]Welcome to PROMETHEUS[/]",
            "",
            "A local-first, hardware-honest coding agent.",
            "This wizard picks a model bundle that fits your machine,",
            "checks Ollama, and gets you vibe-coding in under a minute.",
            "",
            "[dim]Next: confirm your project folder.[/]",
        ]
    if step == 1:
        return [
            "[gold]Project folder[/]",
            "",
            f"[k]Path[/] [v]{snap.project_path}[/]",
            f"[k]Git[/]  [{'ok' if snap.git.available else 'warn'}]{snap.git.status_label}[/]",
            "",
            "[dim]PROMETHEUS will work in this folder.[/]",
            "[dim]You can change it with: prometheus tui --workspace <path>[/]",
            "",
            "[dim]Next: detect your hardware.[/]",
        ]
    if step == 2:
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
                os=snap.os, arch=snap.arch, cpu=snap.cpu_brand or "\u2014",
                ram=snap.ram_gb, gpu=snap.gpu_name or "CPU mode",
                vram=snap.vram_gb, disk=snap.disk_free_gb,
            )
            for line in template
        ]
    if step == 3:
        ollama_state = "running" if snap.ollama_running else "[warn]not running[/]"
        return [
            "[k]Ollama[/]",
            f"  state:    {ollama_state}",
            f"  models:   {len(snap.ollama_models)} installed",
            "",
            "[dim]If not running, start it with:[/]",
            "[v]  ollama serve[/]",
            "",
            "[dim]Next: pick a bundle.[/]",
        ]
    if step == 4:
        try:
            from .hardware import recommended_profile
            recommended = recommended_profile(_wizard_hardware())
        except Exception:
            recommended = snap.bundle_id or "spark-cpu-8gb"
        return [
            "[gold]Recommended bundle[/]",
            "",
            f"  [v]{recommended}[/]",
            "",
            "[dim]Based on your detected hardware. You can confirm,[/]",
            "[dim]or browse alternatives in the next step.[/]",
        ]
    if step == 5:
        try:
            from .bundles import classify_registry, load_registry
            classified = classify_registry(
                load_registry(), _wizard_hardware(), _wizard_models(),
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
    if step == 6:
        try:
            from .first_run import build_pull_info_for_bundle
            bundle_id = snap.bundle_id
            if not bundle_id and not snap.is_demo:
                try:
                    from .config import load_settings
                    bundle_id = load_settings().active_bundle_id
                except Exception:
                    bundle_id = None
            if bundle_id:
                infos = build_pull_info_for_bundle(bundle_id, _wizard_models())
            else:
                infos = []
        except Exception:
            infos = []
        if not infos:
            return [
                "[gold]Model pull / validate[/]",
                "",
                "Once you /use a bundle, PROMETHEUS will:",
                "  1. Show each model with download size and license",
                "  2. Ask confirmation before pulling",
                "  3. Run a smoke test after each pull",
                "",
                "[dim]Models are never auto-downloaded without your confirmation.[/]",
                "[dim]Use /qualify <bundle-id> to qualify now.[/]",
            ]
        lines = ["[gold]Models to pull[/]", ""]
        for info in infos:
            status = "[ok]installed[/]" if info.already_installed else "[warn]not installed[/]"
            req = "required" if info.required else "optional"
            lines.append(
                f"  [k]{info.model_id}[/]"
                f"  [dim]({info.role}, ~{info.download_size_gb:.1f} GB, {info.license})[/]"
                f"  {status} [dim]{req}[/]"
            )
        lines.append("")
        lines.append("[dim]Confirmation required before each download (unless --yes).[/]")
        return lines
    if step == 7:
        return [
            "[gold]Git & memory setup[/]",
            "",
            "[k]Git[/]",
            f"  [{'ok' if snap.git.available else 'warn'}]{snap.git.status_label}[/]",
            f"  [dim]branch: {snap.git.branch or '(none)'}[/]",
            "",
            "[k]Memory[/]",
            f"  [{'ok' if snap.memory.ok else 'warn'}]{snap.memory.status_label}[/]",
            f"  [dim]words: {snap.memory.word_count}/{snap.memory.limit}[/]",
            "",
            "[dim]PROMETHEUS checkpoints every mutation via Git.[/]",
            "[dim]Project memory lives in .prometheus/memory.md (bounded to 1024 words).[/]",
        ]
    return [
        "[gold]Ready to code[/]",
        "",
        "[dim]Type an objective and press Enter:[/]",
        "[v]  add JWT auth to /api/login with tests[/]",
        "",
        "[dim]Or open the command palette with Ctrl+P.[/]",
    ]


# ---------------------------------------------------------------------------
# Interactive setup — mouse-clickable bundle picker + model pull + verify
# ---------------------------------------------------------------------------

class BundleListItem(Static):
    """One clickable row in the setup bundle list."""

    DEFAULT_CSS = """
    BundleListItem {
        height: 2;
        padding: 0 1;
        border: solid transparent;
    }
    BundleListItem:hover {
        background: $boost;
    }
    BundleListItem.selected {
        border: solid #c9a227;
        background: #181b24;
    }
    """

    def __init__(self, bundle_id: str, label: str, status: str, recommended: bool = False) -> None:
        super().__init__(markup=True)
        self.bundle_id = bundle_id
        self.label = label
        self.status = status
        self.recommended = recommended
        self._selected = False
        self._render()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.set_class(selected, "selected")
        self._render()

    def _render(self) -> None:
        marker = "[gold]▶[/] " if self._selected else "  "
        tag = {
            "recommended": "[ok]recommended[/]",
            "installed": "[ok]installed[/]",
            "compatible": "[info]compatible[/]",
            "blocked": "[err]blocked[/]",
        }.get(self.status, f"[dim]{self.status}[/]")
        rec = " [gold]★[/]" if self.recommended else ""
        self.update(f"{marker}[v]{self.bundle_id:<22}[/] {self.label}{rec}  {tag}")

    async def on_click(self, _event) -> None:
        try:
            screen = self.app.screen  # type: ignore[attr-defined]
            if hasattr(screen, "select_bundle"):
                screen.select_bundle(self.bundle_id)  # type: ignore[attr-defined]
        except Exception:
            pass


class InteractiveSetupScreen(ModalScreen[dict | None]):
    """Full interactive setup: pick a bundle, download models, verify — all clickable."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    def __init__(self, snapshot: TuiSnapshot | None = None, app=None) -> None:
        super().__init__()
        self.snapshot = snapshot
        self._app_ref = app
        self._selected_id: str | None = None
        self._busy = False
        self._confirm_large: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="setup-card"):
            yield Static("[gold]PROMETHEUS · Setup[/]", id="setup-title", markup=True)
            yield Static("", id="setup-hw", markup=True)
            yield Static("[section]Bundles[/] — click to select", markup=True)
            with VerticalScroll(id="setup-bundle-scroll"):
                yield Static("[dim]loading bundles…[/]", id="setup-bundle-list", markup=True)
            yield Static("", id="setup-models", markup=True)
            yield Static("", id="setup-status", markup=True)
            with Horizontal(id="setup-buttons"):
                yield Button("Select bundle", id="btn-select", variant="primary")
                yield Button("Download models", id="btn-pull", variant="default")
                yield Button("Verify setup", id="btn-verify", variant="default")
                yield Button("All-in-one", id="btn-all", variant="success")
                yield Button("Close", id="btn-close", variant="default")

    def on_mount(self) -> None:
        self._render_hardware()
        self._render_bundle_list()

    def _render_hardware(self) -> None:
        snap = self.snapshot or TuiSnapshot()
        ollama = "[ok]running[/]" if snap.ollama_running else "[warn]not running[/]"
        lines = [
            f"[k]Project[/] [v]{snap.project_path}[/]",
            f"[k]RAM[/]    [v]{snap.ram_gb:.0f} GB[/]  "
            f"[k]GPU[/] [v]{snap.gpu_name or 'CPU'}[/]  "
            f"[k]Ollama[/] {ollama}  "
            f"[k]models[/] [v]{len(snap.ollama_models)}[/]",
        ]
        try:
            self.query_one("#setup-hw", Static).update("\n".join(lines))
        except Exception:
            pass

    def _classified_bundles(self) -> list:
        try:
            from .bundles import classify_registry, load_registry
            from .hardware import detect_hardware
            from .onboarding import check_ollama
            return classify_registry(
                load_registry(), detect_hardware(), check_ollama().models,
            )
        except Exception:
            return []

    def _render_bundle_list(self) -> None:
        scroll = self.query_one("#setup-bundle-scroll", VerticalScroll)
        try:
            for child in list(scroll.children):
                child.remove()
        except Exception:
            pass
        classified = self._classified_bundles()
        if not classified:
            scroll.mount(Static("[dim]No bundles found.[/]", markup=True))
            return
        rec_id = next((c.bundle.id for c in classified if c.status == "recommended"), None)
        if self._selected_id is None and rec_id:
            self._selected_id = rec_id
        for c in classified[:12]:
            if c.bundle.is_add_on:
                continue
            item = BundleListItem(
                c.bundle.id,
                c.bundle.name,
                c.status,
                recommended=(c.bundle.id == rec_id),
            )
            item.set_selected(c.bundle.id == self._selected_id)
            scroll.mount(item)
        self._render_models_panel()

    def select_bundle(self, bundle_id: str) -> None:
        self._selected_id = bundle_id
        scroll = self.query_one("#setup-bundle-scroll", VerticalScroll)
        for child in scroll.children:
            if isinstance(child, BundleListItem):
                child.set_selected(child.bundle_id == bundle_id)
        self._render_models_panel()
        self._set_status(f"Selected [gold]{bundle_id}[/]")

    def _render_models_panel(self) -> None:
        widget = self.query_one("#setup-models", Static)
        if not self._selected_id:
            widget.update("[dim]Select a bundle to see required models.[/]")
            return
        try:
            from .first_run import build_pull_info_for_bundle
            from .onboarding import check_ollama
            infos = build_pull_info_for_bundle(self._selected_id, check_ollama().models)
        except Exception:
            infos = []
        if not infos:
            widget.update(f"[dim]No model info for {self._selected_id}.[/]")
            return
        lines = [f"[section]Models for {self._selected_id}[/]", ""]
        for info in infos:
            st = "[ok]installed[/]" if info.already_installed else "[warn]missing[/]"
            req = "required" if info.required else "optional"
            lines.append(
                f"  [v]{info.model_id}[/] ({info.role}) ~{info.download_size_gb:.1f} GB — {st} [{req}]"
            )
        widget.update("\n".join(lines))

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#setup-status", Static).update(text)
        except Exception:
            pass

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for bid in ("btn-select", "btn-pull", "btn-verify", "btn-all"):
            try:
                self.query_one(f"#{bid}", Button).disabled = busy
            except Exception:
                pass

    def _emit_app_log(self, line: str) -> None:
        app = self._app_ref
        if app is not None and hasattr(app, "_log"):
            try:
                app.call_from_thread(app._log, line)  # type: ignore[attr-defined]
            except Exception:
                pass

    def _confirm_large_download(self, prompt: str) -> bool:
        self._confirm_large = prompt
        self._set_status(
            f"[warn]{prompt}[/] — click [gold]Download models[/] or [gold]All-in-one[/] again to confirm."
        )
        return False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self._busy:
            return
        bid = event.button.id or ""
        if bid == "btn-close":
            self.action_close()
        elif bid == "btn-select":
            self.run_worker(self._worker_select)
        elif bid == "btn-pull":
            self.run_worker(self._worker_pull)
        elif bid == "btn-verify":
            self.run_worker(self._worker_verify)
        elif bid == "btn-all":
            self.run_worker(self._worker_all)

    def _require_bundle(self) -> str | None:
        if not self._selected_id:
            self._set_status("[warn]Select a bundle first (click a row).[/]")
            return None
        return self._selected_id

    def _worker_select(self) -> None:
        bundle_id = self._require_bundle()
        if not bundle_id:
            return
        self.call_from_thread(self._set_busy, True)
        try:
            from .tui_setup_actions import activate_bundle
            ok, msg = activate_bundle(bundle_id)
            styled = f"[ok]{msg}[/]" if ok else f"[err]{msg}[/]"
            self.call_from_thread(self._set_status, styled)
            self.call_from_thread(self._emit_app_log, styled)
            if ok and self._app_ref is not None:
                self.call_from_thread(self._app_ref._tick_telemetry)  # type: ignore[attr-defined]
        finally:
            self.call_from_thread(self._set_busy, False)

    def _worker_pull(self) -> None:
        bundle_id = self._require_bundle()
        if not bundle_id:
            return
        self.call_from_thread(self._set_busy, True)
        try:
            from .tui_setup_actions import pull_bundle_models

            def emit(line: str) -> None:
                self.call_from_thread(self._set_status, line)
                self.call_from_thread(self._emit_app_log, line)

            yes = self._confirm_large is not None
            ok = pull_bundle_models(
                bundle_id,
                yes=yes,
                confirm_large=self._confirm_large_download if not yes else None,
                on_status=emit,
            )
            if ok:
                self._confirm_large = None
                self.call_from_thread(self._render_models_panel)
                if self._app_ref is not None:
                    self.call_from_thread(self._app_ref._tick_telemetry)  # type: ignore[attr-defined]
        finally:
            self.call_from_thread(self._set_busy, False)

    def _worker_verify(self) -> None:
        bundle_id = self._require_bundle()
        if not bundle_id:
            return
        self.call_from_thread(self._set_busy, True)
        try:
            from .tui_setup_actions import verify_bundle_setup

            def emit(line: str) -> None:
                self.call_from_thread(self._set_status, line)
                self.call_from_thread(self._emit_app_log, line)

            verify_bundle_setup(bundle_id, on_status=emit)
        finally:
            self.call_from_thread(self._set_busy, False)

    def _worker_all(self) -> None:
        bundle_id = self._require_bundle()
        if not bundle_id:
            return
        self.call_from_thread(self._set_busy, True)
        try:
            from .tui_setup_actions import setup_bundle_end_to_end

            def emit(line: str) -> None:
                self.call_from_thread(self._set_status, line)
                self.call_from_thread(self._emit_app_log, line)

            yes = self._confirm_large is not None
            ok = setup_bundle_end_to_end(
                bundle_id,
                yes=yes,
                confirm_large=self._confirm_large_download if not yes else None,
                on_status=emit,
            )
            if ok:
                self._confirm_large = None
                self.call_from_thread(self._render_models_panel)
                if self._app_ref is not None:
                    self.call_from_thread(self._app_ref._tick_telemetry)  # type: ignore[attr-defined]
                self.call_from_thread(self._set_status, "[ok]Setup complete — ready to code.[/]")
        finally:
            self.call_from_thread(self._set_busy, False)

    def action_close(self) -> None:
        self.dismiss({"bundle_id": self._selected_id})


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
    "InteractiveSetupScreen",
    "BundleListItem",
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
