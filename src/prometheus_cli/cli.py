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
from .resources import resolve_bundles_v1_dir
from .session import SessionStore

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
    bundles_dir: Path | None = typer.Option(None, "--bundles-dir", help="Override bundles directory (default: auto-resolve)"),
    mode: AutonomyMode = typer.Option(AutonomyMode.PILOT),
    bundle_name: str | None = typer.Option(None, "--bundle", help="Pre-select a bundle (non-interactive)"),
    yes: bool = typer.Option(False, "--yes", help="Accept defaults without prompting"),
    pull: bool = typer.Option(False, "--pull", help="Pull model files via Ollama after setup"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show detected hardware and available bundles; change nothing"),
) -> None:
    """Detect hardware, recommend a bundle, and configure PROMETHEUS."""
    resolved_bundles_dir = resolve_bundles_v1_dir(explicit=bundles_dir)
    report = detect_hardware()
    console.print(Panel.fit("PROMETHEUS setup"))
    console.print(f"OS: {report.os} {report.architecture}" + (" (WSL)" if report.wsl else ""))
    console.print(f"RAM: {report.ram_gb} GB | Disk free: {report.disk_free_gb} GB")
    if report.gpu_vendor:
        console.print(f"GPU: {report.gpu_name or report.gpu_vendor} ({report.vram_gb} GB VRAM)")
    else:
        console.print("GPU: CPU mode")
    console.print(f"[dim]Bundles dir: {resolved_bundles_dir}[/dim]")
    for note in report.notes:
        console.print(f"[dim]• {note}[/dim]")

    if dry_run:
        ollama = check_ollama()
        console.print(f"\nOllama: {'ready' if ollama.running else 'not running'} "
                      f"({len(ollama.models)} models)")
        options = list_available_bundles(resolved_bundles_dir)
        if not options:
            console.print("[red]No bundles found.[/red]")
            raise typer.Exit(code=1)
        default = pick_default_bundle(options, report)
        for opt in options:
            if opt is not default:
                opt.fits, opt.reason = classify_bundle_fit(opt.bundle, report)
        console.print(f"\n[bold]Available bundles ({len(options)}):[/bold]")
        for idx, opt in enumerate(options, 1):
            marker = " (recommended)" if opt is default else ""
            fit_label = "[green]fits[/green]" if opt.fits else "[red]does not fit[/red]"
            console.print(f"  {idx}. {opt.name}{marker} — {fit_label}: {opt.reason}")
        if default:
            console.print(f"\n[bold]Dry run complete.[/bold] Would select: {default.name}")
        else:
            console.print("\n[bold]Dry run complete.[/bold] No recommendation for this hardware.")
        console.print("[dim]No files written, no models pulled.[/dim]")
        raise typer.Exit(code=0)

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

    options = list_available_bundles(resolved_bundles_dir)
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
def telemetry(
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
    gpu_timeout: float = typer.Option(1.5, "--gpu-timeout", help="Max seconds for nvidia-smi/rocm-smi"),
    no_color: bool = typer.Option(False, "--no-color", help="Strip color from bars"),
) -> None:
    """Live CPU/RAM/disk/GPU/VRAM/Ollama/git/sandbox snapshot."""
    from .telemetry import collect_snapshot, render_telemetry_lines

    snapshot = collect_snapshot(
        workspace=str(workspace), gpu_timeout_s=gpu_timeout, cpu_interval_s=0.1
    )
    if json_output:
        console.print(snapshot.as_json())
        return
    console.print(Panel.fit("PROMETHEUS telemetry"))
    lines = render_telemetry_lines(snapshot)
    for line in lines:
        if no_color:
            stripped = line.replace("[bold]", "").replace("[/bold]", "")
            for tag in ("yellow", "green", "red", "dim", "cyan", "magenta"):
                stripped = stripped.replace(f"[{tag}]", "").replace(f"[/{tag}]", "")
            console.print(stripped)
        else:
            console.print(line)


@app.command()
def diagnose(
    since: str = typer.Option(None, "--since", help="Window like '30m', '2h', '1d' (default: all)"),
    export: Path | None = typer.Option(None, "--export", help="Write a diagnostics zip to this path"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """Collect sanitized PROMETHEUS diagnostics (versions, config, errors, git, ollama)."""
    from .diagnostics import collect_diagnostics, export_zip, render_diagnostics_lines

    diag = collect_diagnostics(since_str=since)
    if export:
        out = export_zip(diag, export)
        console.print(f"[green]Exported:[/green] {out}")
        return
    if json_output:
        import json as _json
        console.print(_json.dumps(diag, indent=2, default=str))
        return
    console.print(Panel.fit("PROMETHEUS diagnose"))
    for line in render_diagnostics_lines(diag):
        console.print(line)


@app.command()
def tui(
    bundle: Path | None = typer.Option(None, "--bundle", exists=True, readable=True),
    workspace: Path = typer.Option(Path.cwd(), exists=True, file_okay=False),
    no_animation: bool = typer.Option(False, "--no-animation", help="Skip the startup splash animation"),
    demo: bool = typer.Option(
        False, "--demo",
        help="Run in fully-mocked demo mode (no Ollama, no cloud, no real state). For UI preview and tests.",
    ),
    screenshot: Path | None = typer.Option(
        None, "--screenshot",
        help="Export an SVG screenshot of the initial screen to PATH and exit (headless). Implies --no-animation.",
    ),
    screen: str | None = typer.Option(
        None, "--screen",
        help="Initial screen to show or screenshot: 'main' | 'setup' | 'help' | 'models' | 'sandbox' | ...",
    ),
    exit_after_render: bool = typer.Option(
        False, "--exit-after-render",
        help="Run headless, compose once, then exit (for CI smoke tests). No SVG file written.",
    ),
    submit_objective: str | None = typer.Option(
        None, "--submit-objective",
        help="Auto-submit an objective after mount (for testing). Use with --demo or --exit-after-render.",
    ),
) -> None:
    """Launch the interactive Textual TUI (PROMETHEUS application shell)."""
    try:
        from .tui import launch_tui
    except ImportError:
        console.print("[red]Textual is not installed. Install with: pip install 'prometheus-local-agent[tui]'[/red]")
        raise typer.Exit(code=1)

    settings = load_settings()
    bundle_path = bundle or settings.bundle_file
    if not demo and screenshot is None and not exit_after_render and not bundle_path and not submit_objective:
        console.print("[yellow]No bundle configured yet — opening TUI setup.[/yellow]")
        console.print("[dim]Use /setup or /bundles inside the TUI to pick a package.[/dim]")

    disable_anim = no_animation or settings.reduced_motion or screenshot is not None or exit_after_render

    if disable_anim is False:
        try:
            from .splash import pick_size_for_terminal, play as play_splash, should_animate
            if should_animate(no_animation=disable_anim):
                play_splash(pick_size_for_terminal(), duration_s=1.0, fps=12)
        except Exception:
            pass

    launch_tui(
        bundle_path=bundle_path,
        workspace=workspace,
        no_animation=disable_anim,
        demo=demo,
        screenshot_path=screenshot,
        initial_screen=screen if screen and screen != "main" else None,
        exit_after_render=exit_after_render,
        submit_objective=submit_objective,
    )


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
            "installed": "[bold green]installed[/bold green]",
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
            pulled = " [green]installed[/green]" if spec.model in ollama.models else ""
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
rag_app = typer.Typer(help="Local RAG document memory")
browser_app = typer.Typer(help="Browser automation (Playwright)")
astronaut_app = typer.Typer(help="Long-running autonomous sessions")
sandbox_app = typer.Typer(help="Sandbox doctor + enforcement test suite")
provider_app = typer.Typer(help="Provider smoke probes")
vision_app = typer.Typer(help="Vision element inspection (Playwright + computed CSS)")
assets_app = typer.Typer(help="AssetForge — local image generation package")
logo_app = typer.Typer(help="PROMETHEUS brand logo preview and generation")


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
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation for large downloads (>2 GB)"),
) -> None:
    """Pull a model (or a whole bundle's roles) via Ollama with live progress."""
    from .model_aliases import resolve_alias
    from .onboarding import check_ollama, format_pull_progress, inference_smoke_test, pull_model, start_ollama_service
    from .pull_policy import confirm_large_pull, requires_pull_confirmation

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

    to_pull = [t for t in targets if t not in status.models]
    if to_pull:
        needs, size, largest = requires_pull_confirmation(to_pull)
        if needs:
            console.print(
                f"[yellow]Large download warning:[/yellow] {largest} is ~{size:.1f} GB "
                f"(threshold >2 GB)."
            )
        if not confirm_large_pull(to_pull, yes=yes):
            console.print("[yellow]Pull cancelled — no models downloaded.[/yellow]")
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


@mcp_app.command("templates")
def mcp_templates() -> None:
    """List available MCP server templates."""
    from .mcp_templates import list_templates

    templates = list_templates()
    if not templates:
        console.print("[dim]No MCP templates available.[/dim]")
        return
    console.print(Panel.fit(f"MCP templates ({len(templates)})"))
    for tid in templates:
        console.print(f"  • {tid}")


@mcp_app.command("template")
def mcp_template(
    action: str = typer.Argument(..., help="inspect|install"),
    name: str = typer.Argument(..., help="Template id (e.g. whatsapp-starter)"),
) -> None:
    """Inspect or install an MCP server template."""
    from .mcp_templates import install_template, list_templates, load_template
    from .config import ensure_home

    if action == "inspect":
        try:
            template = load_template(name)
        except FileNotFoundError:
            console.print(f"[red]Template '{name}' not found.[/red] Available: {', '.join(list_templates())}")
            raise typer.Exit(code=1)
        console.print(Panel.fit(f"{template.name} ({template.id})"))
        console.print(template.description)
        if template.warning:
            console.print(f"\n[yellow]WARNING:[/yellow] {template.warning}")
        console.print("\n[bold]Servers:[/bold]")
        for s in template.servers:
            console.print(f"  {s.name}: {' '.join(s.command)}")
            console.print(f"    trust={s.trust_level} network={s.network_scope}")
        if template.setup_steps:
            console.print("\n[bold]Setup steps:[/bold]")
            for step in template.setup_steps:
                console.print(f"  • {step}")
    elif action == "install":
        home = ensure_home()
        mcp_path = home / "mcp.json"
        try:
            result = install_template(name, mcp_path)
        except FileNotFoundError:
            console.print(f"[red]Template '{name}' not found.[/red]")
            raise typer.Exit(code=1)
        console.print(f"[green]Installed MCP template '{name}' -> {result}[/green]")
        console.print("[dim]Verify with: prometheus mcp list[/dim]")
    else:
        console.print(f"[red]Unknown action '{action}'.[/red] Use: inspect|install")
        raise typer.Exit(code=1)


@rag_app.command("init")
def rag_init(
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
) -> None:
    """Initialize local RAG storage in .prometheus/rag/."""
    from .rag import RagStore

    store = RagStore(workspace)
    path = store.init()
    console.print(f"[green]RAG initialized:[/green] {path}")
    console.print("Ingest documents with: prometheus rag ingest <path>")


@rag_app.command("ingest")
def rag_ingest(
    source: Path = typer.Argument(..., help="File or directory to ingest"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
) -> None:
    """Ingest documents into the local RAG index."""
    from .rag import RagStore

    store = RagStore(workspace)
    if not store.is_initialized():
        store.init()
    result = store.ingest(source)
    if "error" in result:
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]Ingested:[/green] {result['ingested']} files, {result['chunks']} chunks")
    if result['skipped']:
        console.print(f"[dim]Skipped {result['skipped']} already-ingested files.[/dim]")


@rag_app.command("query")
def rag_query(
    text: str = typer.Argument(..., help="Query text"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
    json_output: bool = typer.Option(False, "--json"),
    limit: int = typer.Option(5, "--limit"),
) -> None:
    """Query the local RAG index."""
    from .rag import RagStore

    store = RagStore(workspace)
    if not store.is_initialized():
        console.print("[yellow]RAG not initialized. Run: prometheus rag init[/yellow]")
        raise typer.Exit(code=1)
    results = store.query(text, limit=limit)
    if not results:
        console.print("[dim]No matching documents found.[/dim]")
        return
    if json_output:
        import json as _json
        print(_json.dumps([r.as_dict() for r in results], indent=2))
        return
    console.print(Panel.fit(f"RAG query: {text}"))
    for i, r in enumerate(results, 1):
        console.print(f"\n[bold]{i}.[/bold] [dim]{r.source}[/dim] (score: {r.score:.0%})")
        console.print(f"  {r.text[:200]}...")


@rag_app.command("status")
def rag_status(
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show RAG index status."""
    from .rag import RagStore

    store = RagStore(workspace)
    st = store.status()
    if json_output:
        import json as _json
        print(_json.dumps(st.as_dict(), indent=2))
        return
    if not st.initialized:
        console.print("[yellow]RAG not initialized.[/yellow] Run: prometheus rag init")
        return
    console.print(Panel.fit("PROMETHEUS RAG"))
    console.print(f"Sources: {st.sources}")
    console.print(f"Chunks:  {st.chunks}")
    console.print(f"Chars:   {st.total_chars:,}")
    console.print(f"Index:   {st.index_path}")


@rag_app.command("reset")
def rag_reset(
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
    confirm: bool = typer.Option(False, "--confirm"),
) -> None:
    """Clear the RAG index."""
    from .rag import RagStore

    if not confirm:
        console.print("[yellow]Pass --confirm to actually reset.[/yellow]")
        raise typer.Exit(code=1)
    store = RagStore(workspace)
    if store.reset():
        console.print("[green]RAG index cleared.[/green]")
    else:
        console.print("[dim]No RAG index to clear.[/dim]")


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
app.add_typer(rag_app, name="rag")
app.add_typer(browser_app, name="browser")
app.add_typer(bundles_app, name="bundles")
app.add_typer(sandbox_app, name="sandbox")
app.add_typer(provider_app, name="provider")


bundleforge_app = typer.Typer(help="BundleForge — create, validate, and install custom bundles", invoke_without_command=True)


@bundleforge_app.callback()
def bundleforge_default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        console.print(Panel.fit("PROMETHEUS BundleForge"))
        console.print("Create, adapt, validate, and install custom model bundles.")
        console.print("\n[bold]Commands:[/bold]")
        console.print("  recommend  Recommend a bundle from a natural-language request")
        console.print("  wizard     Interactive bundle creation wizard")
        console.print("  create     Create a bundle from a template")
        console.print("  inspect    Show full details of a bundle or template")
        console.print("  validate   Validate a bundle file or template")
        console.print("  install    Install a bundle into ~/.prometheus")
        console.print("  export     Export a bundle as a shareable folder")
        console.print("  search     Search templates and catalog by keyword")


@bundleforge_app.command("recommend")
def bundleforge_recommend(
    request: str = typer.Argument(..., help="Natural-language description of what you want to build"),
    quality: bool = typer.Option(False, "--quality", help="Prefer higher-quality models when available"),
    commercial_only: bool = typer.Option(True, "--commercial-safe/--allow-noncommercial", help="Require commercial-safe models"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Recommend a bundle from a natural-language request."""
    from .bundleforge import load_catalog, recommend

    catalog = load_catalog()
    report = detect_hardware()
    result = recommend(request, hardware=report, prefer_quality=quality, commercial_safe_only=commercial_only, catalog=catalog)

    if json_output:
        import json as _json
        print(_json.dumps({
            "use_case": result.use_case,
            "template_id": result.template_id,
            "bundle_id": result.bundle.id,
            "bundle_name": result.bundle.name,
            "confidence": round(result.confidence, 2),
            "matched_keywords": result.matched_keywords,
            "hardware_fit": result.hardware_fit,
            "roles": {r: s.model for r, s in result.bundle.roles.items()},
            "optional": result.bundle.optional,
            "requirements": {
                "min_ram_gb": result.bundle.requirements.min_ram_gb,
                "min_vram_gb": result.bundle.requirements.min_vram_gb,
            },
            "license_warnings": result.license_warnings,
            "alternatives": result.alternatives[:5],
        }, indent=2))
        return

    console.print(Panel.fit("BundleForge recommendation"))
    console.print(f"Request: [dim]{request}[/dim]")
    console.print(f"Use case: [bold]{result.use_case}[/bold]")
    if result.matched_keywords:
        console.print(f"Matched: {', '.join(result.matched_keywords)}")
    console.print(f"Confidence: {result.confidence:.0%}")
    console.print(f"\n[bold]Recommended: {result.bundle.name}[/bold] ({result.template_id})")
    console.print(f"  {result.bundle.description}")
    console.print("\n[bold]Roles:[/bold]")
    for role, spec in result.bundle.roles.items():
        console.print(f"  {role}: {spec.model}")
    if result.bundle.optional:
        console.print("\n[bold]Optional:[/bold]")
        for cap, model in result.bundle.optional.items():
            console.print(f"  {cap}: {model}")
    console.print(f"\n[bold]Requirements:[/bold] {result.bundle.requirements.min_ram_gb} GB RAM, "
                  f"{result.bundle.requirements.min_vram_gb} GB VRAM")
    for reason in result.fit_reasons:
        console.print(f"  [dim]• {reason}[/dim]")
    if result.license_warnings:
        console.print("\n[yellow]License warnings:[/yellow]")
        for w in result.license_warnings:
            console.print(f"  [yellow]• {w}[/yellow]")
    console.print(f"\n[dim]Install with: prometheus bundleforge create --template {result.template_id}[/dim]")


@bundleforge_app.command("wizard")
def bundleforge_wizard(
    yes: bool = typer.Option(False, "--yes", help="Accept all defaults non-interactively"),
    out: Path = typer.Option(Path(".prometheus/bundles"), "--out", help="Output directory"),
) -> None:
    """Interactive bundle creation wizard."""
    from .bundleforge import WizardAnswers, run_wizard, save_bundle
    from rich.prompt import Confirm, Prompt

    defaults = WizardAnswers()
    if yes:
        defaults.use_case = "web development"
        answers, bundle = run_wizard(defaults=defaults)
    else:
        answers, bundle = run_wizard(
            prompt_fn=lambda msg, default: Prompt.ask(msg, default=default),
            confirm_fn=lambda msg, default: Confirm.ask(msg, default=default),
        )
    console.print(Panel.fit(f"Created: {bundle.name}"))
    bundle_path = save_bundle(bundle, out / bundle.id)
    console.print(f"[green]Saved:[/green] {bundle_path}")
    console.print(f"Next: prometheus bundleforge validate '{bundle_path}'")
    console.print(f"Then: prometheus bundleforge install '{bundle_path}'")


@bundleforge_app.command("create")
def bundleforge_create(
    template: str = typer.Argument(..., help="Template id (e.g. game-dev-lite)"),
    out: Path = typer.Option(Path(".prometheus/bundles"), "--out", help="Output directory"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing output"),
) -> None:
    """Create a bundle from a template."""
    from .bundleforge import load_template, save_bundle

    try:
        bundle = load_template(template)
    except FileNotFoundError:
        console.print(f"[red]Template '{template}' not found.[/red]")
        from .bundleforge import list_templates
        console.print(f"Available: {', '.join(list_templates())}")
        raise typer.Exit(code=1)
    target = out / bundle.id
    if target.exists() and not force:
        console.print(f"[yellow]'{target}' already exists. Use --force to overwrite.[/yellow]")
        raise typer.Exit(code=1)
    path = save_bundle(bundle, target)
    console.print(f"[green]Created:[/green] {path}")
    console.print(f"Template: {template}")
    console.print(f"Roles: {', '.join(bundle.roles.keys())}")
    if bundle.optional:
        console.print(f"Optional: {', '.join(bundle.optional.keys())}")


@bundleforge_app.command("inspect")
def bundleforge_inspect(
    target: str = typer.Argument(..., help="Template id or path to bundle.yaml"),
) -> None:
    """Show full details of a bundle or template."""
    from .bundleforge import list_templates, load_forge_bundle, load_template

    path = Path(target)
    if path.is_file():
        bundle = load_forge_bundle(path)
    elif target in list_templates():
        bundle = load_template(target)
    else:
        console.print(f"[red]'{target}' is not a file or known template.[/red]")
        console.print(f"Templates: {', '.join(list_templates())}")
        raise typer.Exit(code=1)

    console.print(Panel.fit(f"{bundle.name} ({bundle.id})"))
    console.print(bundle.description)
    console.print(f"version: {bundle.version} · use_case: {bundle.use_case}")
    console.print(f"commercial_safe: {bundle.commercial_safe}")
    console.print("\n[bold]Roles:[/bold]")
    for role, spec in bundle.roles.items():
        console.print(f"  {role}: {spec.model} ({spec.provider})")
    if bundle.optional:
        console.print("\n[bold]Optional capabilities:[/bold]")
        for cap, model in bundle.optional.items():
            console.print(f"  {cap}: {model}")
    console.print(f"\n[bold]Requirements:[/bold] {bundle.requirements.min_ram_gb} GB RAM, "
                  f"{bundle.requirements.min_vram_gb} GB VRAM, "
                  f"{bundle.requirements.min_disk_gb} GB disk")
    console.print("\n[bold]Permissions:[/bold]")
    console.print(f"  network: {bundle.permissions.network}")
    console.print(f"  package_install: {bundle.permissions.package_install}")
    console.print(f"  browser: {bundle.permissions.browser}")
    console.print(f"  assets: {bundle.permissions.assets}")
    console.print(f"  external_directory: {bundle.permissions.external_directory}")
    if bundle.license_notes:
        console.print(f"\n[bold]License notes:[/bold] {bundle.license_notes}")


@bundleforge_app.command("validate")
def bundleforge_validate(
    target: str = typer.Argument(..., help="Template id or path to bundle.yaml"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Validate a bundle file or template."""
    from .bundleforge import validate_file, validate_template

    path = Path(target)
    if path.is_file():
        result = validate_file(path)
    else:
        result = validate_template(target)

    if json_output:
        import json as _json
        print(_json.dumps({
            "valid": result.valid,
            "errors": result.errors,
            "warnings": result.warnings,
        }, indent=2))
        return

    status = "[green]VALID[/green]" if result.passed else "[red]INVALID[/red]"
    console.print(Panel.fit(f"Validation: {status}"))
    if result.errors:
        console.print("[red]Errors:[/red]")
        for e in result.errors:
            console.print(f"  [red]✗[/red] {e}")
    if result.warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for w in result.warnings:
            console.print(f"  [yellow]![/yellow] {w}")
    if result.passed and not result.warnings:
        console.print("[green]All checks passed with no warnings.[/green]")
    if not result.passed:
        raise typer.Exit(code=1)


@bundleforge_app.command("install")
def bundleforge_install(
    target: str = typer.Argument(..., help="Template id or path to bundle.yaml"),
    force: bool = typer.Option(False, "--force", help="Overwrite if already installed"),
) -> None:
    """Install a bundle into ~/.prometheus/bundles/."""
    import yaml as _yaml

    from .config import ensure_home
    from .bundleforge import list_templates, load_forge_bundle, load_template

    path = Path(target)
    if path.is_file():
        bundle = load_forge_bundle(path)
    elif target in list_templates():
        bundle = load_template(target)
    else:
        console.print(f"[red]'{target}' is not a file or known template.[/red]")
        raise typer.Exit(code=1)

    home = ensure_home()
    dest_dir = home / "bundles"
    dest_dir.mkdir(exist_ok=True)
    v2_path = dest_dir / f"{bundle.id}.yaml"

    if v2_path.exists() and not force:
        console.print(f"[yellow]'{bundle.id}' is already installed. Use --force to overwrite.[/yellow]")
        raise typer.Exit(code=1)

    v2_data = bundle.to_v2_dict()
    v2_path.write_text(_yaml.safe_dump(v2_data, sort_keys=False), encoding="utf-8")
    console.print(f"[green]Installed:[/green] {bundle.id} -> {v2_path}")
    console.print(f"Activate with: prometheus use {bundle.id}")


@bundleforge_app.command("export")
def bundleforge_export(
    target: str = typer.Argument(..., help="Template id or path to bundle.yaml"),
    out: Path = typer.Option(Path("exported-bundle"), "--out", "-o", help="Output directory"),
) -> None:
    """Export a bundle as a shareable folder."""
    from .bundleforge import list_templates, load_forge_bundle, load_template, save_bundle

    path = Path(target)
    if path.is_file():
        bundle = load_forge_bundle(path)
    elif target in list_templates():
        bundle = load_template(target)
    else:
        console.print(f"[red]'{target}' is not a file or known template.[/red]")
        raise typer.Exit(code=1)

    out_dir = out / bundle.id
    bundle_path = save_bundle(bundle, out_dir)
    console.print(f"[green]Exported:[/green] {out_dir}")
    console.print(f"  bundle.yaml: {bundle_path}")
    console.print(f"  README.md: {out_dir / bundle.id / 'README.md'}")
    console.print(f"  LICENSE_NOTES.md: {out_dir / bundle.id / 'LICENSE_NOTES.md'}")
    console.print("[dim]Share the folder or zip it. No secrets are included.[/dim]")


@bundleforge_app.command("search")
def bundleforge_search(
    query: str = typer.Argument(..., help="Search keywords (e.g. 'game', 'rag', 'cpu')"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Search templates and model catalog by keyword."""
    from .bundleforge import search_bundles

    results = search_bundles(query)
    if json_output:
        import json as _json
        print(_json.dumps(results, indent=2))
        return
    if not results:
        console.print(f"[dim]No templates matched '{query}'.[/dim]")
        return
    console.print(Panel.fit(f"BundleForge search: '{query}'"))
    for r in results:
        console.print(f"\n[bold]{r['template_id']}[/bold] (score: {r['score']})")
        console.print(f"  {r['name']}: {r['description']}")


app.add_typer(bundleforge_app, name="bundleforge")


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
        from .bundles import load_bundle as load_bundle_v2
        ollama_model = load_bundle_v2(bundle).controller_spec().model
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


@provider_app.command("list")
def provider_list(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List known provider presets (local + cloud)."""
    from .providers.presets import PRESETS

    if json_output:
        import json as _json

        print(_json.dumps([
            {"id": p.id, "label": p.label, "base_url": p.base_url,
             "kind": p.kind, "api_key_env": p.api_key_env, "notes": p.notes}
            for p in PRESETS.values()
        ], indent=2))
        return
    console.print(Panel.fit(f"Provider presets ({len(PRESETS)})"))
    for p in PRESETS.values():
        marker = " [local, quota-free]" if p.kind == "local" else " [cloud, metered]"
        console.print(f"  [bold]{p.id:<12}[/bold] {p.label}{marker}")
        console.print(f"    endpoint: {p.base_url}")
        if p.api_key_env:
            console.print(f"    api key:  ${p.api_key_env}")


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
                payload = {"model": model, "prompt": "Reply with exactly: PROMETHEUS_SANDBOX_READY",
                           "stream": False, "options": {"num_predict": 16, "temperature": 0}}
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


@astronaut_app.command("tick")
def astronaut_tick(
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
    vision: bool = typer.Option(False, "--vision", help="Run vision-based UI inspection in this tick"),
    seed: int = typer.Option(0, "--seed", help="Random seed for reproducible test selection (0 = time-based)"),
    url: str = typer.Option("", "--url", help="URL for vision inspection (implies --vision)"),
    selector: str = typer.Option("", "--selector", help="CSS selector for vision inspection"),
    profile: Path | None = typer.Option(None, "--profile", exists=True, readable=True,
                                        help="Design profile JSON for vision comparison"),
) -> None:
    """Run one Astronaut Sentinel test tick (focused, random, or vision)."""
    from .astronaut import run_tick

    use_vision = vision or bool(url)
    result = run_tick(workspace, seed=seed, vision=use_vision, url=url, selector=selector,
                      profile=profile)
    console.print(Panel.fit("Astronaut tick"))
    console.print(f"  type: {result['type']}")
    console.print(f"  seed: {result.get('seed', 'N/A')}")
    console.print(f"  result: {result['result']}")
    if result.get("detail"):
        console.print(f"  detail: {result['detail']}")
    console.print(f"[dim]evidence -> {workspace}/.prometheus/astronaut/events.jsonl[/dim]")


@astronaut_app.command("run-once")
def astronaut_run_once(
    objective: str = typer.Argument(..., help="Outcome for this one-shot session"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
    bundle: Path | None = typer.Option(None, "--bundle", exists=True, readable=True),
    yes: bool = typer.Option(False, "--yes", help="Auto-approve mode-allowed actions"),
) -> None:
    """Run a single astronaut macro-attempt (one Arena loop), then stop."""
    from .agent import ArenaLoop, MicroStepEngine, make_default_verify
    from .memory import Intent, ProjectMemoryStore
    from .providers import create_provider
    from .tools.workspace import WorkspaceTools

    settings = load_settings()
    settings.mode = AutonomyMode.ASTRONAUT
    settings.workspace = workspace.resolve()
    bundle_path = bundle or settings.bundle_file
    if not bundle_path:
        console.print("[red]No bundle configured. Run 'prometheus setup' or pass --bundle.[/red]")
        raise typer.Exit(code=1)
    bundle_obj = load_bundle(bundle_path)
    controller_spec = bundle_obj.for_role("controller")
    forge = create_provider(controller_spec)
    envoy = create_provider(controller_spec)
    argus = create_provider(controller_spec)
    mem = ProjectMemoryStore(workspace)
    mem.set_intent(Intent(objective=objective, success_criteria=[]))
    tools = WorkspaceTools(workspace)
    approve = (lambda _c, _r: True) if yes else _approval
    engine = MicroStepEngine(store=mem, tools=tools, settings=settings, approve=approve)
    arena = ArenaLoop(store=mem, tools=tools, engine=engine)
    verify = make_default_verify(workspace)
    providers = {"envoy": envoy, "forge": forge, "argus": argus}
    console.print(Panel.fit(f"Astronaut run-once\nObjective: {objective}"))
    result = arena.run(providers, verify, on_update=lambda line: console.print(f"[cyan]{line}[/cyan]"))
    verdict = "[green]COMPLETE[/green]" if result.accepted else f"[yellow]{result.final_status.upper()}[/yellow]"
    console.print(Panel(
        f"accepted={result.accepted} · attempts={result.attempts}",
        title=f"{verdict} — run-once"))


@astronaut_app.command("report")
def astronaut_report(
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
) -> None:
    """Show the astronaut session report."""
    from .astronaut import read_state

    state = read_state(workspace)
    report_path = workspace / ".prometheus" / "astronaut" / "report.md"
    events_path = workspace / ".prometheus" / "astronaut" / "events.jsonl"
    console.print(Panel.fit("Astronaut report"))
    console.print(f"Status: [bold]{state.status}[/bold]")
    console.print(f"Objective: {state.objective or '(none)'}")
    console.print(f"Macro attempts: {state.macro_attempts}")
    console.print(f"Checkpoints: {state.checkpoints}")
    if events_path.exists():
        lines = events_path.read_text(encoding="utf-8").strip().split("\n")
        console.print(f"Events logged: {len(lines)}")
        import json as _json
        ticks = [ln for ln in lines if ln.strip()]
        passed = sum(1 for ln in ticks if _json.loads(ln).get("result") == "pass")
        console.print(f"Ticks passed: {passed}/{len(ticks)}")
    if report_path.exists():
        console.print(f"\n[bold]Report file:[/bold] {report_path}")
        console.print(report_path.read_text(encoding="utf-8")[:500])


app.add_typer(astronaut_app, name="astronaut")


@vision_app.command("doctor")
def vision_doctor_cmd() -> None:
    """Report vision inspection capabilities (Playwright, browsers, fixtures)."""
    from .vision import vision_doctor

    info = vision_doctor()
    console.print(Panel.fit("PROMETHEUS vision doctor"))
    pw = info["playwright_available"]
    console.print(f"  Playwright: {'available' if pw else '[red]not installed[/red]'}")
    if info.get("driver"):
        d = info["driver"]
        if d.get("browsers"):
            console.print(f"  Browsers: {', '.join(d['browsers'])}")
        if d.get("error"):
            console.print(f"  [yellow]{d['error']}[/yellow]")
    console.print(f"  Fixture UI: {'available' if info['fixture_available'] else '[yellow]not found[/yellow]'}")
    console.print(f"  Vision evidence dir: {info['vision_dir']}")
    if not pw:
        console.print("\n[yellow]Install:[/yellow] pip install 'prometheus-local-agent[browser]' && playwright install chromium")


@vision_app.command("inspect")
def vision_inspect(
    url: str = typer.Option(..., "--url", help="URL to inspect (http:// or file://)"),
    selector: str = typer.Option(None, "--selector", help="CSS selector, e.g. 'button.primary'"),
    role: str = typer.Option(None, "--role", help="ARIA role to locate (e.g. button)"),
    name: str = typer.Option(None, "--name", help="Accessible name to match with --role"),
    test_id: str = typer.Option(None, "--test-id", help="data-testid to locate"),
    profile: Path | None = typer.Option(None, "--profile", exists=True, readable=True,
                                        help="Design profile JSON for comparison"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace", exists=True, file_okay=False),
    headless: bool = typer.Option(True, "--headless/--headed"),
    full_page: bool = typer.Option(False, "--full-page", help="Also capture a full-page screenshot"),
) -> None:
    """Inspect a UI element: element-only screenshot, computed CSS, accessibility."""
    from .vision import VisionInspector

    out_dir = workspace / ".prometheus" / "vision"
    inspector = VisionInspector(headless=headless)
    report = inspector.inspect(
        url=url, selector=selector, role=role, name=name, test_id=test_id,
        profile=profile, out_dir=out_dir, include_full_page=full_page,
    )
    if "error" in report:
        console.print(f"[red]Vision error:[/red] {report['error']}")
        if "hint" in report:
            console.print(f"[yellow]{report['hint']}[/yellow]")
        raise typer.Exit(code=1)
    console.print(Panel.fit(f"Vision inspect — {report['selector']}"))
    console.print(f"  Verdict: {report['verdict']}")
    a11y = report.get("element", {}).get("accessibility", {})
    if a11y:
        console.print(f"  Role: {a11y.get('role', '?')} · Name: {a11y.get('name', '?')}")
    comp = report.get("comparison")
    if comp:
        icon = "[green]PASS[/green]" if comp["matched"] else "[red]FAIL[/red]"
        console.print(f"  Comparison: {icon} — {comp['summary']}")
    console.print(f"  [dim]Evidence -> {out_dir}/[/dim]")
    if comp and not comp["matched"]:
        raise typer.Exit(code=1)


@vision_app.command("compare")
def vision_compare(
    actual: Path = typer.Argument(..., exists=True, readable=True,
                                   help="Path to actual style.json from a vision inspect"),
    expected: Path = typer.Argument(..., exists=True, readable=True,
                                     help="Path to expected design profile JSON"),
) -> None:
    """Compare an actual style snapshot against an expected design profile."""
    from .vision import VisionInspector

    inspector = VisionInspector()
    result = inspector.compare(actual, expected)
    icon = "[green]PASS[/green]" if result.matched else "[red]FAIL[/red]"
    console.print(Panel.fit(f"Vision compare — {icon}"))
    console.print(f"  {result.summary}")
    if not result.matched:
        diffs = [d for d in result.diffs if not d.matched]
        for d in diffs:
            console.print(f"    {d.property}: expected '{d.expected}' got '{d.actual}'")
        raise typer.Exit(code=1)


app.add_typer(vision_app, name="vision")


@assets_app.command("doctor")
def assets_doctor() -> None:
    """Report AssetForge capabilities (rembg, diffusers, torch)."""
    from .assets import doctor

    info = doctor()
    console.print(Panel.fit("AssetForge doctor"))
    console.print(f"  torch: {'available' if info['torch_available'] else '[yellow]not installed[/yellow]'}")
    console.print(f"  diffusers: {'available' if info['diffusers_available'] else '[yellow]not installed[/yellow]'}")
    console.print(f"  rembg (bg removal): {'available' if info['rembg_available'] else '[yellow]not installed[/yellow]'}")
    console.print(f"  image tests enabled: {info['image_tests_enabled']}")
    console.print(f"  [dim]env var: {info['env_var']}=1 to enable image generation[/dim]")


@assets_app.command("setup")
def assets_setup() -> None:
    """Show the install commands needed to enable AssetForge image generation."""
    from .assets import setup

    result = setup()
    if result["ready"]:
        console.print("[green]All dependencies installed.[/green]")
    else:
        console.print("[yellow]Install these to enable image generation:[/yellow]")
        for cmd in result["commands"]:
            console.print(f"  {cmd}")


@assets_app.command("models")
def assets_models() -> None:
    """List supported AssetForge model packages."""
    from .assets.manifest import KNOWN_LICENSES

    console.print(Panel.fit("AssetForge models"))
    for model, info in sorted(KNOWN_LICENSES.items()):
        console.print(f"  [bold]{model}[/bold]")
        console.print(f"    license: {info['license']} · commercial: {info['commercial']}")
        console.print(f"    {info['source']}")


@assets_app.command("generate")
def assets_generate(
    name: str = typer.Argument(..., help="Asset name (no spaces)"),
    kind: str = typer.Option("icon", "--kind", help="icon|hero|illustration|logo|dashboard|mockup|background"),
    size: str = typer.Option("512x512", "--size", help="WxH (256x256, 512x512, 1024x1024, 1536x864, 1920x1080)"),
    transparent: bool = typer.Option(False, "--transparent", help="Remove background after generation"),
    model: str = typer.Option("stabilityai/sdxl-turbo", "--model", help="HuggingFace model id"),
    style: str = typer.Option("", "--style"),
    colors: str = typer.Option("", "--colors"),
    seed: int = typer.Option(0, "--seed", help="0 = random"),
    steps: int = typer.Option(4, "--steps"),
    output_dir: Path = typer.Option(Path("assets/generated"), "--output-dir"),
) -> None:
    """Generate a web asset (icon, hero, illustration) via local image model."""
    from .assets import generate

    result = generate(
        name=name, kind=kind, size=size, transparent=transparent,
        model=model, style=style, colors=colors, seed=seed, steps=steps,
        output_dir=output_dir,
    )
    if "error" in result:
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(code=1)
    console.print(Panel.fit(f"AssetForge generate — {name}"))
    console.print(f"  Kind: {kind} · Size: {size} · Transparent: {transparent}")
    console.print(f"  Model: {model} · Seed: {result['seed']}")
    console.print(f"  Prompt: {result['prompt']}")
    console.print(f"  Image generated: {result['image_generated']}")
    if result.get("skip_reason"):
        console.print(f"  [yellow]{result['skip_reason']}[/yellow]")
    for w in result.get("answers_warnings", []):
        console.print(f"  [yellow]warning: {w}[/yellow]")
    console.print(f"  Manifest: {result['manifest_path']}")
    console.print(f"  [dim]Asset dir: {result['asset_dir']}[/dim]")


@assets_app.command("remove-bg")
def assets_remove_bg(
    input: Path = typer.Argument(..., exists=True, readable=True),
    out: Path = typer.Option(None, "--out", help="Output path (default: <input>-transparent.png)"),
) -> None:
    """Remove background from an image using rembg (MIT-licensed)."""
    from .assets import is_available, remove_background

    if not is_available():
        console.print("[red]rembg not installed. Run: pip install rembg[/red]")
        raise typer.Exit(code=1)
    output_path = out or input.with_stem(input.stem + "-transparent")
    result = remove_background(input, output_path)
    if result["success"]:
        console.print(f"[green]Background removed:[/green] {result['output']}")
        console.print(f"  {result['input_bytes']} -> {result['output_bytes']} bytes")
    else:
        console.print(f"[red]Failed:[/red] {result['error']}")
        raise typer.Exit(code=1)


@assets_app.command("manifest")
def assets_manifest(
    asset_dir: Path = typer.Argument(..., exists=True, file_okay=False,
                                     help="Directory containing generated assets"),
) -> None:
    """Show the provenance manifest for a generated asset."""
    mp = asset_dir / "manifest.json"
    if not mp.exists():
        console.print(f"[red]No manifest.json in {asset_dir}[/red]")
        raise typer.Exit(code=1)
    import json as _json
    data = _json.loads(mp.read_text(encoding="utf-8"))
    console.print(Panel.fit(f"Asset manifest — {data.get('name', '?')}"))
    console.print(f"  Kind: {data.get('kind')}")
    console.print(f"  Model: {data.get('model')}")
    console.print(f"  License: {data.get('license_id', 'unknown')} · Commercial: {data.get('commercial_use')}")
    console.print(f"  Seed: {data.get('seed')} · Size: {data.get('size')}")
    console.print(f"  Transparent: {data.get('transparent')}")
    console.print(f"  Files: {', '.join(data.get('files', []))}")
    if data.get("warnings"):
        console.print("  [yellow]Warnings:[/yellow]")
        for w in data["warnings"]:
            console.print(f"    • {w}")


app.add_typer(assets_app, name="assets")


@logo_app.command("preview")
def logo_preview(
    width: int = typer.Option(64, "--width", min=16, max=160, help="Target character width"),
    animated: bool = typer.Option(False, "--animated", help="Play the rotating-highlight startup animation"),
    no_animation: bool = typer.Option(False, "--no-animation", help="Force static even with --animated"),
    no_color: bool = typer.Option(False, "--no-color", help="Strip ANSI color"),
) -> None:
    """Preview the PROMETHEUS brand logo (static or animated)."""
    from .logo import preview_logo, should_animate_logo

    use_color = not no_color
    if animated and not should_animate_logo(no_animation=no_animation):
        console.print("[dim]tty not detected; showing static fallback[/dim]")
    preview_logo(
        width=width, animated=animated, color=use_color,
        no_animation=no_animation,
    )


@logo_app.command("generate")
def logo_generate(
    source: Path = typer.Option(
        Path("assets/branding/feverducation.png"),
        "--source", exists=True, readable=True,
        help="Source image (PNG/JPG) to derive ASCII art from",
    ),
    out: Path = typer.Option(
        Path("src/prometheus_cli/generated_logo.py"),
        "--out", help="Output Python module path",
    ),
) -> None:
    """Generate a Python module with ASCII art derived from a brand image."""
    from .logo import generate_logo

    ok, message = generate_logo(source=source, out_path=out)
    if ok:
        console.print(f"[green]Generated:[/green] {out}")
        console.print(f"[dim]{message}[/dim]")
    else:
        console.print(f"[yellow]Fallback:[/yellow] {message}")
        console.print(f"[dim]Wrote: {out}[/dim]")


app.add_typer(logo_app, name="logo")


if __name__ == "__main__":
    app()

