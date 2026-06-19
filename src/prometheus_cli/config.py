from __future__ import annotations

import os
from pathlib import Path

import yaml

from .models import ModelBundle, Settings


CONFIG_HOME = Path(os.environ.get("PROMETHEUS_HOME", Path.home() / ".prometheus"))


def ensure_home() -> Path:
    CONFIG_HOME.mkdir(parents=True, exist_ok=True)
    (CONFIG_HOME / "bundles").mkdir(exist_ok=True)
    (CONFIG_HOME / "sessions").mkdir(exist_ok=True)
    return CONFIG_HOME


def load_settings(path: Path | None = None) -> Settings:
    path = path or CONFIG_HOME / "config.yaml"
    if not path.exists():
        return Settings()
    return Settings.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def save_settings(settings: Settings, path: Path | None = None) -> Path:
    ensure_home()
    path = path or CONFIG_HOME / "config.yaml"
    data = settings.model_dump(mode="json")
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def load_bundle(path: Path) -> ModelBundle:
    return ModelBundle.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

