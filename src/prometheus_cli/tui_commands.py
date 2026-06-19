from __future__ import annotations


SLASH_COMMANDS = {
    "/settings": "show model packages and active config",
    "/bundles": "alias for /settings",
    "/models": "show installed Ollama models",
    "/doctor": "hardware + Ollama service report",
    "/qualify": "qualify the first installed model or a bundle (/qualify <id>)",
    "/modes": "autonomy modes",
    "/clear": "clear the log",
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
    out = [f"[bold]Model Packages[/bold] — active: {active} · local sessions {quota}"]
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


__all__ = ["SLASH_COMMANDS", "doctor_lines", "help_lines", "modes_lines", "models_lines", "settings_lines"]
