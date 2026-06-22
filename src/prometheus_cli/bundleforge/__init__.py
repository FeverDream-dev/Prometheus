from __future__ import annotations

from .catalog import ModelCatalog, ModelEntry, load_catalog, reload_catalog
from .recommend import (
    MultiRecommendation,
    RecommendationResult,
    detect_capabilities,
    list_templates,
    load_template,
    recommend,
    recommend_multi,
    search_bundles,
)
from .schema import ForgeBundle, ForgePermissions, ForgeRequirements, ForgeRoleSpec, load_forge_bundle
from .validate import ValidationResult, validate_all_templates, validate_bundle, validate_file, validate_template
from .wizard import WizardAnswers, run_wizard, save_bundle

__all__ = [
    "ForgeBundle",
    "ForgePermissions",
    "ForgeRequirements",
    "ForgeRoleSpec",
    "ModelCatalog",
    "ModelEntry",
    "MultiRecommendation",
    "RecommendationResult",
    "ValidationResult",
    "WizardAnswers",
    "detect_capabilities",
    "list_templates",
    "load_catalog",
    "load_forge_bundle",
    "load_template",
    "recommend",
    "recommend_multi",
    "reload_catalog",
    "run_wizard",
    "save_bundle",
    "search_bundles",
    "validate_all_templates",
    "validate_bundle",
    "validate_file",
    "validate_template",
]
