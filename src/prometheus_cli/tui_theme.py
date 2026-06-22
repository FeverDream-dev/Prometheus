"""Visual identity for the PROMETHEUS TUI.

Ancient myth + serious developer tool + local AI workstation. Obsidian/near-black
canvas, warm gold accent, muted bronze/sandstone borders. No clown colors, no
generic purple gradient, no massive empty bordered areas, no low-contrast text.

This module is the single source of truth for the color palette and the Textual
CSS string used by :class:`prometheus_cli.tui.PrometheusApp`. Screens and widgets
import the palette tuples for inline styling; the App loads :data:`APP_CSS` as its
``CSS`` classvar.
"""
from __future__ import annotations

# ---- Palette (hex strings, no leading '#' for Textual CSS variables) ----
# Obsidian / near-black canvas
BG_OBSIDIAN = "#0b0c10"
BG_PANEL = "#13151c"
BG_PANEL_RAISED = "#181b24"
BG_INPUT = "#0e1016"

# Warm gold accent (primary action / highlights)
ACCENT_GOLD = "#d4a02a"
ACCENT_GOLD_BRIGHT = "#f0c050"
ACCENT_GOLD_DIM = "#8a6a1a"

# Bronze / sandstone borders
BORDER_BRONZE = "#5b4a2a"
BORDER_SANDSTONE = "#3a3530"
BORDER_DIM = "#23252d"

# Text
TEXT_PRIMARY = "#e6e2d8"      # warm white
TEXT_SECONDARY = "#a59c8a"    # sandstone
TEXT_MUTED = "#6b6557"        # muted bronze
TEXT_DEMO = "#d4a02a"

# Status (calm, not clown)
STATUS_OK = "#7a9a4a"          # muted olive
STATUS_WARN = "#c08a3a"       # amber
STATUS_ERROR = "#a04a4a"      # muted brick
STATUS_INFO = "#5a8aa0"       # steel blue

# Semantic
HEADER_TITLES = ACCENT_GOLD_BRIGHT
SECTION_TITLES = ACCENT_GOLD


# ---- TuiSnapshot badge helpers (return a (label, color) pair) ----

def status_color(ok: bool | None) -> str:
    if ok is None:
        return TEXT_MUTED
    return STATUS_OK if ok else STATUS_WARN


# ---- Sidebar sections (the persistent command rail) ----
# Maps to slash commands. Rendered as a vertical rail of labeled entries.

SIDEBAR_SECTIONS: list[tuple[str, str, str]] = [
    # (label, slash_command, blurb)
    ("Chat",      "",         "ask PROMETHEUS anything"),
    ("Plan",      "/plan",    "objective + acceptance criteria"),
    ("Files",     "",         "recent workspace changes"),
    ("Models",    "/models",  "installed Ollama models"),
    ("Bundles",   "/bundles", "model packages"),
    ("Tools",     "/tools",   "built-in agent tools"),
    ("MCP",       "/mcp",     "MCP servers"),
    ("Sandbox",   "/sandbox", "enforcement tier + policy"),
    ("Memory",    "/memory",  "bounded project memory"),
    ("Vision",    "/vision",  "CSS / a11y inspector"),
    ("Assets",    "/assets",  "AssetForge image generation"),
    ("Astronaut", "/astronaut", "long-run autonomous mode"),
    ("Settings",  "/settings", "config + provider"),
]


# ---- Command palette metadata ----
# Each entry: (name, description, shortcut, availability, source)
# source: "local" | "cloud" | "external"

COMMAND_PALETTE: list[tuple[str, str, str, str, str]] = [
    # (command, description, shortcut, availability, source)
    ("/help",      "Command palette + grouped help",          "Ctrl+P",  "always",   "local"),
    ("/setup",     "First-run setup wizard",                   "",        "always",   "local"),
    ("/settings",  "Show all editable settings",               "",        "always",   "local"),
    ("/models",    "Installed Ollama models",                  "",        "ollama",   "local"),
    ("/bundles",   "Browse model packages",                    "",        "always",   "local"),
    ("/use",       "Select active package (/use <id>)",        "",        "always",   "local"),
    ("/sandbox",   "Sandbox tier + policy status",             "",        "always",   "local"),
    ("/mcp",       "MCP server status",                        "",        "always",   "external"),
    ("/memory",    "Bounded project memory",                   "",        "always",   "local"),
    ("/tools",     "List built-in tools",                      "",        "always",   "local"),
    ("/vision",    "CSS / a11y vision inspector",              "",        "browser",  "external"),
    ("/assets",    "AssetForge local image generation",        "",        "torch",    "external"),
    ("/astronaut", "Astronaut sentinel status",                "",        "always",   "local"),
    ("/doctor",    "Hardware + Ollama service report",         "",        "always",   "local"),
    ("/plan",      "Plan an objective",                        "",        "always",   "local"),
    ("/build",     "Run an objective through the orchestrator", "Enter",   "bundle",   "local"),
    ("/mode",      "Switch autonomy mode",                     "",        "always",   "local"),
    ("/clear",     "Clear the transcript",                     "",        "always",   "local"),
    ("/exit",      "Exit PROMETHEUS",                          "Ctrl+Q",  "always",   "local"),
]


# ---- App CSS — the single stylesheet for the whole shell ----

APP_CSS = f"""
Screen {{
    background: {BG_OBSIDIAN};
    color: {TEXT_PRIMARY};
    layout: vertical;
}}

/* ---- Top brand header ---- */
#brand-header {{
    dock: top;
    height: 3;
    background: {BG_PANEL};
    border-bottom: solid {BORDER_BRONZE};
    padding: 0 1;
    layout: horizontal;
}}
#brand-mark {{
    width: auto;
    color: {ACCENT_GOLD_BRIGHT};
    padding: 1 1 0 1;
}}
#brand-title {{
    width: auto;
    color: {ACCENT_GOLD_BRIGHT};
    padding: 1 2 0 0;
}}
#brand-subtitle {{
    color: {TEXT_SECONDARY};
    padding: 1 2 0 0;
}}
#brand-spacer {{ width: 1fr; }}
#brand-mode, #brand-provider, #brand-bundle {{
    width: auto;
    color: {TEXT_SECONDARY};
    padding: 1 1 0 1;
}}
#brand-mode .badge-value, #brand-provider .badge-value, #brand-bundle .badge-value {{
    color: {ACCENT_GOLD_BRIGHT};
}}

/* Demo-mode ribbon */
#demo-ribbon {{
    dock: top;
    height: 1;
    background: {ACCENT_GOLD_DIM};
    color: {BG_OBSIDIAN};
    text-align: center;
}}

/* ---- Workspace: 3-column horizontal ---- */
#workspace {{
    height: 1fr;
    layout: horizontal;
}}

/* Left sidebar / command rail */
#sidebar {{
    width: 26;
    min-width: 22;
    background: {BG_PANEL};
    border-right: solid {BORDER_SANDSTONE};
    padding: 0;
    overflow: auto auto;
}}
.sidebar-section {{
    color: {TEXT_MUTED};
    padding: 0 1;
    height: 1;
}}
.sidebar-entry {{
    color: {TEXT_PRIMARY};
    padding: 0 1;
    height: 1;
}}
.sidebar-entry .cmd {{
    color: {ACCENT_GOLD};
}}
.sidebar-entry .desc {{
    color: {TEXT_MUTED};
}}

/* Main work area */
#main {{
    width: 1fr;
    layout: vertical;
    overflow: auto auto;
    padding: 0 1;
}}
#dashboard-view {{
    height: 1fr;
    overflow: auto auto;
}}
#command-view {{
    height: 1fr;
    overflow: auto auto;
    display: none;
}}
.section-title {{
    color: {SECTION_TITLES};
    background: {BG_PANEL_RAISED};
    padding: 0 1;
    height: 1;
    border-top: solid {BORDER_BRONZE};
    border-bottom: solid {BORDER_DIM};
}}
.section-body {{
    color: {TEXT_PRIMARY};
    padding: 0 1;
}}
.kv-line {{ color: {TEXT_PRIMARY}; }}
.kv-line .k {{ color: {TEXT_SECONDARY}; }}
.kv-line .v {{ color: {TEXT_PRIMARY}; }}
.hint {{ color: {TEXT_MUTED}; }}
.next-action {{
    color: {ACCENT_GOLD_BRIGHT};
    background: {BG_PANEL_RAISED};
    padding: 0 1;
    height: 1;
    border-top: solid {BORDER_BRONZE};
}}

/* Right inspector */
#inspector {{
    width: 34;
    min-width: 28;
    background: {BG_PANEL};
    border-left: solid {BORDER_SANDSTONE};
    padding: 0;
    overflow: auto auto;
}}
.inspector-title {{
    color: {SECTION_TITLES};
    background: {BG_PANEL_RAISED};
    padding: 0 1;
    height: 1;
    border-bottom: solid {BORDER_DIM};
}}
.inspector-row {{
    color: {TEXT_PRIMARY};
    padding: 0 1;
    height: 1;
}}
.inspector-row .k {{ color: {TEXT_SECONDARY}; }}
.inspector-row .v {{ color: {TEXT_PRIMARY}; }}

/* Conversation log — constructed with markup=True in Python so [bold]...[/] renders */
#transcript {{
    height: 1fr;
    border: solid {BORDER_DIM};
    background: {BG_OBSIDIAN};
    padding: 0 1;
}}

/* Approval strip */
#approval {{
    height: auto;
    max-height: 5;
    background: {BG_PANEL_RAISED};
    border: solid {STATUS_WARN};
    padding: 0 1;
    display: none;
}}

/* Bottom command input */
#cmd-input {{
    dock: bottom;
    height: 3;
    background: {BG_INPUT};
    border: solid {BORDER_BRONZE};
    padding: 0 1;
}}
#cmd-input:focus {{
    border: solid {ACCENT_GOLD};
}}

/* Status bar — single line, dense */
#status-bar {{
    dock: bottom;
    height: 1;
    background: {BG_PANEL_RAISED};
    color: {TEXT_SECONDARY};
    padding: 0 1;
}}
#status-bar .seg-k {{ color: {TEXT_MUTED}; }}
#status-bar .seg-v {{ color: {TEXT_PRIMARY}; }}
#status-bar .seg-sep {{ color: {BORDER_BRONZE}; }}

/* Built-in Header/Footer — keep them quiet so our brand header dominates */
Header {{
    display: none;
}}
Footer {{
    background: {BG_PANEL};
    color: {TEXT_SECONDARY};
    border-top: solid {BORDER_SANDSTONE};
}}

/* ---- Command screens (pushed via /help, /models, etc.) ---- */
.command-screen {{
    background: {BG_OBSIDIAN};
    padding: 0 1;
    layout: vertical;
    overflow: auto auto;
}}
.command-screen .title {{
    color: {ACCENT_GOLD_BRIGHT};
    background: {BG_PANEL_RAISED};
    padding: 0 1;
    height: 1;
    border-bottom: solid {BORDER_BRONZE};
}}
.command-screen .subtitle {{
    color: {TEXT_SECONDARY};
    padding: 0 1;
    height: 1;
}}
.command-screen .card {{
    background: {BG_PANEL};
    border: solid {BORDER_SANDSTONE};
    padding: 0 1;
    margin: 0 0 0 0;
}}
.command-screen .card-title {{
    color: {ACCENT_GOLD};
    height: 1;
}}
.command-screen .card-row {{
    color: {TEXT_PRIMARY};
    height: 1;
}}
.command-screen .card-row .k {{ color: {TEXT_SECONDARY}; }}
.command-screen .card-row .v {{ color: {TEXT_PRIMARY}; }}
.command-screen .ok    {{ color: {STATUS_OK}; }}
.command-screen .warn  {{ color: {STATUS_WARN}; }}
.command-screen .err   {{ color: {STATUS_ERROR}; }}
.command-screen .info  {{ color: {STATUS_INFO}; }}
.command-screen .dim   {{ color: {TEXT_MUTED}; }}
.command-screen .gold  {{ color: {ACCENT_GOLD_BRIGHT}; }}

/* ---- Setup wizard (modal) ---- */
/* ModalScreen provides its own dimmed background; we only style its children. */
#wizard-card {{
    width: 80;
    max-width: 100;
    height: auto;
    max-height: 80;
    background: {BG_PANEL};
    border: solid {BORDER_BRONZE};
    padding: 1 2;
}}
#wizard-title {{ color: {ACCENT_GOLD_BRIGHT}; text-align: center; }}
#wizard-step  {{ color: {TEXT_SECONDARY}; text-align: center; }}
#wizard-body  {{ color: {TEXT_PRIMARY}; }}
#wizard-buttons {{
    height: 3;
    layout: horizontal;
    padding: 1 0 0 0;
}}
#wizard-buttons Button {{ margin: 0 1; }}

/* ---- Command palette (modal) ---- */
/* ModalScreen provides its own dimmed background; we only style its children. */
#palette-card {{
    width: 90;
    max-width: 100;
    height: auto;
    max-height: 70;
    background: {BG_PANEL};
    border: solid {BORDER_BRONZE};
    padding: 0;
    margin: 2 0 0 0;
}}
#palette-input {{
    border: solid {BORDER_BRONZE};
    background: {BG_INPUT};
    padding: 0 1;
}}
#palette-list {{
    border-top: solid {BORDER_DIM};
    background: {BG_OBSIDIAN};
}}
.palette-row {{
    height: 2;
    padding: 0 1;
    color: {TEXT_PRIMARY};
}}
"""


def truncate_for_width(text: str, width: int) -> str:
    """Truncate a single-line string to a visual cell width, adding an ellipsis."""
    if len(text) <= width:
        return text
    if width <= 1:
        return "…"
    return text[: width - 1] + "…"


__all__ = [
    "APP_CSS",
    "ACCENT_GOLD",
    "ACCENT_GOLD_BRIGHT",
    "ACCENT_GOLD_DIM",
    "BG_INPUT",
    "BG_OBSIDIAN",
    "BG_PANEL",
    "BG_PANEL_RAISED",
    "BORDER_BRONZE",
    "BORDER_DIM",
    "BORDER_SANDSTONE",
    "COMMAND_PALETTE",
    "SIDEBAR_SECTIONS",
    "STATUS_ERROR",
    "STATUS_INFO",
    "STATUS_OK",
    "STATUS_WARN",
    "TEXT_DEMO",
    "TEXT_MUTED",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "HEADER_TITLES",
    "SECTION_TITLES",
    "status_color",
    "truncate_for_width",
]
