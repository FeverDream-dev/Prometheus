from __future__ import annotations


SLASH_COMMANDS = {
    "/settings": "show all editable settings and their current values",
    "/bundles": "show model packages and active config",
    "/models": "show installed Ollama models",
    "/providers": "show configured providers",
    "/mcp": "show MCP server status",
    "/tools": "list built-in tools",
    "/permissions": "show autonomy mode and policy",
    "/doctor": "hardware + Ollama service report",
    "/sessions": "list recent coding sessions",
    "/resume": "resume a session (/resume <id>)",
    "/mode": "switch autonomy mode (/mode copilot|pilot|astronaut)",
    "/qualify": "qualify the first installed model or a bundle (/qualify <id>)",
    "/use": "select the active package (/use <id>, e.g. /use spark-cpu-8gb)",
    "/memory": "bounded project memory status (/memory inspect|why|rebuild|export|reset)",
    "/modes": "autonomy modes",
    "/vision": "vision element inspection (/vision inspect <selector>)",
    "/assets": "AssetForge local image generation (/assets generate <kind>)",
    "/astronaut": "astronaut sentinel status (/astronaut start|pause|stop|report)",
    "/clear": "clear the log",
    "/exit": "exit the TUI",
    "/help": "show this help",
}


def help_lines() -> list[str]:
    out = ["[bold]Slash commands:[/bold]"]
    for cmd, desc in SLASH_COMMANDS.items():
        out.append(f"  {cmd:<12} {desc}")
    return out


def doctor_lines(report, ollama) -> list[str]:
    ollama_state = "running" if ollama.running else "installed, service NOT running"
    return [
        f"OS: {report.os} {report.architecture} | RAM: {report.ram_gb:.0f} GB | "
        f"VRAM: {report.vram_gb:.0f} GB | disk: {report.disk_free_gb:.0f} GB",
        f"Ollama: {ollama_state} ({len(ollama.models)} models)",
    ]


def models_lines(ollama) -> list[str]:
    out = [f"[bold]Installed Ollama models ({len(ollama.models)}):[/bold]"]
    for m in ollama.models:
        out.append(f"  • {m}")
    return out


def modes_lines() -> list[str]:
    from .policy import mode_description
    from .models import AutonomyMode

    return [f"[bold]{mode.value}[/bold]: {mode_description(mode)}" for mode in AutonomyMode]


def sessions_lines(limit: int = 10) -> list[str]:
    from .config import ensure_home
    from .session import SessionStore

    home = ensure_home()
    store = SessionStore(home / "sessions" / "prometheus.db")
    try:
        rows = store.list_sessions(limit=limit)
    finally:
        store.close()
    if not rows:
        return ["[dim]No sessions yet. Run an objective to create one.[/dim]"]
    out = [f"[bold]Recent sessions ({len(rows)}):[/bold]"]
    for s in rows:
        out.append(f"  {s.id[:12]}  {s.completion_percent:>5.1f}%  {s.status:<10}  {s.objective[:50]}")
    return out


def permissions_lines(settings) -> list[str]:
    from .policy import mode_description

    out = [
        f"[bold]Autonomy mode:[/bold] {settings.mode.value} — {mode_description(settings.mode)}",
        f"Sandbox: {settings.effective_sandbox_tier().value}",
        f"Network: {'allowed' if settings.allow_network else 'denied'}",
        f"Package install: {'allowed' if settings.allow_package_install else 'requires approval'}",
        f"Multi-model review: {'on' if settings.multi_agent_review else 'off'}",
        f"Local-only (no cloud fallback): {'on' if settings.local_only else 'off'}",
        f"Step limit: {'unlimited' if settings.step_limit() is None else settings.step_limit()}",
        f"Runtime limit: {'unlimited' if settings.runtime_limit_minutes() is None else str(settings.runtime_limit_minutes()) + ' min'}",
    ]
    return out


def tools_lines() -> list[str]:
    return [
        "[bold]Built-in tools:[/bold]",
        "  Repository  list_files, read_file (bounded), write_file (atomic), apply_patch, diff, search",
        "  Process     run_command (argv array), supervised, streaming, timeouts, exit codes",
        "  Git         status, diff, log, checkpoint, rollback, branch",
        "  Browser     navigate, click, fill, text, screenshot, evidence (Playwright)",
        "  Web         fetch (bounded, domain-permitted, untrusted, cited)",
        "  MCP         per-server namespaced tools (untrusted output)",
    ]


def mcp_lines() -> list[str]:
    return [
        "[bold]MCP servers:[/bold]",
        "[dim]None configured globally. MCP servers are added per-project and run out-of-process.[/dim]",
        "[dim]Output is delimited as untrusted data; prompt injection cannot alter system policy.[/dim]",
        "[dim]Use 'prometheus' with a project .prometheus.yaml to register stdio/HTTP MCP servers.[/dim]",
    ]


def providers_lines(settings) -> list[str]:
    out = ["[bold]Providers:[/bold]", "  ollama (default, local, quota-free) — http://127.0.0.1:11434"]
    if not settings.local_only:
        out.append("  openai-compatible (cloud, metered) — configured per-bundle")
        out.append("  [dim]Cloud use requires explicit configuration and is provider-metered.[/dim]")
    else:
        out.append("  [dim]Cloud providers disabled (local_only mode).[/dim]")
    return out


_STATUS_TAG = {
    "recommended": "[green]recommended[/green]",
    "installed": "[bold green]installed[/bold]",
    "available": "available",
    "experimental": "[yellow]experimental[/yellow]",
    "incompatible": "[red]incompatible[/red]",
}


def settings_lines(settings, classified: list, installed_models: list[str] | None = None) -> list[str]:
    active = settings.active_bundle_id or "(none — run /qualify or prometheus setup)"
    quota = "unlimited" if settings.unlimited_local_sessions else "metered"
    cloud_key_status = "configured" if not settings.local_only else "disabled (local-only)"
    out = [
        "[bold]Settings[/bold] — stored in ~/.prometheus/config.yaml",
        f"  autonomy mode: {settings.mode.value} (/mode to switch)",
        f"  default/active bundle: {active}",
        f"  provider: ollama (default) · cloud: {cloud_key_status}",
        "  Ollama URL: http://127.0.0.1:11434",
        f"  install packages automatically: {'on' if settings.allow_package_install else 'off'}",
        f"  sandbox: {settings.effective_sandbox_tier().value}",
        f"  browser testing: {'enabled' if not settings.local_only else 'off (local-only)'}",
        f"  multi-agent review: {'on' if settings.multi_agent_review else 'off'}",
        f"  audio markers: {'on' if settings.sounds else 'off'}",
        f"  telemetry: {'on' if settings.telemetry else 'off (default)'}",
        f"  max steps: {'unlimited' if settings.step_limit() is None else settings.step_limit()}",
        f"  max runtime: {'unlimited' if settings.runtime_limit_minutes() is None else str(settings.runtime_limit_minutes()) + ' min'}",
        f"  local sessions: {quota}",
        f"  local-only (no cloud fallback): {'on' if settings.local_only else 'off'}",
    ]
    out.append(f"[bold]Model Packages[/bold] — active: {active} · local sessions {quota}")
    for c in classified:
        tag = _STATUS_TAG.get(c.status, c.status)
        add_on = " (add-on)" if c.bundle.is_add_on else ""
        out.append(f"  {c.bundle.name}{add_on} — {tag} (~{c.bundle.total_download_gb():.1f} GB)")
        ctrl = c.bundle.roles.get("controller")
        if ctrl:
            present = " [pulled]" if ctrl.model in (installed_models or []) else ""
            out.append(f"      controller: {ctrl.model}{present}")
        if c.reasons:
            out.append(f"      [dim]{c.reasons[0]}[/dim]")
    return out


def mode_switch_lines(settings, arg: str) -> list[str]:
    from .models import AutonomyMode

    arg = (arg or "").strip().lower()
    valid = {m.value for m in AutonomyMode}
    if arg not in valid:
        return [f"[red]Unknown mode '{arg}'.[/red] Use one of: {', '.join(sorted(valid))}"]
    settings.mode = AutonomyMode(arg)
    from .config import save_settings

    save_settings(settings)
    return [f"[green]Autonomy mode set to {settings.mode.value}.[/green] Saved to ~/.prometheus/config.yaml"]


def resume_lines(session_id: str) -> list[str]:
    sid = (session_id or "").strip()
    if not sid:
        return ["[red]/resume needs a session id.[/red] Run /sessions to list them."]
    from .config import ensure_home
    from .session import SessionStore

    home = ensure_home()
    store = SessionStore(home / "sessions" / "prometheus.db")
    try:
        session = store.get_session(sid)
        if session is None:
            return [f"[red]Session {sid} not found.[/red]"]
        pct = store.completion_percent(sid)
        return [
            f"[bold]Session {sid}[/bold]",
            f"  objective: {session['objective'][:80]}",
            f"  status: {session['status']} · completion: {pct:.1f}%",
            f"  mode: {session['mode']}",
            f"[dim]Run in a terminal: prometheus resume {sid}[/dim]",
        ]
    finally:
        store.close()


__all__ = [
    "SLASH_COMMANDS",
    "doctor_lines",
    "help_lines",
    "mode_switch_lines",
    "modes_lines",
    "models_lines",
    "resume_lines",
    "settings_lines",
]
