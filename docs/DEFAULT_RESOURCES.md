# Default Packaged Resources

PROMETHEUS ships default bundles, prompts, schemas, and i18n files inside the
wheel so that `prometheus setup`, `prometheus bundles list`, and the TUI work
immediately after install — no repository checkout required.

## Packaged layout

```
src/prometheus_cli/resources/
├── __init__.py              # loader module (get_resource_root, resolve_bundles_dir, etc.)
├── bundles_v2/              # 10 v2 bundle manifests (the authoritative registry)
│   ├── 01-spark-cpu-8gb.yaml
│   ├── 02-ember-8gb-gpu.yaml
│   ├── 03-forge-12gb.yaml
│   ├── 04-oracle-gemma4-12gb.yaml
│   ├── 05-titan-24gb.yaml
│   ├── 06-hephaestus-code-24gb.yaml
│   ├── 07-vibethinker-review-addon.yaml
│   ├── 08-cloud-hybrid.yaml
│   ├── 09-vibethinker-sandbox-q2.yaml
│   └── 10-vibethinker-sandbox-q4.yaml
├── bundles_v1/              # 8 v1 bundle manifests (used by the setup wizard)
├── prompts/                 # agent prompt templates
│   ├── CONTROLLER.md
│   ├── COMPLETION_AUDITOR.md
│   └── VIBETHINKER_REVIEWER.md
├── schemas/                 # JSON schemas
│   ├── bundle-v2.schema.json
│   ├── bundle.schema.json
│   └── tool-call.schema.json
├── i18n/                    # internationalization
│   ├── en.json
│   └── pt-BR.json
└── default_config.yaml      # default settings template
```

## Bundle directory precedence (highest first)

1. `--bundles-dir` CLI flag (explicit override)
2. `./.prometheus/bundles` (project-local overrides)
3. `~/.prometheus/bundles` (user-level overrides)
4. packaged defaults (read-only, always available)

## Sync workflow

The canonical sources live in the top-level `config/bundles-v2/`,
`config/bundles/`, `prompts/`, `schemas/`, and `i18n/` directories. After
changing any of those files, run:

```sh
python scripts/sync_package_resources.py
```

This copies the approved defaults into `src/prometheus_cli/resources/` and
rejects any model weights or binary files.

## What is NOT shipped

- Model weights (`.gguf`, `.bin`, `.safetensors`, etc.) — never included
- Caches (`.ollama`, `.prometheus`)
- Secrets, API keys
- `__pycache__`, `node_modules`

## Verification

```sh
bash scripts/clean_install_defaults_smoke.sh
```

This builds a wheel, installs it into a clean venv, and verifies that
`prometheus bundles list`, `prometheus setup --dry-run`, and `prometheus doctor`
all work without a repository checkout.
