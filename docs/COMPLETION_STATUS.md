# PROMETHEUS — Completion Status

Evidence-driven matrix for the "Complete the Real Product" prompt. Every status
is backed by code + a test or a real run, not a doc claim.

Branch: `completion` (forked from `main` @ `0ba135b`, which delivered the MVP
recovery: installer, website, first-run wizard, real-Ollama E2E, splash, docs).

Audit environment: Linux x86_64, AMD Ryzen 7 3700X, 47 GB RAM, AMD GPU (0 GB
VRAM detected), Ollama running with `gemma4:latest`, `gemma4:e2b`,
`llama3.2:latest`. macOS / native Windows not executed here (CI + mocked tests).

## Reproduce baseline

```bash
git checkout completion
uv venv .venv --python 3.11 && . .venv/bin/activate
uv pip install -e '.[dev,tui]'
pytest -q          # baseline 247 + 2 opt-in (grows this branch)
ruff check src tests
prometheus doctor
```

## What `main` already delivers (verified, not re-proven here)

Public one-line installer (root `install.sh`/`install.ps1`, no PyPI, SHA-256),
`prometheus update`/`uninstall`, release workflow, GitHub Pages site + workflow,
first-run wizard (consent-gated Ollama install, streaming pull, inference smoke),
SQLite sessions + resume, deterministic completion evaluator, Git
checkpoint/rollback, atomic writes, secret redaction, path/symlink guards,
sandbox broker, Playwright browser tools, MCP client (stdio), rotating ASCII
splash (placeholder logo). Real-Ollama E2E proven (`llama3.2:latest`).

## Completion-prompt requirement matrix

Criticality: C5=critical safety/core, C3=important, C2=standard, C1=nice.

| § | Requirement | Crit | Code | Test | Runtime evidence | Status |
|---|---|---|---|---|---|---|
| 1 | Audit + this matrix | C3 | this file | — | — | done |
| 2 | Quota-free local settings (unlimited local, caps, budgets) | C5 | `models.py` Settings | unit | `prometheus doctor` | done |
| 3 | Selectable v2 model packages (Spark/Ember/Forge/Oracle/Titan/Hephaestus/VibeThinker) | C5 | `bundles.py`, `config/bundles-v2/` | 20 unit | `prometheus bundles` | done |
| 3 | Rich bundle schema + validation (reject unknown/missing-license/non-https/unsafe-id) | C3 | `bundles.py` | unit | — | done |
| 3 | Hardware-fit classification + "why recommended" | C3 | `bundles.py` | unit | `prometheus bundles` | done |
| 3 | Qualification harness (chat/json/tool/code) + "verified" gate | C5 | `qualification.py` | 7 unit | `prometheus qualify` 4/4 real | done |
| 4 | `/settings` + slash commands + Model Packages surface | C5 | `tui.py`, `tui_commands.py` | 14 unit | headless TUI launches | done |
| 4 | Full navigable bundle CRUD screens (install/compare/edit/export) | C3 | partial (`bundles`/`qualify` CLI) | — | — | partial |
| 5 | Model router by capability + real-time RAM/VRAM + hot-swap | C5 | `router.py` | 15 unit | capability+memory rules | done |
| 6 | MCP product (stdio + Streamable HTTP, trust, injection boundary) | C3 | `mcp_client.py` (stdio) + fixture | 7 e2e | real fixture server | done(stdio) |
| 7 | Typed tool broker (file/patch/process/Git/browser/web) | C5 | `tools/`, `browser.py`, `tools/web.py` | unit+e2e | real repair + real Chromium + web fetch | done(core) |
| 8 | Aggressive Ollama test matrix + disposable repair E2E | C5 | `test_e2e_ollama.py` | opt-in | granite4.1:3b 4/4 + repair | done |
| 9 | Repo organization + .gitignore rejecting models/secrets/artifacts | C3 | `.gitignore`, `test_repo_hygiene.py` | 5 unit | `git ls-files` clean | done |
| 10 | Professional Pages site (SEO, JSON-LD, sitemap, Lighthouse 95+) | C3 | `website/` | `test_website.py` | local preview | in progress(redesign) |
| 11 | 18 acceptance gates | C5 | — | — | — | see below |

## Acceptance gates (§11) — current state

1. `/settings` shows built-in packages w/ fit + roles — **done**
2. One small package pulled/qualified — **done** (Spark/granite4.1:3b pulled + QUALIFIED 4/4)
3. Local sessions have no artificial quota — **done** (Settings.unlimited_local_sessions default True; 0=unlimited)
4. Cloud marked metered/provider-limited — **done** (`/settings` + bundles show "metered" when not unlimited)
5. Router uses capability + memory rules — **done** (`router.py`: capability refusal + live /proc/meminfo free-RAM + KV estimate)
6. Sequential hot-swap without losing task state — **done** (unload→load with handoff preserved; all real bundles sequential by design)
7. VibeThinker cannot call tools — **done** (add-on, no controller; prohibited_capabilities enforced in router)
8. MCP fixture server E2E (not just config parsing) — **done** (real stdio fixture server: handshake, tool discovery, call, injection boundary, error surfacing, reconnect)
9. File/patch/process/Git tools complete a real repair — **done** (real-Ollama repair E2E, granite4.1:3b)
10. Playwright real browser test for a web fixture — **done** (real headless Chromium: navigate/click/fill/console-evidence/screenshot)
11. Local Ollama real-model smoke + tool tests — **done** (qualify 4/4 + inference smoke)
12. Sessions resume after restart — **done**
13. Git checkpoints + safe rollback — **done**
14. No test artifact/model/secret in Git — **done** (hygiene test + .gitignore; tree clean)
15. One-line install works outside a clone — **done** (on `main`)
16. Pages builds + install command tested — **done** (on `main`)
17. Website uses only factual claims + real captures — **partial** (terminal recording still placeholder)
18. Full automated suite passes — **done** (330 + 2 opt-in)

## Test counts (reality)

- `pytest -q` → **330 passed, 2 skipped** (the 2 skips = opt-in real-Ollama; both pass when enabled).
- New this branch: 20 bundles + 7 qualification + 14 tui_commands + 5 hygiene + 7 MCP e2e + 6 browser e2e + 15 router + 10 web tool = 84 new tests.
- Real-model evidence: `granite4.1:3b` (Spark controller, pulled ~2 GB) QUALIFIED 4/4 and drove
  the opt-in repair E2E (2 passed in 2.65s). `llama3.2:latest` also QUALIFIED 4/4.
- Real browser evidence: 6 Playwright tests pass against headless Chromium (navigate, click,
  fill, console-error evidence, screenshot, summary).
- Real MCP evidence: 7 fixture-server E2E tests pass over real stdio JSON-RPC.

## Remaining (honest, no inflated %)

- Full navigable TUI bundle-management screens (install/compare/edit/export/import) — currently
  a renderable `/settings` + `prometheus bundles`/`qualify` CLI.
- Router per-step live RAM/VRAM gating + sequential hot-swap lifecycle (§5) — hardware-fit
  selection is real; runtime memory monitoring is not.
- MCP stdio fixture E2E + Streamable HTTP transport (§6).
- Playwright web-fixture acceptance test (§7/§10).
- Professional Pages redesign (§10: JSON-LD, sitemap, Lighthouse 95+) — current site is the
  recovery-era basic static site.
- Repo restructure into app/agent/providers/models/tools/mcp/... (§9) — deferred; public imports stable.

## Placeholder inventory (this branch)

- Splash logo art (from `main`) — pending official logo image.
- Website terminal recording (from `main`) — pending real capture.
- v2 bundle model tags (qwen3.5/granite4.1/gemma4/devstral) — research-date 2026-06-19; only
  `granite4.1:3b` has been pulled+qualified on this machine. Other tags must be qualified at
  install time; Qwen3-Coder-Next is deliberately excluded from 24 GB local defaults (~52 GB Q4).
