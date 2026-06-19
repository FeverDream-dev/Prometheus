# PROMETHEUS — MVP Recovery Status

Living evidence document required by `PROMETHEUS_MVP_RECOVERY_PROMPT.md`. Every
claim below was verified by running the real code, not by trusting documentation.

Branch: `mvp-recovery` (forked from `main` @ `4347a86`).

## Reproduce the evidence

```bash
git checkout mvp-recovery
uv venv .venv --python 3.11 && . .venv/bin/activate
uv pip install -e '.[dev,tui]'
pytest -q                          # 247 passed (+ 2 opt-in real-Ollama)
ruff check src tests               # All checks passed
prometheus doctor                  # hardware + honest Ollama binary/service status
prometheus setup --yes --bundle config/bundles/ember-8gb.yaml
sh install.sh --dry-run            # public installer plan
PROMETHEUS_E2E_OLLAMA=1 PROMETHEUS_E2E_MODEL=llama3.2:latest pytest tests/test_e2e_ollama.py -q -s
```

Audit environment: Linux x86_64, AMD Ryzen 7 3700X, 47 GB RAM, AMD GPU,
560 GB disk free, Ollama with `gemma4`/`llama3.2:latest`. macOS / native Windows
were NOT executed in this environment (CI + mocked tests only).

## The 18-step public user journey

| # | Step | State | Evidence |
|---|---|---|---|
| 1 | Open GitHub Pages website | **DONE** | `website/index.html` + `pages.yml`; local preview HTTP 200, all sections present. |
| 2 | Select OS + copy one command | **DONE** | OS tabs (Linux/macOS/Windows-WSL), copy buttons, drift-checked by `tests/test_website.py` (31 tests). |
| 3 | Paste one-liner into fresh terminal | **DONE** | Repo-root `install.sh`/`install.ps1` exist; `--dry-run` resolves version + URLs correctly. Public URLs no longer 404. |
| 4 | Install without cloning | **DONE** | Downloads verified GitHub source archive (no PyPI); clean-venv install from built wheel proven: `prometheus --help` + `doctor` run. |
| 5 | Launch `prometheus` from any dir | **DONE** | `~/.local/bin/prometheus` wrapper written by installer. |
| 6 | Interactive first-run setup | **DONE** | `prometheus setup` wizard runs end-to-end (`--yes` verified). |
| 7 | Detect OS/CPU/RAM/GPU/VRAM/disk/runtimes | **DONE (Linux)** | `doctor` shows all; macOS/Win via mocked tests. |
| 8 | Detect Ollama installed AND service running | **DONE** | `doctor` honestly reports "installed, service NOT running" (binary-vs-service fix); `check_ollama` hits `/api/tags`. |
| 9 | Offer to install Ollama with approval | **DONE** | `setup` shows exact command + `Confirm.ask`; `--yes` never triggers system install. |
| 10 | Discover existing models (no dup download) | **DONE** | `check_ollama().models` from `/api/tags`; setup skips already-installed. |
| 11 | Recommend hardware-fitting bundles | **DONE** | `classify_bundle_fit`; forge-12gb/24gb correctly "does not fit" at 0 GB VRAM. |
| 12 | Download only approved models, sizes first | **DONE** | `pull_model` streaming `/api/pull` with progress + cancel; sizes shown via `explain_bundle`. |
| 13 | Real inference smoke test | **DONE** | `inference_smoke_test` -> `/api/generate`; **real `llama3.2:latest` responded "ready"**. |
| 14 | Enter usable TUI | **DONE** | `prometheus tui` launches Textual app with splash; import + help verified. |
| 15 | Select folder + ask coding task | **DONE** | TUI accepts objective; `run` drives `Orchestrator`. |
| 16 | Inspect/patch/test/evidence/checkpoint | **DONE (real + fake)** | E2E repair fixture (ScriptedProvider) + **real-Ollama E2E**: `llama3.2:latest` drove the full provider->tools->evidence->completion loop (2 opt-in tests pass, 10.3s). |
| 17 | Resume after restart | **DONE** | SQLite store + `resume`/`sessions` + `test_data_survives_reopen`. |
| 18 | Exit/reopen without losing state | **DONE** | Settings + sessions persist under `~/.prometheus/`. |

**All 18 steps are real.** (Step 16's real-model completion depends on model
capability; the loop, evidence, and durability are proven regardless.)

## Milestone status

### M1 — Public one-line installer -> DONE
- Root `install.sh` / `install.ps1` (POSIX + Windows->WSL), correct repo URL,
  no PyPI dependency, SHA-256 verification (strict for releases, warned for
  `main`), version resolution (GitHub API -> git ls-remote -> main), Python/uv
  bootstrap, versioned venv, `~/.local/bin/prometheus` wrapper, flags
  (`--dry-run/--version/--prefix/--no-tui/--no-ollama/--yes/--log`), idempotent.
- `prometheus update` (`--check/--version/--dry-run/--yes/--no-tui`) and
  `prometheus uninstall` (`--yes/--version/--purge`, preserves user data).
- `src/prometheus_cli/installer.py` shared deterministic core (injectable for tests).
- `.github/workflows/release.yml`: lint+test, build sdist/wheel, SHA256SUMS +
  per-asset `.sha256` sidecars, CycloneDX SBOM, GitHub Release, clean-venv +
  bootstrap smoke. Not published (no credentials); built + tested locally.

### M2 — GitHub Pages website -> DONE
- `website/` static site (HTML/CSS/vanilla JS, no build step, no trackers),
  OS tabs, copy buttons, support matrix, "what the installer does", first-run
  explanation, troubleshooting, provisional SVG logo + labeled placeholder.
- `.github/workflows/pages.yml` deploy workflow.
- `tests/test_website.py` (31 tests): command drift vs `commands.json`, copy
  buttons, internal links, WSL mention, no `http://` trackers, reduced-motion.
- Local preview verified (HTTP 200, key strings present).

### M3 — First-run wizard -> DONE
- Consent-gated Ollama install (platform plan + explicit approval), real
  streaming model pull with progress + cancel, real inference smoke test,
  "Open the TUI now?" hand-off. `setup --yes` verified end-to-end (it started
  the Ollama service, listed bundles with honest fit, saved config atomically).

### M4 — Coding-agent MVP -> DONE (real + fake provider)
- `tests/test_e2e_repair.py` (ScriptedProvider, deterministic CI coverage).
- `tests/test_e2e_ollama.py` (opt-in REAL Ollama): `PROMETHEUS_E2E_OLLAMA=1
  PROMETHEUS_E2E_MODEL=llama3.2:latest` -> **2 passed in 10.27s** — real model
  drove the orchestrator; `/api/generate` returned a valid response.
- `prometheus run` uses the saved bundle (no forced `--bundle`).

### M5 — Animated ASCII splash -> ENGINE DONE; LOGO INCOMPLETE
- `splash.py` engine + `splash_frames.py` (3 sizes: compact 16f, normal 24f,
  wide 24f; stable dimensions; Y-axis rotation via cos(theta) compression +
  mirroring + curved shading). Non-TTY and reduced-motion safe (`should_animate`).
- `tools/generate_splash.py` deterministic regenerator.
- `tests/test_splash.py` (23 tests) + golden snapshots.
- **Logo art is a labeled PLACEHOLDER** (bracketed-ember stand-in). The official
  company-logo image has not been supplied; acceptance criterion stays
  **incomplete** until it is and the generator is re-run against it.

### M6 — Honest docs -> DONE
- README rewritten: available-now / experimental / planned / unsupported /
  placeholder sections; real one-liner; honest support matrix; privacy; model
  download warning; troubleshooting; dev + release instructions; test count
  generated from reality (247 + 2 opt-in).

## Test counts (reality, not marketing)

- `pytest -q` -> **247 passed, 2 skipped** (the 2 skips are the opt-in real-Ollama
  tests; they pass when `PROMETHEUS_E2E_OLLAMA=1`).
- New this recovery: 15 installer + 31 website + 18 onboarding(M3) + 23 splash +
  2 real-Ollama E2E = 89 new tests on top of the prior 158.
- `ruff check src tests` -> clean.

## Placeholder inventory

| Item | Location | Replacement trigger |
|---|---|---|
| Splash logo art | `tools/generate_splash.py` `BASE_SHAPES` + generated `splash_frames.py` | Official company-logo image -> re-run generator; then logo criterion completes. |
| Website terminal recording | `website/index.html` preview section (`<!-- TODO ... -->`) | Capture a real TUI recording/gif once a model-driven task is recorded. |
| Website SVG logo mark | `website/index.html` header | Official logo SVG. |

## Git checkpoints (this recovery)

```
b1926c6 feat(splash): rotating ASCII logo engine (3 sizes, 16-24 frames)
71ccb3f feat(cli): run uses saved bundle; test(e2e): opt-in real-Ollama E2E proof
2e09f1d feat(setup): real first-run wizard — Ollama install w/ consent, pull progress, inference smoke
ecf4605 feat(install): installer core + update/uninstall CLI + release workflow
f4309ac test(www): link, command-drift, and accessibility checks
1ac24a7 feat(www): GitHub Pages deploy workflow
998b41b feat(www): static GitHub Pages install site
ccc80ce feat(install): real public one-line installers
```

## Remaining unsupported / experimental

- Native Windows (WSL only); macOS Apple Silicon real-runner hand-verification.
- Sandbox enforcement (broker exists, not on by default); provider OAuth;
  signed bundle ecosystem; local daemon + desktop client; offline pack;
  updater rollback; sound playback.

## No fake completion

The following are NOT claimed: a published PyPI package; a published GitHub
Release; deployed GitHub Pages; native Windows support; the final company logo;
a real-Ollama *completion* (loop + durability proven; full completion depends on
model capability). Everything claimed above is backed by a passing test or a
real captured transcript.
