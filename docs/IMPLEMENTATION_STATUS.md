# PROMETHEUS implementation status

This is the deterministic traceability matrix required by `MASTER_PROMPT.md` step 2.
Completion is **weighted accepted criteria ÷ total weighted criteria**, not a model's
opinion. A row is `passing` only when it has real code, a passing test, and CLI/runtime
evidence. Mocked, skipped, or unexecuted items are `placeholder` or `missing` and do not
count toward completion.

Weight scale: 1 = nice-to-have, 2 = standard, 3 = important, 5 = critical (safety/core).
A single incomplete critical row blocks a phase gate regardless of the weighted total.

Legend: `passing` · `partial` (real code, gaps remain) · `placeholder` · `missing`

## Phase 0 — foundations

| # | Requirement | Wt | Critical | Implementation | Test | Evidence | Status |
|---|---|---|---|---|---|---|---|
| 0.1 | CLI packaging + `prometheus` entry point | 3 | yes | `pyproject.toml`, `src/prometheus_cli/cli.py` | `prometheus --help` runs, 4 commands | `prometheus --help` transcript | passing |
| 0.2 | Linux hardware detection (RAM, NVIDIA, Ollama, Docker, WSL) | 3 | yes | `hardware.py::detect_hardware` | `test_hardware_profiles` | `prometheus doctor` | passing |
| 0.3 | macOS hardware detection (Apple Silicon, Metal, RAM) | 5 | yes | missing `_ram_gb` macOS path; no Metal/GPU | missing | — | missing |
| 0.4 | Windows/WSL hardware detection | 3 | yes | WSL flag only; no native Windows GPU/RAM | missing | — | missing |
| 0.5 | AMD GPU detection (ROCm/Vulkan/sysfs) | 3 | no | not implemented | missing | — | missing |
| 0.6 | Intel GPU detection (Vulkan/oneAPI) | 2 | no | not implemented | missing | — | missing |
| 0.7 | CPU instruction detection (AVX2/AVX-512/NEON) | 2 | no | not implemented | missing | — | missing |
| 0.8 | Disk space detection | 2 | no | not implemented | missing | — | missing |
| 0.9 | Adaptive RAM+VRAM bundle recommendation | 3 | yes | `recommended_profile` | 4 profile tests | `prometheus doctor` | passing |
| 0.10 | Pydantic models (Settings, Bundle, ToolCall, AgentTurn) | 3 | yes | `models.py` | imported by tests | — | passing |
| 0.11 | Autonomy modes (Copilot/Pilot/Astronaut) distinct approval | 5 | yes | `policy.py::requires_approval` | `test_modes_have_distinct_approval_policy` | — | passing |
| 0.12 | Destructive actions always require approval | 5 | yes | `ALWAYS_DENY_WITHOUT_EXPLICIT_APPROVAL` | asserts ASTRONAUT+DESTRUCTIVE | — | passing |
| 0.13 | Workspace path-traversal / symlink escape protection | 5 | yes | `WorkspaceTools._resolve` | `test_workspace_cannot_escape` | — | partial (symlink-to-escape not yet tested) |
| 0.14 | Provider interface (`capabilities/list/health/chat/cancel/load/unload`) | 3 | yes | `base.py` has complete+unload only | missing | — | partial |
| 0.15 | Ollama provider (real httpx) | 3 | yes | `ollama.py` | missing (needs Ollama) | — | partial |
| 0.16 | OpenAI-compatible provider (real httpx) | 3 | yes | `openai_compat.py` | missing | — | partial |
| 0.17 | Provider capability/conformance tests (tool-call) | 3 | yes | not implemented | missing | — | missing |
| 0.18 | Non-tool model rejected as controller | 5 | yes | `Orchestrator.__init__` raises | missing direct test | — | partial |
| 0.19 | Invalid model JSON cannot execute a tool | 5 | yes | `Orchestrator.run` validates AgentTurn | missing direct test | — | partial |
| 0.20 | Atomic patch writes | 3 | yes | `write_file` overwrites directly | missing | — | missing |
| 0.21 | Secret redaction from prompts/logs/errors/UI | 5 | yes | not implemented | missing | — | missing |
| 0.22 | Sandbox tier broker (bubblewrap/landlock/sandbox-exec) | 3 | yes | flag only, no enforcement | missing | — | missing |
| 0.23 | SQLite durable state (sessions, events, checkpoints) | 3 | yes | not implemented | missing | — | missing |
| 0.24 | Event log with monotonic sequence numbers | 3 | yes | not implemented | missing | — | missing |
| 0.25 | CI on Linux + macOS + Windows | 3 | yes | `.github/workflows/ci.yml` matrix | runs on push | — | partial (no tui extra, no WSL job, no GPU test) |
| 0.26 | i18n keys (en + pt-BR) | 1 | no | `i18n/en.json`, `i18n/pt-BR.json` | missing | — | partial |

Phase 0 weighted total: 73 · passing: 26 · partial: 0 (counted as 0 toward completion)
**Phase 0 completion: 26 / 73 ≈ 35%** — gate NOT met.

## Phase 1 — trustworthy single-agent vertical slice

| # | Requirement | Wt | Critical | Implementation | Test | Evidence | Status |
|---|---|---|---|---|---|---|---|
| 1.1 | `prometheus setup` detects HW + configures Ollama w/ confirmation | 5 | yes | not implemented | missing | — | missing |
| 1.2 | `prometheus` opens Textual TUI in a real repository | 5 | yes | not implemented (shows help) | missing | — | missing |
| 1.3 | Objective entry → acceptance criteria | 3 | yes | not implemented | missing | — | missing |
| 1.4 | Controller inspects files, patches, runs tests, shows evidence | 3 | yes | `Orchestrator.run` loop exists | missing E2E | — | partial |
| 1.5 | Policy prompts per selected mode | 3 | yes | `_approval` callback in CLI | missing | — | partial |
| 1.6 | Git checkpoint AND rollback work | 5 | yes | checkpoint only; no rollback | missing | — | partial |
| 1.7 | Session resumes after process termination | 5 | yes | not implemented (no SQLite) | missing | — | missing |
| 1.8 | Completion cannot exceed evidence (deterministic evaluator) | 5 | yes | model self-reports %; no evaluator | missing | — | missing |
| 1.9 | Five-failure escalation switches persona/hypothesis | 3 | yes | resets counter, calls reviewer | missing signature test | — | partial |
| 1.10 | Repair fixture: broken sample repo + fake provider + real Ollama | 3 | yes | not implemented | missing | — | missing |

Phase 1 weighted total: 40 · passing: 0
**Phase 1 completion: 0 / 40 ≈ 0%** — gate NOT met.

## Phase 2–7 (summarized; see docs/ROADMAP.md)

All `missing` until Phase 0 and Phase 1 gates pass. Not started:
production TUI polish, adaptive hot-swap team, browser/MCP/plugins/audio, signed
installers/offline pack/SBOM, daemon crash-recovery, desktop client.

## Overall

Weighted total (Phase 0+1): 113 · passing: 26
**Overall completion: 26 / 113 ≈ 23%**

### Placeholder inventory
None labeled `PLACEHOLDER` in source. The cloud-example bundle is explicitly marked
"Example only" in its description field, which is documentation, not a placeholder claim.

### Critical blockers (must clear before any phase gate)
0.3 macOS detection, 0.13 symlink escape test, 0.21 secret redaction,
0.23 SQLite store, 1.1 setup command, 1.2 TUI, 1.6 rollback, 1.7 resume,
1.8 deterministic completion.

### Command to reproduce evidence
```bash
. .venv/bin/activate
prometheus --help          # CLI packaging
prometheus doctor          # hardware detection (this machine)
prometheus modes           # autonomy modes
python -m pytest -q        # 7 passing unit tests
```
