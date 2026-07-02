from __future__ import annotations


SLASH_COMMANDS = {
    "/help": "show grouped command help",
    "/setup": "first-run setup wizard (hardware, bundle, configure)",
    "/setup-wizard": "interactive setup — pick bundle, download models, verify",
    "/settings": "show all editable settings and their current values",
    "/bundles": "show model packages and active config",
    "/models": "show installed Ollama models",
    "/provider": "show configured providers",
    "/use": "select the active package (/use <id>, e.g. /use spark-cpu-8gb)",
    "/mode": "switch autonomy mode (/mode copilot|pilot|astronaut)",
    "/modes": "autonomy modes",
    "/memory": "bounded project memory (/memory inspect|why|rebuild|export|reset)",
    "/mcp": "show MCP server status",
    "/tools": "list built-in tools",
    "/permissions": "show autonomy mode and policy",
    "/sandbox": "sandbox enforcement tier and policy status",
    "/vision": "vision element inspection (/vision inspect <selector>)",
    "/assets": "AssetForge local image generation (/assets generate <kind>)",
    "/astronaut": "astronaut sentinel status (/astronaut start|pause|stop|report)",
    "/telemetry": "live CPU/RAM/GPU/disk/Ollama snapshot",
    "/logo": "show the PROMETHEUS brand mark",
    "/diagnose": "collect sanitized diagnostics (versions, errors, git, ollama)",
    "/doctor": "hardware + Ollama service report",
    "/sessions": "list recent coding sessions",
    "/resume": "resume a session (/resume <id>)",
    "/qualify": "qualify the first installed model or a bundle (/qualify <id>)",
    "/clear": "clear the log",
    "/exit": "exit the TUI",
}


_COMMAND_GROUPS: list[tuple[str, list[str]]] = [
    ("Setup", ["/setup", "/setup-wizard", "/use", "/bundles", "/provider", "/models", "/doctor"]),
    ("Models & Coding", ["/mode", "/modes", "/qualify", "/sessions", "/resume", "/memory"]),
    ("Safety", ["/sandbox", "/permissions", "/tools", "/mcp"]),
    ("Browser & Vision", ["/vision", "/astronaut", "/assets"]),
    ("System", ["/telemetry", "/logo", "/diagnose", "/settings", "/help", "/clear", "/exit"]),
]


def help_lines() -> list[str]:
    out = ["[bold cyan]PROMETHEUS command palette[/bold cyan]", ""]
    catalog = dict(SLASH_COMMANDS)
    for group_name, cmds in _COMMAND_GROUPS:
        out.append(f"[bold]{group_name}[/bold]")
        for cmd in cmds:
            desc = catalog.get(cmd, "")
            out.append(f"  {cmd:<13} {desc}")
        out.append("")
    return out


def suggest_command(typed: str) -> str | None:
    """Return the closest matching slash command for a typo, or None."""
    import difflib

    if not typed:
        return None
    typed_low = typed.lower()
    if typed_low in SLASH_COMMANDS:
        return typed_low
    cmds = list(SLASH_COMMANDS.keys())
    matches = difflib.get_close_matches(typed_low, cmds, n=1, cutoff=0.6)
    return matches[0] if matches else None


def unknown_command_lines(typed: str) -> list[str]:
    suggestion = suggest_command(typed)
    if suggestion:
        return [
            f"[yellow]Unknown command:[/yellow] {typed}",
            f"Did you mean [bold]{suggestion}[/bold]?",
            "Type [bold]/help[/bold] to see all commands.",
        ]
    return [
        f"[yellow]Unknown command:[/yellow] {typed}",
        "Type [bold]/help[/bold] to see all commands.",
    ]


def doctor_lines(report, ollama) -> list[str]:
    ollama_state = "running" if ollama.running else "installed, service NOT running"
    out = [
        f"OS: {report.os} {report.architecture} | RAM: {report.ram_gb:.0f} GB | "
        f"VRAM: {report.vram_gb:.0f} GB | disk: {report.disk_free_gb:.0f} GB",
        f"Ollama: {ollama_state} ({len(ollama.models)} models)",
    ]
    if getattr(ollama, "duplicate_servers", False):
        count = getattr(ollama, "serve_process_count", 0)
        out.append(
            f"[yellow]Warning: {count} ollama serve processes detected. "
            "Stop duplicates (pkill -f 'ollama serve'; ollama serve) — "
            "empty model lists and hangs are common.[/yellow]"
        )
    elif ollama.installed and not ollama.running:
        out.append("[yellow]Start Ollama: ollama serve[/yellow]")
    return out


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
    "installed": "[bold green]installed[/bold green]",
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


def sandbox_lines() -> list[str]:
    from .sandbox import docker_available, tier_available

    out = ["[bold]Sandbox enforcement tiers:[/bold]"]
    for tier in ("off", "basic", "docker", "native"):
        ok, reason = tier_available(tier)
        mark = "[green]available[/green]" if ok else "[red]unavailable[/red]"
        out.append(f"  {tier:<7} {mark} — {reason}")
    out.append(f"  docker binary: {'present' if docker_available() else 'absent'}")
    out.append("[dim]CLI: prometheus sandbox test --workspace <dir> --all[/dim]")
    return out


def vision_lines() -> list[str]:
    from .vision import vision_doctor

    info = vision_doctor()
    pw = info["playwright_available"]
    out = ["[bold]Vision inspector:[/bold]"]
    out.append(f"  Playwright: {'available' if pw else '[red]not installed[/red]'}")
    driver = info.get("driver") or {}
    if driver.get("browsers"):
        out.append(f"  Browsers: {', '.join(driver['browsers'])}")
    if driver.get("error"):
        out.append(f"  [yellow]{driver['error']}[/yellow]")
    out.append(f"  Fixture UI: {'available' if info['fixture_available'] else '[yellow]not found[/yellow]'}")
    out.append(f"  Evidence dir: {info['vision_dir']}")
    if not pw:
        out.append("[dim]Install: pip install 'prometheus-local-agent[browser]' && playwright install chromium[/dim]")
    return out


def assets_lines() -> list[str]:
    from .assets import doctor

    info = doctor()
    out = ["[bold]AssetForge:[/bold]"]
    for key, label in [("torch_available", "torch"), ("diffusers_available", "diffusers"),
                       ("rembg_available", "rembg (bg removal)")]:
        out.append(f"  {label}: {'available' if info[key] else '[yellow]not installed[/yellow]'}")
    out.append(f"  image tests: {'enabled' if info['image_tests_enabled'] else 'disabled'}")
    out.append(f"[dim]{info['env_var']}=1 to enable image generation[/dim]")
    return out


def astronaut_lines(workspace) -> list[str]:
    from pathlib import Path

    from .astronaut import read_state

    ws = Path(workspace)
    stop = (ws / ".prometheus" / "STOP").exists()
    pause = (ws / ".prometheus" / "PAUSE").exists()
    state = read_state(ws)
    out = ["[bold]Astronaut session:[/bold]"]
    out.append(f"  status: [bold]{state.status}[/bold]")
    if state.objective:
        out.append(f"  objective: {state.objective[:60]}")
    out.append(f"  macro attempts: {state.macro_attempts} · checkpoints: {state.checkpoints}")
    if state.final_status:
        out.append(f"  final: {state.final_status}")
    if pause:
        out.append("  [yellow]PAUSE control file present[/yellow]")
    if stop:
        out.append("  [red]STOP control file present[/red]")
    out.append("[dim]CLI: prometheus astronaut start|pause|resume|stop|tick|report[/dim]")
    return out


def setup_lines(settings, classified) -> list[str]:
    from .hardware import detect_hardware, recommended_profile

    report = detect_hardware()
    active = settings.active_bundle_id
    out = ["[bold]PROMETHEUS first-run setup[/bold]"]
    out.append(f"  OS: {report.os} {report.architecture}" + (" (WSL)" if report.wsl else ""))
    out.append(f"  RAM: {report.ram_gb} GB | GPU: {report.gpu_name or 'CPU mode'}")
    recommended = recommended_profile(report)
    out.append(f"  Recommended bundle: [bold]{recommended}[/bold]")
    if active:
        out.append(f"  [green]Active bundle: {active}[/green]")
    else:
        out.append("  [yellow]No bundle active yet.[/yellow]")
    out.append("")
    out.append("[bold]Available bundles:[/bold]")
    for c in classified:
        tag = _STATUS_TAG.get(c.status, c.status)
        add_on = " (add-on)" if c.bundle.is_add_on else ""
        out.append(f"  /use {c.bundle.id:<20} {c.bundle.name}{add_on} — {tag}")
    out.append("")
    out.append("Type [bold]/use <bundle-id>[/bold] to select, then enter an objective to start coding.")
    out.append("Type [bold]/help[/bold] for all commands.")
    return out


def first_run_banner(settings) -> list[str]:
    if settings.active_bundle_id:
        return []
    return [
        "[gold]Welcome to PROMETHEUS![/]",
        "No model bundle configured yet. Type [gold]/setup[/] to pick a bundle,",
        "or [gold]/help[/] to see all commands.",
        "",
    ]


def onboarding_lines(settings) -> list[str]:
    """Polished first-run panel: logo header, system summary, recommended bundle,
    Ollama status, and next-action commands. Used in on_mount when no bundle is
    active, and by the /setup command."""
    from .hardware import detect_hardware, recommended_profile
    from .onboarding import check_ollama

    report = detect_hardware()
    ollama = check_ollama()
    recommended = recommended_profile(report)
    out: list[str] = []
    out.append("[bold cyan]╔════════════════════════════════════════╗[/bold cyan]")
    out.append("[bold cyan]║      P R O M E T H E U S                ║[/bold cyan]")
    out.append("[bold cyan]║      local-first coding agent           ║[/bold cyan]")
    out.append("[bold cyan]╚════════════════════════════════════════╝[/bold cyan]")
    out.append("")
    out.append("[bold]System summary[/bold]")
    out.append(f"  OS:     {report.os} {report.architecture}" + (" (WSL)" if report.wsl else ""))
    out.append(f"  CPU:    {report.cpu_brand or 'unknown'}")
    out.append(f"  RAM:    {report.ram_gb:.0f} GB")
    out.append(f"  GPU:    {report.gpu_name or 'CPU-only mode'}")
    if report.gpu_vendor and report.vram_gb:
        out.append(f"  VRAM:   {report.vram_gb:.1f} GB ({report.gpu_vendor})")
    out.append(f"  Disk:   {report.disk_free_gb:.0f} GB free")
    out.append("")
    out.append(f"[bold]Recommended bundle:[/bold] [bold green]{recommended}[/bold green]")
    provider = "ollama-only" if settings.local_only else "ollama (default) · cloud-capable"
    out.append(f"[bold]Provider:[/bold] {provider}")
    ollama_state = "[green]running[/green]" if ollama.running else "[yellow]not running[/yellow]"
    out.append(f"[bold]Ollama:[/bold] {ollama_state} · {len(ollama.models)} models")
    if not ollama.running:
        out.append("  [dim]start with: ollama serve[/dim]")
    out.append("")
    if settings.active_bundle_id:
        out.append(f"[bold green]Active bundle:[/bold green] {settings.active_bundle_id}")
        out.append("Type an objective to start, or [bold]/help[/bold] for all commands.")
    else:
        out.append("[yellow]No model bundle configured.[/yellow]")
        out.append(f"[bold]Next:[/bold] type [bold]/setup[/bold] or [bold]/use {recommended}[/bold] to begin.")
    out.append("")
    out.append("[bold]Quick commands[/bold]")
    out.append("  [bold]/setup[/bold]      pick a bundle and configure")
    out.append("  [bold]/models[/bold]     list installed Ollama models")
    out.append("  [bold]/bundles[/bold]    browse all model packages")
    out.append("  [bold]/telemetry[/bold]  live CPU/RAM/GPU snapshot")
    out.append("  [bold]/help[/bold]       full command palette")
    return out


def telemetry_lines() -> list[str]:
    from .telemetry import collect_snapshot, render_telemetry_lines

    snapshot = collect_snapshot(cpu_interval_s=0.05)
    return render_telemetry_lines(snapshot)


def logo_lines() -> list[str]:
    from .logo import render_logo

    art = render_logo(0, size="compact", color=False)
    return art.splitlines()


def diagnose_lines() -> list[str]:
    from .diagnostics import collect_diagnostics, render_diagnostics_lines

    diag = collect_diagnostics()
    return render_diagnostics_lines(diag)


def provider_lines(settings) -> list[str]:
    out = ["[bold]Providers:[/bold]", "  ollama (default, local, quota-free) — http://127.0.0.1:11434"]
    if not settings.local_only:
        out.append("  openai-compatible (cloud, metered) — configured per-bundle")
        out.append("  [dim]Cloud use requires explicit configuration and is provider-metered.[/dim]")
    else:
        out.append("  [dim]Cloud providers disabled (local_only mode).[/dim]")
    return out


__all__ = [
    "SLASH_COMMANDS",
    "astronaut_lines",
    "assets_lines",
    "diagnose_lines",
    "doctor_lines",
    "first_run_banner",
    "help_lines",
    "logo_lines",
    "mode_switch_lines",
    "modes_lines",
    "models_lines",
    "onboarding_lines",
    "provider_lines",
    "providers_lines",
    "resume_lines",
    "sandbox_lines",
    "settings_lines",
    "setup_lines",
    "suggest_command",
    "telemetry_lines",
    "unknown_command_lines",
    "vision_lines",
]
