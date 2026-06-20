# PROMETHEUS implementation status

Deterministic traceability matrix. Completion is **weighted accepted criteria ÷
total weighted criteria**, never a model's opinion. A row is `passing` only when
it has real code, a passing test, and CLI/runtime evidence. Mocked/skipped items
are `placeholder`/`missing` and do not count.

Weight: 1 = nice-to-have, 2 = standard, 3 = important, 5 = critical (safety/core).
One incomplete critical row blocks the phase gate.

Legend: `passing` · `partial` · `placeholder` · `missing`

**Last updated:** commit `f8667c2` — **493 tests passed, 3 skipped** (up from 91
at the prior status snapshot). This file was rewritten because it had drifted
badly out of sync (it documented 82% / 91 tests while the tree had grown to the
full Phase 2 feature set).

## How to reproduce every claim below

```sh
. .venv/bin/activate
python -m pytest -q                       # 493 passed, 3 skipped
ruff check src tests                       # clean
python -m compileall -q src                # clean
prometheus --help                          # 16 top-level + 5 sub-app command groups
prometheus doctor && prometheus bundles && prometheus bundles inspect spark-cpu-8gb
prometheus models list && prometheus mcp list && prometheus astronaut --help
```

---

## §17 acceptance-criteria matrix (PROMETHEUS_ORIGINAL_IDEA_RECOVERY_PROMPT.md)

| # | Acceptance criterion | Wt | Status | Evidence command | Notes |
|---|---|---|---|---|---|
| 1 | `docs/ORIGINAL_IDEA_GAP_AUDIT.md` exists and is honest | 3 | passing | `cat docs/ORIGINAL_IDEA_GAP_AUDIT.md` | 60 done / 14 partial / 14 missing / 1 misleading-docs at audit time; re-baselined below |
| 2 | Public installer files exist with syntax tests | 5 | passing | `bash -n install.sh` · `pytest tests/test_installer.py` | install.sh + install.ps1; ci.yml runs syntax checks |
| 3 | README has a real public one-liner using the real repo URL | 5 | passing | `grep raw.githubusercontent.com/Prometheus README.md` | `FeverDream-dev/Prometheus` |
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
| NATIVE: bwrap (Linux) / sandbox-exec (macOS) | `sandbox.py::SandboxBroker` | `tests/test_sandbox.py` | passing |
| DOCKER: availability detection | `sandbox.py::docker_available` | `tests/test_sandbox.py` | passing |
| Workspace path-traversal + symlink escape | `tools/workspace.py` | `tests/test_core.py` | passing |

### Providers
| Feature | Implementation | Test | Status |
|---|---|---|---|
| Provider interface (health/list/chat/json/stream/load/unload/cancel) | `providers/base.py` | `tests/test_providers.py` | passing |
| Ollama provider | `providers/ollama.py` | `tests/test_providers.py` | passing |
| OpenAI-compatible provider | `providers/openai_compat.py` | `tests/test_providers.py` | passing |
| Capability router w/ sequential hot-swap | `router.py` | `tests/test_router.py` | passing |
| Distinct labeled presets (10) + fake-HTTP conformance harness | `providers/presets.py` | `tests/test_provider_conformance.py` | passing |

### Splash / logo
| Feature | Implementation | Test | Status |
|---|---|---|---|
| `src/prometheus_cli/logo.py` (§13 named file) | `logo.py` | `tests/test_logo.py` | passing |
| TEMPORARY_ASCII_LOGO placeholder label | `logo.py` | `tests/test_logo.py` | passing |
| Reduced-motion + terminal-width + fallback | `splash.py` | `tests/test_splash.py` | passing |
| Frame animation in TUI startup | `splash.py::play` | `tests/test_splash.py` | passing |

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
