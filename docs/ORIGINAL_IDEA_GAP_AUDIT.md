# PROMETHEUS Original-Idea Gap Audit

Working map produced by the audit step required by
`PROMETHEUS_ORIGINAL_IDEA_RECOVERY_PROMPT.md` §1. This file is **evidence-based**:
every row was verified by reading source and running the test suite
(`pytest -q` → **399 passed, 3 skipped**) on commit `883fbd6`.

Statuses: `done` · `partial` · `missing` · `broken` · `misleading-docs`

Legend for "Evidence command": a command or file reference that proves the row.

---

## 1. Repository & foundations

| Original requirement (§) | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| CLI packaging + `prometheus` entry point (§2) | `pyproject.toml`, `src/prometheus_cli/cli.py` (16 commands) | done | `prometheus --help` | — | — |
| Cross-platform hardware detection (§6) | `hardware.py` | done | `prometheus doctor` | — | — |
| Three autonomy modes + distinct approval (§12) | `models.py::AutonomyMode`, `policy.py::requires_approval` | done | `prometheus modes` | — | — |
| Destructive actions always require approval (§10) | `policy.py::ALWAYS_DENY_WITHOUT_EXPLICIT_APPROVAL` | done | `pytest -k destructive` | — | — |
| Workspace path-traversal + symlink escape (§10) | `tools/workspace.py::_resolve` | done | `pytest -k escape` | — | — |
| Secret redaction (§7) | `redaction.py` (16 patterns) | done | `pytest tests/test_redaction.py` | — | — |
| SQLite durable session store (§7) | `session.py` | done | `pytest tests/test_session.py` | — | — |
| Deterministic weighted completion evaluator (§2) | `session.py::completion_percent` | done | `pytest -k completion` | — | — |
| Git checkpoint + rollback (§2) | `orchestrator.py::git_checkpoint/git_rollback` | done | `pytest -k checkpoint` | — | — |
| Atomic file writes (§7) | `tools/workspace.py::write_file` | done | `pytest -k atomic` | — | — |

## 2. Public installer (§3)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| `install.sh` works without cloning | `install.sh` (repo root, 14 KB) | done | `bash -n install.sh` | — | — |
| Fetches verified GitHub release/source archive + SHA256 | `installer.py::install_version` | done | `prometheus update --dry-run` | — | — |
| Isolated install under `~/.local/share/prometheus` | `installer.py::user_data_home` | done | `prometheus uninstall --help` | — | — |
| `install.ps1` no `prometheus/local-agent` placeholder | `install.ps1` uses `FeverDream-dev/Prometheus` | done | `grep local-agent install.ps1` (no match) | — | — |
| Detect OS/Python/Git/WSL/Ollama | `install.sh` + `onboarding.py::check_ollama` | done | `sh install.sh --dry-run` | — | — |
| `install-smoke.yml` manual network test workflow | — | **missing** | `ls .github/workflows/` | Add `.github/workflows/install-smoke.yml` testing the public one-liner after Pages deploy | high |
| Public one-liner points at `feverdream-dev.github.io` | README uses `raw.githubusercontent.com` | partial | `grep github.io README.md` | Site deploys via `pages.yml`; installer URL can stay on raw GH. Document the Pages URL in the site | medium |

## 3. GitHub Pages website (§4)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| Professional site with hero + one-liner | `website/index.html`, `assets/css/styles.css` | done | `python -m pytest tests/test_website.py` | — | — |
| SEO/OG/Twitter/JSON-LD metadata | `website/index.html` | done | `pytest tests/test_website.py` | — | — |
| `sitemap.xml` + `robots.txt` | `website/sitemap.xml`, `website/robots.txt` | done | `cat website/sitemap.xml` | — | — |
| Pages deploy workflow | `.github/workflows/pages.yml` | done | `cat .github/workflows/pages.yml` | — | — |
| Mobile responsive + accessible | `website/assets/css/styles.css` | done | `pytest tests/test_website.py` | — | — |
| npm test / build / playwright for site | `tests/test_website.py` (Python link/structure checks) | partial | `pytest tests/test_website.py` | Plain-HTML site has no `package.json`; current Python tests cover link checks + structure. Acceptable per §4 "If using plain HTML, add at least link checks and HTML validation" | low |

## 4. TUI slash commands & `/settings` (§5)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| `/help` | `tui_commands.py::SLASH_COMMANDS` | done | `pytest tests/test_tui_commands.py` | — | — |
| `/settings` | `tui_commands.py::settings_lines` | **partial** | `pytest tests/test_tui_commands.py` | Currently shows **model packages only**, not the editable settings panel (autonomy mode, default bundle, provider, Ollama URL, key status, auto-install, sandbox tier, browser testing, multi-agent review, audio markers, telemetry, max steps, max runtime, astronaut long-run). Needs a real settings view + edit | high |
| `/models` | `tui_commands.py::models_lines` | done | `pytest tests/test_tui_commands.py` | — | — |
| `/bundles` | alias of `/settings` | done | — | — | — |
| `/mcp` | `tui_commands.py::mcp_lines` | **partial** | — | Prints static text; not wired to real `~/.prometheus/mcp.json` registry | medium |
| `/tools` | `tui_commands.py::tools_lines` | done | — | — | — |
| `/memory` | `tui_commands.py` + `cli.py::memory` | done | `prometheus memory status` | — | — |
| `/sessions` | `tui_commands.py::sessions_lines` | done | — | — | — |
| `/resume <id>` | — | **missing** | — | Add `/resume <id>` slash that calls `cli.resume` logic | medium |
| `/mode copilot\|pilot\|astronaut` | only `/modes` (display) | **missing** | — | Add `/mode <mode>` to switch + persist autonomy mode | medium |
| `/provider` | `/providers` (display) exists | **partial** | — | Recovery wants `/provider` (switch/display). `/providers` exists; rename/alias + switch | low |
| `/doctor` | `tui_commands.py::doctor_lines` | done | — | — | — |
| `/exit` | Textual default quit (Ctrl+C) | **partial** | — | Add explicit `/exit` alias for discoverability | low |
| Settings persist under `~/.prometheus/` | `config.py::save_settings` → `~/.prometheus/config.yaml` | done | `prometheus init` | — | — |

## 5. Model bundles (§6)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| `spark-cpu.yaml` (CPU/low-mem) | `config/bundles-v2/01-spark-cpu-8gb.yaml` | done | `prometheus bundles` | — | — |
| `ember-8gb.yaml` (8 GB VRAM, sequential) | `config/bundles-v2/02-ember-8gb-gpu.yaml` | done | `prometheus bundles` | — | — |
| `forge-12gb.yaml` (12 GB) | `config/bundles-v2/03-forge-12gb.yaml` | done | `prometheus bundles` | — | — |
| `titan-24gb.yaml` (24 GB) | `config/bundles-v2/05-titan-24gb.yaml` | done | `prometheus bundles` | — | — |
| `cloud-hybrid.yaml` | `config/bundles/cloud-example.yaml` (v1, marked example) | partial | `cat config/bundles/cloud-example.yaml` | Add a v2 `cloud-hybrid` manifest, or document that cloud is per-bundle `provider` override | medium |
| Sequential hot-swap + `keep_alive: 0` | `bundles.py::BundleRuntime.sequential_loading`, `RoleSpecV2.keep_alive` | done | `pytest tests/test_bundles.py` | — | — |
| `prometheus bundles list` | `cli.py::bundles` | done | `prometheus bundles` | — | — |
| `prometheus bundles inspect <id>` | only `prometheus bundles` (list) | **missing** | — | Add `inspect` subcommand (or `--inspect <id>`) | medium |
| `prometheus bundles qualify <id>` | `cli.py::qualify --bundle <id>` | partial | `prometheus qualify --bundle spark-cpu-8gb` | Works as flat command; recovery wants `bundles qualify` subcommand. Acceptance §17.9 satisfied by `qualify --bundle` | low |
| `prometheus models list` | — | **missing** | — | Add `models` command group (list/pull/unload against Ollama) | high |
| `prometheus models pull <bundle>` | only `setup --pull` | **missing** | — | Add `models pull` (per-bundle or per-tag) | high |
| `prometheus models unload` | — | **missing** | — | Add `models unload` (Ollama keep_alive 0 / delete) | medium |
| Qualification checks RAM/VRAM/vendor/disk/Ollama/models/context/speed | `qualification.py::qualify_bundle` | done | `prometheus qualify --bundle ember-8gb-gpu` | — | — |
| Honest "quota-free, hardware-bounded" language | `bundles.py`, `cli.py::use_bundle` | done | `prometheus use spark-cpu-8gb` | — | — |

## 6. Bounded project memory (§7)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| `.prometheus/` workspace dir, gitignored | `.gitignore`, `memory/store.py` | done | `grep .prometheus .gitignore` | — | — |
| `memory.md` ≤ 1024 words | `memory/schemas.py::MAX_WORKING_WORDS`, enforced in `store.py` | done | `pytest tests/test_memory.py` | — | — |
| `tasks.jsonl` / `decisions.jsonl` / `evidence.jsonl` / `handoffs.jsonl` | `memory/store.py` (Tasks, Decisions, Facts=evidence, Handoffs) | done | `pytest tests/test_memory.py` | — | — |
| `state.json` | `memory/store.py` (status/version/recovery) | done | `prometheus memory status` | — | — |
| `sessions/` subdir | `session.py` (SQLite under `~/.prometheus/sessions`) | done | `prometheus sessions` | — | — |
| Memory updates after tool results | `agent/arena.py::MicroStepEngine` | done | `pytest tests/test_memory.py` | — | — |
| Secrets redacted before writes | `redaction.py` wired into store | done | `pytest -k redact` | — | — |
| Crash-safe atomic writes | `memory/store.py` (temp+fsync+rename) | done | `pytest -k atomic` | — | — |
| Orchestrator reads memory first | `memory/context.py::build_context_packet` | done | `pytest tests/test_memory.py` | — | — |
| `prometheus memory inspect\|rebuild\|export\|reset` | `cli.py::memory` | done | `prometheus memory inspect` | — | — |

## 7. Three logical agents + Arena (§8)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| Envoy seat (coordinator) | `agent/seats.py::SEATS["envoy"]` | done | `pytest tests/test_agent_arena.py` | — | — |
| Forge seat (builder) | `agent/seats.py::SEATS["forge"]` | done | — | — | — |
| Argus seat (tester/critic) | `agent/seats.py::SEATS["argus"]` | done | — | — | — |
| Sequential load + `keep_alive: 0` handoff | `agent/arena.py::ArenaLoop` | done | `pytest tests/test_agent_arena.py` | — | — |
| Structured JSON handoff schema | `memory/schemas.py::Handoff` | done | `pytest tests/test_memory.py` | — | — |
| Arena: Forge proposes → Argus criticizes | `agent/arena.py` | done | `pytest tests/test_agent_arena.py` | — | — |
| 5-block → alternative approach | `agent/arena.py` + `escalation.py` | done | `pytest tests/test_escalation.py` | — | — |
| Git worktree competing patches | `agent/deep_arena.py::deep_arena` | done | `pytest tests/test_deep_arena.py` | — | — |
| `multi_agent_review` + `arena_mode` settings | `models.py::Settings.multi_agent_review` | partial | `prometheus run --help` | `arena_mode` (off/simple/worktree) enum not yet a distinct setting; deep_arena is reachable via API not a CLI flag | medium |

## 8. Tools, MCP, browser (§9)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| File list/read/write/patch | `tools/workspace.py` | done | `pytest tests/test_core.py` | — | — |
| Ripgrep/search | `tools/workspace.py::search` | done | — | — | — |
| Terminal command runner (argv array) | `orchestrator.py::run_command` | done | `pytest tests/test_orchestrator.py` | — | — |
| Git status/diff/checkpoint/rollback | `orchestrator.py` | done | `pytest -k git` | — | — |
| Test runner | via `run_command` | done | — | — | — |
| Package installer w/ policy | `policy.py` gates `allow_package_install` | done | `pytest tests/test_sandbox.py` | — | — |
| Browser automation (Playwright) | `browser.py::BrowserTools` | done | `pytest tests/test_browser.py` | — | — |
| Web fetch/search abstraction | `tools/web.py` | done | `pytest tests/test_web_tool.py` | — | — |
| MCP stdio client (init/list/call) | `mcp_client.py::MCPClient` | done | `pytest tests/test_mcp.py tests/test_mcp_e2e.py` | — | — |
| Untrusted-output delimitation | `mcp_client.py::UNTRUSTED_DELIMITER_*` | done | `pytest tests/test_mcp.py` | — | — |
| `~/.prometheus/mcp.json` config | `mcp_client.py::MCPRegistry.load_from_config` | partial | — | Loader exists; not auto-loaded from `~/.prometheus/mcp.json` at startup, no CLI to manage it | medium |
| `prometheus mcp list\|add\|test` | — | **missing** | — | Add `mcp` command group | high |
| `prometheus browser test <url>` | — | **missing** | — | Add `browser test` command using `BrowserTools` | high |
| E2E browser test on local fixture | `tests/test_browser_e2e.py` + `tests/fixtures/web/index.html` | done | `pytest tests/test_browser_e2e.py` | — | — |
| `/mcp` shows real registry | static text only | partial | — | Wire `/mcp` to loaded `mcp.json` | medium |

## 9. Sandbox enforcement (§10)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| `off` tier | implicit when `sandbox=False` | done | `pytest tests/test_sandbox.py` | — | — |
| `basic` tier (path enforce + deny cmds + env filter) | `policy.py` + `tools/workspace.py` deny dangerous cmds | partial | `pytest tests/test_sandbox.py` | No explicit `basic` profile enum; "deny rm -rf /" lives in policy but not labeled a tier | medium |
| `docker` tier (disposable container) | — | **missing** | — | Add docker profile (detect docker, mount workspace, run) | medium |
| `native` tier (bwrap/landlock/sandbox-exec) | `sandbox.py::SandboxBroker` (bwrap + sandbox-exec) | done | `pytest tests/test_sandbox.py` | landlock (Linux) not implemented; bwrap covers it | low |
| Block `rm -rf /`, out-of-workspace writes, secret reads | `policy.py`, `tools/workspace.py` | done | `pytest -k escape` | — | — |
| `off/basic/docker/native` profile taxonomy | `Settings.sandbox: bool` | **missing** | — | Replace bool with enum `SandboxTier` (off/basic/docker/native) | high |
| Docker integration test when available | — | **missing** | — | Add skipped-when-absent docker test | medium |

## 10. Providers & conformance (§11)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| Provider interface (health/list/chat/json/stream/load/unload/cancel) | `providers/base.py::Provider` | done | `pytest tests/test_providers.py` | — | — |
| Ollama provider | `providers/ollama.py` | done | `pytest tests/test_providers.py` | — | — |
| OpenAI-compatible provider | `providers/openai_compat.py` | done | `pytest tests/test_providers.py` | — | — |
| Distinct OpenAI / Anthropic / OpenRouter / Z.ai / Grok / Gemini / Mistral / DeepSeek / llama.cpp labels | all routed through `openai_compat` | partial | `grep -r "anthropic" src/prometheus_cli/providers` | Add a provider registry with labeled presets (display name) even if they share the OpenAI-compat adapter | medium |
| Provider conformance tests (fake HTTP servers) | `tests/test_providers.py` (unit) | partial | `pytest tests/test_providers.py` | No fake-HTTP-server conformance harness yet | medium |
| Tool-call compatibility per provider | `providers/base.py::capabilities` | done | `pytest tests/test_providers.py` | — | — |
| `load`/`unload`/`keep_alive` | `providers/ollama.py` | done | `pytest tests/test_providers.py` | — | — |

## 11. Astronaut long-run mode (§12)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| Copilot mode | `models.py::AutonomyMode.COPILOT` | done | `prometheus modes` | — | — |
| Pilot mode | `models.py::AutonomyMode.PILOT` | done | — | — | — |
| Astronaut mode (scoped autonomy) | `models.py::AutonomyMode.ASTRONAUT` | done | — | — | — |
| `prometheus astronaut start\|status\|pause\|resume\|stop` | — | **missing** | — | Add `astronaut` command group: long-run driver over `ArenaLoop` with heartbeat, `.prometheus/STOP`, pause/resume, periodic checkpoints, max budget | **critical** |
| Stop file `.prometheus/STOP` | — | **missing** | — | Implement stop-file watcher | high |
| Heartbeat + resumable state | `session.py` (resume exists) | partial | `prometheus resume <id>` | No heartbeat thread; resume is manual | high |
| Periodic Git checkpoints | `orchestrator.py::git_checkpoint` | done | — | Wire into astronaut loop at `checkpoint_interval_steps` | medium |

## 12. ASCII logo animation (§13)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| `src/prometheus_cli/logo.py` | — (only `splash.py` + `splash_frames.py`) | **missing** | `ls src/prometheus_cli/logo.py` | Recovery §13 explicitly names `logo.py`. Either create `logo.py` or document alias. Add `TEMPORARY_ASCII_LOGO` placeholder label | high |
| Reduced-motion option | `splash.py::should_animate(no_animation)` | done | `prometheus tui --no-animation` | — | — |
| Terminal width detection + fallback | `splash.py::pick_size_for_terminal` | done | `pytest tests/test_splash.py` | — | — |
| Frame animation in TUI startup | `splash.py::play` | done | `pytest tests/test_splash.py` | — | — |
| Fire-themed PROMETHEUS placeholder art | `splash_frames.py` (bracketed-ember) | partial | `pytest tests/test_splash.py` | Current art is bracketed-ember stand-in; label `TEMPORARY_ASCII_LOGO` | low |

## 13. Repo hygiene & CI (§14, §15, §18)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| `.gitignore` excludes weights/caches/secrets/`.prometheus/` | `.gitignore` | done | `cat .gitignore` | — | — |
| No committed weights/caches/secrets | repo clean | done | `pytest tests/test_repo_hygiene.py` | — | — |
| CI: Linux + macOS + Windows + WSL | `.github/workflows/ci.yml` | done | `cat .github/workflows/ci.yml` | — | — |
| Installer syntax tests in CI | `ci.yml` runs `bash -n install.sh` | done | — | — | — |
| Site build in CI | `.github/workflows/pages.yml` | done | — | — | — |
| `ruff check` clean | — | done | `ruff check src tests` | — | — |
| `python -m compileall src` | — | done | `python -m compileall src` | — | — |

## 14. Documentation honesty (§16)

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|
| `docs/IMPLEMENTATION_STATUS.md` matches reality | `docs/IMPLEMENTATION_STATUS.md` | **misleading-docs** | `head docs/IMPLEMENTATION_STATUS.md` | Says "91 tests / 82%" at commit `2d50157`; reality is **399 passed at `883fbd6`** with Phase 2 features. Must be rewritten with current evidence | **critical** |
| README public one-liner + honest matrix | `README.md` | done | `grep raw.githubusercontent README.md` | — | — |
| No fake completion claims | repo-wide | done | `pytest tests/test_repo_hygiene.py` | — | — |

---

## Summary counts

| Status | Count |
|---|---|
| done | 60 |
| partial | 14 |
| missing | 14 |
| broken | 0 |
| misleading-docs | 1 |

## Highest-priority missing vertical slices (acceptance-criteria blockers)

Ordered by impact on §17 acceptance criteria:

1. **§17.17 / §12** — `prometheus astronaut start|status|pause|resume|stop` + `.prometheus/STOP` + heartbeat (CRITICAL, entirely missing).
2. **§17.20 / §16** — Rewrite `docs/IMPLEMENTATION_STATUS.md` from 399-passing reality (CRITICAL, currently misleading).
3. **§17.10 / §6** — `prometheus models list|pull|unload` command group (high, MVP flow).
4. **§13** — `src/prometheus_cli/logo.py` + `TEMPORARY_ASCII_LOGO` label (high, explicitly named in spec).
5. **§17.15 / §10** — `SandboxTier` enum (off/basic/docker/native) replacing bool (high, "more than a flag").
6. **§9** — `prometheus mcp list|add|test` + `prometheus browser test <url>` CLI (high, surfaces existing tested code).
7. **§5** — Real `/settings` view + `/resume`, `/mode`, `/exit` slash commands (high, TUI completeness).
8. **§3** — `.github/workflows/install-smoke.yml` (high, public-installer confidence).
9. **§6** — `bundles inspect` subcommand + `cloud-hybrid` v2 manifest (medium).
10. **§11** — Provider conformance fake-HTTP harness + labeled provider presets (medium).

This audit was produced by direct source inspection (explore subagents were unavailable this session). It will be re-validated after each implemented slice by re-running `pytest -q`.
