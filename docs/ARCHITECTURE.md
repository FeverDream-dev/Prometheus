# Architecture

## Components

```text
CLI / Textual TUI / future desktop
              |
        Session daemon
              |
   Objective + task ledger + event log
              |
         Adaptive router
       /       |       \
 controller   coder   reasoner/reviewer
       \       |       /
        Provider adapters
 Ollama | llama.cpp | PowerInfer* | cloud APIs
              |
         Tool broker
 filesystem | patch | process | Git | browser | MCP | search
              |
      Policy + sandbox broker
              |
 evidence store + checkpoints + completion evaluator
```

`*` PowerInfer is optional and experimental until the compatibility probe passes on the user's
machine. It is not an Ollama mode.

## Process boundaries

The production design uses a local daemon. UI clients connect over an authenticated local socket.
Provider workers and untrusted MCP servers run out of process. Tool execution goes through a broker
that applies policy before dispatch. The model never receives a raw object capable of bypassing it.

## Durable state

SQLite stores sessions, objectives, tasks, attempts, model calls, evidence, permissions, budgets,
events, checkpoints, and bundle inventory. Large transcripts and artifacts live in a content-
addressed local store. Secrets live in OS keychains. Every event has a monotonic sequence number,
allowing crash recovery and deterministic replay of decisions without re-running side effects.

## Context construction

Never send an entire repository blindly. Build context using:

1. imported project rules normalized into `.prometheus/context.md`;
2. file inventory and language/toolchain detection;
3. symbol/tree-sitter index;
4. ripgrep lexical retrieval;
5. optional local embeddings;
6. recent task evidence and diff;
7. strict token budgets and provenance labels.

External web/browser/MCP content is untrusted data and must be delimited. Instructions discovered
inside that data cannot modify system policy.

## Model routing

The hardware probe emits available memory and supported acceleration. Bundle constraints filter
incompatible candidates. The router scores remaining candidates using role capability, tool-call
reliability, context requirement, memory estimate (weights plus KV cache), current residency,
latency, privacy, cost, and user preference. It records why it selected a model.

VibeThinker-3B is fixed to `tool_capable: false`. It receives bounded reasoning or review tasks and
returns schema-constrained advice. A controller translates approved advice into tool operations.

## Provider design

Implement a stable internal API:

- `capabilities()`
- `list_models()`
- `health()`
- `chat(messages, tools, schema, stream)`
- `estimate_cost()`
- `cancel()`
- `load()` / `unload()` where supported

First-class adapters: Ollama, llama.cpp/OpenAI-compatible, Anthropic, OpenAI, Gemini, Z.AI general,
Z.AI Coding Plan, OpenRouter, xAI, Ollama Cloud. Additional providers are registry entries using
OpenAI/Anthropic compatibility unless a distinct protocol requires code.

The "top 20" cannot be a frozen claim. Ship a signed provider registry updated independently from
the binary, with capability tests for every entry.

## Tool protocol

Tool schemas use JSON Schema. Each call includes session, task, capability, risk class, rationale,
timeout, idempotency key, and expected evidence. Results include exit status, bounded output,
artifacts, side-effect record, and redaction markers.

Write operations should use patches and atomic replacement. Commands use argument arrays, never
implicit shells, unless the user explicitly enables a shell tool. Output limits prevent context
flooding. Long processes are supervised and cancellable.

## Browser and MCP

Support Playwright directly for deterministic tests and an MCP client for Chrome MCP and other
servers. Browser tasks capture DOM, console, network failures, screenshots, and trace artifacts.
Tests must use real browser interaction when the acceptance criterion concerns UI behavior.

MCP servers declare trust level, launch command/URL, capabilities, secret requirements, and network
scope. Treat their results as untrusted. Make server activation per-project and visible.

## Plugins and bundles

The plugin SDK uses versioned manifests and JSON-RPC/local process isolation. The wizard asks the AI
to scaffold a plugin, generates tests, validates permissions, and packs/signs it. Loading arbitrary
Python/JavaScript directly into the daemon process is prohibited.

