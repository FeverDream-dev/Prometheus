from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from .bundles import classify_registry, find_bundle, load_registry, sanitize_bundle
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
    format_pull_progress,
    inference_smoke_test,
    list_available_bundles,
    ollama_install_plan,
    pick_default_bundle,
    run_ollama_install,
    start_ollama_service,
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
    if report.ollama_running:
        console.print("Ollama: installed, service running")
    elif report.ollama_installed:
        console.print("Ollama: installed, service NOT running (start with: ollama serve)")
    else:
        console.print("Ollama: not installed")
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
        plan = ollama_install_plan()
        console.print("\n[yellow]Ollama is not installed.[/yellow]")
        console.print("Recommended bundle needs Ollama for local inference.")
        if plan.command:
            console.print("PROMETHEUS can install it for you. It will run:")
            console.print(f"  [bold]{plan.command}[/bold]")
            console.print(f"[dim]({plan.description})[/dim]")
        want_install = (bundle_name is None) and (not yes) and Confirm.ask(
            "Install Ollama now with the command above?", default=False
        )
        if want_install and plan.command:
            console.print("Running installer (it may request sudo internally)…")
            result_install = run_ollama_install(plan)
            if result_install.success:
                console.print("[green]Ollama installed.[/green]")
                if start_ollama_service():
                    ollama = check_ollama()
                    console.print(f"Ollama service: {'ready' if ollama.running else 'not responding'}")
                else:
                    console.print("[yellow]Install succeeded but the service did not respond. "
                                  "Start it with: ollama serve[/yellow]")
            else:
                console.print(f"[red]Install failed (exit {result_install.returncode}).[/red]")
                console.print(f"[dim]{result_install.output[-400:]}[/dim]")
        else:
            console.print(f"Install Ollama manually: {ollama.install_hint}")
            console.print("Or re-run setup after installing, then pick a bundle.")
    elif not ollama.running:
        console.print("\n[yellow]Ollama is installed but not running.[/yellow]")
        if yes or Confirm.ask("Start the Ollama service now?", default=True):
            if start_ollama_service():
                ollama = check_ollama()
                console.print(f"Ollama service: {'ready' if ollama.running else 'not responding'}")
            else:
                console.print("Start it manually with: ollama serve")
        else:
            console.print("Start it manually with: ollama serve")
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
            if spec.provider != "ollama":
                continue
            if spec.model in ollama.models:
                console.print(f"Already installed: {spec.model}")
                continue
            console.print(f"Pulling {spec.model}…")
            last = {"pct": -1}

            def on_progress(data, _last=last):
                line = format_pull_progress(data)
                pct = data.get("completed", 0) * 100 // max(data.get("total", 1), 1)
                if pct != _last["pct"] or data.get("status") in ("success", "pulling manifest"):
                    console.print(f"  {line}")
                    _last["pct"] = pct

            from .onboarding import pull_model

            ok = pull_model(spec.model, on_progress=on_progress)
            if ok:
                console.print(f"[green]Pulled {spec.model}.[/green]")
            else:
                console.print(f"[red]Pull failed for {spec.model}. "
                              f"Run manually: ollama pull {spec.model}[/red]")
        ollama = check_ollama()
        controller_spec = next(
            (s for s in chosen.bundle.models if s.provider == "ollama" and s.tool_capable),
            chosen.bundle.models[0] if chosen.bundle.models else None,
        )
        if controller_spec and controller_spec.model in ollama.models:
            console.print(f"\nRunning inference smoke test on [bold]{controller_spec.model}[/bold]…")
            smoke = inference_smoke_test(controller_spec.model)
            if smoke.success:
                console.print(f"[green]Inference OK.[/green] Response: {smoke.response[:80]}")
            else:
                console.print(f"[yellow]Smoke test did not return a response: {smoke.error}[/yellow]")
                console.print("[yellow]The model is installed; inference may still work for longer prompts.[/yellow]")
    elif pull and not ollama.running:
        console.print("[yellow]Skipping model pull: Ollama is not running.[/yellow]")

    console.print(f"\nNext: prometheus run \"<objective>\" --bundle {chosen.path} --workspace .")

    if yes:
        return
    if Confirm.ask("Open the PROMETHEUS TUI now?", default=False):
        try:
            from .tui import launch_tui

            launch_tui(bundle_path=chosen.path, workspace=Path.cwd())
        except ImportError:
            console.print("[red]Textual is not installed. Run: pip install 'prometheus-local-agent[tui]'[/red]")


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
    bundle: Path | None = typer.Option(None, "--bundle", exists=True, readable=True,
                                       help="Model bundle YAML (defaults to the one saved by 'prometheus setup')"),
    workspace: Path = typer.Option(Path.cwd(), exists=True, file_okay=False),
    mode: AutonomyMode | None = typer.Option(None),
    resume: str | None = typer.Option(None, "--resume", help="Session ID to resume"),
) -> None:
    """Run an evidence-driven coding session."""
    settings = load_settings()
    settings.workspace = workspace.resolve()
    if mode:
        settings.mode = mode
    bundle_path = bundle or settings.bundle_file
    if not bundle_path:
        console.print("[red]No bundle specified and none saved.[/red] Run 'prometheus setup' or pass --bundle.")
        raise typer.Exit(code=1)
    if not settings.bundle_file:
        settings.bundle_file = bundle_path
    home = ensure_home()
    store = SessionStore(home / "sessions" / "prometheus.db")
    orchestrator = Orchestrator(settings, load_bundle(bundle_path), approve=_approval, session_store=store)
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
    no_animation: bool = typer.Option(False, "--no-animation", help="Skip the startup splash animation"),
) -> None:
    """Launch the interactive Textual TUI."""
    try:
        from .splash import pick_size_for_terminal, play as play_splash, should_animate
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
    if should_animate(no_animation=no_animation):
        play_splash(pick_size_for_terminal(), duration_s=1.0, fps=12)
    launch_tui(bundle_path=bundle_path, workspace=workspace)


@app.command()
def qualify(
    model: str | None = typer.Option(None, "--model", help="Qualify a specific model tag instead of a bundle"),
    bundle_id: str | None = typer.Option(None, "--bundle", help="Bundle id to qualify (e.g. spark-cpu-8gb)"),
    base_url: str = typer.Option("http://127.0.0.1:11434", "--base-url"),
) -> None:
    """Run capability tests against a real model (chat, structured output, tool, code patch)."""
    from .onboarding import check_ollama
    from .qualification import qualify_bundle, qualify_model

    status = check_ollama(base_url)
    if not status.running:
        console.print(f"[red]Ollama service not responding at {base_url}.[/red]")
        raise typer.Exit(code=1)
    if model:
        console.print(Panel.fit(f"Qualifying model [bold]{model}[/bold]"))
        report = qualify_model(model, base_url)
    else:
        registry = load_registry()
        target = next((b for b in registry if b.id == (bundle_id or "")), None)
        if target is None:
            console.print(f"[red]No bundle '{bundle_id}'. Available: {', '.join(b.id for b in registry)}[/red]")
            raise typer.Exit(code=1)
        console.print(Panel.fit(f"Qualifying bundle [bold]{target.id}[/bold] (controller {target.controller_spec().model})"))
        report = qualify_bundle(target, base_url)
    for r in report.results:
        mark = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        console.print(f"  {mark} {r.name} — {r.detail}")
    verdict = "[green]QUALIFIED[/green]" if report.passed else "[yellow]PARTIAL[/yellow]"
    console.print(f"\n{verdict}: {report.passed_count}/{len(report.results)} capability tests passed.")
    if not report.passed:
        raise typer.Exit(code=1)


@app.command()
def modes() -> None:
    """Explain autonomy levels."""
    for mode in AutonomyMode:
        console.print(f"[bold]{mode.value}[/bold]: {mode_description(mode)}")


@app.command()
def bundles(
    json_output: bool = typer.Option(False, "--json"),
    installed: bool = typer.Option(False, "--installed", help="Show only bundles whose models are already pulled"),
) -> None:
    """List selectable model packages with hardware fit and status."""
    from .hardware import detect_hardware
    from .onboarding import check_ollama

    registry = load_registry()
    if not registry:
        console.print("[red]No model packages found.[/red]")
        raise typer.Exit(code=1)
    report = detect_hardware()
    ollama = check_ollama()
    classified = classify_registry(registry, report, ollama.models)
    if installed:
        classified = [c for c in classified if c.bundle.installed_fraction(ollama.models) > 0]
    if json_output:
        import json as _json

        console.print(_json.dumps([
            {
                "id": c.bundle.id,
                "name": c.bundle.name,
                "status": c.status,
                "fits_hardware": c.fits_hardware,
                "download_gb": c.bundle.total_download_gb(),
                "add_on": c.bundle.is_add_on,
                "experimental": c.bundle.experimental,
                "unlimited_local_sessions": c.bundle.runtime.unlimited_local_sessions,
                "reasons": c.reasons,
                "roles": {r: s.model for r, s in c.bundle.roles.items()},
            }
            for c in classified
        ], indent=2))
        return
    console.print(Panel.fit(f"PROMETHEUS model packages — {report.ram_gb:.0f} GB RAM, "
                            f"{report.vram_gb:.0f} GB VRAM, Ollama "
                            f"{'ready' if ollama.running else 'down'}"))
    for c in classified:
        tag = {
            "recommended": "[green]recommended[/green]",
            "installed": "[bold green]installed[/bold]",
            "available": "available",
            "experimental": "[yellow]experimental[/yellow]",
            "incompatible": "[red]incompatible[/red]",
        }[c.status]
        marker = " (add-on)" if c.bundle.is_add_on else ""
        console.print(f"\n[bold]{c.bundle.name}[/bold]{marker} — {tag}")
        console.print(f"  {c.bundle.description}")
        console.print(f"  download ~{c.bundle.total_download_gb():.1f} GB · "
                      f"local sessions {'unlimited' if c.bundle.runtime.unlimited_local_sessions else 'metered'}")
        for role, spec in c.bundle.roles.items():
            opt = " (optional)" if spec.optional else ""
            pulled = " [installed]" if spec.model in ollama.models else ""
            console.print(f"    {role}: {spec.model}{opt}{pulled}")
        for reason in c.reasons:
            console.print(f"  [dim]• {reason}[/dim]")


@app.command(name="use")
def use_bundle(
    bundle_id: str = typer.Argument(..., help="Package id, e.g. spark-cpu-8gb"),
) -> None:
    """Select the active model package (materializes it so run/tui use it)."""
    import yaml

    registry = load_registry()
    match = find_bundle(bundle_id, registry)
    if match is None:
        console.print(f"[red]No package '{bundle_id}'.[/red] Available: "
                      f"{', '.join(b.id for b in registry)}")
        raise typer.Exit(code=1)
    if match.is_add_on:
        console.print(f"[red]'{bundle_id}' is an add-on (no controller) and cannot be the active package.[/red]")
        raise typer.Exit(code=1)
    settings = load_settings()
    home = ensure_home()
    active_dir = home / "bundles"
    active_dir.mkdir(exist_ok=True)
    active_path = active_dir / f"active-{match.id}.yaml"
    v1 = match.to_v1_bundle()
    active_path.write_text(yaml.safe_dump(v1.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
    settings.active_bundle_id = match.id
    settings.bundle_file = active_path
    save_settings(settings)
    console.print(f"[green]Active package:[/green] {match.name} ({match.id})")
    console.print(f"Controller: {match.controller_spec().model}")
    quota = "quota-free / unlimited" if match.runtime.unlimited_local_sessions else "metered"
    console.print(f"Local sessions: {quota}")
    console.print(f"Materialized bundle: {active_path}")
    console.print("Next: prometheus run \"<objective>\" --workspace .   (or: prometheus tui)")


@app.command()
def export(
    bundle_id: str = typer.Argument(..., help="Package id to export"),
    out: Path = typer.Option(Path("exported-bundle.yaml"), "--out", "-o"),
) -> None:
    """Export a sanitized bundle manifest (no secrets or personal paths)."""
    import yaml

    registry = load_registry()
    match = find_bundle(bundle_id, registry)
    if match is None:
        console.print(f"[red]No package '{bundle_id}'.[/red]")
        raise typer.Exit(code=1)
    sanitized = sanitize_bundle(match)
    out.write_text(yaml.safe_dump(sanitized, sort_keys=False), encoding="utf-8")
    console.print(f"[green]Exported sanitized manifest:[/green] {out}")
    console.print("[dim]Secret-named fields and absolute/personal paths were stripped.[/dim]")


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

