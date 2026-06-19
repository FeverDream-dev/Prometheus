# PROMETHEUS — MVP Recovery Status

Living evidence document required by `PROMETHEUS_MVP_RECOVERY_PROMPT.md`. Every
claim below was verified by running the real code, not by trusting documentation.

Branch: `mvp-recovery` (forked from `main` @ `4347a86`).
Last updated: start of MVP recovery session.

## How this baseline was produced

```bash
git checkout mvp-recovery
.venv/bin/prometheus --help          # 8 commands present
.venv/bin/prometheus doctor          # works on Linux (AMD, Ollama ready)
.venv/bin/ruff check src tests       # All checks passed
.venv/bin/python -m pytest -q        # 160 passed
```

Environment of the audit: Linux x86_64, AMD Ryzen 7 3700X, 47 GB RAM, AMD GPU,
560 GB disk free, Ollama running, Docker ready. macOS / Windows / WSL were not
executed in this environment — they are marked "unverified" below.

## Vertical slice: website → one-line install → first-run → model → TUI → coding task → tests → Git checkpoint → resume

| Step | State | Evidence |
|---|---|---|
| 1. Open GitHub Pages website | **MISSING** | No `docs/` Pages content, no `website/`, no Pages workflow. |
| 2. Select OS + copy one command | **MISSING** | No site exists. |
| 3. Paste one-liner into fresh terminal | **BROKEN** | Root `install.sh` / `install.ps1` do not exist → `raw.githubusercontent.com/FeverDream-dev/Prometheus/main/install.sh` returns HTTP 404. |
| 4. Install without cloning | **BROKEN** | `scripts/install.sh` falls back to `pip install prometheus-local-agent` from PyPI. Package is **not published** (no release workflow, no PyPI badge, no release in git history) → fake completion. |
| 5. Launch `prometheus` from any dir | **PARTIAL** | Wrapper logic exists in `scripts/install.sh`, but installer itself is broken (see step 4). |
| 6. Interactive first-run setup | **PARTIAL** | `prometheus setup` is a real wizard (HW + bundle selection), but does **not** install Ollama — only prints a hint. No model download with progress/cancel. |
| 7. Detect OS/CPU/RAM/GPU/VRAM/disk/runtimes | **WORKING (Linux)** | `doctor` shows all of these. macOS/Win mocked tests only — unverified on real runners. |
| 8. Detect Ollama installed **and** service running | **WORKING** | `onboarding.check_ollama` hits `/api/tags` (distinguishes binary vs service). Verified: reports "ready" with model count. |
| 9. Offer to install Ollama with approval | **MISSING** | Setup only prints `curl … ollama.com/install.sh` hint. No consent-gated install path. |
| 10. Discover existing models (no dup download) | **WORKING** | `check_ollama().models` lists from `/api/tags`. |
| 11. Recommend hardware-fitting bundles | **WORKING** | `classify_bundle_fit` + `recommended_profile`. |
| 12. Download only approved models, sizes first | **PARTIAL** | Shows approx sizes via `_APPROX_DOWNLOAD_GB`; `--pull` only echoes `ollama pull` hint, no real progress/cancel. |
| 13. Real inference smoke test | **MISSING** | No post-setup inference probe. |
| 14. Enter usable TUI | **WORKING** | `prometheus tui` launches Textual app (streaming, approvals, status bar). Verified import + help. |
| 15. Select folder + ask coding task | **WORKING** | TUI accepts objective; `run` command drives `Orchestrator`. |
| 16. Inspect/patch/test/evidence/checkpoint | **WORKING (fake provider)** | E2E repair fixture (`test_e2e_repair.py`) proves the full loop with a `ScriptedProvider`. **No real-Ollama E2E proof yet.** |
| 17. Resume after restart | **WORKING** | SQLite store + `resume`/`sessions` commands + `test_data_survives_reopen`. |
| 18. Exit/reopen without losing state | **WORKING** | Settings + sessions persist in `~/.prometheus/`. |

## Milestone status

### M1 — Public one-line installer  →  **BROKEN / MOSTLY MISSING**
- Root `install.sh`, `install.ps1` **do not exist** (only `scripts/` versions, clone-only).
- `scripts/install.ps1` references the **wrong repo** (`prometheus/local-agent`) — placeholder owner.
- Falls back to **unpublished PyPI package** — fake completion.
- No SHA-256 verification, no GitHub release artifact download.
- Missing flags: `--dry-run`, `--version`, `--prefix`, `--no-ollama`, noninteractive/CI.
- No `prometheus update`, no `prometheus uninstall`.
- No `uv`/Python runtime bootstrapping (errors "install Python yourself").
- No release workflow (`.github/workflows/release.yml` missing).

### M2 — GitHub Pages website  →  **MISSING ENTIRELY**
No site, no Pages workflow, no copy-button, no OS tabs.

### M3 — First-run wizard  →  **PARTIAL**
Wizard exists but: no Ollama install flow, no model download w/ progress+cancel,
no inference smoke test, no atomic "launch TUI now" hand-off.

### M4 — Coding-agent MVP  →  **PARTIAL (fake-provider only)**
Orchestrator, tools, policy, checkpoints, evidence, completion evaluator all real.
Proven only with `ScriptedProvider`. **No real-Ollama E2E proof.** `prometheus run`
requires `--bundle` even when settings has one.

### M5 — Animated rotating ASCII logo  →  **MISSING ENTIRELY**
No splash module, no frames, no animation engine. (Source logo image also not yet
supplied by user → acceptance criterion stays incomplete even after engine lands.)

### M6 — Honest docs  →  **STALE/OVERCLAIMING**
README advertises clone-only `sh scripts/install.sh` as the install command
(violates "Do not describe a cloned-repository command as the public one-liner").
`docs/IMPLEMENTATION_STATUS.md` says "91 tests" — actual is **160**. README "What
works" lists cross-platform/GPU claims unverified on real macOS/Win runners.

## Falsely / ambiguously advertised

- README "Install (one-liner from a fresh clone)" — a clone is **not** a public one-liner.
- README "Runs on Linux, macOS, and Windows/WSL" — only Linux executed here.
- `docs/IMPLEMENTATION_STATUS.md` "91 tests passing" — actually 160 (docs stale).
- `scripts/install.ps1` URL `prometheus/local-agent` — wrong owner/repo.
- `scripts/install.sh` "Installing PROMETHEUS from PyPI" — package not published.

## What genuinely works (verified this session)

- 160 pytest tests pass; `ruff check src tests` clean.
- `prometheus doctor/setup/run/sessions/resume/init/modes/tui` all import & run.
- Cross-platform hardware probe (Linux real; macOS/Win via mocked unit tests).
- Ollama binary-vs-service distinction via real `/api/tags` health check.
- SQLite session store: events, tasks, evidence, checkpoints, resume, monotonic seq.
- Deterministic weighted completion evaluator (overrides model self-report).
- Atomic file writes, Git checkpoint + rollback, path-traversal + symlink-escape guards.
- Secret redaction (16 patterns), wired into orchestrator.
- Three autonomy modes with distinct approval; destructive always-denied w/o explicit OK.
- Sandbox broker (bwrap/sandbox-exec), Browser tools (Playwright), MCP client — real code + tests.
- E2E repair fixture with deterministic provider + lie-blocking test.

## Placeholder inventory (start of session)

None labeled `PLACEHOLDER` in source. Gaps are **missing** (not placeholder UX).

## Priority order for this recovery

1. **M1 installer + release workflow + CLI update/uninstall** (critical path — unblocks the whole public journey).
2. **M2 website** (independent; command contract is fixed by the prompt).
3. **M5 ASCII animation** (independent; engine lands now, final art pending user logo).
4. **M3 wizard hardening** (Ollama install flow, model pull progress, inference smoke test).
5. **M4 real-Ollama E2E proof** + minor `run` ergonomics.
6. **M6 README/status rewrite** — only after behavior is implemented and tested.

## Test commands (reproduce evidence)

```bash
.venv/bin/python -m pytest -q          # baseline: 160 passed
.venv/bin/ruff check src tests          # clean
.venv/bin/prometheus doctor             # hardware report
.venv/bin/prometheus setup --yes        # noninteractive onboarding
```
