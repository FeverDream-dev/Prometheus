# Acceptance tests

## Critical MVP gates

- Fresh install runs `prometheus doctor`, `init`, and a local Ollama smoke session.
- Path traversal and symlink escape tests fail closed.
- Copilot/Pilot/Astronaut produce distinct, documented approval behavior.
- Destructive actions never become approval-free.
- Invalid model JSON cannot execute a tool.
- A non-tool model is rejected as controller.
- Every write yields a diff and checkpoint; rollback restores the prior state.
- Completion below 95% or with a failing critical criterion is rejected.
- Placeholder scan lists every placeholder and blocks production completion.
- Secrets are redacted from log, model request, error, and UI snapshots.

## Adaptive routing

- 8 GB profile runs sequentially without concurrent model residency.
- 12/24 GB profiles account for KV cache and current free memory.
- Out-of-memory unloads/reduces context/falls back without losing the task ledger.
- Five identical failure signatures trigger a different persona/model and hypothesis.
- Cloud fallback never occurs without user configuration and network/privacy permission.

## Browser/MCP

- Playwright operates the real UI, collecting console/network/trace evidence.
- Chrome MCP can be selected and revoked per project.
- Prompt injection inside a webpage cannot alter permissions or system policy.
- Malicious MCP output is treated as data and cannot execute an unapproved nested action.

## Long-running sessions

- Kill -9 and reboot recovery continue from the last durable event.
- Idempotency prevents repeating external effects.
- Time/token/cost/disk ceilings stop work cleanly and save state.
- Heartbeat distinguishes active, waiting, rate-limited, blocked, and crashed.

## Cross-platform

- Linux: CPU, NVIDIA, AMD/Vulkan where supported.
- Windows: WSL baseline; native later.
- macOS: Apple Silicon Metal and CPU fallback.
- Terminals: common xterm, Windows Terminal/WSL, iTerm/Terminal.

## Release gate

Unit, integration, end-to-end, security, installer, upgrade, downgrade, SBOM, license, and artifact
signature checks pass. The release report maps every product requirement to evidence or explicitly
marks it incomplete.

