from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FirstRunState:
    has_config: bool = False
    has_active_bundle: bool = False
    ollama_installed: bool = False
    ollama_running: bool = False
    has_models: bool = False
    model_count: int = 0
    has_git_repo: bool = False
    has_memory: bool = False
    workspace: Path = field(default_factory=Path.cwd)
    recommended_bundle: str = ""
    recommended_models: list[str] = field(default_factory=list)

    @property
    def is_first_run(self) -> bool:
        return not self.has_config or not self.has_active_bundle

    @property
    def needs_ollama_setup(self) -> bool:
        return not self.ollama_installed or not self.ollama_running or not self.has_models

    @property
    def needs_project_setup(self) -> bool:
        return not self.has_git_repo or not self.has_memory

    @property
    def guidance(self) -> str:
        if self.is_first_run and self.needs_ollama_setup:
            return "first_run_full"
        if self.is_first_run:
            return "first_run_select_bundle"
        if self.ollama_installed and not self.ollama_running:
            return "ollama_down"
        if not self.has_models:
            return "no_models"
        if self.needs_project_setup:
            return "project_init"
        return "ready"

    @property
    def next_action(self) -> str:
        g = self.guidance
        if g == "first_run_full":
            return "Run the setup wizard: /setup"
        if g == "first_run_select_bundle":
            return f"Select a bundle: /use {self.recommended_bundle}"
        if g == "no_models":
            return f"Pull models: prometheus models pull --bundle {self.recommended_bundle}"
        if g == "ollama_down":
            return "Start Ollama: ollama serve"
        if g == "project_init":
            return "Initialize project: prometheus init ."
        return "Type an objective to start coding"

    @property
    def no_model_message(self) -> str:
        if self.has_models:
            return ""
        bundle = self.recommended_bundle or "a bundle"
        models = self.recommended_models[:2]
        model_hint = f"Next: pull {models[0]}" if models else f"Next: choose {bundle}"
        return (
            f"Ollama is ready but no models are installed yet. "
            f"Recommended bundle: {bundle}. {model_hint}."
        )


def detect_first_run(
    home: Path | None = None,
    workspace: Path | None = None,
    ollama_status=None,
) -> FirstRunState:
    from .config import CONFIG_HOME, load_settings

    ws = workspace or Path.cwd()
    home_dir = home or CONFIG_HOME

    config_path = home_dir / "config.yaml"
    has_config = config_path.is_file()

    settings = load_settings() if has_config else None
    has_active_bundle = bool(settings and settings.active_bundle_id)

    if ollama_status is not None:
        ollama_installed = ollama_status.installed
        ollama_running = ollama_status.running
        model_count = len(ollama_status.models)
    else:
        try:
            from .onboarding import check_ollama
            status = check_ollama()
            ollama_installed = status.installed
            ollama_running = status.running
            model_count = len(status.models)
        except Exception:
            ollama_installed = False
            ollama_running = False
            model_count = 0

    has_models = model_count > 0

    git_dir = ws / ".git"
    has_git_repo = git_dir.is_dir()

    memory_file = ws / ".prometheus" / "memory.md"
    has_memory = memory_file.is_file()

    recommended_bundle = ""
    recommended_models: list[str] = []
    try:
        from .bundles import classify_registry, load_registry
        from .hardware import detect_hardware
        from .onboarding import check_ollama as _check_ollama
        hw = detect_hardware()
        ollama = _check_ollama()
        registry = load_registry()
        classified = classify_registry(registry, hw, ollama.models)
        rec = next((c for c in classified if c.status == "recommended"), None)
        if rec:
            recommended_bundle = rec.bundle.id
            for role_spec in rec.bundle.roles.values():
                recommended_models.append(role_spec.model)
    except Exception:
        pass

    return FirstRunState(
        has_config=has_config,
        has_active_bundle=has_active_bundle,
        ollama_installed=ollama_installed,
        ollama_running=ollama_running,
        has_models=has_models,
        model_count=model_count,
        has_git_repo=has_git_repo,
        has_memory=has_memory,
        workspace=ws,
        recommended_bundle=recommended_bundle,
        recommended_models=recommended_models,
    )


@dataclass
class ModelPullInfo:
    model_id: str
    role: str
    download_size_gb: float
    disk_required_gb: float
    min_ram_gb: int
    min_vram_gb: int
    license: str
    provider: str
    required: bool
    already_installed: bool = False

    @property
    def is_local(self) -> bool:
        return self.provider in ("ollama", "diffusers", "rembg")

    @property
    def privacy_level(self) -> str:
        if self.provider in ("ollama", "diffusers", "rembg"):
            return "local-only"
        return "cloud"

    def summary_lines(self) -> list[str]:
        status = "[ok]installed[/]" if self.already_installed else "[warn]not installed[/]"
        req = "required" if self.required else "optional"
        lines = [
            f"[k]Model[/]    [v]{self.model_id}[/]",
            f"[k]Role[/]     [v]{self.role}[/]",
            f"[k]Download[/] [v]~{self.download_size_gb:.1f} GB[/]",
            f"[k]Disk[/]     [v]{self.disk_required_gb:.0f} GB free needed[/]",
            f"[k]RAM[/]      [v]{self.min_ram_gb} GB minimum[/]",
            f"[k]VRAM[/]     [v]{self.min_vram_gb} GB minimum[/]",
            f"[k]License[/]  [v]{self.license}[/]",
            f"[k]Provider[/] [v]{self.provider} ({self.privacy_level})[/]",
            f"[k]Status[/]   {status}",
            f"[k]Priority[/] [v]{req}[/]",
        ]
        return lines


def build_pull_info_for_bundle(bundle_id: str, installed_models: list[str] | None = None) -> list[ModelPullInfo]:
    from .bundleforge.catalog import load_catalog
    from .bundles import find_bundle, load_registry

    installed = set(installed_models or [])
    registry = load_registry()
    bundle = find_bundle(bundle_id, registry)
    if bundle is None:
        return []

    try:
        catalog = load_catalog()
    except Exception:
        catalog = None

    result: list[ModelPullInfo] = []
    for role_name, role_spec in bundle.roles.items():
        entry = catalog.by_id(role_spec.model) if catalog else None
        result.append(ModelPullInfo(
            model_id=role_spec.model,
            role=role_name,
            download_size_gb=role_spec.approximate_download_gb,
            disk_required_gb=role_spec.approximate_download_gb + 2,
            min_ram_gb=entry.min_ram_gb if entry else bundle.hardware.minimum_ram_gb,
            min_vram_gb=entry.min_vram_gb if entry else bundle.hardware.minimum_vram_gb,
            license=entry.license if entry else "check_upstream",
            provider=bundle.runtime.provider,
            required=not role_spec.optional,
            already_installed=role_spec.model in installed,
        ))
    return result


__all__ = [
    "FirstRunState",
    "ModelPullInfo",
    "build_pull_info_for_bundle",
    "detect_first_run",
]
