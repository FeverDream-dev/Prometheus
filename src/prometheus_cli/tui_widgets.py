"""Composite widgets for the PROMETHEUS TUI.

All widgets read from :class:`prometheus_cli.tui_state.TuiSnapshot` and render
via ``Static`` (markup ON by default) so Rich markup like ``[gold]…[/]`` renders
correctly rather than leaking through as raw brackets.

Widgets expose ``update_snapshot(snap)`` so :class:`prometheus_cli.tui.PrometheusApp`
can refresh them after telemetry ticks or command dispatch.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from .tui_state import TuiSnapshot
from .tui_theme import (
    SIDEBAR_SECTIONS,
    STATUS_OK,
    STATUS_WARN,
    truncate_for_width,
)


# ---------------------------------------------------------------------------
# Top brand header
# ---------------------------------------------------------------------------

class BrandHeader(Static):
    """Three-line top header: logo · project · breadcrumb · mode/provider/bundle."""

    _breadcrumb: str = ""
    _last_snap: TuiSnapshot | None = None

    def set_breadcrumb(self, text: str) -> None:
        self._breadcrumb = text
        if self._last_snap is not None:
            self.update_snapshot(self._last_snap)

    def clear_breadcrumb(self) -> None:
        self.set_breadcrumb("")

    def update_snapshot(self, snap: TuiSnapshot) -> None:
        self._last_snap = snap
        mark = "\U0001f525"
        title = f"{mark} PROMETHEUS"
        subtitle = "local-first coding agent"
        project = truncate_for_width(snap.project_path or "(no project)", 48)
        crumb = f"  [bronze]\u203a[/]  [gold]{self._breadcrumb}[/]" if self._breadcrumb else ""
        self.update(
            f"[gold]{title}[/]  [dim]{subtitle}[/]"
            f"  [bronze]\u00b7[/]  [k]project[/] [v]{project}[/]"
            f"{crumb}"
        )
        # Right-side badges — set via separate widgets in compose(); keep main line simple.


class BrandBadges(Static):
    """Right-aligned mode/provider/bundle badges that sit in the header row."""

    def update_snapshot(self, snap: TuiSnapshot) -> None:
        demo = " [demo]DEMO[/]" if snap.is_demo else ""
        self.update(
            f"{demo}"
            f"  [k]mode[/] [v]{snap.mode_label}[/]"
            f"  [k]provider[/] [v]{snap.provider}[/]"
            f"  [k]bundle[/] [v]{snap.bundle_label}[/]"
        )


class SidebarEntry(Static):
    """A clickable sidebar entry. Clicking dispatches its slash command."""

    DEFAULT_CSS = """
    SidebarEntry {
        height: 1;
        padding: 0 1;
        color: $text;
    }
    SidebarEntry:hover {
        background: $boost;
    }
    SidebarEntry.active {
        background: #181b24;
        color: #f0c050;
    }
    """

    def __init__(self, label: str, cmd: str, desc: str = "") -> None:
        super().__init__(markup=True)
        self.sidebar_label = label
        self.sidebar_cmd = cmd
        self.sidebar_desc = desc
        self._render_entry()

    def _render_entry(self) -> None:
        cmd_part = f"[cmd]{self.sidebar_cmd}[/]" if self.sidebar_cmd else "[dim]—[/]"
        self.update(f"[v]{self.sidebar_label:<10}[/] {cmd_part}")

    async def on_click(self, event) -> None:
        if self.sidebar_cmd:
            try:
                self.app._dispatch_slash_text(self.sidebar_cmd)  # type: ignore[attr-defined]
            except Exception:
                pass


class CommandRail(VerticalScroll):
    """Left sidebar rail. Yields one :class:`SidebarEntry` per section plus
    static header/footer hints. Entries are clickable."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield Static("[section]COMMANDS[/]", markup=True, classes="sidebar-section")
        for label, cmd, desc in SIDEBAR_SECTIONS:
            yield SidebarEntry(label=label, cmd=cmd, desc=desc)
        yield Static("", markup=True, classes="sidebar-section")
        yield Static("[dim]Ctrl+P palette[/]", markup=True, classes="sidebar-section")
        yield Static("[dim]/help  /setup  /exit[/]", markup=True, classes="sidebar-section")

    def update_snapshot(self, snap: TuiSnapshot) -> None:
        pass


# ---------------------------------------------------------------------------
# Right inspector panel
# ---------------------------------------------------------------------------

class InspectorPanel(Static):
    """Right-hand contextual panel. Shows a system digest by default;
    individual command screens can override via :meth:`set_context`."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._context_lines: list[str] | None = None

    def set_context(self, lines: list[str] | None) -> None:
        self._context_lines = lines
        if self._snapshot is not None:
            self.update_snapshot(self._snapshot)

    _snapshot: TuiSnapshot | None = None

    def render_default(self, snap: TuiSnapshot) -> str:
        lines = ["[section]INSPECTOR[/]", ""]
        lines.append("[section]System[/]")
        lines.append(f"  [k]OS[/]      [v]{snap.os} {snap.arch}[/]")
        lines.append(f"  [k]CPU[/]     [v]{truncate_for_width(snap.cpu_brand or '—', 26)}[/]")
        lines.append(f"  [k]RAM[/]     [v]{snap.ram_gb:.0f} GB[/]")
        gpu = snap.gpu_name or "CPU mode"
        lines.append(f"  [k]GPU[/]     [v]{truncate_for_width(gpu, 26)}[/]")
        if snap.vram_gb:
            lines.append(f"  [k]VRAM[/]    [v]{snap.vram_gb:.0f} GB[/]")
        lines.append(f"  [k]Disk[/]    [v]{snap.disk_free_gb:.0f} GB free[/]")

        lines.append("")
        lines.append("[section]Backend[/]")
        ollama_color = STATUS_OK if snap.ollama_running else STATUS_WARN
        lines.append(f"  [k]Ollama[/]  [{ollama_color}]{snap.ollama_label}[/]")
        for m in snap.ollama_models[:5]:
            lines.append(f"    [dim]• {m}[/]")
        if len(snap.ollama_models) > 5:
            lines.append(f"    [dim]… +{len(snap.ollama_models) - 5} more[/]")

        lines.append("")
        lines.append("[section]Policy[/]")
        lines.append(f"  [k]Mode[/]      [v]{snap.mode_label}[/]")
        lines.append(f"  [k]Sandbox[/]   [v]{snap.sandbox_tier}[/]")
        lines.append(f"  [k]Local-only[/] [v]{'on' if snap.local_only else 'off'}[/]")

        lines.append("")
        lines.append("[section]Memory[/]")
        lines.append(f"  [k]Status[/]  [v]{snap.memory.status_label}[/]")

        lines.append("")
        lines.append("[section]Git[/]")
        if snap.git.available:
            lines.append(f"  [k]Branch[/]  [v]{snap.git.branch}[/]")
            dirty_color = STATUS_WARN if snap.git.dirty else STATUS_OK
            lines.append(f"  [k]State[/]   [{dirty_color}]{snap.git.status_label}[/]")
            for c in snap.git.recent_commits[:3]:
                lines.append(f"    [dim]{truncate_for_width(c, 28)}[/]")
        else:
            lines.append("  [dim]no git repo[/]")

        return "\n".join(lines)

    def update_snapshot(self, snap: TuiSnapshot) -> None:
        self._snapshot = snap
        if self._context_lines is not None:
            self.update("\n".join(self._context_lines))
        else:
            self.update(self.render_default(snap))


# ---------------------------------------------------------------------------
# Bottom status bar — one dense line
# ---------------------------------------------------------------------------

class StatusBar(Static):
    """Single-line dense status bar: provider|bundle|mode|sandbox|git|memory."""

    def render_default(self, snap: TuiSnapshot) -> str:
        parts: list[str] = []
        for label, value in snap.status_bar_segments:
            parts.append(f"[seg-k]{label}[/] [seg-v]{value}[/]")
        sep = "  [seg-sep]·[/]  "
        line = sep.join(parts)
        prefix = "[demo]DEMO[/] " if snap.is_demo else ""
        return f"{prefix}{line}"

    def update_snapshot(self, snap: TuiSnapshot) -> None:
        self.update(self.render_default(snap))


# ---------------------------------------------------------------------------
# Demo ribbon
# ---------------------------------------------------------------------------

class DemoRibbon(Static):
    """One-line gold ribbon shown only in demo mode."""

    def update_snapshot(self, snap: TuiSnapshot) -> None:
        if snap.is_demo:
            self.update(
                "DEMO MODE — mocked data for preview/testing only. "
                "Use `prometheus tui` (without --demo) for real state."
            )
            self.styles.display = "block"
        else:
            self.styles.display = "none"


# ---------------------------------------------------------------------------
# Reusable section header for the main column
# ---------------------------------------------------------------------------

class SectionTitle(Static):
    """Bronze-bordered section title strip used inside the main column."""


class NextAction(Static):
    """The 'next recommended action' line pinned to the bottom of main column."""


__all__ = [
    "BrandBadges",
    "BrandHeader",
    "CommandRail",
    "DemoRibbon",
    "InspectorPanel",
    "NextAction",
    "SectionTitle",
    "StatusBar",
]
