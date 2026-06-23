# PROMETHEUS — Cursor project audit

**Date:** 2026-06-23  
**Repo:** FeverDream-dev/Prometheus (`prometheus-local-agent` 0.1.2)  
**Auditor:** Cursor implementation agent

## What the project does

PROMETHEUS is a local-first, installable TUI/CLI coding agent. Users install from GitHub, run `prometheus tui` in any project folder, pick a model bundle, and work with Ollama/local models plus optional cloud providers. Core capabilities include bounded memory, Git checkpoints, sandboxing, MCP, RAG, vision testing, and AssetForge image generation.

## Where things live

| Area | Location |
|---|---|
| CLI entry + commands | `src/prometheus_cli/cli.py` (`prometheus` Typer app) |
| TUI application shell | `src/prometheus_cli/tui.py`, `tui_screens.py`, `tui_widgets.py`, `tui_theme.py`, `tui_commands.py`, `tui_state.py` |
| Packaged defaults | `src/prometheus_cli/resources/` (`bundles_v2/`, `bundles_v1/`, `prompts/`, `schemas/`, `i18n/`, `model_catalog/`, `bundleforge/`, `mcp_templates/`) |
| Resource resolution | `src/prometheus_cli/resources/__init__.py` (`importlib`-friendly paths, precedence: CLI → project → user → packaged) |
| Bundles registry | `src/prometheus_cli/bundles.py` |
| BundleForge | `src/prometheus_cli/bundleforge/` |
| Session / SQLite | `src/prometheus_cli/session.py` |
| Memory | `src/prometheus_cli/memory/` |
| Providers | `src/prometheus_cli/providers/` |
| Sandbox | `src/prometheus_cli/sandbox.py`, `sandbox_test.py` |
| Installers | `install.sh`, `install.ps1`, `public/install.sh`, `public/install.ps1`, `src/prometheus_cli/installer.py` |
| Tests | `tests/` (97+ test modules) |
| Smoke scripts | `scripts/clean_install_defaults_smoke.sh`, `tui_visual_smoke.sh`, `local_model_smoke.sh`, `full_installed_product_smoke.sh` |

## What was broken (reported)

1. **Installed package missing default bundles** — `prometheus setup` showed `No bundles found. Pass --bundles-dir.`
2. **TUI runtime errors** — SQLite thread-safety, objectives submitted without bundle
3. **Raw Rich markup** in TUI transcript (`[bold yellow]...`)
4. **No-bundle UX** — users could type objectives with no model configured
5. **Testing only from repo checkout** — not from real install path
6. **No low-end model validation** — tests assumed 24 GB GPUs

## Current status (this session)

| Phase | Status | Evidence |
|---|---|---|
| 0 Audit | **done** | this file |
| 1 Packaged defaults | **passing** | 61 tests; `clean_install_defaults_smoke.sh` PASS (10 bundles) |
| 2 TUI thread safety | **passing** | 35 tests; `repro_tui_sqlite_thread_bug.py` PASS |
| 3 TUI 2.0 / markup | **passing** | 187 tests |
| 4 BundleForge | **passing** | 90 tests |
| 5 Low-end models | **in progress** | new tests + `local_model_smoke.sh`; Ollama live tests skipped unless `PROMETHEUS_RUN_OLLAMA_TESTS=1` |
| 6 Full install smoke | **passing** | `full_installed_product_smoke.sh` PASS (2026-06-23) |
| 7 Release | **pending** | commit + push after all phases pass |

## Fixes applied this session

- Added `pull_policy.py` — models >2 GB require confirmation unless `--yes`
- Added bundle ID aliases (`ember-8gb` → `ember-8gb-gpu`, `spark-cpu` → `spark-cpu-8gb`)
- Added Phase 5 tests: `test_low_end_model_matrix.py`, `test_ollama_model_pull_policy.py`, `test_bundle_qualification_8gb.py`, `test_bundle_qualification_12gb.py`
- Added `scripts/local_model_smoke.sh` and `scripts/full_installed_product_smoke.sh`

## Fix order (completed / remaining)

1. ✅ Package resources in wheel (`pyproject.toml` package-data + `MANIFEST.in`)
2. ✅ TUI SQLite per-thread connections (`session.py`)
3. ✅ No-bundle objective blocking + setup guidance (`tui.py`)
4. ✅ Raw markup ban in TUI rendering
5. ✅ BundleForge + model catalog
6. 🔄 Low-end model matrix tests + smoke report
7. 🔄 Full public-install smoke + docs update
8. ⏳ Commit `product: fix installed bundles TUI and BundleForge` + push

## Required default bundles (shipped)

V2 registry (`bundles list`): `spark-cpu-8gb`, `ember-8gb-gpu`, `forge-12gb`, `titan-24gb`, `cloud-hybrid`, `vibethinker-sandbox-q2/q4`, plus add-ons.

V1 + BundleForge templates additionally ship: `assetforge-lite-8gb`, `rag-docs-local`, `game-dev-lite`, `webapp-local-lite`, `mcp-whatsapp-starter` (via `resources/bundleforge/` and `bundles_v1/`).

## Next actions

1. Run Phase 5 acceptance tests + `local_model_smoke.sh`
2. Run `full_installed_product_smoke.sh` against public installer
3. Run full `pytest -q` + `ruff check`
4. Update `INSTALLER_PROOF.md`, `IMPLEMENTATION_STATUS.md`, `TUI_VISUAL_QA.md`
5. Commit and push to `main`
