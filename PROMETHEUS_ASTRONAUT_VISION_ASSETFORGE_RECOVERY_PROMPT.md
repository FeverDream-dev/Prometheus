# PROMETHEUS Update Recovery Prompt — Astronaut Vision + AssetForge

Repository: `https://github.com/FeverDream-dev/Prometheus`

You are OpenCode working inside the existing PROMETHEUS repository.

Do **not** rewrite this prompt as documentation. Do **not** make another plan-only PR. Your task is to audit the updated repository, preserve every useful feature already added, and implement the missing original PROMETHEUS product features plus the new Astronaut Vision and AssetForge package requirements.

PROMETHEUS is intended to become a local-first adaptive AI coding agent similar in usability to Claude Code/OpenCode, but optimized for home/local hardware with Ollama, hardware-aware model bundles, bounded memory, real tools, MCP, browser testing, sandboxing, multimodal checks, optional image generation, and a serious public install website.

---

## 0. Current audit baseline to verify again

Before changing code, verify the current repository state. Do not assume the README is correct.

Known public findings that must be re-checked:

1. The README still presents install as “one-liner from a fresh clone,” not a real public website installer.
2. The README claims the platform runs on Linux/macOS/Windows/WSL and has hardware detection, local Ollama operation, deterministic completion, Git rollback, Textual TUI, schema loop, and tests.
3. The README also admits browser automation, full MCP transport, native sandboxes, sound playback, provider-specific OAuth, signed bundle ecosystem, daemon recovery, and desktop client are not finished.
4. The repository shows no public GitHub release yet.
5. `scripts/install.sh` still uses `prometheus-local-agent` as a package name unless installing from local source.
6. `scripts/install.ps1` still contains placeholder URLs such as `prometheus/local-agent`.
7. `src/prometheus_cli/cli.py` currently exposes only the earlier main commands, and does not expose the full `sandbox`, `models`, `provider`, `assets`, `vision`, `mcp`, or `astronaut` command groups.
8. `docs/IMPLEMENTATION_STATUS.md` still reports around 82% overall completion for its current scope, with critical blockers around sandbox enforcement, provider conformance tests, and failure-signature tracking.

Create or update:

```text
docs/UPDATE_GAP_AUDIT.md
docs/IMPLEMENTATION_STATUS.md
```

The audit table must include:

```text
Requirement | Current status | Evidence location | Missing implementation | Priority | Test command
```

Use these statuses only:

```text
passing
partial
missing
broken
misleading-docs
```

A row is `passing` only if there is source code, a CLI/TUI path, tests, and execution evidence.

---

## 1. Preserve the original idea

The original PROMETHEUS idea is still correct and must stay:

- local-first by default;
- Ollama-first local inference;
- optional cloud providers;
- hardware detection for CPU, NVIDIA, AMD, Intel, Apple Silicon, and WSL;
- automatic model bundle recommendation;
- hot-swapping logical agents when RAM/VRAM is limited;
- TUI first, browser/desktop later;
- bounded project memory in `.prometheus/`;
- deterministic tools owned by PROMETHEUS, not by the model;
- Git checkpoints and rollback;
- evidence-driven completion;
- Copilot, Pilot, and Astronaut autonomy modes;
- no fake placeholders counted as complete;
- professional public GitHub Pages website;
- public copy-paste installer;
- model bundles that real users can select from `/settings`.

The new additions must also stay, but be made more detailed and real:

- VibeThinker sandbox proof;
- Playwright/browser testing;
- MCP support;
- long-running Astronaut module;
- targeted vision inspection of UI elements;
- optional local image-generation package for web assets.

---

## 2. Ten missing competitive features to implement

Implement these features inspired by Claude Code and OpenCode. Do not copy their branding or proprietary behavior. Implement PROMETHEUS equivalents.

### 2.1 Real public installation and release channel

Required:

```sh
curl -fsSL https://feverdream-dev.github.io/Prometheus/install.sh | sh
```

```powershell
irm https://feverdream-dev.github.io/Prometheus/install.ps1 | iex
```

The installer must work without cloning first. It must install from a real GitHub release artifact or a real source archive fallback. It must not depend on an unpublished PyPI package. It must remove every placeholder URL.

Commands:

```sh
prometheus doctor
prometheus setup
prometheus tui
```

must work after installation.

### 2.2 Full TUI slash command shell

Add commands:

```text
/help
/settings
/connect
/models
/bundles
/provider
/mcp
/tools
/memory
/sessions
/resume <id>
/mode copilot|pilot|astronaut
/plan
/build
/undo
/redo
/share
/assets
/vision
/astronaut
/exit
```

The TUI must not be only an objective input box. It must behave like an application shell.

### 2.3 Plan/Build mode separation

Implement a read-only Plan mode that cannot edit files or run risky commands.

Implement Build mode for actual modifications.

Tab or a slash command should switch modes.

Acceptance:

```text
Plan mode can read/search/analyze.
Plan mode cannot edit files.
Build mode can edit according to current permission policy.
```

### 2.4 Project initialization and context manifests

Implement:

```sh
prometheus init
prometheus init --import
```

It must analyze the repository and create/update:

```text
AGENTS.md
.prometheus/project-map.json
.prometheus/memory.md
.prometheus/rules/imported.json
```

It should import relevant rules from:

```text
AGENTS.md
CLAUDE.md
.claude/
.cursorrules
.cursor/rules/
.opencode/
.github/copilot-instructions.md
```

Convert imported rules into PROMETHEUS’ own clear schema instead of blindly copying them.

### 2.5 Agents and subagents with separate contexts

Implement configurable agents:

```text
Envoy    — user-facing conversation, research, multimodal interpretation
Forge    — coding/patching/building
Argus    — testing, verification, log reading, fake-completion detection
Scout    — external docs/dependency research, read-only
Planner  — read-only planning
AssetForge — image asset generation
VisionSentinel — UI element visual inspection
```

Each agent must support:

```text
model
provider
prompt file
permissions
max steps
temperature
hidden/system agent flag
context handoff schema
```

On 8 GB VRAM, only one local model may be loaded at a time. Use logical seats and structured handoffs.

### 2.6 Hooks and lifecycle events

Implement hooks similar in concept to coding-agent lifecycle hooks:

```text
SessionStart
InstructionsLoaded
UserPromptSubmit
PreToolUse
PermissionRequest
PostToolUse
PostToolUseFailure
TaskCreated
TaskCompleted
FileChanged
PreCompact
PostCompact
SessionEnd
AstronautTick
VisionInspection
AssetGenerated
```

Hooks must be configured in:

```text
.prometheus/hooks.json
~/.prometheus/hooks.json
```

Hooks may add context, block actions, request approval, or run commands according to sandbox policy. Hooks must not bypass permissions.

### 2.7 Full MCP support

Implement at least:

```text
stdio MCP transport
HTTP/SSE transport
WebSocket transport if practical
initialize
list_tools
call_tool
resources if practical
prompts as slash commands if practical
tool permission gating
server scopes: user, project, workspace
OAuth token status without exposing secrets
```

Commands:

```sh
prometheus mcp list
prometheus mcp add
prometheus mcp remove
prometheus mcp test
prometheus mcp call
```

TUI:

```text
/mcp
```

### 2.8 Granular permissions and sandbox policy

Implement a granular permission matrix:

```text
read
edit
patch
bash
git
network
package_install
browser
mcp
web_fetch
web_search
lsp
assets
vision
external_directory
destructive
```

Each permission must support:

```text
allow
ask
deny
```

Policy must apply globally, per agent, per tool, and per sandbox profile.

### 2.9 LSP diagnostics integration

Implement:

```sh
prometheus lsp doctor
prometheus lsp diagnostics
```

The agent must be able to read compiler/language-server diagnostics and use them as evidence.

MVP languages:

```text
TypeScript/JavaScript
Python
PHP
Rust
Go
```

Skip unsupported language servers honestly.

### 2.10 Plugins, custom tools, skills, and shareable sessions

Implement:

```text
.prometheus/plugins/
.prometheus/tools/
.prometheus/skills/
~/.prometheus/plugins/
~/.prometheus/tools/
~/.prometheus/skills/
```

Commands:

```sh
prometheus tools list
prometheus tools add
prometheus skills list
prometheus skills run
prometheus share export
```

`share export` must create a local sanitized bundle first. It must not upload anything unless the user explicitly configures a remote endpoint.

---

## 3. Astronaut Sentinel module

The new Astronaut idea must be implemented as a **limited but real autonomous testing daemon**, not an unsafe infinite loop.

### 3.1 Concept

Astronaut Sentinel is a background/long-running module that continuously helps verify the project. It performs tests in three ways:

1. focused tests on the area currently being changed;
2. seeded random tests across safe parts of the project;
3. vision-based UI inspections when the project is a web/browser system.

It must never be allowed to run destructively without policy approval.

### 3.2 Commands

Implement:

```sh
prometheus astronaut start "objective"
prometheus astronaut status
prometheus astronaut pause
prometheus astronaut resume
prometheus astronaut stop
prometheus astronaut tick
prometheus astronaut run-once
prometheus astronaut report
```

TUI:

```text
/astronaut
/astronaut start
/astronaut pause
/astronaut stop
/astronaut report
```

### 3.3 Long-running safety

Astronaut must have:

```text
.prometheus/astronaut/state.json
.prometheus/astronaut/events.jsonl
.prometheus/astronaut/report.md
.prometheus/STOP
```

Controls:

```text
max_runtime_minutes
max_steps_per_tick
tick_interval_seconds
random_test_probability
focused_test_probability
vision_test_probability
network_allowed
package_install_allowed
browser_allowed
sandbox_profile
```

`prometheus astronaut stop` must stop cleanly.

Creating `.prometheus/STOP` must stop it even if the TUI is closed.

### 3.4 Random but reproducible testing

Random tests must be seeded and logged.

Example evidence:

```json
{
  "type": "astronaut_random_test",
  "seed": 12345,
  "selected_area": "settings form",
  "reason": "recently changed file and low previous coverage",
  "commands": ["pytest tests/test_settings.py -q"],
  "result": "pass"
}
```

Random tests must not mutate production databases, send emails, charge payments, call real APIs, or touch external systems unless a test sandbox is explicitly configured.

### 3.5 Focused testing

When Forge changes a file, Astronaut must map related tests:

```text
changed file -> related unit tests
changed route -> browser E2E tests
changed CSS/design token -> vision inspection
changed provider/sandbox/policy -> security tests
changed installer -> clean-HOME install test
```

### 3.6 Vision-based UI inspection

Implement a dedicated `vision` package:

```text
src/prometheus_cli/vision/
  inspector.py
  playwright_driver.py
  style_snapshot.py
  element_capture.py
  comparison.py
  reports.py
```

Commands:

```sh
prometheus vision doctor
prometheus vision inspect --url http://localhost:3000 --selector "button.primary" --profile button-primary
prometheus vision inspect --url http://localhost:3000 --role button --name "Save" --profile button-primary
prometheus vision compare --actual .prometheus/vision/latest.json --expected design/button-primary.json
```

TUI:

```text
/vision inspect button.primary
/vision inspect role=button name=Save
```

### 3.7 Element-only screenshots

For detailed inspection of a specific UI item, PROMETHEUS must **not** screenshot the whole page as the primary artifact.

It must:

1. locate the element through Playwright locator, role, text, test id, or CSS selector;
2. verify the element is visible and stable;
3. collect bounding box;
4. capture only that element as a PNG;
5. collect computed CSS;
6. collect accessibility role/name/state;
7. capture hover/focus/disabled variants if requested;
8. compare deterministic style data first;
9. send only the element crop to a vision model if visual reasoning is needed;
10. store evidence in `.prometheus/vision/`.

Allowed primary evidence:

```text
element.png
element-hover.png
element-focus.png
style.json
accessibility.json
comparison.json
report.md
```

Full-page screenshots may be captured only as secondary context when explicitly requested or when the element cannot be isolated.

### 3.8 Style validation

Implement style checks for:

```text
background color
foreground/text color
border color
border radius
font family
font size
font weight
line height
padding
margin
width/height
box shadow
opacity
contrast ratio
cursor
hover state
focus ring
disabled state
icon alignment
shape/corner consistency
dominant colors from crop
edge/corner estimation from crop
visual similarity to baseline
```

The deterministic CSS snapshot must be the first judge. A vision model is a second reviewer, not the source of truth.

### 3.9 Vision models

Use local multimodal models only when configured and available.

Support model bundle roles:

```text
vision_inspector
style_critic
accessibility_critic
```

The default MVP may use deterministic CSS + image metrics without requiring a VLM. Optional VLM support can use local models from Ollama if available.

### 3.10 Vision tests

Add:

```text
tests/test_vision_style_snapshot.py
tests/test_vision_element_capture.py
tests/test_vision_comparison.py
tests/integration/test_playwright_element_screenshot.py
tests/integration/test_astronaut_vision_tick.py
```

Use a local fixture website:

```text
tests/fixtures/web_ui/
  index.html
  styles.css
  playwright.config.ts
  tests/
  design/button-primary.json
```

Acceptance:

```sh
prometheus vision inspect --url <fixture-url> --selector "button.primary" --profile tests/fixtures/web_ui/design/button-primary.json
```

must pass for correct style and fail for intentionally changed style.

---

## 4. AssetForge — local image generation package

Implement an optional package that lets PROMETHEUS generate web assets such as icons, hero images, illustrations, buttons, thumbnails, transparent PNGs, UI decorative elements, and dashboard images.

This is not a replacement for deterministic UI design. It is a local asset-generation assistant.

### 4.1 Commands

Implement:

```sh
prometheus assets doctor
prometheus assets setup
prometheus assets models
prometheus assets generate
prometheus assets generate --kind icon --name dashboard-map --transparent --size 512x512
prometheus assets generate --kind hero --name landing-hero --size 1536x864
prometheus assets remove-bg input.png --out output.png
prometheus assets variations input.png --count 4
prometheus assets manifest
```

TUI:

```text
/assets
/assets generate icon
/assets generate transparent icon
/assets remove-bg
```

### 4.2 Interactive questions

When the user asks for an asset, AssetForge must ask only the missing questions:

```text
Where will the asset be used?
What kind of asset is it: icon, hero, illustration, logo-like mark, dashboard art, product mockup, background?
What style should it follow?
What colors should it use?
Should it have transparency?
What size/aspect ratio?
Should text be included? If yes, warn that image models are bad at legible text and suggest rendering text in HTML/SVG instead.
Is it for commercial use?
Should the output be raster PNG/WebP only, or also SVG/vector-style approximation?
```

### 4.3 Model packages

Create bundle manifests:

```text
config/bundles/assetforge-lite-8gb.yaml
config/bundles/assetforge-quality-12gb.yaml
config/bundles/assetforge-transparent-experimental.yaml
```

Recommended stack:

#### AssetForge Lite, 8 GB target

```text
image_generator: stabilityai/sdxl-turbo
background_removal: rembg with u2netp or silueta
upscaler: optional local ESRGAN/Real-ESRGAN if installed
```

Notes:

- SDXL-Turbo is fast and can run in very few steps.
- Use it for icons, small illustrations, placeholder hero art, concept images, and rapid web assets.
- Do not promise perfect text rendering.
- Check Stability AI license requirements before commercial use.

#### AssetForge Quality, 12 GB+ target

```text
image_generator: black-forest-labs/FLUX.1-schnell
fallback_generator: stabilityai/sdxl-turbo
background_removal: rembg or licensed BRIA if user has rights
```

Notes:

- FLUX.1-schnell has strong prompt following and Apache-2.0 licensing, but it is heavier.
- Use CPU offload when needed.
- The user must accept any gated model terms if Hugging Face requires it.

#### AssetForge Transparent Experimental

```text
transparent_generation: LayerDiffuse-compatible workflow, when available
fallback: generate image -> remove background -> alpha matte cleanup
```

Notes:

- Native transparent generation is better in principle, but treat it as experimental.
- Fallback to background removal for MVP.

### 4.4 Licensing policy

The system must track asset provenance:

```text
model
model license
prompt
negative prompt
seed
size
steps
date
commercial_use_status
background_removal_model
post-processing steps
```

Write:

```text
assets/generated/<asset-name>/manifest.json
assets/generated/<asset-name>/README.md
```

Do not allow commercial claims when model license is non-commercial.

BRIA RMBG weights are non-commercial unless separately licensed. Do not make BRIA the default for a business/commercial product unless the user configures a commercial license.

`rembg` is acceptable as a default background-removal tool because it is MIT licensed, but individual downloaded model weights still need provenance.

### 4.5 Output standards

Generated assets must be organized:

```text
assets/generated/
  <asset-name>/
    source.png
    transparent.png
    web-512.png
    web-256.png
    web-128.png
    preview.webp
    manifest.json
    README.md
```

The agent must also be able to integrate the asset into a web project:

```sh
prometheus assets integrate --asset dashboard-map --target web/src/assets
```

Integration must update imports and tests when possible.

### 4.6 AssetForge tests

Add:

```text
tests/test_assets_manifest.py
tests/test_assets_prompt_questions.py
tests/test_assets_license_policy.py
tests/test_assets_background_removal_command.py
tests/integration/test_assetforge_sdxl_turbo_smoke.py
```

Image model tests must be skipped unless enabled:

```sh
PROMETHEUS_RUN_IMAGE_TESTS=1
```

Do not download large weights in normal CI.

Manual workflow:

```text
.github/workflows/assetforge-smoke.yml
```

---

## 5. VibeThinker sandbox proof must remain

Keep and improve the VibeThinker proof requirement.

Required commands:

```sh
prometheus models pull vibethinker-q2
prometheus models pull vibethinker-q4
prometheus models inspect vibethinker-q2
prometheus provider smoke --provider ollama --model hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
prometheus sandbox doctor
prometheus sandbox test --bundle config/bundles/vibethinker-sandbox-q2.yaml --workspace tests/fixtures/sandbox_target --all
```

Do not make VibeThinker a tool-calling controller. PROMETHEUS owns tools and asks VibeThinker only for structured suggestions/review.

---

## 6. Public website must be upgraded

Create or improve the GitHub Pages website.

It must include:

```text
hero
real install commands
hardware detection explanation
model bundle selector explanation
local-first privacy explanation
Astronaut Sentinel explanation
Vision element inspection demo
AssetForge local image generation package
VibeThinker sandbox proof
What works now
What is experimental
Roadmap
SEO metadata
OpenGraph/Twitter metadata
JSON-LD SoftwareApplication
sitemap.xml
robots.txt
```

Design target: serious, polished, Apple/Google-grade. No fake testimonials, fake numbers, generic AI gradients, or vague magic language.

The website must include actual commands, not imaginary release commands. If releases are not yet published, implement the release workflow and source-archive fallback first.

---

## 7. Implementation commands to add

At minimum these CLI command groups must exist:

```text
prometheus doctor
prometheus setup
prometheus init
prometheus run
prometheus tui
prometheus sessions
prometheus resume
prometheus modes

prometheus models list
prometheus models inspect
prometheus models pull
prometheus models unload

prometheus bundles list
prometheus bundles inspect
prometheus bundles qualify

prometheus provider list
prometheus provider smoke

prometheus sandbox doctor
prometheus sandbox test

prometheus mcp list
prometheus mcp add
prometheus mcp test
prometheus mcp call

prometheus tools list
prometheus skills list

prometheus memory inspect
prometheus memory rebuild
prometheus memory export
prometheus memory reset --confirm

prometheus astronaut start
prometheus astronaut status
prometheus astronaut pause
prometheus astronaut resume
prometheus astronaut stop
prometheus astronaut tick
prometheus astronaut report

prometheus vision doctor
prometheus vision inspect
prometheus vision compare

prometheus assets doctor
prometheus assets setup
prometheus assets models
prometheus assets generate
prometheus assets remove-bg
prometheus assets manifest
```

---

## 8. Testing mandate

Run tests constantly.

Required offline tests:

```sh
python -m compileall src
python -m pytest -q
ruff check src tests
bash -n scripts/install.sh
prometheus doctor
prometheus bundles list
prometheus sandbox doctor
prometheus vision doctor
prometheus assets doctor
prometheus tui --help
```

PowerShell test if available:

```powershell
pwsh -NoProfile -File scripts/install.ps1 -WhatIf
```

Manual model tests:

```sh
PROMETHEUS_RUN_OLLAMA_TESTS=1 prometheus models pull vibethinker-q2
PROMETHEUS_RUN_OLLAMA_TESTS=1 prometheus provider smoke --provider ollama --model hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
PROMETHEUS_RUN_OLLAMA_TESTS=1 prometheus sandbox test --bundle config/bundles/vibethinker-sandbox-q2.yaml --workspace tests/fixtures/sandbox_target --all
```

Manual browser/vision tests:

```sh
PROMETHEUS_RUN_BROWSER_TESTS=1 prometheus vision inspect --url http://localhost:4173 --selector "button.primary" --profile tests/fixtures/web_ui/design/button-primary.json
PROMETHEUS_RUN_BROWSER_TESTS=1 prometheus astronaut tick --vision
```

Manual image tests:

```sh
PROMETHEUS_RUN_IMAGE_TESTS=1 prometheus assets generate --kind icon --name test-icon --transparent --size 512x512
```

Do not fake success. If a dependency is missing, skip with exact reason and include a manual workflow.

---

## 9. Git hygiene

Never commit:

```text
*.gguf
*.safetensors
*.bin
*.onnx
models/
.ollama/
.cache/huggingface/
.u2net/
.prometheus/
**/.prometheus/
assets/generated/**/source.png
assets/generated/**/transparent.png
assets/generated/**/web-*.png
*.log
.env
.env.*
```

Generated test reports may be committed only when small, sanitized, and useful as fixtures. Runtime user state must never be committed.

---

## 10. Acceptance criteria for this session

Do not stop until these are true or clearly blocked with evidence:

1. Updated gap audit exists.
2. README no longer overclaims unfinished features.
3. Public installer strategy is corrected.
4. Placeholder installer URLs are removed.
5. `models`, `bundles`, `provider`, `sandbox`, `mcp`, `memory`, `astronaut`, `vision`, and `assets` command groups exist.
6. TUI has slash commands for settings, models, bundles, memory, vision, assets, and astronaut.
7. Astronaut Sentinel has working start/status/pause/resume/stop/tick/report MVP.
8. Vision inspector captures element-only screenshots and computed CSS snapshots.
9. Vision comparison passes/fails against a fixture.
10. AssetForge package manifests exist.
11. AssetForge asks missing questions and writes provenance manifests.
12. Image generation tests are skipped by default but available manually.
13. VibeThinker Q2/Q4 sandbox bundle support remains.
14. MCP cannot bypass sandbox policy.
15. Browser automation cannot bypass sandbox policy.
16. LSP diagnostics MVP exists.
17. Hook lifecycle MVP exists.
18. GitHub Pages site exists and explains install, Astronaut, Vision, AssetForge, and sandbox proof.
19. Tests run and results are written to implementation status.
20. No model weights, caches, secrets, local `.prometheus`, or generated asset binaries are committed.

---

## 11. Work procedure

Use this loop:

```text
1. Audit current repo.
2. Update docs/UPDATE_GAP_AUDIT.md.
3. Pick the highest-priority missing vertical slice.
4. Implement source code.
5. Add tests.
6. Run tests.
7. Fix failures.
8. Update docs/IMPLEMENTATION_STATUS.md with evidence.
9. Commit/checkpoint.
10. Continue.
```

Start now. The first vertical slice should be:

```text
Astronaut Vision MVP:
  - command group
  - Playwright element-only screenshot
  - computed CSS snapshot
  - style comparison fixture
  - Astronaut tick that runs focused/random/vision test
  - evidence and memory update
```

The second vertical slice should be:

```text
AssetForge Lite MVP:
  - command group
  - model package manifest
  - prompt-question flow
  - provenance manifest
  - optional rembg background removal
  - skipped image-generation smoke test behind PROMETHEUS_RUN_IMAGE_TESTS
```
