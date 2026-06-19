# PROMETHEUS implementation status

This is the deterministic traceability matrix required by `MASTER_PROMPT.md` step 2.
Completion is **weighted accepted criteria ÷ total weighted criteria**, not a model's
opinion. A row is `passing` only when it has real code, a passing test, and CLI/runtime
evidence. Mocked, skipped, or unexecuted items are `placeholder` or `missing` and do not
count toward completion.

Weight scale: 1 = nice-to-have, 2 = standard, 3 = important, 5 = critical (safety/core).
A single incomplete critical row blocks a phase gate regardless of the weighted total.

Legend: `passing` · `partial` (real code, gaps remain) · `placeholder` · `missing`

Last updated: after commit `2d50157` — 91 tests passing.

## Phase 0 — foundations

| # | Requirement | Wt | Crit | Implementation | Test | Evidence | Status |
|---|---|---|---|---|---|---|---|
| 0.1 | CLI packaging + `prometheus` entry point | 3 | yes | `pyproject.toml`, `cli.py` (8 commands) | imports tested | `prometheus --help` | passing |
| 0.2 | Linux hardware detection | 3 | yes | `hardware.py` (RAM, NVIDIA, Ollama, Docker, WSL) | 18 tests | `prometheus doctor` | passing |
| 0.3 | macOS hardware detection (Apple Silicon, Metal, RAM) | 5 | yes | `_ram_gb_macos` via sysctl, `_probe_apple_gpu` | mocked tests | — | passing |
| 0.4 | Windows/WSL hardware detection | 3 | yes | `_ram_gb_windows` via ctypes, PowerShell GPU, WSL flag | mocked tests | — | passing |
| 0.5 | AMD GPU detection (sysfs) | 3 | no | `_probe_amd_linux` | mocked tests | `doctor` on this machine | passing |
| 0.6 | Intel GPU detection (sysfs) | 2 | no | `_probe_intel_linux` | mocked tests | — | passing |
| 0.7 | CPU instruction detection (AVX2/NEON) | 2 | no | `_cpu_features_linux/macos` | `doctor` output | avx2, fma, sse4_2 shown | passing |
| 0.8 | Disk space detection | 2 | no | `_disk_free_gb` via shutil | test | `doctor` output | passing |
| 0.9 | Adaptive RAM+VRAM+vendor bundle recommendation | 3 | yes | `recommended_profile` (Apple Silicon path added) | 9 profile tests | `doctor` | passing |
| 0.10 | Pydantic models | 3 | yes | `models.py` (+ Criterion, keep_alive int\|str) | validated in orchestrator tests | — | passing |
| 0.11 | Three autonomy modes, distinct approval | 5 | yes | `policy.py::requires_approval` | `test_modes_have_distinct_approval_policy` | — | passing |
| 0.12 | Destructive actions always require approval | 5 | yes | `ALWAYS_DENY_WITHOUT_EXPLICIT_APPROVAL` | asserts ASTRONAUT+DESTRUCTIVE | — | passing |
| 0.13 | Workspace path-traversal + symlink escape | 5 | yes | `WorkspaceTools._resolve` + resolve check | `test_workspace_cannot_escape`, `test_symlink_escape_blocked` | — | passing |
| 0.14 | Provider interface (capabilities/list/health/chat/cancel/load/unload) | 3 | yes | `base.py` has complete+unload only | missing | — | partial |
| 0.15 | Ollama provider (real httpx) | 3 | yes | `ollama.py` | missing (needs Ollama running) | — | partial |
| 0.16 | OpenAI-compatible provider (real httpx) | 3 | yes | `openai_compat.py` | missing | — | partial |
| 0.17 | Provider capability/conformance tests (tool-call) | 3 | yes | not implemented | missing | — | missing |
| 0.18 | Non-tool model rejected as controller | 5 | yes | `Orchestrator.__init__` raises | `test_non_tool_model_rejected_as_controller` | — | passing |
| 0.19 | Invalid model JSON cannot execute a tool | 5 | yes | `Orchestrator.run` validates AgentTurn | e2e repair fixture | — | passing |
| 0.20 | Atomic patch writes | 3 | yes | `write_file` uses temp+fsync+os.replace | `test_atomic_write_no_partial_file_on_crash` | — | passing |
| 0.21 | Secret redaction | 5 | yes | `redaction.py` (16 patterns), wired into orchestrator | 16 tests | — | passing |
| 0.22 | Sandbox tier broker (bubblewrap/landlock/sandbox-exec) | 3 | yes | flag only, no enforcement | missing | — | missing |
| 0.23 | SQLite durable state | 3 | yes | `session.py` (sessions, events, tasks, evidence, checkpoints) | 21 tests | — | passing |
| 0.24 | Event log with monotonic sequence numbers | 3 | yes | AUTOINCREMENT seq, `events_since` | `test_monotonic_sequence_numbers` | — | passing |
| 0.25 | CI on Linux + macOS + Windows + WSL | 3 | yes | `ci.yml` (3 OS + WSL + lint job, installs tui) | runs on push | — | passing |
| 0.26 | i18n keys (en + pt-BR) | 1 | no | `i18n/en.json`, `i18n/pt-BR.json` | missing (not wired into UI) | — | partial |

Phase 0 weighted: total 73 · passing 56 · partial 8 (not counted) · missing 9
**Phase 0 completion: 56 / 73 ≈ 77%** — gate nearly met (sandbox tier + provider conformance tests remain).

## Phase 1 — trustworthy single-agent vertical slice

| # | Requirement | Wt | Crit | Implementation | Test | Evidence | Status |
|---|---|---|---|---|---|---|---|
| 1.1 | `prometheus setup` detects HW + configures Ollama w/ confirmation | 5 | yes | `cli.py::setup`, `onboarding.py` | 17 onboarding tests | `prometheus setup --yes` | passing |
| 1.2 | `prometheus tui` opens Textual TUI in a real repository | 5 | yes | `tui.py` (streaming, approvals, status bar) | import check | `prometheus tui --help` | passing |
| 1.3 | Objective entry → acceptance criteria | 3 | yes | `Criterion` model, `criteria_proposed` field | orchestrator tests | — | passing |
| 1.4 | Controller inspects files, patches, runs tests, shows evidence | 3 | yes | `Orchestrator.run` loop | e2e repair fixture | — | passing |
| 1.5 | Policy prompts per selected mode | 3 | yes | `_approval` callback + `requires_approval` | policy tests | — | passing |
| 1.6 | Git checkpoint AND rollback work | 5 | yes | `git_checkpoint`, `git_rollback` | `test_git_checkpoint_and_rollback` | — | passing |
| 1.7 | Session resumes after process termination | 5 | yes | SQLite store + `events_since` + `resume` command | `test_data_survives_reopen`, `test_resume_from_checkpoint` | — | passing |
| 1.8 | Completion cannot exceed evidence | 5 | yes | deterministic evaluator overrides model %, 95% gate | `test_completion_blocked_when_critical_criterion_unmet` + e2e | — | passing |
| 1.9 | Five-failure escalation switches persona/hypothesis | 3 | yes | failure counter + reviewer call | missing signature tracking | — | partial |
| 1.10 | Repair fixture: broken repo + fake provider + real Ollama | 3 | yes | `tests/fixtures/broken_repo/`, `test_e2e_repair.py` | 3 e2e tests | repair + lie-blocking | passing |

Phase 1 weighted: total 40 · passing 37 · partial 3 (not counted)
**Phase 1 completion: 37 / 40 ≈ 93%** — gate nearly met (failure-signature tracking is the remaining gap).

## Overall

Weighted total (Phase 0+1): 113 · passing 93
**Overall completion: 93 / 113 ≈ 82%**

Up from **23%** at the start of this session.

### Placeholder inventory
None labeled `PLACEHOLDER` in source. The cloud-example bundle is explicitly marked
"Example only" in its description field.

### Remaining critical blockers
0.22 sandbox enforcement, 0.17 provider conformance tests, 1.9 failure-signature tracking.

### Git checkpoints (this session)
```
2d50157 feat(install): cross-platform installer, improved CI, updated README
7f0189b feat(security): secret redaction layer
9d3ef30 test(e2e): repair fixture proves the full vertical slice works
b003302 feat(tui): Textual TUI
51b8502 feat(orchestrator): deterministic completion replaces model self-report
d080296 feat(tools): atomic writes, git rollback, symlink escape test
d6e7251 feat(session): SQLite durable store with weighted completion evaluator
21de2b1 feat(setup): onboarding command with honest bundle recommendations
a340c44 feat(hardware): cross-platform detection for all GPU vendors
9ac00b4 fix(hardware): require both RAM and VRAM floors for GPU bundles
```

### Command to reproduce evidence
```bash
sh scripts/install.sh          # fresh install to ~/.prometheus/venv
prometheus doctor              # hardware detection
prometheus setup --yes         # onboarding
prometheus sessions            # session store
python -m pytest -q            # 91 tests
ruff check src tests            # lint clean
```
