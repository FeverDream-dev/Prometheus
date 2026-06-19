from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from .config import load_bundle, load_settings, save_settings
from .hardware import detect_hardware, recommended_profile
from .models import AutonomyMode, Risk, ToolCall
from .orchestrator import Orchestrator
from .policy import mode_description


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
    console.print(f"OS: {report.os} {report.architecture}")
    console.print(f"RAM: {report.ram_gb} GB")
    console.print(f"GPU: {report.gpu_name or 'CPU mode'} ({report.vram_gb} GB VRAM)")
    console.print(f"Ollama: {'ready' if report.ollama_installed else 'not installed'}")
    console.print(f"Recommended bundle: [bold]{recommended_profile(report)}[/bold]")


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
) -> None:
    """Run an evidence-driven coding session."""
    settings = load_settings()
    settings.workspace = workspace.resolve()
    if mode:
        settings.mode = mode
    orchestrator = Orchestrator(settings, load_bundle(bundle), approve=_approval)
    result = orchestrator.run(objective, on_update=lambda line: console.print(f"[cyan]{line}[/cyan]"))
    console.print(Panel(result.message, title=f"{result.status} — {result.completion_percent}%"))


@app.command()
def modes() -> None:
    """Explain autonomy levels."""
    for mode in AutonomyMode:
        console.print(f"[bold]{mode.value}[/bold]: {mode_description(mode)}")


if __name__ == "__main__":
    app()

