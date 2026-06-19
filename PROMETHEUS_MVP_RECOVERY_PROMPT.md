# PROMETHEUS — MVP RECOVERY AND PUBLIC RELEASE PROMPT

Repository: `https://github.com/FeverDream-dev/Prometheus`

## Your role

You are taking over an existing software repository as a senior product engineer, release
engineer, UX engineer, QA lead, and autonomous coding-agent architect. Your task is not to write
another plan, rewrite the README, or decorate incomplete code. Your task is to inspect the actual
repository, understand what truly works, repair what does not, and produce a publicly installable,
testable PROMETHEUS MVP.

PROMETHEUS is intended to become a local-first alternative to tools such as Claude Code and
OpenCode. It must let ordinary users install it on their own computer, configure local or cloud
models, open a project, ask for a programming outcome, and watch the agent inspect, modify, test,
and checkpoint the real repository.

The current machine is only a development and testing environment. Do not hard-code anything for
this computer. The software must be distributable to other users.

## Critical interpretation

This is an IMPLEMENTATION assignment.

Do not respond by creating a new specification, universal prompt, proposal, architecture-only
document, or list of suggestions. Do not ask where the output should go. The output goes into the
actual source repository: application code, installers, tests, release workflows, website files,
and documentation that accurately reflects tested behavior.

You must begin by reading the repository and running it. Documentation is evidence of intent, not
evidence that a feature works. Independently verify every claim.

## Product outcome for this session

By the end of this implementation session, a technically competent stranger should be able to:

1. Open the PROMETHEUS GitHub Pages website.
2. Select their operating system.
3. Copy one command.
4. Paste it into a fresh terminal.
5. Install PROMETHEUS without cloning the repository manually.
6. Launch `prometheus` from any directory.
7. Complete an interactive first-run setup.
8. Have PROMETHEUS detect their OS, CPU, RAM, GPU vendor, VRAM, available disk, and existing local
   AI runtimes.
9. Detect whether Ollama is installed and whether its API/service is running.
10. If Ollama is missing, clearly offer to install it with explicit user approval.
11. Discover existing Ollama models instead of downloading duplicates.
12. Recommend model bundles that genuinely fit the detected hardware.
13. Download only models the user approves, showing approximate sizes first.
14. Run a real inference smoke test.
15. Enter a usable PROMETHEUS TUI.
16. Select a folder/repository and ask PROMETHEUS to perform a small coding task.
17. See files inspected, changes proposed/applied, tests executed, evidence reported, and a Git
   checkpoint created.
18. Exit and reopen PROMETHEUS without losing configuration or session state.

If all 18 steps are not real, do not call the project a finished MVP. Mark exactly what remains.

## Mandatory initial audit

Before editing:

1. Clone or open the real repository and inspect the current branch, status, and recent commits.
2. Read `README.md`, `MASTER_PROMPT.md`, `AGENTS.md`, `docs/PRODUCT_SPEC.md`,
   `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/ROADMAP.md`,
   `docs/ACCEPTANCE_TESTS.md`, and `docs/IMPLEMENTATION_STATUS.md`.
3. Inspect all source modules, especially CLI, TUI, onboarding, providers, hardware detection,
   session storage, orchestration, tools, sandbox, browser, MCP, and installers.
4. Run formatting, linting, unit tests, integration tests, packaging, CLI help, `doctor`, `setup`,
   and TUI startup.
5. Search for `TODO`, `FIXME`, `PLACEHOLDER`, fake providers, hard-coded paths, placeholder URLs,
   unimplemented functions, skipped tests, swallowed exceptions, and claims that lack evidence.
6. Verify whether `prometheus-local-agent` is actually available from the package source used by
   the installer. Never assume it is published.
7. Verify every URL in shell and PowerShell installers. The only repository is
   `FeverDream-dev/Prometheus`; remove incorrect placeholder owners/repositories.
8. Test the advertised installation command from outside the repository.
9. Inspect GitHub Actions, releases, packages, Pages settings/workflows, tags, and artifact names.
10. Produce a short factual baseline in `docs/MVP_RECOVERY_STATUS.md`: working, partially working,
    broken, missing, and falsely/ambiguously advertised.

Do not spend the session expanding this document. Once the audit is written, implement the MVP.

## Priority rule

The priority is not the number of modules or tests. The priority is a complete vertical user
journey:

`website -> one-line installation -> first-run setup -> local model -> real TUI -> real coding task -> tests -> Git checkpoint -> resume`

Work on this journey before adding more providers, personas, abstract schemas, or long-term design.

# Milestone 1 — Make the public one-line installer real

## Required public commands

Provide copy-paste commands that work without a pre-existing clone.

POSIX baseline for Linux, macOS, and WSL:

```sh
curl -fsSL https://raw.githubusercontent.com/FeverDream-dev/Prometheus/main/install.sh | sh
```

Windows PowerShell entry point:

```powershell
irm https://raw.githubusercontent.com/FeverDream-dev/Prometheus/main/install.ps1 | iex
```

These root bootstrap files may delegate to versioned release assets, but the commands shown above
must remain stable. If piping a remote script is not desired, the website must also show a safer
download-and-inspect alternative.

## Installer behavior

Implement root `install.sh` and `install.ps1`, plus shared/versioned installer logic as appropriate.
The installer must:

- detect OS and architecture;
- support Linux distributions reasonably, macOS, and Windows via WSL for the current MVP;
- explain when native Windows is not yet supported rather than pretending it is;
- detect `curl`/`wget`, Git, Python/uv, required system facilities, available disk, and write access;
- install its own supported Python runtime or `uv` when necessary instead of simply failing with
  “install Python yourself” on a supposedly automatic installer;
- never modify system Python packages;
- install into a user-controlled versioned location such as
  `~/.local/share/prometheus/versions/<version>`;
- place a stable launcher in `~/.local/bin/prometheus` or the proper platform equivalent;
- add PATH safely or give an exact shell-specific command when automatic modification is refused;
- install from a tagged GitHub Release artifact, a verified source archive, or a verified package;
- never depend on an unpublished PyPI package;
- use the correct `FeverDream-dev/Prometheus` URLs everywhere;
- resolve the latest stable release through GitHub or accept `PROMETHEUS_VERSION`;
- verify SHA-256 checksums before executing/installing downloaded release artifacts;
- show what will be installed and where;
- be idempotent and safe to run twice;
- support `--dry-run`, `--version`, `--prefix`, `--no-ollama`, and noninteractive/CI modes;
- leave useful diagnostic logs without leaking secrets;
- stop with an actionable message and nonzero status on failure;
- run `prometheus doctor` and then first-run setup after installation;
- supply a real uninstaller that preserves models/projects unless explicitly asked to remove them.

Do not describe a cloned-repository command as the public one-liner.

## Release artifacts

Create a GitHub Actions release workflow that, on a version tag:

- runs all required tests;
- builds Python wheel/source artifacts or self-contained platform bundles;
- creates checksums;
- generates an SBOM/license inventory where practical;
- attaches versioned artifacts and checksums to a GitHub Release;
- verifies that the public bootstrap can install that release in clean CI environments;
- fails the release if the install smoke test fails.

If repository credentials prevent publishing a release, build and test the exact artifacts locally
and leave the workflow ready. Do not claim they were published.

# Milestone 2 — Build the GitHub Pages installation website

Create a polished, fast static product/install website deployable through GitHub Pages at the
repository’s standard Pages URL. Use the simplest maintainable stack that works reliably. Avoid
creating a complex web application when static HTML/CSS/JavaScript is sufficient.

The site must include:

- PROMETHEUS identity and the company logo;
- a plain explanation: local-first multi-model coding agent;
- OS tabs: Linux, macOS, Windows/WSL;
- the real one-line command for each supported path;
- a copy button with visual confirmation;
- a safer manual installation option;
- system requirements and honest support matrix;
- “What the installer does” disclosure;
- first-run explanation, including Ollama and model downloads;
- screenshots or terminal recordings generated from the real program, not fabricated UI;
- quick commands: `prometheus`, `prometheus setup`, `prometheus doctor`,
  `prometheus update`, and `prometheus uninstall`;
- troubleshooting for PATH, Ollama service, GPU detection, WSL, permissions, and offline use;
- links to releases, source, issues, license, security policy, and documentation;
- mobile and desktop responsive design;
- accessible contrast, keyboard navigation, and reduced-motion behavior;
- no trackers or analytics unless explicitly opt-in.

Create a GitHub Actions Pages workflow. Test internal links and the copy buttons. The README must
show the same commands as the website; generate shared command data or test for drift.

# Milestone 3 — Replace setup hints with a real first-run wizard

`prometheus setup` must be a coherent interactive wizard. It must not merely print instructions.

## Detection

Collect and display:

- OS, architecture, WSL/native status;
- CPU model and logical cores;
- total and currently available RAM;
- GPU vendor/model(s): NVIDIA, AMD, Intel, Apple Silicon;
- available VRAM or unified memory with honest “unknown” handling;
- free disk space in the installation/model locations;
- existing Ollama binary;
- Ollama service/API health at the configured base URL;
- already installed Ollama models from `/api/tags` or the supported API;
- existing llama.cpp/LM Studio/vLLM/SGLang-compatible endpoints when configured;
- Docker/Podman availability for optional sandboxing;
- Git and browser/Playwright prerequisites.

Do not confuse “binary exists” with “service works.” Test the API.

## Ollama installation

If Ollama is missing:

1. Explain why PROMETHEUS recommends it.
2. Offer choices: install Ollama, configure another local OpenAI-compatible endpoint, configure a
   cloud provider, or exit setup.
3. Install only after explicit confirmation.
4. Use a supported platform-specific method and report exactly what command/package will run.
5. Start or guide the service as required, then verify the API.
6. If automatic installation is unavailable for that platform, give one precise fallback without
   losing setup progress.

Never silently pipe an unrelated vendor script as root. Never request `sudo` until the user has
seen the exact reason and command.

## Model selection

- Discover installed models first.
- Benchmark/qualify models by role rather than trusting marketing names.
- Recommend an 8 GB/CPU, 12 GB, and 24 GB path using real memory estimates including context/KV
  cache headroom.
- Explain why each model is recommended and which role it fills.
- VibeThinker must remain a reasoner/reviewer and must not directly control tools.
- Show download size, estimated runtime memory, context default, and disk impact.
- Allow user-selected Ollama models and custom bundles.
- Confirm before every download.
- Show pull progress and allow cancellation/resume.
- On insufficient memory, lower context or hot-swap sequentially instead of crashing.
- After configuration, run a real prompt, validate a non-empty response, and save the working
  configuration atomically.

## First launch

After setup succeeds, offer to open the TUI immediately. A new user must not need to manually edit
YAML to begin.

# Milestone 4 — Produce a genuinely usable coding-agent MVP

The TUI must support a real task, not only display panes.

Minimum usable workflow:

1. Start with `prometheus` as the default command; `prometheus tui` may remain an alias.
2. Show the animated company-logo splash briefly, then the main interface.
3. Select/open the current workspace.
4. Display selected model bundle/backend and Ollama health.
5. Accept a natural-language coding objective.
6. Inspect repository files with bounded context.
7. Create a concise plan and acceptance criteria.
8. Read and patch real files.
9. Show diffs before or immediately after application according to autonomy mode.
10. Execute relevant tests/build/lint through the permission broker.
11. Display streaming model output, tool calls, command output, failures, and progress.
12. Create a Git checkpoint before risky changes and a checkpoint after verified progress.
13. Support rollback.
14. Escalate after five genuinely repeated failures to another model/persona/hypothesis.
15. Persist the session and resume it after restart.
16. Require evidence before declaring completion.

Make keyboard shortcuts discoverable. Implement clean cancellation so Ctrl+C does not corrupt the
session. Handle terminal resize and narrow terminals. Never hide a blocked approval behind another
screen.

## Demonstration task

Create a small deliberately broken fixture repository and an end-to-end demonstration that asks
PROMETHEUS to repair it using a real local Ollama model. The demonstration must prove:

- provider communication;
- repository inspection;
- file modification;
- command/test execution;
- evidence capture;
- Git checkpoint;
- successful completion or an honest failure report.

A deterministic fake provider is acceptable for CI protocol coverage but cannot be the only MVP
proof. Record exact instructions for the opt-in real-Ollama E2E test.

# Milestone 5 — Animated rotating ASCII company logo

The user will attach the official company-logo image to the clean implementation chat and/or add it
to the repository. Treat that image as the visual source of truth.

Create a PROMETHEUS ASCII-art identity derived from the supplied logo, similar in spirit to a
high-quality animated terminal splash. Do not substitute a generic flame, letter P, or unrelated
Prometheus mythology symbol.

## Required implementation

- Preserve the recognizable silhouette and important negative spaces of the supplied logo.
- Create at least three terminal sizes: compact, normal, and wide/high-detail.
- Create a smooth simulated 3D Y-axis rotation with approximately 16–32 frames.
- Use horizontal compression, edge changes, shading characters, and mirroring so the logo appears
  to turn—not merely move left/right or use a spinner beside a static logo.
- Render without scrolling or severe flicker using Textual refresh/update facilities or an
  equivalent terminal-safe renderer.
- Center the logo and include `PROMETHEUS` tastefully without destroying the artwork.
- Adapt to terminal width and skip animation when the terminal is too small.
- Respect reduced-motion/no-animation settings and provide `--no-animation`.
- Work in monochrome and ANSI color terminals; never make color necessary for recognition.
- Keep startup fast. Do not delay every CLI subcommand with a long animation.
- Show the full animation on interactive TUI startup; use a static compact mark for help/errors.
- Put frames/assets in a maintainable data file and include a regeneration tool if frames are
  algorithmically derived from the source image.
- Add snapshot tests for sizes and frames, ensure all frames have stable dimensions, and test that
  noninteractive output never emits animation control sequences.
- Add the source logo and generated ASCII assets with clear licensing/ownership metadata.

Before finalizing the frames, render the animation in a real terminal and capture a short terminal
recording/GIF for the website. If the source logo has not been provided, implement the animation
engine with a clearly labeled temporary test shape but keep the logo acceptance criterion
incomplete. Do not pretend the temporary shape is the final logo.

# Milestone 6 — Honest documentation and release readiness

Rewrite the README only after behavior is implemented and tested.

The README must distinguish:

- available now and verified;
- experimental;
- planned;
- unsupported.

Remove statements such as “works cross-platform,” “sandbox enforcement,” “Playwright browser
testing,” or exact test counts when they are not supported by current evidence. Test counts must be
generated or easy to update, not frozen marketing text.

Add:

- exact public installation commands;
- first-run screenshots/recording;
- uninstall/update instructions;
- current support matrix;
- privacy/network behavior;
- model download warning and disk estimates;
- troubleshooting;
- development and release instructions.

# Work discipline

## Continue rather than asking routine questions

Do not repeatedly ask the user which file to create or whether to proceed to the next normal
implementation step. Inspect, choose reversible engineering defaults, implement, and test. Ask only
when you require credentials, publishing authority, the missing logo source, or a truly material
product decision.

## Evidence-driven progress

Maintain `docs/MVP_RECOVERY_STATUS.md` with:

- current vertical-slice milestone;
- completed acceptance criteria;
- exact test commands and results;
- clean-install test environments;
- screenshots/recordings/artifacts;
- known failures;
- placeholder inventory;
- latest Git checkpoint;
- next highest-value task.

Do not assign arbitrary completion percentages. Calculate them from weighted acceptance criteria.
No critical installer, setup, inference, TUI, tool, Git, or persistence criterion may be bypassed by
a high aggregate percentage.

## Git discipline

- Preserve existing user work.
- Work on a dedicated branch such as `mvp-recovery` unless instructed otherwise.
- Commit small verified vertical slices.
- Never rewrite public history.
- Do not push, publish a release, or enable Pages without available authorization.
- If authorization exists, push only after tests pass and report the resulting URLs.

## No fake completion

The following do not count as implementation:

- a document describing an installer;
- a shell script that only works inside a clone;
- an installer that references an unpublished package;
- detecting an Ollama binary without checking the service;
- printing an Ollama install hint instead of offering a functioning setup path;
- unit tests that mock every external boundary;
- a TUI that cannot complete a real coding task;
- a fake provider response;
- a placeholder ASCII logo;
- a website with a command that has never been tested on a clean environment;
- a release workflow that has never built its artifacts locally;
- claiming support for platforms that only received static code review.

# Required test matrix

At minimum, test:

1. Unit tests and lint/type checks.
2. Package build and wheel installation in a clean virtual environment.
3. Public POSIX one-liner in a clean Ubuntu container/VM from outside the repository.
4. Re-running the installer for idempotency.
5. Uninstall/update flow.
6. macOS install through CI or a real runner.
7. WSL/PowerShell bootstrap through the best available real/CI environment, clearly documenting
   any untested boundary.
8. CPU-only hardware detection.
9. NVIDIA detection where a runner is available; fixture tests for AMD/Intel/Apple plus real-runner
   evidence when available.
10. Ollama absent, installed-but-stopped, running-with-no-models, and running-with-existing-models.
11. Model pull cancellation/failure and disk-space failure.
12. Real Ollama inference smoke test.
13. TUI startup, resize, keyboard navigation, approval, cancellation, and resume.
14. End-to-end repair fixture with real file changes/tests/Git.
15. Website link/copy-button/accessibility checks.
16. Release artifact/checksum/bootstrap smoke test.
17. ASCII animation dimensions, reduced motion, non-TTY output, and snapshot stability.

# Order of execution

Follow this order unless repository evidence proves a prerequisite must move:

1. Audit and baseline.
2. Fix the actual package/install source.
3. Implement and test the root one-line bootstraps.
4. Complete first-run Ollama/runtime/model setup.
5. Prove a real local inference.
6. Complete one real coding-agent vertical slice in the TUI.
7. Add session resume/checkpoint proof.
8. Integrate the supplied logo and rotating ASCII animation.
9. Build and deploy-ready GitHub Pages site.
10. Build release artifacts and clean-install CI.
11. Correct README/status claims.
12. Run the complete acceptance matrix and deliver the MVP report.

# Final handoff

At the end, provide:

- the branch and final commit hash;
- exact files changed;
- exact public installation commands;
- local GitHub Pages preview/deployed URL if authorized;
- release artifact names and checksums;
- test summary with exact commands;
- real Ollama E2E result and model used;
- TUI demonstration result;
- installer environments tested;
- remaining unsupported or experimental items;
- placeholder inventory;
- the shortest sequence I can use to test PROMETHEUS myself.

Do not conclude with only “the tests pass.” Demonstrate the complete user journey. Start by auditing
the real repository now, then implement the highest-priority broken link in the public installation
journey.
