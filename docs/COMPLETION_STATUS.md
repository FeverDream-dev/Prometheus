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
| 2 | Quota-free local settings (unlimited local, caps, budgets) | C5 | `models.py` Settings | unit | `prometheus doctor` | in progress |
| 3 | Selectable v2 model packages (Spark/Ember/Forge/Oracle/Titan/Hephaestus/VibeThinker) | C5 | `bundles.py`, `config/bundles-v2/` | unit | `prometheus bundles` | in progress |
| 3 | Rich bundle schema + validation (reject unknown/missing-license) | C3 | `bundles.py` | unit | — | in progress |
| 3 | Hardware-fit classification + "why recommended" | C3 | `bundles.py` | unit | `prometheus bundles` | in progress |
| 4 | `/settings` + slash commands + Model Packages screen | C5 | `tui.py` | unit/import | TUI launch | in progress |
| 4 | Bundle install/compare/select per project; atomic persist | C3 | — | — | — | planned |
| 5 | Model router by capability + real-time RAM/VRAM + hot-swap | C5 | partial (`orchestrator.py`) | — | — | partial |
| 6 | MCP product (stdio + Streamable HTTP, trust, injection boundary) | C3 | `mcp_client.py` (stdio) | unit | fixture server | partial |
| 7 | Typed tool broker (file/patch/process/Git/browser/web) | C5 | `tools/workspace.py`, `browser.py` | unit | E2E repair | partial |
| 8 | Aggressive Ollama test matrix + disposable repair E2E | C5 | `test_e2e_ollama.py` | opt-in | llama3.2 | partial |
| 9 | Repo organization + .gitignore rejecting models/secrets/artifacts | C3 | `.gitignore` | — | — | in progress |
| 10 | Professional Pages site (SEO, JSON-LD, sitemap, Lighthouse 95+) | C3 | `website/` (basic) | `test_website.py` | local preview | partial |
| 11 | 18 acceptance gates | C5 | — | — | — | see below |

## Acceptance gates (§11) — current state

1. `/settings` shows built-in packages w/ fit + roles — **in progress**
2. One small package pulled/qualified or existing model qualified — **in progress**
3. Local sessions have no artificial quota — **in progress** (Settings)
4. Cloud marked metered/provider-limited — **planned**
5. Router uses capability + memory rules — **partial**
6. Sequential hot-swap without losing task state — **partial**
7. VibeThinker cannot call tools — **enforced** (orchestrator rejects non-tool controller; v2 marks it review-only)
8. MCP fixture server E2E (not just config parsing) — **partial** (stdio client exists; fixture test planned)
9. File/patch/process/Git tools complete a real repair — **done** (E2E repair fixture + real-Ollama)
10. Playwright real browser test for a web fixture — **partial** (browser module exists; web-fixture test planned)
11. Local Ollama real-model smoke + tool tests — **done** (llama3.2 inference + E2E)
12. Sessions resume after restart — **done**
13. Git checkpoints + safe rollback — **done**
14. No test artifact/model/secret in Git — **enforced** (.gitignore + this audit)
15. One-line install works outside a clone — **done** (clean-venv proof on `main`)
16. Pages builds + install command tested — **done** (workflow + drift tests on `main`)
17. Website uses only factual claims + real captures — **partial** (terminal recording still placeholder)
18. Full automated suite passes — **in progress** (247 + growing)

## Known false/inflated claims to avoid

- Do NOT say "unlimited AI" without the §2 explanation (RAM/VRAM/context/disk bounds).
- Do NOT mark a v2 bundle "verified" until its qualification suite passes on the runtime.
- Do NOT advertise parallel multi-agent if hardware forces sequential (v2 sets `maximum_loaded_models`).
- Do NOT route VibeThinker to tools (enforced; it is a review add-on only).
- Qwen3-Coder-Next is NOT a 24 GB default (~52 GB Q4) — excluded from local defaults.

## Placeholder inventory (this branch)

- Splash logo art (carried from `main`) — pending official logo image.
- Website terminal recording (carried) — pending real capture.
- v2 bundle model tags (qwen3.5/granite4.1/gemma4/devstral) — research-date
  2026-06-19; must be re-qualified at install time. None are installed on this
  machine, so qualification uses available models (llama3.2/gemma4) as capability
  proxies unless a small package is pulled.
