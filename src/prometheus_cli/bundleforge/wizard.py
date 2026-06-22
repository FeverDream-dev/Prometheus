from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from ..hardware import HardwareReport, detect_hardware
from .catalog import ModelCatalog, load_catalog
from .recommend import list_templates, recommend
from .schema import ForgeBundle


@dataclass
class WizardAnswers:
    use_case: str = ""
    auto_detect_hardware: bool = True
    deployment: str = "local"
    capabilities: list[str] = field(default_factory=list)
    commercial_safe_only: bool = True
    allow_large_downloads: bool = True
    priority: str = "balanced"
    project_rag: bool = False
    mcp_apps: list[str] = field(default_factory=list)
    agent_team: bool = True


PromptFn = Callable[[str, str | None], str]
ConfirmFn = Callable[[str, bool], bool]
ChoiceFn = Callable[[str, list[str], int], int]


def run_wizard(
    prompt_fn: PromptFn | None = None,
    confirm_fn: ConfirmFn | None = None,
    choice_fn: ChoiceFn | None = None,
    hardware: HardwareReport | None = None,
    catalog: ModelCatalog | None = None,
    defaults: WizardAnswers | None = None,
) -> tuple[WizardAnswers, ForgeBundle]:
    answers = defaults or WizardAnswers()
    hw = hardware or detect_hardware()
    cat = catalog or load_catalog()

    if prompt_fn:
        use_case_input = prompt_fn(
            "What are you building? (e.g. 'a 2D game', 'a RAG assistant for my docs', 'WhatsApp automation')",
            answers.use_case or "",
        )
    else:
        use_case_input = answers.use_case or "web development"

    answers.use_case = use_case_input

    if confirm_fn:
        answers.auto_detect_hardware = confirm_fn(
            f"Auto-detect hardware? (RAM: {hw.ram_gb:.0f} GB, VRAM: {hw.vram_gb:.0f} GB)",
            True,
        )

    if choice_fn:
        dep_options = ["local", "cloud", "hybrid"]
        answers.deployment = dep_options[choice_fn("Local-only, cloud, or hybrid?", dep_options, 0)]

        cap_options = ["coding", "research", "vision", "image_generation", "rag", "mcp", "browser_testing"]
        priority_options = ["quality", "speed", "privacy", "low_memory", "balanced"]

        selected_cap_idx = choice_fn("Which capabilities do you need?", cap_options, 0)
        answers.capabilities = [cap_options[selected_cap_idx]] if selected_cap_idx is not None else ["coding"]

        selected_prio_idx = choice_fn("Priority: quality, speed, privacy, or low memory?", priority_options, 4)
        answers.priority = priority_options[selected_prio_idx]
    else:
        if not answers.capabilities:
            answers.capabilities = ["coding"]
        if not answers.priority:
            answers.priority = "balanced"

    if confirm_fn:
        answers.commercial_safe_only = confirm_fn("Require commercial-safe models only?", True)
        answers.allow_large_downloads = confirm_fn("Allow downloading large models (several GB)?", True)
        answers.project_rag = confirm_fn("Create project-specific RAG index?", False)
        answers.agent_team = confirm_fn("Use an agent team (envoy/builder/critic)?", True)

    prefer_quality = answers.priority == "quality"
    result = recommend(
        use_case_input,
        hardware=hw,
        prefer_quality=prefer_quality,
        commercial_safe_only=answers.commercial_safe_only,
        catalog=cat,
    )

    return answers, result.bundle


def save_bundle(bundle: ForgeBundle, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = output_dir / "bundle.yaml"
    data = bundle.model_dump(mode="json")
    bundle_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    readme = output_dir / "README.md"
    readme.write_text(
        f"# {bundle.name}\n\n{bundle.description}\n\n"
        f"**Use case:** {bundle.use_case}\n\n"
        f"**Roles:** {', '.join(bundle.roles.keys())}\n\n"
        f"**License notes:** {bundle.license_notes}\n",
        encoding="utf-8",
    )

    license_notes = output_dir / "LICENSE_NOTES.md"
    license_notes.write_text(
        f"# License Notes for {bundle.name}\n\n{bundle.license_notes}\n\n"
        f"Each model retains its upstream license. Verify before commercial use.\n",
        encoding="utf-8",
    )

    return bundle_path


__all__ = [
    "WizardAnswers",
    "run_wizard",
    "save_bundle",
]
