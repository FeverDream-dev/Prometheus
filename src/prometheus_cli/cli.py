from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from .config import ensure_home, load_bundle, load_settings, save_settings
from .hardware import detect_hardware, recommended_profile
from .installer import (
    DEFAULT_REPO,
    current_version,
    install_version,
    installed_versions,
    path_needs_bindir,
    resolve_latest_version,
    uninstall as uninstall_prometheus,
    user_data_home,
)
from .models import AutonomyMode, Risk, ToolCall
from .onboarding import (
    check_ollama,
    classify_bundle_fit,
    explain_bundle,
    list_available_bundles,
    pick_default_bundle,
)
from .orchestrator import Orchestrator
from .policy import mode_description
from .session import SessionStore

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
BUNDLES_DIR = CONFIG_DIR / "bundles"

app = typer.Typer(help="PROMETHEUS — local-first adaptive coding agent", no_args_is_help=True)
console = Console()


@app.command()
def doctor(json_output: bool = typer.Option(False, "--json")) -> None:
    """Inspect hardware and recommend a model bundle."""
    report = detect_hardware()
    if json_output:
        console.print(report.as_json())
        return
    console.print(Panel.fit("PROMETHEUS hardware report"))
    console.print(f"OS: {report.os} {report.architecture}" + (" (WSL)" if report.wsl else ""))
    console.print(f"RAM: {report.ram_gb} GB")
    if report.cpu_brand:
        console.print(f"CPU: {report.cpu_brand}")
    if report.cpu_features:
        notable = [f for f in ("avx2", "avx512f", "neon", "fma", "sse4_2") if f in report.cpu_features]
        if notable:
            console.print(f"CPU features: {', '.join(notable)}")
    if report.gpu_vendor:
        gpu_label = report.gpu_name or report.gpu_vendor
        extras = []
        if report.vram_gb:
            extras.append(f"{report.vram_gb} GB VRAM")
        if report.metal:
            extras.append("Metal")
        if report.unified_memory:
            extras.append("unified memory")
        suffix = f" ({', '.join(extras)})" if extras else ""
        console.print(f"GPU: {gpu_label}{suffix}")
    else:
        console.print("GPU: CPU mode")
    console.print(f"Disk free: {report.disk_free_gb} GB")
    console.print(f"Ollama: {'ready' if report.ollama_installed else 'not installed'}")
    console.print(f"Docker: {'ready' if report.docker_installed else 'not installed'}")
    console.print(f"Recommended bundle: [bold]{recommended_profile(report)}[/bold]")
    for note in report.notes:
        console.print(f"[dim]• {note}[/dim]")


@app.command()
def setup(
    bundles_dir: Path = typer.Option(BUNDLES_DIR, "--bundles-dir"),
    mode: AutonomyMode = typer.Option(AutonomyMode.PILOT),
    bundle_name: str | None = typer.Option(None, "--bundle", help="Pre-select a bundle (non-interactive)"),
    yes: bool = typer.Option(False, "--yes", help="Accept defaults without prompting"),
    pull: bool = typer.Option(False, "--pull", help="Pull model files via Ollama after setup"),
) -> None:
    """Detect hardware, recommend a bundle, and configure PROMETHEUS."""
    report = detect_hardware()
    console.print(Panel.fit("PROMETHEUS setup"))
    console.print(f"OS: {report.os} {report.architecture}" + (" (WSL)" if report.wsl else ""))
    console.print(f"RAM: {report.ram_gb} GB | Disk free: {report.disk_free_gb} GB")
    if report.gpu_vendor:
        console.print(f"GPU: {report.gpu_name or report.gpu_vendor} ({report.vram_gb} GB VRAM)")
    else:
        console.print("GPU: CPU mode")
    for note in report.notes:
        console.print(f"[dim]• {note}[/dim]")

    ollama = check_ollama()
    if not ollama.installed:
        console.print(f"\n[yellow]Ollama is not installed.[/yellow]\nInstall: {ollama.install_hint}")
    elif not ollama.running:
        console.print("\n[yellow]Ollama is installed but not running.[/yellow]\nStart it with: ollama serve")
    else:
        console.print(f"\nOllama: ready ({len(ollama.models)} models available)")

    options = list_available_bundles(bundles_dir)
    if not options:
        console.print("[red]No bundles found.[/red] Pass --bundles-dir.")
        raise typer.Exit(code=1)

    default = pick_default_bundle(options, report)
    for opt in options:
        if opt is default:
            continue
        opt.fits, opt.reason = classify_bundle_fit(opt.bundle, report)

    console.print("\n[bold]Available bundles:[/bold]")
    for idx, opt in enumerate(options, 1):
        marker = " (recommended)" if opt is default else ""
        fit_label = "[green]fits[/green]" if opt.fits else "[red]does not fit[/red]"
        console.print(f"  {idx}. {opt.name}{marker} — {fit_label}: {opt.reason}")

    if bundle_name:
        chosen = next((o for o in options if o.name == bundle_name), None)
        if chosen is None:
            console.print(f"[red]Bundle '{bundle_name}' not found.[/red]")
            raise typer.Exit(code=1)
    elif yes or default is None:
        chosen = default or options[0]
    else:
        console.print(f"\nRecommended: [bold]{default.name}[/bold]")
        console.print(explain_bundle(default.bundle, report))
        selection = Prompt.ask(
            "Choose a bundle by number, or press Enter for the recommended one",
            default=str(options.index(default) + 1),
        )
        try:
            chosen = options[int(selection) - 1]
        except (ValueError, IndexError):
            chosen = default

    settings = load_settings()
    settings.bundle_file = chosen.path
    settings.mode = mode
    path = save_settings(settings)
    console.print(f"\nSaved [bold]{path}[/bold]")
    console.print(f"Bundle: {chosen.name}")
    console.print(mode_description(mode))

    if pull and ollama.running:
        for spec in chosen.bundle.models:
            if spec.provider == "ollama":
                console.print(f"Pulling {spec.model}…")
                typer.echo(f"  Run manually to confirm: ollama pull {spec.model}")
    elif pull and not ollama.running:
        console.print("[yellow]Skipping model pull: Ollama is not running.[/yellow]")

    console.print(f"\nNext: prometheus run \"<objective>\" --bundle {chosen.path} --workspace .")


@app.command("init")
def initialize(
    workspace: Path = typer.Argument(Path.cwd()),
    mode: AutonomyMode = typer.Option(AutonomyMode.PILOT),
) -> None:
    """Create user configuration for this machine."""
    settings = load_settings()
    settings.workspace = workspace.resolve()
    settings.mode = mode
    path = save_settings(settings)
    console.print(f"Saved {path}")
    console.print(mode_description(mode))


def _approval(call: ToolCall, risk: Risk) -> bool:
    console.print(Panel(f"{call.tool}\n{call.arguments}\nReason: {call.reason}", title=f"{risk.value} approval"))
    return Confirm.ask("Allow?", default=False)


@app.command()
def run(
    objective: str = typer.Argument(..., help="Outcome PROMETHEUS must achieve"),
    bundle: Path = typer.Option(..., exists=True, readable=True),
    workspace: Path = typer.Option(Path.cwd(), exists=True, file_okay=False),
    mode: AutonomyMode | None = typer.Option(None),
    resume: str | None = typer.Option(None, "--resume", help="Session ID to resume"),
) -> None:
    """Run an evidence-driven coding session."""
    settings = load_settings()
    settings.workspace = workspace.resolve()
    if mode:
        settings.mode = mode
    if not settings.bundle_file:
        settings.bundle_file = bundle
    home = ensure_home()
    store = SessionStore(home / "sessions" / "prometheus.db")
    orchestrator = Orchestrator(settings, load_bundle(bundle), approve=_approval, session_store=store)
    result = orchestrator.run(objective, on_update=lambda line: console.print(f"[cyan]{line}[/cyan]"))
    store.close()
    console.print(Panel(result.message, title=f"{result.status} — {result.completion_percent}%"))


@app.command()
def sessions(limit: int = typer.Option(20, "--limit")) -> None:
    """List recent coding sessions and their completion."""
    home = ensure_home()
    store = SessionStore(home / "sessions" / "prometheus.db")
    for s in store.list_sessions(limit=limit):
        console.print(f"[bold]{s.id[:12]}[/bold]  {s.completion_percent:>5.1f}%  {s.status:<10}  {s.objective[:60]}")
    store.close()


@app.command()
def resume(session_id: str) -> None:
    """Show the state of a session for manual continuation."""
    home = ensure_home()
    store = SessionStore(home / "sessions" / "prometheus.db")
    session = store.get_session(session_id)
    if session is None:
        console.print(f"[red]Session {session_id} not found.[/red]")
        raise typer.Exit(code=1)
    console.print(Panel(f"Session {session_id}"))
    console.print(f"Objective: {session['objective']}")
    console.print(f"Status: {session['status']}")
    console.print(f"Mode: {session['mode']}")
    console.print(f"Completion: {store.completion_percent(session_id)}%")
    console.print(f"Critical criteria met: {'yes' if store.all_critical_passed(session_id) else 'no'}")
    console.print(f"Tasks: {store.task_count(session_id)}")
    console.print(f"Last event seq: {store.last_event_seq(session_id)}")
    checkpoints = store.list_checkpoints(session_id)
    if checkpoints:
        console.print(f"\nCheckpoints ({len(checkpoints)}):")
        for cp in checkpoints[:5]:
            console.print(f"  {cp['commit_sha'][:12]}  {cp['message'][:60]}")
    store.close()


@app.command()
def tui(
    bundle: Path | None = typer.Option(None, "--bundle", exists=True, readable=True),
    workspace: Path = typer.Option(Path.cwd(), exists=True, file_okay=False),
) -> None:
    """Launch the interactive Textual TUI."""
    try:
        from .tui import launch_tui
    except ImportError:
        console.print("[red]Textual is not installed. Install with: pip install 'prometheus-local-agent[tui]'[/red]")
        raise typer.Exit(code=1)
    settings = load_settings()
    bundle_path = bundle or settings.bundle_file
    if not bundle_path:
        console.print("[yellow]No bundle configured. Run 'prometheus setup' first.[/yellow]")
        console.print("Or pass --bundle <path>")
        raise typer.Exit(code=1)
    launch_tui(bundle_path=bundle_path, workspace=workspace)


@app.command()
def modes() -> None:
    """Explain autonomy levels."""
    for mode in AutonomyMode:
        console.print(f"[bold]{mode.value}[/bold]: {mode_description(mode)}")


@app.command()
def update(
    version: str | None = typer.Option(None, "--version", help="Pin a version tag (e.g. v0.1.0) or 'main'"),
    check: bool = typer.Option(False, "--check", help="Only show current vs latest; do not install"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would happen; change nothing"),
    yes: bool = typer.Option(False, "--yes", help="Noninteractive confirmation"),
    no_tui: bool = typer.Option(False, "--no-tui", help="Do not install the TUI extra"),
) -> None:
    """Update PROMETHEUS to the latest (or a pinned) release."""
    latest = resolve_latest_version(DEFAULT_REPO)
    target = version or latest.version
    here = current_version() or "unknown"
    console.print(Panel.fit("PROMETHEUS update"))
    console.print(f"Installed: {here}")
    console.print(f"Latest   : {latest}")
    console.print(f"Target   : [bold]{target}[/bold]")
    if check:
        if here == target:
            console.print("[green]Already up to date.[/green]")
            raise typer.Exit(code=0)
        console.print("[yellow]Update available.[/yellow]")
        raise typer.Exit(code=0)
    if here == target and not version:
        console.print("[green]Already up to date.[/green]")
        raise typer.Exit(code=0)
    if dry_run:
        console.print("[yellow]DRY RUN[/yellow] — would download, verify, and install.")
        raise typer.Exit(code=0)
    if not yes:
        if not Confirm.ask(f"Install PROMETHEUS {target}?", default=True):
            raise typer.Exit(code=1)
    try:
        result = install_version(target, DEFAULT_REPO, install_tui=not no_tui)
    except Exception as exc:
        console.print(f"[red]Update failed:[/red] {exc}")
        raise typer.Exit(code=1)
    console.print(f"[green]Updated to {result.version}.[/green]")
    console.print(f"Verified: {'yes' if result.verified else 'no (unreleased build)'}")
    console.print(f"Launcher: {result.wrapper}")
    if path_needs_bindir():
        console.print(f"[yellow]Add {result.wrapper.parent} to your PATH to run 'prometheus'.[/yellow]")


@app.command()
def uninstall(
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompt"),
    purge: bool = typer.Option(False, "--purge", help="Also remove user config, sessions, and bundles"),
    version: str | None = typer.Option(None, "--version", help="Remove a single version only"),
) -> None:
    """Remove PROMETHEUS. Preserves your config/sessions/models unless --purge."""
    console.print(Panel.fit("PROMETHEUS uninstall"))
    versions = installed_versions()
    here = current_version() or "unknown"
    if not versions and not version:
        console.print("[yellow]No PROMETHEUS versions found under the install root.[/yellow]")
        raise typer.Exit(code=0)
    console.print(f"Installed version(s): {', '.join(versions) or '(none)'}")
    console.print(f"Current: {here}")
    if purge:
        console.print("[red]--purge: will ALSO delete config, sessions, and bundles under "
                      f"{user_data_home()}[/red]")
        console.print("[red]Shared Ollama models are never touched.[/red]")
    else:
        console.print("[green]Default: keeping your config, sessions, and bundles "
                      "(use --purge to remove them too).[/green]")
        console.print("[green]Shared Ollama models are never touched.[/green]")
    if not yes and not Confirm.ask("Proceed with uninstall?", default=False):
        raise typer.Exit(code=1)
    result = uninstall_prometheus(version=version, purge=purge)
    if result.removed_versions:
        console.print(f"Removed versions: {', '.join(result.removed_versions)}")
    if result.removed_wrapper:
        console.print("Removed launcher.")
    if result.removed_user_data:
        console.print("[red]Removed user data (config/sessions/bundles).[/red]")
    console.print("[bold]PROMETHEUS uninstalled.[/bold]")


if __name__ == "__main__":
    app()

