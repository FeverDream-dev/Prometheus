# Product specification

## Vision

PROMETHEUS gives people a Claude Code/OpenCode-class experience using local models by default,
while allowing explicitly configured cloud models when they improve quality. It must run on an
8 GB CPU machine, benefit from 12/24 GB GPUs, hot-swap models when memory is constrained, and
remain useful offline after models and dependencies have been acquired.

## Users

- Hobbyist: free personal use, simple installer, recommended local bundle.
- Power user: custom agents, model bundles, MCP servers, permissions, and automations.
- Team/business: commercial license, policy packs, auditability, shared signed bundles.
- Plugin author: schema-first SDK and AI-assisted plugin scaffolding.

## Core experiences

### Onboarding

`prometheus setup` detects OS, WSL, CPU, RAM, GPUs, VRAM, drivers, runtimes, disk space, and
Ollama. It explains—not merely selects—the recommended bundle and estimated download/memory
requirements. The user may select another bundle, CPU-only mode, an existing model, or a cloud
provider. No model downloads without confirmation.

### Three autonomy modes

- Copilot: reads automatically; asks before mutations, commands, installs, network, and Git.
- Pilot: edits and safe tests automatically; asks before network, installs, privileged/risky
  commands, deployment, external writes, and destructive actions.
- Astronaut: works unattended within an agreed objective, budget, workspace, and permissions.
  Hard safety gates remain. It must persist sessions, survive restarts, and emit heartbeats.

"100% freedom" means no routine approval inside the declared capability envelope. It never means
unbounded access to secrets, privilege escalation, payments, destructive commands, or external
systems outside that envelope.

### Adaptive model team

The router selects roles rather than hard-coded model names:

- controller: tool-capable agent loop;
- coder: implementation/refactoring specialist;
- reasoner: difficult algorithms and constrained plans;
- reviewer/tester: diagnoses failures and challenges completion;
- vision: screenshots, browser states, diagrams.

One model may fill several roles. If RAM/VRAM is insufficient, the runtime saves state, unloads the
current model, loads the next specialist, then resumes. Users can override every selection.

### Failure escalation

Attempts are grouped by failure signature and hypothesis. After five failed attempts on the same
path, PROMETHEUS must:

1. freeze the failing diff and evidence;
2. ask a reviewer/reasoner for a new diagnosis;
3. select a different model/persona when available;
4. revert or branch from the last good checkpoint;
5. try a materially different approach;
6. ask the user only when authority or information is genuinely missing.

### Completion

Each session maintains a requirement traceability matrix. Completion percentage is weighted
accepted criteria divided by total weighted criteria—not a model's opinion. "Complete" requires:

- at least the configured target (default 95%);
- every critical criterion passing;
- test/build/browser evidence where relevant;
- no undisclosed placeholders or mocks;
- a clean summary of remaining work and limitations;
- a recoverable Git checkpoint.

## Scope

PROMETHEUS may create or modify software, inspect repositories, install approved dependencies,
download approved applications, operate browser workflows, use MCP servers, and run configured
development tools. These capabilities are subject to permission scopes and platform safety.

## Bundle ecosystem

A `.prometheus-bundle` is a signed archive containing a manifest, role models, prompts, personas,
MCP/tool declarations, permission requests, compatibility constraints, tests, license metadata,
and optional assets. Installation shows the requested capabilities and rejects hidden executable
hooks. The AI may scaffold bundles, but deterministic validators and tests decide validity.

## Desktop roadmap

The first UI is CLI/TUI. The later desktop application should use a Chromium-based shell such as
Tauri/Electron with the same local daemon. Proton is not the application framework; it may only be
a compatibility option for unrelated Windows applications.

## Explicit non-goals for MVP

- Training or fine-tuning foundation models.
- Pretending every local model is safe or capable of tool use.
- Bypassing provider subscription restrictions.
- Fully autonomous deployment or purchases without explicit capability grants.
- Replacing legal review for the dual-license terms.

