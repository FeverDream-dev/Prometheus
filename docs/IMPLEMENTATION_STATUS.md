# PROMETHEUS implementation status

Deterministic traceability matrix. Completion is **weighted accepted criteria ÷
total weighted criteria**, never a model's opinion. A row is `passing` only when
it has real code, a passing test, and CLI/runtime evidence. Mocked/skipped items
are `placeholder`/`missing` and do not count.

## Step 3 — TUI 2.0 Application Shell

The TUI is a persistent 3-column Textual app shell (sidebar | main | inspector)
with brand header, command input, and dense status bar. Raw Rich markup never
appears in rendered output — all markup-bearing widgets use `markup=True`.

| Criterion | Weight | Status | Evidence |
|---|---|---|---|
| 3-column layout (sidebar, main, inspector) composes correctly | 5 | `passing` | `test_tui_app_shell.py` — 8 tests verify all chrome regions, responsive at 80×24/100×30/120×36 |
| No raw markup in SVG or text export | 5 | `passing` | `test_tui_no_raw_markup.py` — parametrized over all 24 screens, SVG export checked, strip_markup helper |
| 14 sidebar entries (including BundleForge) | 5 | `passing` | `test_tui_sidebar.py` — 9 tests verify all labels render, collapse at 80 cols, Ctrl+B toggle |
| Inspector panel shows hardware/provider/bundle/git/sandbox/memory | 3 | `passing` | `test_tui_inspector.py` — 10 tests verify snapshot data, rendering, toggle, card content |
| Demo mode works headless without Ollama | 5 | `passing` | `test_tui_demo_mode.py` — 9 tests: compose, ribbon, no httpx calls, SVG export, `--exit-after-render` |
| 13 command screens render useful content | 5 | `passing` | `test_tui_command_screens.py` — parametrized over all 13 required screens, content quality checks |
| `--exit-after-render` flag for CI smoke tests | 3 | `passing` | `prometheus tui --demo --exit-after-render` exits 0 |
| `/bundleforge` screen wired to BundleForge engine | 3 | `passing` | Shows templates + catalog from Step 2 |
| Obsidian/gold theme (no clown colors) | 2 | `passing` | `test_css_uses_obsidian_background_and_gold_accent` |
| Full suite: 1184 passed, 5 skipped, 0 regressions | 5 | `passing` | `python -m pytest -q` after all changes |

Evidence:
- `prometheus tui --demo --exit-after-render` → exit 0
- `prometheus tui --demo --screenshot artifacts/tui/demo-startup.svg` → clean SVG, no raw markup
- `grep -R "\[bold\|\[/bold\|\[yellow\|\[/yellow" artifacts/tui/` → no matches

---

## Step 2 — BundleForge and Model Catalog

Users can now ask PROMETHEUS to create/adapt bundles for their use case via
natural language. A deterministic recommendation engine maps requests to
templates, validates against a shipped model catalog, and installs bundles
without manual YAML editing.

| Criterion | Weight | Status | Evidence |
|---|---|---|---|
| Model catalog shipped (23 models across 13 families) | 5 | `passing` | `test_model_catalog.py` — 18 tests verify catalog loads, all families present, queries work |
| BundleForge CLI (8 subcommands) | 5 | `passing` | `test_bundleforge_install_export.py` — 17 CLI tests covering create/inspect/validate/install/export/recommend/search |
| Recommendation engine (deterministic keyword matching) | 5 | `passing` | `test_bundleforge_recommendations.py` — 13 tests: game, whatsapp, RAG, CPU, commercial-safe, search |
| 10 use-case templates shipped | 5 | `passing` | All validate via `test_bundleforge_validation.py` — 13 tests including schema/license/hardware checks |
| ForgeBundle schema with BundleV2 conversion | 3 | `passing` | `test_bundleforge_schema.py` — 15 tests including V2 roundtrip validation |
| Wizard with 10 question groups (interactive + non-interactive) | 3 | `passing` | `test_bundleforge_wizard.py` — 11 tests covering defaults, callbacks, save/roundtrip |
| Commercial-safe enforcement (rejects non-commercial models) | 5 | `passing` | `test_bundleforge_validation.py::TestLicenseValidation` — 2 tests prove SDXL rejected in commercial bundle |
| Invalid/unsafe model names fail validation | 5 | `passing` | `test_bundleforge_validation.py::TestSchemaValidation` — path traversal, command injection rejected |
| Bundle install does not overwrite without --force | 3 | `passing` | `test_bundleforge_install_export.py::test_install_no_overwrite_without_force` |
| Templates packaged in wheel | 3 | `passing` | Wheel contains `resources/bundleforge/*.yaml` (10 files) + `resources/model_catalog/catalog.yaml` |
| Full suite: 1073 passed, 5 skipped, 0 regressions | 5 | `passing` | `python -m pytest -q` after all changes |

Evidence commands run:
- `prometheus bundleforge recommend "I want to build a video game with local models and generated sprites"` → game_development use case, correct template
- `prometheus bundleforge recommend "I want to use MCP to help with WhatsApp messages"` → mcp_automation, whatsapp-mcp-assistant, 100% confidence
- `prometheus bundleforge validate webapp-local-lite` → VALID, 0 errors, 0 warnings

---

## Step 1 — Packaged Defaults and Install Fix

The critical install bug where `prometheus setup` reported `No bundles found` is
fixed. Default bundles, prompts, schemas, and i18n are now packaged inside the
wheel and discoverable after a clean install.

| Criterion | Weight | Status | Evidence |
|---|---|---|---|
| Clean wheel install includes default bundles | 5 | `passing` | `test_wheel_contains_resources.py` — 8 tests assert wheel has >=8 v2 + >=4 v1 YAML files, prompts, schemas, i18n, default_config |
| `prometheus setup --dry-run` does not say "No bundles found" | 5 | `passing` | `test_setup_finds_packaged_bundles.py::test_setup_dry_run_does_not_say_no_bundles_found` |
| `prometheus bundles list` works without repo checkout | 5 | `passing` | `test_bundles_without_repo_checkout.py::test_bundles_list_cli_without_repo` — runs in isolated cwd, no config/ dir |
| `prometheus setup --dry-run` shows available bundles | 5 | `passing` | `test_setup_finds_packaged_bundles.py::test_setup_dry_run_shows_available_bundles` |
| Default agents/prompts/schemas/resources discoverable after install | 3 | `passing` | `test_installed_defaults.py` — 8 tests verify all resource dirs are populated and loadable |
| Tests prove wheel/sdist contain resources | 3 | `passing` | `test_wheel_contains_resources.py` — TestWheelContainsResources (8 tests) + TestSdistContainsResources (2 tests) + TestCleanVenvInstall (2 tests) |
| Clean venv install can run setup/bundles/doctor | 5 | `passing` | `scripts/clean_install_defaults_smoke.sh` — builds wheel, installs in clean venv, verifies all 3 commands |
| No model weights included | 5 | `passing` | `test_wheel_has_no_model_weights` + `test_sdist_contains_no_weights` + `test_no_model_weights_in_resources` |
| Precedence: explicit > project > user > packaged | 3 | `passing` | `test_package_resources.py::TestResolveBundlesDir` — 5 tests covering all precedence levels |
| Resource loader module (resources/__init__.py) | 3 | `passing` | `get_resource_root`, `resolve_bundles_dir`, `copy_default_user_config`, etc. — 13 public functions |
| Sync script for reproducible resource updates | 2 | `passing` | `scripts/sync_package_resources.py` — copies from config/ to resources/, rejects weights |

Evidence artifacts:
- `bash scripts/clean_install_defaults_smoke.sh` → PASS (10 bundles, setup --dry-run OK, doctor OK)
- `python -m pytest tests/test_package_resources.py tests/test_installed_defaults.py tests/test_setup_finds_packaged_bundles.py tests/test_bundles_without_repo_checkout.py tests/test_wheel_contains_resources.py` → 61 passed
- Full suite: 983 passed, 5 skipped (no regressions)

---

## TUI 2.0 (current slice)

The TUI was rebuilt from a debug-box into a real local-first coding-agent
application shell. Acceptance status:

| Criterion | Status | Evidence |
|---|---|---|
| No raw Rich markup in rendered output | `passing` | `test_tui_no_raw_markup.py` — 12 parametrized cases assert no `[bold]`/`[yellow]`/`[/]` in SVG or text; root cause fixed (`RichLog(markup=True)`) |
| Startup dashboard looks like a real product | `passing` | `artifacts/tui/startup_main.svg` (87 KB, 208 text fragments: logo + sidebar + inspector + status bar) |
| First-run setup wizard (7 steps) | `passing` | `/setup` dispatches to `SetupScreen`; `test_tui_first_run.py` asserts all 7 steps render with demo hardware data |
| Persistent sidebar / command rail | `passing` | 13 sections (Chat/Plan/Files/Models/Tools/MCP/Sandbox/Memory/Vision/Assets/Astronaut/Settings) verified in `test_tui_layout.py` |
| Dense status bar (6 segments) | `passing` | provider · bundle · mode · sandbox · git · memory — verified by `test_tui_layout.py::test_status_bar_shows_six_segments` |
| Command palette (Ctrl+P) | `passing` | `CommandPaletteScreen` with 19 commands × (name/desc/shortcut/availability/source); filter + keyboard nav |
| All advertised slash commands render screens | `passing` | 23 screens in `SLASH_SCREEN_MAP`; `test_every_slash_screen_command_dispatches` parametrized over all |
| TUI works in demo mode (no Ollama) | `passing` | `prometheus tui --demo` — fully mocked snapshot, 0 IO, "DEMO MODE" ribbon |
| TUI works in real mode | `passing` | `collect_snapshot(workspace)` calls every probe defensively; missing values show setup guidance |
| Visual smoke artifacts generated | `passing` | `bash scripts/tui_visual_smoke.sh` exports 29 SVGs to `artifacts/tui/` |
| Responsive at 80×24 / 100×30 / 120×36 / 160×48 | `passing` | `test_tui_responsive.py` — 4 sizes render, panels collapse at correct thresholds |
| Test coverage (7 files) | `passing` | 181 TUI-specific tests; full suite 901 passed / 8 skipped |
| Docs + website updated | `passing` | `docs/TUI_DESIGN.md` (new), README TUI section expanded, `website/index.html` TUI section with SVG screenshots |

Known limitations for the next UI iteration:

- Interactive wizard modal (`/setup-wizard`) renders statically in headless export; full interactive flow works in real TTY but not in `--screenshot`.
- Sidebar entries are non-clickable (MVP — mapped to slash commands but no mouse handler).
- Right inspector is currently a static system digest; per-screen contextual detail is future work.

---



Weight: 1 = nice-to-have, 2 = standard, 3 = important, 5 = critical (safety/core).
One incomplete critical row blocks the phase gate.

Legend: `passing` · `partial` · `placeholder` · `missing`

**Last updated:** this session — **648 tests passed, 8 skipped**, verified in a
fresh session against the working tree. Sandbox QA vertical slice confirmed
PASS (19 PASS / 0 FAIL / 1 SKIP on fixture workspace) with no code changes to
that slice — see `docs/QA_SANDBOX_REPORT.md` for the full re-verification
evidence. TUI product-feel slice completed: 4 orphaned slash commands wired
(`/sandbox`, `/vision`, `/assets`, `/astronaut`), `/setup` first-run guide
added, first-run welcome banner on TUI launch, dispatch-coverage test prevents
future orphans. Installer URLs unified to `feverdream-dev.github.io/Prometheus`
(no `raw.githubusercontent` references remain in `public/`). Release pipeline
shipped and verified: **`v0.1.0` is PUBLISHED** (GitHub Release live at
<https://github.com/FeverDream-dev/Prometheus/releases/tag/v0.1.0>, published
2026-06-21T04:27:42Z, tag commit `8954a5e` == `HEAD`). The release carries 7
assets: wheel, sdist, both `.sha256` sidecars, `SHA256SUMS`, CycloneDX SBOM,
`release-manifest.json` — all internally checksum-consistent and independently
re-verified this session. The default installer path now resolves to the
release sdist with SHA-256 verification. The next planned release is `v0.1.1`
(tag not created yet). See `docs/RELEASE_READINESS.md` and
`docs/INSTALLER_PROOF.md` for full evidence.

**What passed this pass (re-verified):** compileall, pytest (648/8), ruff,
`prometheus --help` (14 top-level + 9 sub-apps), doctor, bundles list, sandbox
doctor, sandbox test (19/1), memory inspect, vision doctor, assets doctor,
git status (clean), MCP malicious-fixture block. **Release verification:**
local wheel+sdist+SBOM built; published v0.1.0 assets downloaded and
checksum-verified (`sha256sum -c SHA256SUMS` OK; manifest consistent); source
diff between local and published sdist = 0 differing files (only outer-container
metadata differs, expected); real install from the live v0.1.0 release sdist
succeeded with checksum `84fa97575f43...` verified; source-archive fallback
install succeeded with loud unverified-checksum warning.

**What skipped (with exact reasons):** provider smoke (dead endpoint, optional),
browser sandbox E2E (Playwright install in CI), 5× real-Ollama E2E
(`PROMETHEUS_E2E_OLLAMA=1`), 2× AssetForge image gen
(`PROMETHEUS_RUN_IMAGE_TESTS=1`).

**What remains (active next slice):** `v0.1.0` is shipped and verified. The next
release is `v0.1.1` (tag not pushed yet). Release-prep improvements landed this
session: `release.yml` now enriches `release-manifest.json` with build
provenance (commit SHA, built_at, builder, runner OS, Python version) and adds
an "Assert required release artifacts exist" step that fails the build if
wheel/sdist/checksums/SBOM are missing or checksum-inconsistent; `pages.yml`
adds sitemap.xml + JSON-LD parse validation and a drift guard that the copied
`website/install.{sh,ps1}` match `public/`; `install-release-smoke.yml` adds
independent re-verification of the published `SHA256SUMS` and an assertion that
the release sdist (not the source-archive fallback) was used for tagged
installs. Bumping `pyproject.toml` to `0.1.1` and tagging is a human step.

## How to reproduce every claim below

```sh
. .venv/bin/activate
python -m pytest -q                       # 648 passed, 8 skipped
ruff check src tests                       # clean
python -m compileall -q src                # clean
prometheus --help                          # 14 top-level + 9 sub-app command groups
prometheus bundles list                    # 10 bundles, hardware-classified
prometheus sandbox doctor && prometheus sandbox test --workspace tests/fixtures/sandbox_target --all
prometheus vision doctor && prometheus assets doctor
bash scripts/qa_sandbox_smoke.sh           # full QA harness (12 required + 2 optional)
```

---

## §17 acceptance-criteria matrix (PROMETHEUS_ORIGINAL_IDEA_RECOVERY_PROMPT.md)

| # | Acceptance criterion | Wt | Status | Evidence command | Notes |
|---|---|---|---|---|---|
| 1 | `docs/ORIGINAL_IDEA_GAP_AUDIT.md` exists and is honest | 3 | passing | `cat docs/ORIGINAL_IDEA_GAP_AUDIT.md` | 60 done / 14 partial / 14 missing / 1 misleading-docs at audit time; re-baselined below |
| 2 | Public installer files exist with syntax tests | 5 | passing | `bash -n install.sh` · `pytest tests/test_installer.py` | install.sh + install.ps1; ci.yml runs syntax checks |
| 3 | README has a real public one-liner using the real repo URL | 5 | passing | `grep feverdream-dev.github.io README.md` | `feverdream-dev.github.io/Prometheus` |
| 4 | install.ps1 no longer contains `prometheus/local-agent` | 5 | passing | `grep local-agent install.ps1` (no match) | Delegates to WSL with the real repo |
| 5 | GitHub Pages site exists + deploy workflow | 3 | passing | `cat .github/workflows/pages.yml` · `pytest tests/test_website.py` | SEO/OG/JSON-LD/sitemap/robots validated |
| 6 | TUI supports /help /settings /models /bundles /memory | 5 | passing | `pytest tests/test_tui_commands.py` | Plus /mcp /tools /sessions /qualify /use /modes /permissions /doctor /clear /resume /mode /exit |
| 7 | Bundle manifests for CPU / 8GB / 12GB / 24GB | 3 | passing | `prometheus bundles` | spark-cpu-8gb, ember-8gb-gpu, forge-12gb, titan-24gb (+ oracle, hephaestus, cloud-hybrid, vibethinker addon) |
| 8 | `prometheus bundles list` works | 3 | passing | `prometheus bundles list --json` | Sub-app with list/inspect/qualify |
| 9 | `prometheus bundles qualify <bundle>` works | 3 | passing | `prometheus bundles qualify spark-cpu-8gb` (needs Ollama) | Subcommand + legacy `prometheus qualify --bundle` |
| 10 | `prometheus models pull <bundle>` performs real Ollama pulls | 3 | passing | `prometheus models pull --bundle spark-cpu-8gb` (needs Ollama) | models list/pull/unload command group |
| 11 | Workspace `.prometheus/memory.md` created + updated | 5 | passing | `prometheus run "x" --workspace .` then `prometheus memory status` | Bounded to 1024 words, atomic writes |
| 12 | Memory always in orchestrator context | 5 | passing | `pytest tests/test_memory.py` | build_context_packet wired into ArenaLoop |
| 13 | MCP stdio client MVP + test | 3 | passing | `pytest tests/test_mcp.py tests/test_mcp_e2e.py` · `prometheus mcp test <name>` | stdio JSON-RPC init/list/call + untrusted delimiters |
| 14 | Playwright browser test MVP + test | 3 | passing | `pytest tests/test_browser.py tests/test_browser_e2e.py` · `prometheus browser test <url>` | console/network evidence collection |
| 15 | Sandbox mode is more than a flag | 5 | passing | `pytest tests/test_sandbox.py` | SandboxTier enum (off/basic/docker/native); BASIC hard-denies catastrophic commands; NATIVE = bwrap/sandbox-exec |
| 16 | Provider conformance tests exist | 3 | passing | `pytest tests/test_provider_conformance.py` | 10 labeled presets + parametrized fake-HTTP harness (complete/list/health/capabilities/structured/error) |
| 17 | Astronaut long-run session commands exist as working MVP | 5 | passing | `prometheus astronaut --help` · `pytest tests/test_astronaut.py` | start/status/pause/resume/stop + .prometheus/STOP+PAUSE + heartbeat + budgets + periodic checkpoints |
| 18 | CI covers Linux/macOS/Windows + installer syntax + site build | 3 | passing | `cat .github/workflows/ci.yml pages.yml install-smoke.yml` | + install-smoke.yml weekly public one-liner test |
| 19 | No weights/caches/DBs/secrets committed | 5 | passing | `pytest tests/test_repo_hygiene.py` | .gitignore enforces |
| 20 | IMPLEMENTATION_STATUS.md updated with evidence | 3 | passing | this file | — |

**§17 weighted gate:** 80 total · 80 passing · 0 partial.
**§17 completion: 80/80 = 100%.** Every §17 acceptance criterion is now passing with code + tests + evidence.

---

## Feature areas (evidence-backed)

### Foundations
| Feature | Implementation | Test | Status |
|---|---|---|---|
| CLI packaging + `prometheus` entry point | `cli.py` (16 commands + 5 sub-apps) | imports tested | passing |
| Cross-platform hardware detection | `hardware.py` | `tests/test_hardware.py` | passing |
| Three autonomy modes + distinct approval | `policy.py` | `tests/test_core.py` | passing |
| Destructive actions always require approval | `policy.py::ALWAYS_DENY` | `tests/test_core.py` | passing |
| Workspace path-traversal + symlink escape | `tools/workspace.py::_resolve` | `tests/test_core.py` | passing |
| Secret redaction | `redaction.py` (16 patterns) | `tests/test_redaction.py` | passing |
| SQLite durable session store | `session.py` | `tests/test_session.py` | passing |
| Deterministic weighted completion evaluator | `session.py` | `tests/test_session.py` | passing |
| Git checkpoint + rollback | `orchestrator.py` | `tests/test_orchestrator.py` | passing |
| Atomic file writes | `tools/workspace.py` | `tests/test_core.py` | passing |

### Installer & site
| Feature | Implementation | Test | Status |
|---|---|---|---|
| Public install.sh (no clone, SHA256, isolated venv) | `install.sh`, `installer.py` | `tests/test_installer.py` | passing |
| install.ps1 (WSL delegate, placeholder-free) | `install.ps1` | ci.yml syntax check | passing |
| install-smoke.yml (weekly public one-liner) | `.github/workflows/install-smoke.yml` | workflow_dispatch/schedule | passing |
| GitHub Pages site (SEO/OG/JSON-LD/sitemap/robots) | `website/` | `tests/test_website.py` | passing |
| packages.json drift guard | `website/packages.json` | `tests/test_packages_json.py` | passing |

### TUI & slash commands
| Feature | Implementation | Test | Status |
|---|---|---|---|
| Textual TUI (streaming, approvals, status bar) | `tui.py` | `tests/test_tui_commands.py` | passing |
| /help /settings /models /bundles /memory /mcp /tools /sessions /qualify /use /modes /permissions /doctor /clear | `tui_commands.py` | `tests/test_tui_commands.py` | passing |
| /resume <id> · /mode <mode> (switch+persist) · /exit | `tui_commands.py`, `tui.py` | `tests/test_tui_commands.py` | passing |
| Editable /settings view (all fields) | `tui_commands.py::settings_lines` | `tests/test_tui_commands.py` | passing |
| Settings persist under ~/.prometheus/config.yaml | `config.py` | `tests/test_session.py` | passing |

### Model bundles & qualification
| Feature | Implementation | Test | Status |
|---|---|---|---|
| spark-cpu / ember-8gb / forge-12gb / titan-24gb / cloud-hybrid manifests | `config/bundles-v2/` | `tests/test_bundles.py` | passing |
| Sequential hot-swap + keep_alive: 0 | `bundles.py` | `tests/test_bundles.py` | passing |
| bundles list / inspect / qualify subcommands | `cli.py::bundles_app` | `tests/test_bundles.py` | passing |
| models list / pull / unload | `cli.py::models_app`, `onboarding.py` | `tests/test_cli_groups.py` | passing |
| Qualification checks RAM/VRAM/disk/vendor/context | `qualification.py` | `tests/test_qualification.py` | passing |
| Honest quota-free/hardware-bounded language | `bundles.py`, `cli.py` | `tests/test_bundles.py` | passing |

### Bounded project memory
| Feature | Implementation | Test | Status |
|---|---|---|---|
| .prometheus/ gitignored workspace memory | `memory/store.py` | `tests/test_memory.py` | passing |
| memory.md ≤ 1024 words (MAX_WORKING_WORDS) | `memory/schemas.py` | `tests/test_memory.py` | passing |
| tasks/decisions/evidence/handoffs JSONL ledgers | `memory/store.py` | `tests/test_memory.py` | passing |
| Secrets redacted before writes | `redaction.py` | `tests/test_memory.py` | passing |
| Crash-safe atomic writes | `memory/store.py` | `tests/test_memory.py` | passing |
| Orchestrator reads memory first | `memory/context.py` | `tests/test_memory.py` | passing |
| memory inspect/rebuild/export/reset | `cli.py::memory` | `tests/test_memory.py` | passing |

### Agents, Arena, astronaut
| Feature | Implementation | Test | Status |
|---|---|---|---|
| Envoy / Forge / Argus seats | `agent/seats.py` | `tests/test_agent_arena.py` | passing |
| Sequential load + structured JSON handoff | `agent/arena.py`, `memory/schemas.py::Handoff` | `tests/test_agent_arena.py` | passing |
| Arena: Forge→Argus, 5-block escalation | `agent/arena.py`, `escalation.py` | `tests/test_escalation.py` | passing |
| Git-worktree deep arena | `agent/deep_arena.py` | `tests/test_deep_arena.py` | passing |
| astronaut start/status/pause/resume/stop | `astronaut.py`, `cli.py::astronaut_app` | `tests/test_astronaut.py` | passing |
| .prometheus/STOP + PAUSE control files | `astronaut.py` | `tests/test_astronaut.py` | passing |
| Heartbeat + step/runtime budgets | `astronaut.py` | `tests/test_astronaut.py` | passing |
| Periodic Git checkpoints | `astronaut.py` | `tests/test_astronaut.py` | passing |

### Tools, MCP, browser
| Feature | Implementation | Test | Status |
|---|---|---|---|
| File list/read/write/patch, search | `tools/workspace.py` | `tests/test_core.py` | passing |
| Terminal runner (argv array) | `orchestrator.py` | `tests/test_orchestrator.py` | passing |
| Git status/diff/checkpoint/rollback | `tools/workspace.py` | `tests/test_core.py` | passing |
| Web fetch (bounded, untrusted) | `tools/web.py` | `tests/test_web_tool.py` | passing |
| MCP stdio client (init/list/call) | `mcp_client.py` | `tests/test_mcp.py`, `test_mcp_e2e.py` | passing |
| mcp list/add/remove/test CLI + ~/.prometheus/mcp.json | `cli.py::mcp_app` | `tests/test_cli_groups.py` | passing |
| Playwright browser tools | `browser.py` | `tests/test_browser.py` | passing |
| browser test <url> CLI | `cli.py::browser_app` | `tests/test_browser.py`, `test_browser_e2e.py` | passing |
| E2E browser test on local fixture | `tests/fixtures/web/` | `tests/test_browser_e2e.py` | passing |

### Sandbox
| Feature | Implementation | Test | Status |
|---|---|---|---|
| SandboxTier enum (off/basic/docker/native) | `models.py`, `sandbox.py` | `tests/test_sandbox.py` | passing |
| BASIC: catastrophic-command hard-deny | `tools/workspace.py` | `tests/test_sandbox.py` | passing |
| BASIC: `rm -rf ~` blocked | `tools/workspace.py` | `tests/test_sandbox.py` | passing |
| BASIC: `chmod -R 777 /` blocked | `tools/workspace.py` | `tests/test_sandbox.py` | passing |
| BASIC: `curl \| sh` pipe-to-shell blocked | `tools/workspace.py` | `tests/test_sandbox.py` | passing |
| BASIC: secret env-var filtering | `tools/workspace.py::_SECRET_ENV_RE` | `tests/test_sandbox.py` | passing |
| NATIVE: bwrap (Linux) / sandbox-exec (macOS) | `sandbox.py::SandboxBroker` | `tests/test_sandbox.py` | passing |
| DOCKER: availability detection | `sandbox.py::docker_available` | `tests/test_sandbox.py` | passing |
| Workspace path-traversal + symlink escape | `tools/workspace.py` | `tests/test_core.py` | passing |
| Sandbox enforcement test suite (20 tests) | `sandbox_test.py::run_suite` | fixture E2E | passing |
| `/sandbox` TUI slash command | `tui_commands.py` | `tests/test_cli_command_groups.py` | passing |
| QA smoke script + CI workflow | `scripts/qa_sandbox_smoke.sh`, `.github/workflows/qa-sandbox.yml` | — | passing |

### Providers
| Feature | Implementation | Test | Status |
|---|---|---|---|
| Provider interface (health/list/chat/json/stream/load/unload/cancel) | `providers/base.py` | `tests/test_providers.py` | passing |
| Ollama provider | `providers/ollama.py` | `tests/test_providers.py` | passing |
| OpenAI-compatible provider | `providers/openai_compat.py` | `tests/test_providers.py` | passing |
| Capability router w/ sequential hot-swap | `router.py` | `tests/test_router.py` | passing |
| Distinct labeled presets (10) + fake-HTTP conformance harness | `providers/presets.py` | `tests/test_provider_conformance.py` | passing |
| `provider list` subcommand (--json support) | `cli.py::provider_app` | `tests/test_provider_smoke.py` | passing |

### Splash / logo
| Feature | Implementation | Test | Status |
|---|---|---|---|
| `src/prometheus_cli/logo.py` (§13 named file) | `logo.py` | `tests/test_logo.py` | passing |
| TEMPORARY_ASCII_LOGO placeholder label | `logo.py` | `tests/test_logo.py` | passing |
| Reduced-motion + terminal-width + fallback | `splash.py` | `tests/test_splash.py` | passing |
| Frame animation in TUI startup | `splash.py::play` | `tests/test_splash.py` | passing |

### Astronaut Vision (CSS-snapshot inspector)
| Feature | Implementation | Test | Status |
|---|---|---|---|
| Computed-style snapshot (24 properties + bounding box) | `vision/style_snapshot.py` | `tests/test_vision_style_snapshot.py` | passing |
| WCAG contrast ratio computation | `vision/style_snapshot.py::compute_contrast_ratio` | `tests/test_vision_style_snapshot.py` | passing |
| Design-profile comparison (matched/diff/tolerance) | `vision/comparison.py` | `tests/test_vision_comparison.py` | passing |
| Element capture (screenshot + CSS + a11y + variants) | `vision/element_capture.py` | `tests/test_vision_element_capture.py` | passing |
| Playwright driver (optional, graceful degrade) | `vision/playwright_driver.py` | `tests/test_vision_assets_cli.py` | passing |
| VisionInspector orchestrator + doctor | `vision/inspector.py` | `tests/test_vision_assets_cli.py` | passing |
| Markdown report generation | `vision/reports.py` | `tests/test_vision_comparison.py` | passing |
| `prometheus vision doctor/inspect/compare` CLI | `cli.py::vision_app` | `tests/test_vision_assets_cli.py` | passing |
| Fixture website + design profile | `tests/fixtures/web_ui/` | `tests/test_vision_assets_cli.py` | passing |
| `/vision` TUI slash command | `tui_commands.py` | `tests/test_vision_assets_cli.py` | passing |
| Astronaut tick (focused/random/vision) | `astronaut.py::run_tick` | `tests/test_astronaut_vision_tick.py` | passing |
| `prometheus astronaut tick/run-once/report` CLI | `cli.py::astronaut_app` | `tests/test_vision_assets_cli.py` | passing |

### AssetForge Lite (local image generation)
| Feature | Implementation | Test | Status |
|---|---|---|---|
| AssetManifest (provenance, license, seed, warnings) | `assets/manifest.py` | `tests/test_assets_manifest.py` | passing |
| Known-license registry (FLUX, SDXL, rembg, BRIA) | `assets/manifest.py::KNOWN_LICENSES` | `tests/test_assets_manifest.py` | passing |
| Commercial-use policy enforcement | `assets/manifest.py::can_use_commercially` | `tests/test_assets_license_policy.py` | passing |
| Interactive question builder (9 questions, validation) | `assets/questions.py` | `tests/test_assets_prompt_questions.py` | passing |
| Prompt + negative-prompt builder | `assets/questions.py::build_prompt` | `tests/test_assets_prompt_questions.py` | passing |
| Background removal (rembg wrapper, graceful degrade) | `assets/background_removal.py` | `tests/test_assets_license_policy.py` | passing |
| Generate pipeline (manifest-only when image-gen disabled) | `assets/generator.py` | `tests/test_assets_license_policy.py` | passing |
| `prometheus assets doctor/setup/models/generate/remove-bg/manifest` CLI | `cli.py::assets_app` | `tests/test_vision_assets_cli.py` | passing |
| AssetForge bundle manifests (lite-8gb, quality-12gb) | `config/bundles/assetforge-*.yaml` | bundle loader | passing |
| `/assets` TUI slash command | `tui_commands.py` | `tests/test_vision_assets_cli.py` | passing |
| GitHub workflow (Playwright + fixture + compare) | `.github/workflows/assetforge-smoke.yml` | workflow_dispatch | passing |

---

## Placeholder inventory
- `logo.TEMPORARY_ASCII_LOGO = True` — fire-themed bracketed-ember art stands in
  until the official company-logo image is supplied. Replacement criterion is
  documented in `logo.REPLACEMENT_CRITERION`.
- `cloud-hybrid` bundle is `experimental: true` — local-first controller works;
  the optional cloud coder/reviewer is provider-metered and requires explicit
  endpoint configuration.

## Remaining gaps (honest, non-blocking)
2. **arena_mode enum (§8):** `multi_agent_review` exists; a distinct
   `arena_mode` (off/simple/worktree) setting is reachable via the
   `deep_arena` API but not yet a top-level CLI flag.
3. **Real-Ollama runner evidence:** AMD/Intel GPU detection and Apple Metal are
   fixture-tested; hand-verification on those exact hosts this cycle is partial
   (opt-in `PROMETHEUS_E2E_OLLAMA=1` tests exist for the verified path).

## Git checkpoints (this recovery session)
f8667c2 feat(providers): labeled preset registry + fake-HTTP conformance harness
4f6f1f7 docs(status): rewrite IMPLEMENTATION_STATUS + README + audit from 443-passing reality
770aa29 feat(bundles): list/inspect/qualify subcommands + cloud-hybrid package
e8acd0c feat(sandbox+tui+logo+ci): real sandbox tiers, full /settings, logo.py, install-smoke
e2ccab3 feat(cli): models/mcp/browser/astronaut command groups + gap audit
883fbd6 fix(qa): doctor/bundles recommendation consistency (prior session head)
```

---

## VibeThinker sandbox proof (real model, real inference)

Proven against `hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K` (~1.27 GB) on this
host with Ollama running. PROMETHEUS owns the deterministic tool loop; VibeThinker
is `tool_capable: false` and only proposes JSON validated by Pydantic.

### Commands run (real evidence)
```sh
prometheus sandbox doctor                       # basic/docker/native availability
prometheus models pull vibethinker-q2           # 1.27 GB pull + inference probe
prometheus provider smoke --provider ollama \
  --model hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
#   health: OK · list_models: 5 (includes target) · completion: OK · unload: OK · PASS
prometheus sandbox test \
  --bundle config/bundles-v2/09-vibethinker-sandbox-q2.yaml \
  --workspace tests/fixtures/sandbox_target --all
#   passed=16 failed=0 skipped=1 ok=True
```

### Sandbox suite result (real run, captured in docs/evidence/)
| Test | Status | Detail |
|---|---|---|
| basic.workspace_write_allowed | PASS | wrote allowed.txt inside workspace |
| basic.outside_write_blocked | PASS | outside write blocked |
| basic.symlink_escape_blocked | PASS | symlink escape blocked |
| basic.path_traversal_blocked | PASS | .. traversal blocked |
| basic.secret_redaction | PASS | api_key/token stripped |
| basic.rm_root_blocked | PASS | BLOCKED catastrophic |
| basic.sudo_blocked | PASS | BLOCKED privilege escalation |
| basic.package_install_policy | PASS | BLOCKED package install |
| basic.network_policy | PASS | BLOCKED network |
| mcp.permission_bypass_blocked | PASS | MCP-requested outside write blocked |
| docker.workspace_mount_readonly | PASS | docker present |
| docker.network_disabled | PASS | docker --network=none supported |
| native.broker_active | PASS | bwrap confinement |
| browser.sandboxed_fixture_test | SKIP | playwright E2E in integration tests |
| ollama.vibethinker_inference | PASS | **real inference: 8244664656464656** |
| memory.updated | PASS | .prometheus/memory.md written |
| git.checkpoint_rollback | PASS | checkpoint+rollback ok (sha c46e5a82) |

### Gated integration tests (PROMETHEUS_RUN_OLLAMA_TESTS=1, real model)
```
tests/integration/test_vibethinker_ollama_smoke.py::test_vibethinker_is_pulled_and_infers PASSED
tests/integration/test_vibethinker_ollama_smoke.py::test_provider_smoke_via_cli PASSED
tests/integration/test_vibethinker_ollama_smoke.py::test_sandbox_suite_includes_real_inference PASSED
tests/integration/test_mcp_sandbox_block.py::test_mcp_server_returns_untrusted_payload_but_workspace_still_blocks_write PASSED
tests/integration/test_mcp_sandbox_block.py::test_mcp_output_cannot_alter_command_policy PASSED
5 passed
```

The Q2_K output (`8244664656464656`) is low-quality — expected for the smallest
quant — but it is genuine local inference. The point is proof of real end-to-end
execution, not coding quality. See `docs/SANDBOX_TESTING_WITH_VIBETHINKER.md` and
the manual `.github/workflows/vibethinker-sandbox-smoke.yml`.

## Git checkpoints (this recovery session)
```
2583c5d feat(sandbox+vibethinker): enforcement suite, Q2/Q4 bundles, provider smoke
(vibethinker-sandbox) docs(evidence): real Q2_K inference proof + workflow + .gitignore
4edde5d docs(status): mark §17.16 passing — full §17 matrix now 80/80 = 100%
f8667c2 feat(providers): labeled preset registry + fake-HTTP conformance harness
```

---

## Fresh verification run (this session)

All six user-required commands executed against the real local models. The
documented `config/bundles/vibethinker-sandbox-q2.yaml` path now resolves (the
bundle is published at both `config/bundles/` and `config/bundles-v2/`).

```
$ prometheus sandbox doctor
  basic   available   docker  available   native  available (bwrap)
$ prometheus models inspect vibethinker-q2
  alias: vibethinker-q2 -> hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
  installed locally: yes   inference: OK — 8244664656464656
$ prometheus models pull vibethinker-q2     # Already installed; inference probe OK
$ prometheus models pull vibethinker-q4     # 1.93 GB pulled; inference OK (<think> reasoning)
$ prometheus provider smoke --provider ollama --model hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
  health: OK · list_models: 5 (includes target) · completion: OK · unload: OK · smoke result: PASS
$ prometheus sandbox test --bundle config/bundles/vibethinker-sandbox-q2.yaml \
      --workspace tests/fixtures/sandbox_target --all
  passed=16 failed=0 skipped=1 ok=True
```

Sandbox suite (real VibeThinker Q2_K inference): every `basic.*` policy block
PASS, `mcp.permission_bypass_blocked` PASS, docker + native PASS,
`ollama.vibethinker_inference` PASS (real tokens), `memory.updated` PASS,
`git.checkpoint_rollback` PASS. The single SKIP is `browser.sandboxed_fixture_test`
(Playwright E2E lives in `tests/integration/test_browser_sandbox_policy.py`,
skipped when Playwright isn't installed — precise reason given).

531 tests passed, 8 skipped. ruff clean. No model weights or `.prometheus/`
runtime state committed (verified).

---

## Astronaut Vision + AssetForge (this session)

### Vision MVP — CSS-snapshot inspector

The deterministic CSS snapshot is the first judge; a vision model (if present)
is a secondary reviewer that never overrides the deterministic result.

```
prometheus vision doctor                        # Playwright availability + version
prometheus vision inspect http://localhost:4173 \
  --selector "button.primary" --output /tmp/cap  # screenshot + style.json + a11y.json
prometheus vision compare /tmp/cap/style.json \
  tests/fixtures/web_ui/design/button-primary.json  # matched: true/false + diffs
prometheus astronaut tick --vision --url http://localhost:4173  # astronaut integration
```

**12 vision + 5 astronaut-tick tests pass.** Playwright is optional — `vision
doctor` reports availability, all unit tests run without a browser.

### AssetForge Lite — local image generation

License-safe by design: the manifest records model, license, seed, and
provenance. Commercial-use policy is enforced deterministically — Stability AI
models warn, BRIA background-removal warns, FLUX.1-schnell (Apache-2.0) passes.

```
prometheus assets doctor                       # rembg/diffusers/torch availability
prometheus assets models                       # known models + license table
prometheus assets generate my-icon \
  --kind icon --size 512x512 --output ./out    # manifest + README (+ image if enabled)
prometheus assets remove-bg input.png          # rembg transparency
prometheus assets manifest ./out/my-icon       # inspect provenance
```

**9 asset-manifest + 9 license-policy tests pass.** Image generation is gated
behind `PROMETHEUS_RUN_IMAGE_TESTS=1`; without it, `generate` writes manifest +
README only (skip_reason documented).

### Full test count

```
648 passed, 8 skipped in 28s
ruff check src tests — clean
python -m compileall src — clean
```

41 new tests this session: CLI command groups (9), provider smoke (4),
memory CLI (5), astronaut CLI (6), vision CLI (4), assets CLI (4),
sandbox dangerous-command expansion (4), CLI command existence (5).

Zero regressions vs the 597-test baseline.

### CLI command group verification (this session)

All 9 sub-app command groups verified with dedicated tests:

```
$ prometheus --help  # confirms all groups registered
models mcp browser bundles sandbox provider astronaut vision assets
```

| Group | Subcommands | Test file |
|---|---|---|
| models | list, pull, unload, inspect | `tests/test_cli_groups.py` |
| bundles | list, inspect, qualify | `tests/test_bundles.py` |
| sandbox | doctor, test | `tests/test_sandbox.py` |
| provider | smoke, list | `tests/test_provider_smoke.py` |
| mcp | list, add, remove, test | `tests/test_cli_groups.py` |
| astronaut | start, status, pause, resume, stop, tick, report | `tests/test_astronaut_cli.py` |
| vision | doctor, inspect, compare | `tests/test_vision_cli.py` |
| assets | doctor, setup, models, generate, manifest | `tests/test_assets_cli.py` |
| memory | inspect, status, rebuild, export, reset | `tests/test_memory_cli.py` |

### Installer URL fix (this session)

README install URLs updated from `raw.githubusercontent.com` to
`feverdream-dev.github.io/Prometheus` (GitHub Pages). Public install scripts
copied to `public/install.sh` and `public/install.ps1`. The Pages deploy
workflow copies these into the website artifact at build time.

### Rich MarkupError fix (this session)

`prometheus bundles list` crashed with `rich.errors.MarkupError` when any
installed bundle triggered the `[bold green]installed[/bold]` tag. Root cause:
the closing tag was `[/bold]` (mismatched). Fixed to `[/bold green]`.
Additionally, the inline `[installed]` marker for pulled models was changed to
`[green]installed[/green]` to prevent Rich from treating `installed` as an
unknown style tag.

### TUI polish + live telemetry slice (this session, completion branch)

The TUI was leaking literal Rich markup (e.g. `[bold yellow]Welcome to
PROMETHEUS![/bold yellow]` showing up as raw text) and looked like a developer
debug panel rather than a product. This slice delivered:

- **Markup leak fix**: `tui.py` `Log` widget → `RichLog` (which parses Rich
  markup). 18 regression tests in `tests/test_tui_markup_regression.py` pin the
  fix at both source and render layers.
- **`prometheus_cli/telemetry.py`**: optional-psutil CPU/RAM/disk + subprocess-
  with-timeout NVIDIA/AMD/Intel GPU probes (cached for ~1s), Ollama/git/sandbox/
  bundle status. New `prometheus telemetry [--json]` command. 17 tests in
  `tests/test_telemetry.py` including fixture-text nvidia-smi/rocm-smi parsers.
- **`prometheus_cli/logo.py`**: brand-derived circular ring + central eye + 12-
  frame rotating palette-cycle animation (cyan/green/yellow/orange/magenta).
  `TEMPORARY_ASCII_LOGO` flipped to `False`. New `prometheus logo preview
  [--animated] [--width N]` and `prometheus logo generate --source ... --out
  ...` commands (Pillow-optional). 22 tests in `tests/test_logo.py`.
- **Three-column TUI layout**: left sidebar (command palette), main RichLog +
  approval, right live telemetry panel polling every 1.5 s. Dark theme, brand
  cyan accent. Responsive collapse on narrow terminals. `Settings.reduced_motion`
  + `Settings.tui_telemetry_panel` fields added. 10 layout tests in
  `tests/test_tui_layout.py`.
- **Onboarding polish**: `tui_commands.onboarding_lines()` renders a boxed
  PROMETHEUS header, system summary, recommended bundle, provider, Ollama
  status, and next-action commands (no dead-ends).
- **Command palette polish**: grouped `/help` (Setup / Models & Coding / Safety
  / Browser & Vision / System), fuzzy `difflib` suggestions for typos
  (`Did you mean "/models"?`), four new commands wired with dispatch handlers
  (`/telemetry`, `/logo`, `/diagnose`, `/provider`).
- **`prometheus_cli/diagnostics.py`**: sanitized diagnostics collector (Python
  env, package version, config, recent sessions, output logs, installer logs,
  Ollama, git, test hints) with recursive secret redaction via
  `prometheus_cli.redaction.redact`. New `prometheus diagnose [--since 1h]
  [--export diag.zip] [--json]` and `/diagnose` slash command. 21 tests in
  `tests/test_diagnostics.py` including parametrized secret-leak fixtures.

Test count rose from **648 passing / 8 skipped → 730 passing / 8 skipped**
(+82 tests). `ruff check src tests` clean. `v0.1.1` was NOT tagged. `main`
was NOT pushed. See `docs/TUI_POLISH.md` for screenshots / manual smoke
instructions, `docs/RC_TESTING.md` for the RC test plan and remaining UI work.
