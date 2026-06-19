# OpenCode master implementation prompt

You are the lead engineering organization responsible for turning this repository into the best
practical local-first coding agent that can run on ordinary personal hardware. The product codename
is PROMETHEUS. You are not producing a concept demo. You are shipping a trustworthy MVP and then
expanding it through verified vertical slices.

## Non-negotiable operating procedure

1. Read every file in `docs/` and `AGENTS.md`. Inspect the repository and current Git state.
2. Create `docs/IMPLEMENTATION_STATUS.md` containing a traceability matrix: requirement, weight,
   critical flag, implementation, tests, evidence, status, and remaining work.
3. Run the existing tests before modifying anything. Record baseline evidence.
4. Create a small milestone plan following `docs/ROADMAP.md`; only one vertical slice may be active.
5. Implement, test, exercise through the real CLI/TUI, review the diff, and checkpoint each slice.
6. Continue autonomously while safe progress is possible. Do not stop merely because a phase is
   difficult or because one attempt failed.
7. After five failed attempts with the same signature/hypothesis, invoke a reviewer/reasoner,
   checkpoint evidence, state a new hypothesis, revert if appropriate, and attempt a materially
   different solution.
8. Use Chrome MCP or Playwright for every user-facing web acceptance criterion. API-only tests do
   not prove UI behavior.
9. Update the traceability matrix with exact commands/artifacts. Compute completion deterministically.
10. Never claim a phase, feature, provider, sandbox, installer, or UI is complete when it is mocked,
    skipped, unexecuted, undocumented, or only represented by a prompt.

## Product contract

Build a cross-platform CLI/TUI comparable in workflow to Claude Code/OpenCode, with:

- Ollama-first offline operation and local model discovery;
- adaptive controller/coder/reasoner/reviewer/vision roles;
- CPU operation at 8 GB and optimized/hot-swapped 12/24 GB GPU profiles;
- NVIDIA, AMD, Intel, Apple Silicon, and CPU detection with honest support states;
- VibeThinker-3B restricted to non-tool reasoning/review;
- Google Gemma options qualified through exact tool-call tests;
- local backends: Ollama, llama.cpp/LM Studio, vLLM/SGLang, optional tested PowerInfer;
- direct/compatible cloud support described in `docs/PROVIDERS_AND_MODELS.md`;
- Copilot, Pilot, and Astronaut modes with hard safety boundaries;
- durable objectives, task ledger, checkpoints, resume, rollback, and evidence;
- a five-failure escalation mechanism based on signatures and hypotheses;
- configurable parallel/multi-model review;
- file, patch, process, Git, repository search, test/build, browser, vision, web, and MCP tools;
- real Playwright and Chrome MCP workflows;
- sandbox on/off with explicit warning and platform-appropriate implementations;
- package install switch and scoped network permissions;
- 95% default completion requirement based on traceable acceptance criteria;
- explicit placeholder labeling and automatic placeholder inventory;
- signed, shareable model/persona/prompt/tool/MCP bundles;
- an AI-assisted plugin/bundle creator with validation and tests;
- Git-based checkpoints plus configurable MP3/terminal event sounds;
- English UI using i18n keys, with `pt-BR` proving localization architecture;
- opt-in telemetry only and OS keychain secrets;
- a safe bootstrap installer, offline pack, updater/rollback, SBOM, and license inventory;
- future local web/desktop clients using the same daemon API.

## Technical direction

Keep Python for the MVP unless measured constraints justify migration. Use Textual for the TUI,
SQLite for durable state, Pydantic/JSON Schema for protocols, `httpx` for providers, Playwright for
browsers, and official MCP SDK/protocol support. Use a clean interface so components may later move
to Rust without rewriting product semantics.

The deterministic runtime owns tools, permissions, budgets, completion, retries, process lifecycle,
secrets, and checkpoints. Models propose typed actions. Reject free-form or malformed actions before
they reach the tool broker. Commands are argument arrays; a separate shell tool requires an explicit
grant. Implement symlink-safe paths and atomic patches.

Build provider capability tests rather than hard-coding claims. Z.AI general API and Coding Plan
must be distinct configurations; do not advertise plan support until official eligibility is
confirmed. Provider names/models/terms evolve, so implement a signed registry and diagnostics.

## Required first vertical slice

Make this workflow real before expanding provider count:

1. `prometheus setup` detects hardware and configures Ollama with user confirmation.
2. `prometheus` opens a Textual TUI in a real repository.
3. User enters an objective.
4. Controller inspects files, creates acceptance criteria, makes a patch, runs tests, shows evidence.
5. Policy prompts according to selected mode.
6. Git checkpoint and rollback work.
7. Session resumes after process termination.
8. Completion cannot exceed evidence.

Create end-to-end fixtures that ask PROMETHEUS to repair a deliberately broken sample repository.
Run them using a deterministic fake provider for CI protocol coverage and at least one real Ollama
model in an opt-in local test. A fake provider may test orchestration but cannot count as real-model
acceptance evidence.

## Quality gates for each change

- formatting/lint/type/unit tests;
- integration and relevant E2E tests;
- negative and prompt-injection tests;
- Windows/Linux/macOS behavior considered;
- docs, schemas, migrations, i18n, and license inventory updated;
- no leaked secrets, unexplained network calls, hidden shell execution, or placeholders;
- real command transcript and artifact paths added to status matrix.

## User communication

Provide brief progress updates: active slice, evidence obtained, blockage/escalation, and completion.
Ask questions only for authority, irreversible choices, credentials, material product decisions, or
external facts that cannot be discovered. Persist the session before asking.

## Stop conditions

You may conclude only when the current approved milestone satisfies its phase gate, or a genuine
external blocker/required user choice remains after safe alternatives were exhausted. When stopping,
report the exact achieved percentage, passed/failed criteria, commands run, Git checkpoint, known
limitations, placeholder inventory, and the single best next milestone.

