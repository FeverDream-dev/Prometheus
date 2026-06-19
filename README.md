# PROMETHEUS

PROMETHEUS is a local-first, adaptive multi-model coding agent. It combines a tool-capable
controller with optional coding, reasoning, reviewing, and vision specialists. Ollama is the
default backend; cloud and other local OpenAI-compatible backends are pluggable.

This repository is both:

1. a runnable MVP foundation; and
2. a strict implementation package for OpenCode to evolve into a production CLI/TUI.

## What works in the MVP

- Hardware inspection and automatic 8/12/24 GB profile recommendation.
- Ollama and generic OpenAI-compatible provider calls.
- Adaptive role bundles and sequential model unloading hooks.
- Copilot, Pilot, and Astronaut autonomy policies.
- Workspace-contained file tools, command execution, Git checkpoints.
- Schema-constrained agent loop, completion threshold, retry/escalation foundation.
- CLI onboarding/configuration and unit tests.

Browser automation, full MCP transport, native sandboxes, sound playback, rich Textual TUI,
provider-specific OAuth, long-running daemon recovery, and signed installers are specified but
not falsely presented as finished. OpenCode must implement them according to `MASTER_PROMPT.md`.

## Quick start for developers

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
prometheus doctor
prometheus init . --mode pilot
prometheus run "Inspect this repository and run its tests" \
  --bundle config/bundles/ember-8gb.yaml --workspace .
```

The default bundles use normal Ollama model identifiers as placeholders that the model registry
and installer must validate. VibeThinker is deliberately configured as a non-tool reviewer.

## Build with OpenCode

Give OpenCode the repository root and paste `MASTER_PROMPT.md`. It must follow `AGENTS.md`, the
phase gates, and every acceptance test. The agent is explicitly prohibited from claiming that a
specified feature is implemented when it is only mocked or documented.

## Product principles

- Local and private by default; internet use is explicit and visible.
- The deterministic engine, never an untrusted model, owns permissions and tool execution.
- Tests and runtime evidence determine completion.
- Every mutation is checkpointed and recoverable.
- Small specialist models supplement—not impersonate—tool-trained controller models.
- Users can author, export, sign, and share model/agent/tool bundles.

See `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, and `docs/SECURITY.md`.

