from __future__ import annotations

import time
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from .bundles import classify_bundle, classify_registry, find_bundle, load_registry, sanitize_bundle
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
    v2_recommended = None
    try:
        from .onboarding import check_ollama as _check_ollama
        ollama_models = _check_ollama().models
        v2_recs = classify_registry(load_registry(), report, ollama_models)
        v2_recommended = next((c for c in v2_recs if c.status == "recommended"), None)
    except Exception:
        pass
    if v2_recommended is not None:
        console.print(f"Recommended package: [bold]{v2_recommended.bundle.id}[/bold] "
                      f"({v2_recommended.bundle.name})")
    else:
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
    classic: bool = typer.Option(False, "--classic", help="Use the legacy one-shot orchestrator instead of the bounded-memory Arena"),
    yes: bool = typer.Option(False, "--yes", help="Auto-approve mode-allowed actions (noninteractive/CI)"),
) -> None:
    """Run an evidence-driven coding session (bounded-memory Arena by default)."""
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
    approve = (lambda _c, _r: True) if yes else _approval
    if classic:
        orchestrator = Orchestrator(settings, load_bundle(bundle_path), approve=approve, session_store=store)
        result = orchestrator.run(objective, on_update=lambda line: console.print(f"[cyan]{line}[/cyan]"))
        store.close()
        console.print(Panel(result.message, title=f"{result.status} — {result.completion_percent}%"))
        return
    _run_arena(objective, bundle_path, workspace, settings, store, approve)


def _run_arena(objective, bundle_path, workspace, settings, session_store, approve_fn) -> None:
    from .agent import ArenaLoop, MicroStepEngine, make_default_verify
    from .memory import Intent, ProjectMemoryStore
    from .providers import create_provider
    from .tools.workspace import WorkspaceTools

    bundle = load_bundle(bundle_path)
    controller_spec = bundle.for_role("controller")
    forge = create_provider(controller_spec)
    envoy = create_provider(controller_spec)
    argus = None
    if settings.multi_agent_review:
        try:
            argus = create_provider(bundle.for_role("reviewer"))
        except KeyError:
            argus = create_provider(controller_spec)
    mem = ProjectMemoryStore(workspace)
    mem.set_intent(Intent(objective=objective, success_criteria=[]))
    tools = WorkspaceTools(workspace)
    engine = MicroStepEngine(store=mem, tools=tools, settings=settings, approve=approve_fn)
    arena = ArenaLoop(store=mem, tools=tools, engine=engine)
    verify = make_default_verify(workspace)
    providers = {"envoy": envoy, "forge": forge, "argus": argus}
    console.print(Panel.fit(f"PROMETHEUS Arena — bounded memory + micro-steps\nBundle: {bundle.name} · Mode: {settings.mode.value}"))
    result = arena.run(providers, verify, on_update=lambda line: console.print(f"[cyan]{line}[/cyan]"))
    mem.set_working_memory(f"# Session result\n\nobjective: {objective}\nstatus: {result.final_status}\nattempts: {result.attempts}\naccepted: {result.accepted}\n")
    session_store.close()
    verdict = "[green]COMPLETE[/green]" if result.accepted else f"[yellow]{result.final_status.upper()}[/yellow]"
    console.print(Panel(
        f"accepted={result.accepted} · attempts={result.attempts} · signatures={result.failure_signatures}",
        title=f"{verdict} — Arena",
    ))


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
def memory(
    action: str = typer.Argument("status", help="status|inspect|why|rebuild|export|reset"),
    arg: str | None = typer.Argument(None, help="fact id (for 'why') or export path (for 'export')"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
) -> None:
    """Inspect or manage PROMETHEUS bounded project memory (.prometheus/)."""
    from .memory import ProjectMemoryStore

    store = ProjectMemoryStore(workspace)
    if action == "status":
        st = store.status()
        intent = store.get_intent()
        console.print(Panel.fit("PROMETHEUS memory"))
        console.print(f"Working memory: {'OK' if st.ok else 'NOT OK'} — {st.word_count}/{st.limit} words "
                      f"(v{st.version}){' [recovered]' if st.recovered else ''}")
        if st.error:
            console.print(f"[yellow]{st.error}[/yellow]")
        console.print(f"Intent: {intent.objective if intent else '(none)'}")
        console.print(f"Tasks: {len(store.get_tasks())} · Decisions: {len(store.list_decisions())} · "
                      f"Facts: {len(store.list_facts())} · Revisions: {len(store.list_revisions())}")
    elif action == "inspect":
        intent = store.get_intent()
        console.print("[bold]Intent:[/bold]", intent.objective if intent else "(none)")
        console.print("[bold]Tasks:[/bold]")
        for t in store.get_tasks():
            console.print(f"  [{t.status}] {t.id}: {t.description}")
        console.print("[bold]Recent decisions:[/bold]")
        for d in store.list_decisions()[-8:]:
            console.print(f"  {d.choice}")
        console.print("[bold]Verified facts:[/bold]")
        for f in store.list_facts()[-12:]:
            console.print(f"  ({f.confidence.value}/{f.provenance.source}) {f.summary}")
    elif action == "why":
        if not arg:
            console.print("[red]'why' needs a fact id.[/red]")
            raise typer.Exit(code=1)
        fact = store.why(arg)
        if fact is None:
            console.print(f"[red]No fact '{arg}'.[/red]")
            raise typer.Exit(code=1)
        console.print(f"[bold]{fact.summary}[/bold]")
        console.print(f"confidence: {fact.confidence.value} · source: {fact.provenance.source} · "
                      f"event: {fact.provenance.event_id}")
    elif action == "rebuild":
        st = store.rebuild()
        console.print(f"[green]Rebuilt working memory:[/green] v{st.version}, {st.word_count} words")
    elif action == "export":
        dest = Path(arg) if arg else workspace / "prometheus-memory-export.json"
        out = store.export(dest)
        console.print(f"[green]Sanitized export:[/green] {out}")
    elif action == "reset":
        if not Confirm.ask("Checkpoint then clear project memory?", default=False):
            raise typer.Exit(code=0)
        store.reset()
        console.print("[green]Project memory reset.[/green]")
    else:
        console.print(f"[red]Unknown memory action '{action}'.[/red] Try: status|inspect|why|rebuild|export|reset")
        raise typer.Exit(code=1)


bundles_app = typer.Typer(help="List, inspect, and qualify model packages", invoke_without_command=True)


def _print_bundles(json_output: bool, installed_only: bool) -> None:
    from .hardware import detect_hardware
    from .onboarding import check_ollama

    registry = load_registry()
    if not registry:
        console.print("[red]No model packages found.[/red]")
        raise typer.Exit(code=1)
    report = detect_hardware()
    ollama = check_ollama()
    classified = classify_registry(registry, report, ollama.models)
    if installed_only:
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


@bundles_app.callback()
def bundles_default(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json"),
    installed: bool = typer.Option(False, "--installed", help="Show only bundles whose models are already pulled"),
) -> None:
    """With no subcommand, list selectable model packages (alias for 'bundles list')."""
    if ctx.invoked_subcommand is None:
        _print_bundles(json_output, installed)


@bundles_app.command("list")
def bundles_list(
    json_output: bool = typer.Option(False, "--json"),
    installed: bool = typer.Option(False, "--installed", help="Show only bundles whose models are already pulled"),
) -> None:
    """List selectable model packages with hardware fit and status."""
    _print_bundles(json_output, installed)


@bundles_app.command("inspect")
def bundles_inspect(
    bundle_id: str = typer.Argument(..., help="Package id, e.g. ember-8gb-gpu"),
) -> None:
    """Show full details and hardware-fit reasoning for one package."""
    registry = load_registry()
    match = find_bundle(bundle_id, registry)
    if match is None:
        console.print(f"[red]No package '{bundle_id}'.[/red] Available: "
                      f"{', '.join(b.id for b in registry)}")
        raise typer.Exit(code=1)
    from .hardware import detect_hardware
    from .onboarding import check_ollama

    report = detect_hardware()
    ollama = check_ollama()
    classified = classify_bundle(match, report, ollama.models)
    console.print(Panel.fit(f"{match.name} ({match.id})"))
    console.print(match.description)
    console.print(f"experimental: {match.experimental} · add-on: {match.is_add_on}")
    console.print(f"hardware floor: {match.hardware.minimum_ram_gb} GB RAM, "
                  f"{match.hardware.minimum_vram_gb} GB VRAM, "
                  f"{match.hardware.minimum_free_disk_gb} GB disk")
    console.print(f"runtime: provider={match.runtime.provider} · "
                  f"sequential={match.runtime.sequential_loading} · "
                  f"max_loaded={match.runtime.maximum_loaded_models} · "
                  f"context={match.runtime.default_context}")
    console.print(f"download ~{match.total_download_gb():.1f} GB · "
                  f"local sessions {'unlimited' if match.runtime.unlimited_local_sessions else 'metered'}")
    console.print("[bold]Roles:[/bold]")
    for role, spec in match.roles.items():
        opt = " (optional)" if spec.optional else ""
        pulled = " [installed]" if spec.model in ollama.models else ""
        caps = ", ".join(spec.capabilities) or "(none)"
        console.print(f"  {role}: {spec.model}{opt}{pulled} — caps: {caps} · keep_alive={spec.keep_alive}")
    console.print("[bold]Licenses:[/bold]")
    for lic in match.licenses:
        console.print(f"  {lic.model}: {lic.license} ({lic.source})")
    if match.qualification.required:
        console.print(f"[bold]Qualification tests:[/bold] {', '.join(match.qualification.required)}")
    console.print(f"[bold]Fit on this host:[/bold] {classified.status} — {classified.reasons[0]}")


@bundles_app.command("qualify")
def bundles_qualify(
    bundle_id: str = typer.Argument(..., help="Package id to qualify"),
    base_url: str = typer.Option("http://127.0.0.1:11434", "--base-url"),
) -> None:
    """Run capability tests against a package's controller model."""
    from .onboarding import check_ollama
    from .qualification import qualify_bundle

    status = check_ollama(base_url)
    if not status.running:
        console.print(f"[red]Ollama service not responding at {base_url}.[/red]")
        raise typer.Exit(code=1)
    registry = load_registry()
    target = find_bundle(bundle_id, registry)
    if target is None:
        console.print(f"[red]No bundle '{bundle_id}'.[/red]")
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


models_app = typer.Typer(help="List, pull, and unload Ollama models")
mcp_app = typer.Typer(help="Manage MCP stdio servers")
browser_app = typer.Typer(help="Browser automation (Playwright)")
astronaut_app = typer.Typer(help="Long-running autonomous sessions")
sandbox_app = typer.Typer(help="Sandbox doctor + enforcement test suite")
provider_app = typer.Typer(help="Provider smoke probes")


@models_app.command("list")
def models_list(
    base_url: str = typer.Option("http://127.0.0.1:11434", "--base-url"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List models installed in the local Ollama registry."""
    from .onboarding import check_ollama

    status = check_ollama(base_url)
    if not status.running:
        console.print(f"[red]Ollama service not responding at {base_url}.[/red]")
        console.print("[dim]Start it with: ollama serve[/dim]")
        raise typer.Exit(code=1)
    if json_output:
        import json as _json

        console.print(_json.dumps({"models": status.models}, indent=2))
        return
    console.print(Panel.fit(f"Ollama models ({len(status.models)}) — {base_url}"))
    if not status.models:
        console.print("[dim]No models pulled yet. Use: prometheus models pull <name>[/dim]")
    for m in status.models:
        console.print(f"  • {m}")


@models_app.command("pull")
def models_pull(
    model: str = typer.Argument(None, help="Model tag or alias (e.g. llama3.2:latest or vibethinker-q2). Omit to pull the active bundle's models."),
    bundle_id: str = typer.Option(None, "--bundle", help="Pull every role model of this package id"),
    base_url: str = typer.Option("http://127.0.0.1:11434", "--base-url"),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Run a one-token inference probe after pull"),
) -> None:
    """Pull a model (or a whole bundle's roles) via Ollama with live progress."""
    from .model_aliases import resolve_alias
    from .onboarding import check_ollama, format_pull_progress, inference_smoke_test, pull_model, start_ollama_service

    status = check_ollama(base_url)
    if not status.running:
        if not start_ollama_service(base_url):
            console.print(f"[red]Ollama service not responding at {base_url}.[/red]")
            console.print("[dim]Install: curl -fsSL https://ollama.com/install.sh | sh  ·  then: ollama serve[/dim]")
            raise typer.Exit(code=1)
        status = check_ollama(base_url)

    targets: list[str] = []
    if model:
        resolved = resolve_alias(model)
        if resolved != model:
            console.print(f"[dim]alias {model} -> {resolved}[/dim]")
        targets = [resolved]
    elif bundle_id:
        registry = load_registry()
        match = find_bundle(bundle_id, registry)
        if match is None:
            console.print(f"[red]No package '{bundle_id}'.[/red]")
            raise typer.Exit(code=1)
        targets = [r.model for r in match.roles.values()]
    else:
        settings = load_settings()
        if settings.active_bundle_id:
            match = find_bundle(settings.active_bundle_id)
            if match:
                targets = [r.model for r in match.roles.values()]
        if not targets:
            console.print("[red]Provide a model tag/alias, --bundle <id>, or set an active package (prometheus use <id>).[/red]")
            raise typer.Exit(code=1)

    for tag in targets:
        if tag in status.models:
            console.print(f"Already installed: {tag}")
        else:
            console.print(f"Pulling {tag}…")
            last = {"pct": -1}

            def on_progress(data, _last=last):
                line = format_pull_progress(data)
                pct = data.get("completed", 0) * 100 // max(data.get("total", 1), 1)
                if pct != _last["pct"] or data.get("status") in ("success", "pulling manifest"):
                    console.print(f"  {line}")
                    _last["pct"] = pct

            ok = pull_model(tag, base_url=base_url, on_progress=on_progress)
            if ok:
                console.print(f"[green]Pulled {tag}.[/green]")
            else:
                console.print(f"[red]Pull failed for {tag}. Run manually: ollama pull {tag}[/red]")
                raise typer.Exit(code=1)
        if verify:
            smoke = inference_smoke_test(tag, base_url=base_url)
            if smoke.success:
                console.print(f"[green]Inference OK[/green] on {tag}: {smoke.response[:60]}")
            else:
                console.print(f"[yellow]Inference probe did not return text: {smoke.error}[/yellow]")
                console.print("[yellow]Model is installed; longer prompts may still work.[/yellow]")


@models_app.command("inspect")
def models_inspect(
    model: str = typer.Argument(..., help="Model tag or alias (e.g. vibethinker-q2)"),
    base_url: str = typer.Option("http://127.0.0.1:11434", "--base-url"),
) -> None:
    """Show resolved tag, install status, and a one-token inference probe."""
    from .model_aliases import is_alias, resolve_alias
    from .onboarding import check_ollama, inference_smoke_test

    resolved = resolve_alias(model)
    status = check_ollama(base_url)
    installed = resolved in status.models
    console.print(Panel.fit(f"model inspect — {model}"))
    if is_alias(model):
        console.print(f"alias:   {model} -> {resolved}")
    else:
        console.print(f"tag:     {resolved}")
    console.print(f"Ollama:  {'running' if status.running else 'down'}")
    console.print(f"installed locally: {'yes' if installed else 'no'}")
    if installed and status.running:
        smoke = inference_smoke_test(resolved, base_url=base_url)
        if smoke.success:
            console.print(f"inference: [green]OK[/green] — {smoke.response[:60]}")
        else:
            console.print(f"inference: [yellow]no response[/yellow] — {smoke.error}")
    elif not installed:
        console.print("[dim]Pull with: prometheus models pull " + model + "[/dim]")


@models_app.command("unload")
def models_unload(
    model: str = typer.Argument(None, help="Model tag to evict from VRAM. Omit to evict all resident models."),
    base_url: str = typer.Option("http://127.0.0.1:11434", "--base-url"),
) -> None:
    """Evict model(s) from Ollama memory (frees VRAM; weights stay on disk)."""
    from .onboarding import check_ollama, unload_model

    status = check_ollama(base_url)
    if not status.running:
        console.print(f"[red]Ollama service not responding at {base_url}.[/red]")
        raise typer.Exit(code=1)
    if unload_model(model, base_url=base_url):
        target = model or "all resident models"
        console.print(f"[green]Unloaded {target} from VRAM.[/green] Weights remain on disk.")
    else:
        console.print("[red]Unload failed.[/red]")
        raise typer.Exit(code=1)


@mcp_app.command("list")
def mcp_list() -> None:
    """List configured MCP stdio servers."""
    from .mcp_client import MCPRegistry

    registry = _load_mcp_registry(MCPRegistry())
    servers = registry.list_servers()
    if not servers:
        console.print("[dim]No MCP servers configured.[/dim]")
        console.print("Add one with: prometheus mcp add <name> -- <command> [args…]")
        return
    console.print(Panel.fit(f"MCP servers ({len(servers)})"))
    for s in servers:
        console.print(f"  [bold]{s.name}[/bold] — trust={s.trust_level} net={s.network_scope}")
        console.print(f"    command: {' '.join(s.command)}")


@mcp_app.command("add")
def mcp_add(
    name: str = typer.Argument(..., help="Server name (alphanumeric/dash)"),
    trust_level: str = typer.Option("untrusted", "--trust", help="untrusted|trusted"),
    network_scope: str = typer.Option("none", "--network", help="none|outbound"),
    argv: list[str] = typer.Argument(..., help="Launch command after '--', e.g. -- python -m my_mcp_server"),
) -> None:
    """Register an MCP stdio server in ~/.prometheus/mcp.json."""
    import json as _json
    import re

    from .config import ensure_home

    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", name):
        console.print(f"[red]Invalid server name '{name}'.[/red]")
        raise typer.Exit(code=1)
    if not argv:
        console.print("[red]A launch command is required after '--'.[/red]")
        raise typer.Exit(code=1)
    ensure_home()
    cfg_path = ensure_home() / "mcp.json"
    data = {}
    if cfg_path.exists():
        data = _json.loads(cfg_path.read_text(encoding="utf-8"))
    servers = data.setdefault("servers", [])
    servers = [s for s in servers if s.get("name") != name]
    servers.append({
        "name": name,
        "command": argv,
        "trust_level": trust_level,
        "network_scope": network_scope,
        "env": {},
    })
    data["servers"] = servers
    cfg_path.write_text(_json.dumps(data, indent=2), encoding="utf-8")
    console.print(f"[green]Registered MCP server '{name}'.[/green] -> {cfg_path}")
    console.print("[dim]Test it with: prometheus mcp test " + name + "[/dim]")


@mcp_app.command("remove")
def mcp_remove(name: str = typer.Argument(...)) -> None:
    """Remove an MCP server from ~/.prometheus/mcp.json."""
    import json as _json

    from .config import ensure_home

    cfg_path = ensure_home() / "mcp.json"
    if not cfg_path.exists():
        console.print("[dim]No mcp.json exists.[/dim]")
        return
    data = _json.loads(cfg_path.read_text(encoding="utf-8"))
    servers = data.get("servers", [])
    before = len(servers)
    servers = [s for s in servers if s.get("name") != name]
    if len(servers) == before:
        console.print(f"[yellow]No server named '{name}'.[/yellow]")
        return
    data["servers"] = servers
    cfg_path.write_text(_json.dumps(data, indent=2), encoding="utf-8")
    console.print(f"[green]Removed MCP server '{name}'.[/green]")


@mcp_app.command("test")
def mcp_test(name: str = typer.Argument(..., help="Server name to probe")) -> None:
    """Probe an MCP server: initialize, list tools, report capabilities."""
    from .mcp_client import MCPClient, MCPError, MCPRegistry

    registry = _load_mcp_registry(MCPRegistry())
    cfg = registry.get(name)
    if cfg is None:
        console.print(f"[red]No MCP server '{name}'. Run: prometheus mcp list[/red]")
        raise typer.Exit(code=1)
    console.print(f"Launching {name}: {' '.join(cfg.command)}")
    client = MCPClient(cfg)
    try:
        info = client.initialize()
        console.print(f"[green]Initialized.[/green] server: {info.get('serverInfo', {}).get('name', '?')}")
        tools = client.list_tools()
        console.print(Panel.fit(f"Tools ({len(tools)})"))
        for t in tools:
            console.print(f"  [bold]{t.name}[/bold] — {t.description[:80]}")
        if tools:
            console.print("[dim]Output is delimited as untrusted data; it cannot alter system policy.[/dim]")
    except MCPError as exc:
        console.print(f"[red]MCP error: {exc}[/red]")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[red]Failed to start/communicate: {exc}[/red]")
        raise typer.Exit(code=1)
    finally:
        client.close()


@browser_app.command("test")
def browser_test(
    url: str = typer.Argument(..., help="URL to open (http(s):// or file://)"),
    screenshot: Path | None = typer.Option(None, "--screenshot", help="Save a PNG to this path"),
    headless: bool = typer.Option(True, "--headless/--headed"),
) -> None:
    """Open a URL in Playwright, collect console/network evidence, optionally screenshot."""
    try:
        from .browser import BrowserTools
    except ImportError:
        console.print("[red]Playwright not installed. pip install 'prometheus-local-agent[browser]' && playwright install chromium[/red]")
        raise typer.Exit(code=1)
    try:
        tools = BrowserTools(headless=headless)
        nav = tools.navigate(url)
        console.print(nav)
        evidence = tools.collect_evidence()
        console.print(Panel(evidence.summary(), title="browser evidence"))
        if screenshot:
            png_b64 = tools.screenshot()
            import base64

            screenshot.write_bytes(base64.b64decode(png_b64.split("base64 ")[-1]) if "base64" in png_b64 else b"")
            console.print(f"[green]Screenshot:[/green] {screenshot}")
        if evidence.console_errors:
            console.print(f"[yellow]{len(evidence.console_errors)} console error(s) detected.[/yellow]")
            raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[red]Browser test failed: {exc}[/red]")
        raise typer.Exit(code=1)
    finally:
        try:
            tools.close()
        except Exception:
            pass


def _load_mcp_registry(registry):
    """Load ~/.prometheus/mcp.json into the registry if present."""
    import json as _json

    from .config import ensure_home

    cfg = ensure_home() / "mcp.json"
    if cfg.exists():
        try:
            data = _json.loads(cfg.read_text(encoding="utf-8"))
            registry.load_from_config(data.get("servers", []))
        except (ValueError, OSError):
            pass
    return registry


app.add_typer(models_app, name="models")
app.add_typer(mcp_app, name="mcp")
app.add_typer(browser_app, name="browser")
app.add_typer(bundles_app, name="bundles")
app.add_typer(sandbox_app, name="sandbox")
app.add_typer(provider_app, name="provider")


@sandbox_app.command("doctor")
def sandbox_doctor() -> None:
    """Report which sandbox tiers are available on this host."""
    from .sandbox import docker_available, tier_available

    console.print(Panel.fit("PROMETHEUS sandbox doctor"))
    for tier in ("off", "basic", "docker", "native"):
        ok, reason = tier_available(tier)
        mark = "[green]available[/green]" if ok else "[red]unavailable[/red]"
        console.print(f"  {tier:<7} {mark} — {reason}")
    console.print(f"\ndocker binary: {'present' if docker_available() else 'absent'}")
    console.print("[dim]Run 'prometheus sandbox test --workspace <dir> --all' to exercise enforcement.[/dim]")


@sandbox_app.command("test")
def sandbox_test(
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
    bundle: Path | None = typer.Option(None, "--bundle", exists=True, readable=True,
                                       help="Bundle YAML; its controller model is used for the Ollama inference test"),
    model: str = typer.Option(None, "--model", help="Override the Ollama model tag for the inference test"),
    base_url: str = typer.Option("http://127.0.0.1:11434", "--base-url"),
    all_optional: bool = typer.Option(False, "--all", help="Include docker/native/browser/ollama optional tests"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Run the sandbox enforcement suite and write .prometheus/sandbox-test-report.json."""
    from .sandbox_test import run_suite

    ollama_model = model
    if not ollama_model and bundle:
        ollama_model = load_bundle(bundle).controller_spec().model
    report = run_suite(workspace, ollama_model=ollama_model, base_url=base_url, include_optional=all_optional)
    if json_output:
        import json as _json

        print(_json.dumps(report.to_dict(), indent=2))
    else:
        console.print(Panel.fit(f"Sandbox Test Suite — {workspace}"))
        for r in report.results:
            color = {"PASS": "green", "FAIL": "red", "SKIP": "yellow"}[r.status]
            req = "" if r.required else " (optional)"
            console.print(f"  {r.name:<38} [{color}]{r.status}[/{color}]{req}  {r.detail[:60]}")
        console.print(Panel.fit(
            f"passed={report.passed} failed={report.failed} skipped={report.skipped} ok={report.ok}"))
    if not json_output:
        console.print(f"[dim]report -> {workspace}/.prometheus/sandbox-test-report.json[/dim]")
    if not report.ok:
        raise typer.Exit(code=1)


@provider_app.command("smoke")
def provider_smoke(
    provider: str = typer.Option("ollama", "--provider", help="Provider preset id (ollama, openai, mistral, ...)"),
    model: str = typer.Option(..., "--model", help="Model tag to probe"),
    base_url: str = typer.Option("http://127.0.0.1:11434", "--base-url", help="Override endpoint (Ollama/local)"),
    timeout: float = typer.Option(30.0, "--timeout", help="Per-request timeout seconds"),
) -> None:
    """Probe a provider: health, list models, one completion, unload. Bounded by --timeout."""
    import httpx
    from .providers.presets import preset

    p = preset(provider)
    label = p.label if p else provider
    endpoint = base_url if provider in {"ollama", "llama-cpp"} else (p.base_url if p else base_url)
    console.print(Panel.fit(f"provider smoke — {label} @ {endpoint}"))

    client = httpx.Client(timeout=timeout)
    failures: list[str] = []
    try:
        try:
            r = client.get(f"{endpoint.rstrip('/')}/api/tags" if provider == "ollama" else f"{endpoint.rstrip('/')}/models")
            health_ok = r.status_code == 200
            console.print(f"  health: {'OK' if health_ok else 'FAIL'} (HTTP {r.status_code})")
            if not health_ok:
                failures.append("health")
        except httpx.HTTPError as exc:
            console.print(f"  health: [red]FAIL[/red] — {exc}")
            failures.append("health")

        try:
            if provider == "ollama":
                r = client.get(f"{endpoint.rstrip('/')}/api/tags")
                models = [m.get("name", "") for m in r.json().get("models", [])]
            else:
                r = client.get(f"{endpoint.rstrip('/')}/models")
                models = [m.get("id", "") for m in r.json().get("data", [])]
            console.print(f"  list_models: {len(models)} models{' (includes target)' if model in models else ' (target MISSING)'}")
        except (httpx.HTTPError, ValueError) as exc:
            console.print(f"  list_models: [red]FAIL[/red] — {exc}")
            failures.append("list_models")

        try:
            if provider == "ollama":
                payload = {"model": model, "prompt": "Reply with exactly: PROMETHEUS_SANDBOX_READY", "stream": False}
                r = client.post(f"{endpoint.rstrip('/')}/api/generate", json=payload)
            else:
                payload = {"model": model, "messages": [{"role": "user", "content": "Reply with exactly: PROMETHEUS_SANDBOX_READY"}], "stream": False}
                r = client.post(f"{endpoint.rstrip('/')}/chat/completions", json=payload)
            content = ""
            if r.status_code == 200:
                data = r.json()
                content = data.get("response", "") or (data.get("choices", [{}])[0].get("message", {}).get("content", ""))
            redacted = content.replace(model, "<model>")[:80]
            mark = "OK" if "PROMETHEUS_SANDBOX_READY" in content or content.strip() else "NOKEY"
            console.print(f"  completion: {mark} — '{redacted}'")
            if not content.strip():
                failures.append("completion")
        except httpx.HTTPError as exc:
            console.print(f"  completion: [red]FAIL[/red] — {exc}")
            failures.append("completion")

        if provider == "ollama":
            try:
                r = client.post(f"{endpoint.rstrip('/')}/api/generate", json={"model": model, "keep_alive": 0})
                console.print(f"  unload (keep_alive=0): {'OK' if r.status_code == 200 else 'FAIL'}")
            except httpx.HTTPError as exc:
                console.print(f"  unload: [red]FAIL[/red] — {exc}")
    finally:
        client.close()
    console.print(Panel.fit(f"smoke result: {'PASS' if not failures else 'FAIL — ' + ', '.join(failures)}"))
    if failures:
        raise typer.Exit(code=1)


@astronaut_app.command("start")
def astronaut_start(
    objective: str = typer.Argument(..., help="Outcome the astronaut must achieve"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
    bundle: Path | None = typer.Option(None, "--bundle", exists=True, readable=True),
    max_steps: int = typer.Option(0, "--max-steps", help="0 = unlimited"),
    max_runtime: int = typer.Option(0, "--max-runtime", help="minutes, 0 = unlimited"),
    checkpoint_every: int = typer.Option(5, "--checkpoint-every", help="checkpoint every N attempts"),
    yes: bool = typer.Option(False, "--yes", help="Auto-approve mode-allowed actions (noninteractive)"),
) -> None:
    """Start a long-running autonomous (astronaut-mode) session.

    Runs until the verifier accepts, the step/runtime budget is hit, or a stop
    is requested via `prometheus astronaut stop` (writes .prometheus/STOP)."""
    from .agent import ArenaLoop, MicroStepEngine, make_default_verify
    from .astronaut import AstronautController
    from .memory import Intent, ProjectMemoryStore
    from .providers import create_provider
    from .tools.workspace import WorkspaceTools

    settings = load_settings()
    settings.mode = AutonomyMode.ASTRONAUT
    settings.workspace = workspace.resolve()
    if max_steps:
        settings.max_steps = max_steps
    if max_runtime:
        settings.max_runtime_minutes = max_runtime
    bundle_path = bundle or settings.bundle_file
    if not bundle_path:
        console.print("[red]No bundle configured. Run 'prometheus setup' or pass --bundle.[/red]")
        raise typer.Exit(code=1)
    bundle_obj = load_bundle(bundle_path)
    controller_spec = bundle_obj.for_role("controller")
    forge = create_provider(controller_spec)
    envoy = create_provider(controller_spec)
    argus = None
    if settings.multi_agent_review:
        try:
            argus = create_provider(bundle_obj.for_role("reviewer"))
        except KeyError:
            argus = create_provider(controller_spec)
    mem = ProjectMemoryStore(workspace)
    mem.set_intent(Intent(objective=objective, success_criteria=[]))
    tools = WorkspaceTools(workspace)
    approve = (lambda _c, _r: True) if yes else _approval
    engine = MicroStepEngine(store=mem, tools=tools, settings=settings, approve=approve)
    arena = ArenaLoop(store=mem, tools=tools, engine=engine)
    verify = make_default_verify(workspace)
    providers = {"envoy": envoy, "forge": forge, "argus": argus}
    controller = AstronautController(
        store=mem, tools=tools, arena=arena, providers=providers, verify=verify,
        workspace=workspace, objective=objective,
        max_steps=max_steps, max_runtime_minutes=max_runtime,
        checkpoint_every_attempts=checkpoint_every,
    )
    console.print(Panel.fit(f"PROMETHEUS astronaut — long-run autonomous mode\nObjective: {objective}"))
    result = controller.run(on_update=lambda line: console.print(f"[cyan]{line}[/cyan]"))
    verdict = "[green]COMPLETE[/green]" if result.accepted else f"[yellow]{result.state.status.upper()}[/yellow]"
    console.print(Panel(
        f"accepted={result.accepted} · attempts={result.state.macro_attempts} · "
        f"checkpoints={result.state.checkpoints} · reason={result.reason}",
        title=f"{verdict} — astronaut",
    ))


@astronaut_app.command("status")
def astronaut_status(
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
) -> None:
    """Show the current astronaut session state."""
    from .astronaut import read_state

    state = read_state(workspace)
    stop = (workspace / ".prometheus" / "STOP").exists()
    pause = (workspace / ".prometheus" / "PAUSE").exists()
    console.print(Panel.fit("PROMETHEUS astronaut status"))
    console.print(f"Status: [bold]{state.status}[/bold]")
    console.print(f"Objective: {state.objective or '(none)'}")
    console.print(f"Macro attempts: {state.macro_attempts}")
    console.print(f"Checkpoints: {state.checkpoints}")
    console.print(f"Final status: {state.final_status or '(in progress)'}")
    console.print(f"Stop file: {'present' if stop else 'absent'}")
    console.print(f"Pause file: {'present' if pause else 'absent'}")
    if state.last_heartbeat:
        age = max(0, int(time.time() - state.last_heartbeat))
        console.print(f"Last heartbeat: {age}s ago")


@astronaut_app.command("pause")
def astronaut_pause(
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
) -> None:
    """Pause the running astronaut session (writes .prometheus/PAUSE)."""
    from .astronaut import request_pause

    p = request_pause(workspace)
    console.print(f"[green]Pause requested.[/green] -> {p}")
    console.print("[dim]The astronaut process will halt at the next safe point.[/dim]")


@astronaut_app.command("resume")
def astronaut_resume(
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
) -> None:
    """Resume a paused astronaut session (clears .prometheus/PAUSE)."""
    from .astronaut import clear_pause

    if clear_pause(workspace):
        console.print("[green]Resumed.[/green] Pause file cleared.")
    else:
        console.print("[dim]No pause file present.[/dim]")


@astronaut_app.command("stop")
def astronaut_stop(
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
) -> None:
    """Stop the running astronaut session (writes .prometheus/STOP)."""
    from .astronaut import request_stop

    p = request_stop(workspace)
    console.print(f"[green]Stop requested.[/green] -> {p}")
    console.print("[dim]The astronaut process will exit at the next safe point.[/dim]")


app.add_typer(astronaut_app, name="astronaut")


if __name__ == "__main__":
    app()

