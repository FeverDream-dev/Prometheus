# Implementation roadmap and phase gates

## Phase 0 — foundations

CLI packaging, schemas, hardware probe, Ollama/provider interface, deterministic policy, workspace
boundary, event types, tests. Gate: clean install and test on Linux plus WSL CI.

## Phase 1 — trustworthy single-agent vertical slice

Streaming controller, patch tool, process supervisor, Git checkpoint/rollback, project rule import,
objective ledger, evidence, 95% evaluator, resume. Gate: create and repair a real sample app using
Ollama without manual file edits.

## Phase 2 — production TUI

Textual TUI with streaming panes, task tree, diffs, permission prompts, provider/model status,
context/cost display, mode indicator, cancellation, session browser. Gate: keyboard-only end-to-end
workflow and snapshot tests on all target terminals.

## Phase 3 — adaptive team and hot swap

Role router, memory monitor, unload/load lifecycle, five-failure signatures, reviewer escalation,
parallel review toggle, shared artifact protocol. Gate: forced-low-memory test proves recovery and
materially different escalation.

## Phase 4 — browser, MCP, plugins, audio

Playwright, Chrome MCP, generic MCP client, permissioned MCP registry, plugin SDK/wizard, signed
bundles, configurable sound events. Gate: browser-tested example app and malicious MCP/bundle tests.

## Phase 5 — providers and installers

Direct adapters, dynamic top-provider registry, keychain, costs/budgets, signed installers, model
downloads, license inventory, updater, offline pack. Gate: Windows/WSL, Linux NVIDIA/AMD/CPU, and
macOS Apple Silicon matrices.

## Phase 6 — daemon and unattended Astronaut

SQLite event store, crash recovery, heartbeats, resource limits, scheduled continuation, remote
read-only status. Gate: multi-day fault-injection run resumes without duplicating side effects.

## Phase 7 — desktop

Local web UI and Tauri/Electron shell using the daemon API. Gate: feature parity for primary TUI
flows, signed packages, accessibility, and auto-update rollback.

