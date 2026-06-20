# PROMETHEUS

PROMETHEUS is a local-first, adaptive multi-model coding agent. It combines a
tool-capable controller with optional coding, reasoning, reviewing, and vision
specialists. **Ollama is the default backend**; cloud and other local
OpenAI-compatible backends are pluggable.

Runs on **Linux** (tested), **macOS** (CI), and **Windows/WSL** (WSL only —
native Windows is not supported yet). Detects NVIDIA, AMD, Intel, and Apple
Silicon GPUs and recommends a model bundle that actually fits your hardware.

## Install (public one-liner — no clone needed)

**Linux / macOS / WSL:**
```sh
curl -fsSL https://raw.githubusercontent.com/FeverDream-dev/Prometheus/main/install.sh | sh
```

**Windows (delegates to WSL):**
```powershell
irm https://raw.githubusercontent.com/FeverDream-dev/Prometheus/main/install.ps1 | iex
```

Prefer to inspect first?
```sh
curl -fsSL https://raw.githubusercontent.com/FeverDream-dev/Prometheus/main/install.sh -o install.sh
less install.sh      # review it
sh install.sh
```

The installer downloads the **verified** release source archive from GitHub
(SHA-256 checked for releases), creates an isolated versioned venv under
`~/.local/share/prometheus/versions/<version>`, places a `prometheus` launcher
in `~/.local/bin`, and runs `prometheus doctor`. It **never** touches your
system Python and **never** depends on PyPI. Flags: `--dry-run`, `--version`,
`--prefix`, `--no-tui`, `--no-ollama`, `--yes` (CI).

## Quick start

```bash
prometheus            # launch the TUI (with startup splash)
prometheus setup      # detect hardware, pick a bundle, configure Ollama
prometheus doctor     # full hardware report + Ollama service status
prometheus run "Fix the failing tests" --workspace .
prometheus sessions   # list recent sessions and completion
prometheus resume <id>
prometheus update --check
prometheus uninstall  # keeps your models, sessions, and config by default
```

### Model packages, models, MCP, browser, astronaut

```bash
prometheus bundles                       # list packages with hardware fit
prometheus bundles inspect ember-8gb-gpu  # full manifest + fit reasoning
prometheus bundles qualify spark-cpu-8gb  # capability tests (needs Ollama)
prometheus models list                    # installed Ollama models
prometheus models pull --bundle spark-cpu-8gb   # pull a package's models
prometheus models unload                  # evict models from VRAM (keeps weights)
prometheus mcp list                       # configured MCP stdio servers
prometheus mcp add echo -- python -m my_mcp_server
prometheus mcp test echo                  # initialize + list tools
prometheus browser test https://example.com   # Playwright evidence (console/network)
prometheus astronaut start "objective" --workspace .  # long-run autonomous session
prometheus astronaut status               # state + heartbeat + budgets
prometheus astronaut pause                # writes .prometheus/PAUSE
prometheus astronaut stop                 # writes .prometheus/STOP
```

`prometheus run` uses the bundle saved by `prometheus setup` (or pass
`--bundle <path>`). `prometheus setup` detects Ollama, **offers to install it
only after explicit consent** (showing the exact command), pulls approved
models with live progress, and runs a real inference smoke test.

### Three autonomy modes

| Mode | Behavior |
|---|---|
| **Copilot** | Suggestive: reads automatically, asks before any write/command |
| **Pilot** | Balanced: edits and safe tests automatically, asks before network/installs/risky commands |
| **Astronaut** | Autonomous within declared scope; destructive actions always require approval |

### Completion is evidence-driven

PROMETHEUS never trusts a model's self-reported completion percentage. A
deterministic evaluator computes completion from **weighted acceptance
criteria** that the model proposes and then satisfies with tool-result evidence
(passing tests, successful builds). A session cannot reach "complete" unless the
configured target (default 95%) is met **and** every critical criterion passes.

## Support matrix (honest)

| Platform | Status | Notes |
|---|---|---|
| Linux x86_64 | **Supported** | Verified on the development machine (AMD CPU/GPU, Ollama). CI runs Ubuntu. |
| macOS (Apple Silicon + Intel) | **Supported** | Exercised via CI; not hand-verified in this release cycle. |
| Windows (WSL 2) | **Supported (WSL only)** | The PowerShell bootstrap installs inside WSL. |
| Windows (native) | **Not supported** | Use WSL 2. Native is a later phase. |
| AMD / Intel GPU detection | **Implemented** | Linux sysfs probes; fixture-tested, real-runner evidence partial. |
| Apple Metal | **Implemented** | Mocked tests; not hand-verified on Apple Silicon this cycle. |
| NVIDIA detection | **Implemented** | nvidia-smi probe; fixture-tested. |

## What works (verified)

- Cross-platform hardware detection (CPU/RAM/GPU/VRAM/disk/CPU features) and an
  honest **Ollama binary-vs-service** distinction in `doctor`.
- `prometheus setup` wizard: consent-gated Ollama install, streaming model pull
  with progress + cancellation, and a real `/api/generate` inference smoke test.
- SQLite session store with monotonic event log, tasks, evidence, checkpoints,
  crash-recovery resume.
- Deterministic weighted completion evaluator (overrides model self-report).
- Git checkpoint and rollback; atomic file writes (temp+fsync+rename).
- Secret redaction from evidence, model requests, and output.
- Workspace path-traversal and symlink-escape protection.
- Textual TUI with streaming, approval prompts, status bar, and a startup splash.
- Ollama and OpenAI-compatible provider adapters.
- Schema-constrained agent loop with five-failure escalation.
- Sandbox broker (bubblewrap / sandbox-exec), Playwright browser tools, MCP client.
- **Four-tier sandbox** (`off` / `basic` / `docker` / `native`): the `basic` tier
  hard-denies catastrophic commands (`rm -rf /`, `mkfs`, `dd` to devices, fork
  bombs); `native` confines via bubblewrap/sandbox-exec; `docker` is detected.
- **Bounded project memory** (`.prometheus/memory.md` ≤ 1024 words + JSONL
  ledgers for tasks/decisions/evidence/handoffs), atomic + crash-safe, read by
  the orchestrator every turn.
- **Three-seat Arena** (Envoy/Forge/Argus) with structured handoffs, five-block
  escalation, and a deep-arena git-worktree mode; `multi_agent_review` default on.
- **Astronaut long-run mode** (`prometheus astronaut start/status/pause/resume/stop`)
  with `.prometheus/STOP`+`PAUSE` control files, heartbeat state, step/runtime
  budgets, and periodic Git checkpoints.
- **`prometheus models`** (list/pull/unload), **`prometheus mcp`**
  (list/add/remove/test + `~/.prometheus/mcp.json`), **`prometheus browser test`**,
  and **`prometheus bundles`** sub-app (list/inspect/qualify).
- TUI slash commands: `/help /settings /models /bundles /memory /mcp /tools
  /sessions /qualify /use /modes /permissions /doctor /clear /resume /mode /exit`.
- Rotating ASCII splash engine (3 sizes, 16-24 frames; non-TTY and reduced-motion safe).
- **Real-Ollama inference proven** against `llama3.2:latest` (opt-in E2E test).

## Experimental / planned / unsupported

- **Experimental:** sandbox enforcement (broker present, not enforced by default);
  multi-provider review hot-swap; signed bundle ecosystem.
- **Planned:** native Windows; macOS Apple Silicon real-runner verification;
  local daemon + desktop client; provider OAuth; offline pack; updater rollback.
- **Placeholder:** the splash **logo art** is a temporary bracketed-ember stand-in.
  The official company-logo image has not been supplied; the logo acceptance
  criterion stays **incomplete** until it is and `tools/generate_splash.py` is
  re-run against it.
- **Unsupported:** model training/fine-tuning; bypassing provider subscription
  limits; fully unattended deployment/purchases without explicit grants.

## Privacy and model downloads

- PROMETHEUS is local-first. The installer and setup only contact
  `github.com` (release archive) and `ollama.com`/your configured model endpoint.
- **No telemetry** is collected. Local audit logs are user-readable and deletable.
- Model downloads can be **several GB**. `setup` shows the approximate size of
  each model **before** asking for confirmation, and discovers models you already
  have so nothing is re-downloaded. Shared Ollama models are never removed by
  `prometheus uninstall`.

## Troubleshooting

- **`prometheus: command not found`** — add `~/.local/bin` to PATH:
  `export PATH="$HOME/.local/bin:$PATH"` (add to `~/.bashrc` / `~/.zshrc`).
- **Ollama service not running** — `doctor` reports "installed, service NOT
  running". Start it: `ollama serve` (or let `setup` start it for you).
- **GPU not detected** — install current NVIDIA/AMD drivers; on Apple Silicon use
  an Ollama Metal build. Check `prometheus doctor`.
- **WSL setup** — `wsl --install -d Ubuntu`, then run the Windows one-liner.
- **Offline use** — after models are downloaded, PROMETHEUS runs fully offline.

## For developers

```bash
uv venv .venv --python 3.11 && . .venv/bin/activate
uv pip install -e '.[dev,tui]'
pytest -q                       # 443 tests (+ 3 opt-in real-Ollama)
ruff check src tests
prometheus doctor
```

### Real-Ollama end-to-end (opt-in)

With Ollama running and at least one model installed:
```bash
PROMETHEUS_E2E_OLLAMA=1 PROMETHEUS_E2E_MODEL=llama3.2:latest pytest tests/test_e2e_ollama.py -q -s
```

### Release

Tagging `v*` triggers `.github/workflows/release.yml`: lint + tests, build
sdist/wheel, SHA256SUMS + per-asset `.sha256` sidecars, CycloneDX SBOM, a GitHub
Release, and a clean-venv + bootstrap smoke job that fails the release on
breakage. (No release has been published yet — artifacts are built and tested
locally; the workflow is ready.)

### Project layout

- `src/prometheus_cli/` — CLI, TUI, orchestrator, providers, tools, session,
  hardware, onboarding, installer, sandbox, browser, MCP, splash.
- `install.sh` / `install.ps1` — public one-line bootstraps (repo root).
- `website/` — GitHub Pages static install site.
- `tools/generate_splash.py` — regenerate splash frames from a base shape/logo.
- `config/bundles/` — model bundles; `docs/` — specifications and status.

See `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`,
`docs/ACCEPTANCE_TESTS.md`, and `docs/MVP_RECOVERY_STATUS.md`.

## Product principles

- Local and private by default; internet use is explicit and visible.
- The deterministic engine, never an untrusted model, owns permissions and tools.
- Tests and runtime evidence determine completion.
- Every mutation is checkpointed and recoverable.

## License

Dual license — see `LICENSE.md`.
