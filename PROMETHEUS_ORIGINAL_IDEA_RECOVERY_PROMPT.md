# PROMETHEUS Original-Idea Recovery Prompt

Repository to fix: `https://github.com/FeverDream-dev/Prometheus`

You are OpenCode working inside the existing PROMETHEUS repository. Do **not** rewrite this prompt as documentation. Do **not** create another plan-only file. Read the repository, audit the actual code, then implement the missing product until it is a real MVP that another person can install and use from GitHub.

The original idea is not a documentation project. PROMETHEUS is meant to become a real local-first coding-agent application, similar in spirit to Claude Code/OpenCode, but designed for home/local usage with Ollama, small local models, hardware detection, multi-agent routing, bounded memory, real tools, MCP, browser testing, a TUI, later a browser/desktop app, and a professional public GitHub Pages website.

## 0. Non-negotiable instruction

You must treat the existing repo as incomplete until every feature below is implemented, tested, and honestly documented.

Do not claim a feature is complete because a doc says it exists. A feature is complete only when:

1. source code exists;
2. tests exist;
3. the CLI/TUI uses it;
4. it was executed in a real or sandboxed test;
5. there is evidence in `docs/IMPLEMENTATION_STATUS.md`;
6. it is not a placeholder, mock, fake route, fake command, fake page, or fake claim.

If something cannot be fully completed in this session, implement the most useful vertical slice, label the gap clearly, and add a failing or skipped integration test explaining exactly what remains.

## 1. First: perform a real repository audit

Before coding, inspect these areas:

- `README.md`
- `MASTER_PROMPT.md`
- `docs/PRODUCT_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/ROADMAP.md`
- `docs/INSTALLATION.md`
- `src/prometheus_cli/`
- `src/prometheus_cli/providers/`
- `src/prometheus_cli/tools/`
- `config/bundles/`
- `schemas/`
- `scripts/`
- `.github/workflows/`
- any existing site/docs folder

Create or update `docs/ORIGINAL_IDEA_GAP_AUDIT.md` with a table:

| Original requirement | Current code location | Status | Evidence command | Missing work | Priority |
|---|---|---|---|---|---|

Use statuses only:

- `done`
- `partial`
- `missing`
- `broken`
- `misleading-docs`

Do not spend more than 30 minutes on the audit before coding. The audit is a working map, not the deliverable.

## 2. Correct the product target

PROMETHEUS must become this:

A local-first adaptive coding-agent CLI/TUI that can be installed by a normal user from GitHub, detects the user's hardware, installs or connects to Ollama, recommends and downloads a model bundle, starts an interactive TUI, maintains bounded project memory, runs coding tasks in small tested steps, uses Git checkpoints, uses real tools, supports MCP/browser automation, and can optionally connect to cloud providers.

The MVP must prove this flow:

```text
Fresh computer or clean container
  -> copy one public install command from the website
  -> installer runs
  -> hardware is detected
  -> Ollama is detected or offered for installation
  -> recommended model bundle is selected
  -> at least one small model is pulled or validated
  -> `prometheus doctor` works
  -> `prometheus setup` works
  -> `prometheus tui` opens
  -> user enters a coding objective
  -> agent reads files
  -> agent edits files
  -> agent runs tests
  -> agent creates Git checkpoint
  -> agent updates bounded memory
  -> agent reports evidence, not fake completion
```

## 3. Fix the one-line installer properly

The current install story is not enough if it only works after cloning. Implement a real public installer.

### Required public commands

The website and README must provide commands like these, adjusted to the final URLs:

Linux/macOS/WSL:

```sh
curl -fsSL https://feverdream-dev.github.io/Prometheus/install.sh | sh
```

Alternative for systems without curl:

```sh
wget -qO- https://feverdream-dev.github.io/Prometheus/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://feverdream-dev.github.io/Prometheus/install.ps1 | iex
```

### Installer requirements

Implement `public/install.sh` and `public/install.ps1`, or generate them into the GitHub Pages artifact.

The public installer must:

1. work without cloning the repo first;
2. detect OS and architecture;
3. detect Python 3.11+ or install/help install it;
4. detect Git;
5. detect WSL on Windows and use WSL for MVP if native Windows is not ready;
6. detect Ollama;
7. ask whether to install Ollama if missing;
8. start or explain how to start Ollama;
9. create an isolated install under `~/.prometheus`;
10. install PROMETHEUS from GitHub release artifact, GitHub source archive, or PyPI only if the package is actually published;
11. never depend on a fake PyPI package;
12. never contain placeholder URLs like `prometheus/local-agent`;
13. verify checksums when installing release artifacts;
14. add a `prometheus` command wrapper to PATH or print exact PATH instructions;
15. run `prometheus doctor`;
16. run `prometheus setup --yes` or launch interactive setup;
17. offer to pull the recommended small model bundle;
18. print the next command: `prometheus tui`.

### Installer tests

Add tests/scripts that validate:

```sh
bash -n public/install.sh
pwsh -NoProfile -File public/install.ps1 -WhatIf
```

Add a clean Linux install test in CI using a temporary HOME.

For full network install tests, add a manual workflow:

`.github/workflows/install-smoke.yml`

It must test the public one-liner from GitHub Pages after deployment.

## 4. Build a real GitHub Pages website

Create a professional website, not a generic AI-looking landing page.

Use one of these:

- `site/` built with Vite/Astro/plain HTML;
- or `docs/` only if configured cleanly for GitHub Pages.

Add `.github/workflows/pages.yml` to deploy it.

The site must include:

- hero section with clear product promise;
- copy-paste one-line install commands;
- hardware/model bundle explanation;
- local-first privacy explanation;
- screenshots or terminal recordings if available;
- clear "What works now" and "Roadmap" sections;
- documentation links;
- license explanation;
- SEO metadata;
- OpenGraph/Twitter metadata;
- JSON-LD SoftwareApplication structured data;
- sitemap.xml;
- robots.txt;
- accessible semantic HTML;
- mobile responsive layout;
- Lighthouse-friendly performance;
- no fake testimonials;
- no fake stars/download numbers;
- no vague "AI magic" language;
- no generic purple-blue gradient SaaS look unless it is genuinely refined.

The design quality target is Apple/Google-grade: minimal, fast, clear, elegant, with excellent spacing and typography.

Add tests for the site:

```sh
npm test
npm run build
npx playwright test
```

If using plain HTML, add at least link checks and HTML validation.

## 5. Implement `/settings` and slash commands in the TUI

The current TUI must become a usable application shell.

Implement slash commands:

```text
/help
/settings
/models
/bundles
/mcp
/tools
/memory
/sessions
/resume <id>
/mode copilot|pilot|astronaut
/provider
/doctor
/exit
```

`/settings` must show editable settings:

- autonomy mode;
- default bundle;
- selected provider;
- Ollama URL;
- cloud provider keys status without revealing secrets;
- install packages automatically: on/off;
- sandbox: off/basic/docker/native;
- browser testing: off/playwright/chrome-mcp;
- multi-agent review: on/off;
- audio markers: on/off;
- telemetry: off by default;
- max steps;
- max runtime;
- Astronaut long-run mode.

All settings must persist in a config file under `~/.prometheus/`, not in the repo.

Add tests for parsing slash commands and persisting settings.

## 6. Implement realistic local model bundles

Do not hard-code stale or imaginary model names. At runtime or during bundle qualification, verify whether the configured Ollama model names exist locally or can be pulled.

Create bundle manifests under `config/bundles/`.

Minimum bundles:

### `spark-cpu.yaml`

Purpose: CPU and low-memory testing.

Roles:

- controller/builder: smallest reliable coding/instruct model available through Ollama;
- reviewer: small critic model;
- context: low context by default.

### `ember-8gb.yaml`

Purpose: max 8 GB VRAM.

Logical seats, loaded sequentially:

- Envoy: user-facing general/research/multimodal-capable model when available;
- Forge: coding model;
- Argus: tester/critic.

Only one model should be loaded at a time on 8 GB VRAM. Use `keep_alive: 0` or unload calls between seats when needed.

### `forge-12gb.yaml`

Purpose: balanced 12 GB GPU.

Use stronger coding model and reviewer, still with sequential hot-swap.

### `titan-24gb.yaml`

Purpose: 24 GB quality mode.

Use larger coder/reviewer where practical, with fallback if model does not fit.

### `cloud-hybrid.yaml`

Purpose: optional cloud fallback.

Must support local-first by default and clearly show when cloud is used.

### Bundle commands

Implement:

```sh
prometheus bundles list
prometheus bundles inspect ember-8gb
prometheus bundles qualify ember-8gb
prometheus models list
prometheus models pull ember-8gb
prometheus models unload
```

Bundle qualification must check:

- RAM;
- VRAM;
- CPU/GPU vendor;
- disk;
- Ollama availability;
- local model presence;
- pull availability;
- context length recommendation;
- expected speed tier.

Do not promise "unlimited" in a dishonest way. Use this language:

"Local usage is quota-free after model download, bounded by your hardware, electricity, disk, context size, and runtime settings. Cloud providers may have quotas or costs."

## 7. Implement bounded project memory as a core feature

This is not optional and must not be a user-toggle.

Create `.prometheus/` inside each workspace. It must be gitignored by default unless the user explicitly exports it.

Required files:

```text
.prometheus/
  memory.md
  state.json
  tasks.jsonl
  decisions.jsonl
  evidence.jsonl
  handoffs.jsonl
  sessions/
```

Memory rules:

1. `memory.md` must stay around 1,024 words or less.
2. It must summarize:
   - project goal;
   - current architecture;
   - completed work;
   - active task;
   - next step;
   - known blockers;
   - user constraints;
   - commands that proved success/failure.
3. Full history must go into structured JSONL ledgers.
4. Every agent turn must read bounded memory first.
5. Every meaningful step must update memory atomically.
6. Secrets must be redacted before memory writes.
7. The agent must work in micro-steps, not huge "do everything" plans.
8. The system must retrieve only relevant context from ledgers instead of replaying all history.

Implement CLI/TUI commands:

```sh
prometheus memory inspect
prometheus memory rebuild
prometheus memory export
prometheus memory reset --confirm
```

Add tests:

- memory stays under limit;
- memory updates after tool results;
- decisions/evidence are appended;
- secrets are redacted;
- crash-safe atomic writes work;
- the next orchestrator step receives memory context.

## 8. Implement three logical agents and Arena handoffs

The product idea requires agents, not just one model with a reviewer.

Implement logical seats:

### Envoy

Talks to the user, clarifies goals, summarizes, researches, handles multimodal inputs when model/backend supports them.

### Forge

Writes patches, runs code commands, performs build/test loops.

### Argus

Reads logs, tests, criticizes, finds fake completion, detects placeholders, validates evidence.

On 8 GB VRAM, do **not** load all three models at once. Load sequentially and hand off using structured JSON:

```json
{
  "from": "Forge",
  "to": "Argus",
  "objective": "...",
  "changed_files": [],
  "commands_run": [],
  "evidence": [],
  "open_questions": [],
  "next_recommended_step": "..."
}
```

Arena mode:

1. Forge proposes a fix.
2. Argus tests and criticizes.
3. If blocked five times, Forge and Argus must try alternative approaches.
4. Optionally use Git worktrees for competing patches.
5. Choose the winner by objective tests, not model opinion.

Add settings:

```text
multi_agent_review = true|false
arena_mode = off|simple|worktree
```

Add tests proving that after repeated failure the system uses a different strategy and records the handoff.

## 9. Implement real tools and MCP

The original idea requires tools. Implement a tool registry, not hardcoded scattered methods.

Required built-in tools:

- file list/read/write/patch;
- ripgrep/search;
- terminal command runner;
- Git status/diff/checkpoint/rollback;
- test runner;
- package installer with policy approval;
- browser automation;
- web fetch/search abstraction;
- MCP client transport;
- memory tools;
- model tools.

MCP MVP:

1. support stdio MCP servers;
2. support JSON-RPC initialize/list_tools/call_tool;
3. add config file `~/.prometheus/mcp.json`;
4. add CLI/TUI commands:
   - `prometheus mcp list`
   - `prometheus mcp add`
   - `prometheus mcp test`
   - `/mcp`
5. never allow MCP tools to bypass PROMETHEUS permission policy;
6. store tool evidence.

Browser MVP:

- Playwright local browser testing must work.
- Chrome MCP can be optional if configured.
- Add `prometheus browser test <url>` or equivalent.
- Add at least one E2E test on a small local HTML/server fixture.

## 10. Implement sandbox enforcement

A sandbox flag that does nothing is not enough.

Implement sandbox profiles:

```text
off
basic
docker
native
```

MVP acceptance:

- `off`: current host behavior.
- `basic`: workspace path enforcement, deny dangerous commands by default, environment filtering.
- `docker`: run commands in a disposable container mounted to workspace.
- `native`: use bubblewrap/landlock on Linux and sandbox-exec on macOS where available, otherwise report unsupported.

The policy engine must block or request approval for:

- `rm -rf /`;
- writing outside workspace;
- reading secrets outside allowed paths;
- installing packages when disabled;
- network commands when disabled;
- destructive Git operations.

Add tests for policy and at least one integration test for docker sandbox when Docker is available.

## 11. Implement provider conformance and cloud adapters

The provider interface must support:

- health;
- list models;
- chat/complete;
- structured JSON;
- streaming;
- tool-call compatibility when available;
- load/unload or keep_alive equivalent;
- cancellation;
- token/context metadata.

Providers:

- Ollama;
- OpenAI-compatible;
- OpenAI;
- Anthropic;
- OpenRouter;
- Z.ai/GLM;
- Grok/xAI;
- Google/Gemini;
- Mistral;
- DeepSeek;
- local llama.cpp/LM Studio compatible endpoint.

Cloud providers can be implemented as OpenAI-compatible where possible, but the UI must label them clearly.

Add provider conformance tests with fake HTTP servers. No real API keys in CI.

## 12. Make Astronaut mode real but safe

The original idea includes Copilot, Pilot, and Astronaut.

Implement:

### Copilot

Reads and suggests. Asks before writes and commands.

### Pilot

Can write and run safe tests. Asks before risky/network/install operations.

### Astronaut

Can continue working autonomously within declared scope, but must still require approval for destructive or out-of-scope operations.

Astronaut must support:

- long-running sessions;
- heartbeat;
- resumable state;
- periodic Git checkpoints;
- bounded memory compaction;
- stop file:
  - `.prometheus/STOP`
- pause/resume commands;
- max budget controls;
- visible logs.

Do not implement "infinite loop" recklessly. Implement "unlimited local use" as user-configurable long-run autonomy bounded by safety gates, hardware, and stop controls.

Commands:

```sh
prometheus astronaut start "objective"
prometheus astronaut status
prometheus astronaut pause
prometheus astronaut resume
prometheus astronaut stop
```

## 13. Add ASCII logo animation

The startup screen should have a PROMETHEUS ASCII logo animation.

Implement:

- `src/prometheus_cli/logo.py`;
- reduced-motion option;
- terminal width detection;
- fallback static logo;
- frame animation used in TUI startup;
- no slow startup;
- user can disable animation in accessibility settings.

If the company logo image is provided later, convert it into ASCII frames and include it in the repo only if the user confirms rights to use it.

For now create a clean PROMETHEUS text/fire-themed ASCII animation as a placeholder labeled `TEMPORARY_ASCII_LOGO`.

This placeholder is allowed only until the real logo is supplied.

## 14. Organize repository and Git hygiene

Clean the repo structure:

```text
src/prometheus_cli/
  agents/
  memory/
  tools/
  providers/
  mcp/
  browser/
  sandbox/
  tui/
  installer/
config/
  bundles/
site/
public/
scripts/
tests/
docs/
.github/workflows/
```

Update `.gitignore` to exclude:

```text
.prometheus/
*.db
*.sqlite
*.log
*.gguf
*.safetensors
models/
.ollama/
dist/
build/
.pytest_cache/
.ruff_cache/
node_modules/
.env
.env.*
```

Never commit:

- model weights;
- caches;
- secrets;
- local virtualenvs;
- test artifacts;
- personal machine paths;
- local `.prometheus/` state.

## 15. Testing mandate

Run tests constantly.

Minimum commands:

```sh
python -m pytest -q
ruff check src tests
python -m compileall src
prometheus doctor
prometheus setup --yes
prometheus bundles list
prometheus bundles qualify ember-8gb
prometheus memory inspect
prometheus tui --help
```

Add integration tests where possible:

```sh
tests/integration/test_installer_clean_home.py
tests/integration/test_ollama_sandbox.py
tests/integration/test_browser_playwright.py
tests/integration/test_mcp_stdio.py
tests/integration/test_memory_loop.py
tests/integration/test_astronaut_resume.py
```

For Ollama tests:

- use a tiny model if available;
- skip clearly if Ollama is not installed;
- never download huge models in CI;
- allow manual workflow for real model pulls.

## 16. Documentation honesty

Update README and docs so they say exactly what works.

README must include:

- public one-liner;
- local clone install;
- Windows/WSL instructions;
- first-run flow;
- model bundle list;
- what works now;
- what is still experimental;
- privacy/security notes;
- troubleshooting;
- no fake completion claims.

Remove misleading claims such as "browser testing works" unless it is actually tested.

## 17. Acceptance criteria for this recovery session

Do not stop until these are true or until you have a clear blocker with evidence:

1. `docs/ORIGINAL_IDEA_GAP_AUDIT.md` exists and is honest.
2. Public installer files exist and have syntax tests.
3. README contains a real public one-liner using the real repo URL.
4. PowerShell installer no longer contains placeholder `prometheus/local-agent`.
5. GitHub Pages site exists and has deployment workflow.
6. TUI supports `/help`, `/settings`, `/models`, `/bundles`, `/memory`.
7. Bundle manifests exist for CPU, 8 GB, 12 GB, and 24 GB.
8. `prometheus bundles list` works.
9. `prometheus bundles qualify <bundle>` works.
10. `prometheus models pull <bundle>` performs or confirms real Ollama pulls.
11. Workspace `.prometheus/memory.md` is created and updated.
12. Memory is always included in orchestrator context.
13. MCP stdio client MVP exists and has a test.
14. Playwright browser test MVP exists and has a test.
15. Sandbox mode is more than a flag.
16. Provider conformance tests exist.
17. Astronaut long-run session commands exist at least as a working MVP.
18. CI includes tests for Linux, macOS, Windows, installer syntax, and site build.
19. No model weights, caches, local DBs, or secrets are committed.
20. `docs/IMPLEMENTATION_STATUS.md` is updated with evidence commands.

## 18. Work procedure

Follow this exact loop:

1. Inspect.
2. Update the gap audit.
3. Choose the highest-priority missing vertical slice.
4. Code it.
5. Add tests.
6. Run tests.
7. Fix failures.
8. Make a Git checkpoint.
9. Update implementation status.
10. Continue.

Do not ask the user which document to write. The user wants the program built.

Start now by auditing the repository and implementing the missing original-idea features.
