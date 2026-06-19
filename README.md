# PROMETHEUS

PROMETHEUS is a local-first, adaptive multi-model coding agent. It combines a tool-capable
controller with optional coding, reasoning, reviewing, and vision specialists. Ollama is the
default backend; cloud and other local OpenAI-compatible backends are pluggable.

Runs on Linux, macOS, and Windows/WSL. Detects NVIDIA, AMD, Intel, and Apple Silicon GPUs
automatically and recommends a model bundle that actually fits your hardware.

## Install (one-liner from a fresh clone)

**Linux / macOS / WSL:**
```bash
sh scripts/install.sh
```

**Windows (delegates to WSL):**
```powershell
pwsh scripts/install.ps1
```

The installer creates an isolated virtual environment at `~/.prometheus/venv`, installs
PROMETHEUS, creates a `prometheus` wrapper in `~/.local/bin`, and runs a hardware check.
It never touches your system Python.

## Quick start

```bash
prometheus setup          # detect hardware, pick a bundle, configure Ollama
prometheus doctor         # show full hardware report
prometheus tui            # launch the interactive Textual TUI
prometheus run "Fix the failing tests" --bundle config/bundles/ember-8gb.yaml --workspace .
prometheus sessions       # list recent sessions and completion
prometheus resume <id>    # inspect a session for continuation
```

### Three autonomy modes

| Mode | Behavior |
|---|---|
| **Copilot** | Suggestive: reads automatically, asks before any write/command |
| **Pilot** | Balanced: edits and safe tests automatically, asks before network/installs/risky commands |
| **Astronaut** | Autonomous: works within declared scope. Destructive actions always require approval |

### Completion is evidence-driven

PROMETHEUS never trusts a model's self-reported completion percentage. The deterministic
evaluator computes completion from **weighted acceptance criteria** that the model proposes
and then satisfies with tool-result evidence (passing tests, successful builds). A session
cannot reach "complete" unless the configured target (default 95%) is met **and** every
critical criterion passes.

## What works

- Cross-platform hardware detection (Linux/macOS/Windows, NVIDIA/AMD/Intel/Apple Silicon)
- `prometheus setup` with honest bundle recommendations and fit explanations
- SQLite session store with monotonic event log for crash recovery and resume
- Deterministic weighted completion evaluator (not a model opinion)
- Git checkpoint and rollback
- Atomic file writes (crash-safe via temp+rename)
- Secret redaction from evidence, model requests, and output
- Workspace path-traversal and symlink-escape protection
- Textual TUI with streaming, approval prompts, and status bar
- Ollama and OpenAI-compatible provider adapters
- Schema-constrained agent loop with five-failure escalation
- 91 automated tests including an end-to-end repair fixture

## What is specified but not yet finished

Browser automation (Playwright/Chrome MCP), full MCP transport, native sandboxes
(bubblewrap/landlock/sandbox-exec), sound playback, provider-specific OAuth, signed
bundle ecosystem, daemon recovery, and desktop client. These are tracked in
`docs/IMPLEMENTATION_STATUS.md` and `docs/ROADMAP.md`.

## For developers

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,tui]'
pytest -q           # 91 tests
ruff check src tests
prometheus doctor
```

## Product principles

- Local and private by default; internet use is explicit and visible.
- The deterministic engine, never an untrusted model, owns permissions and tool execution.
- Tests and runtime evidence determine completion.
- Every mutation is checkpointed and recoverable.
- Small specialist models supplement—not impersonate—tool-trained controller models.

See `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, and
`docs/IMPLEMENTATION_STATUS.md`.
