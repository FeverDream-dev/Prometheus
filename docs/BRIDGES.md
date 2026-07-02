# PROMETHEUS remote bridges (planned)

Status: **deferred** — implement after Phase 6 daemon is stable.

## Goal

Hermes-class reach (phone / Telegram anywhere) with **coding-agent semantics**, not assistant chat.

## Event types (daemon → bridge)

| Event | Message shape |
|---|---|
| `git_checkpoint` | Session id, commit SHA, step count |
| `criteria_met` | Description, weight, critical flag |
| `completion_update` | Weighted % from traceability matrix |
| `meets_target` | 95% gate + critical pass summary |
| `astronaut_heartbeat` | active / waiting / blocked / crashed |
| `session_blocked` | Reason + last evidence snippet |

## Commands (bridge → daemon)

- `/status` — current session snapshot
- `/objective <text>` — queue objective (Pilot approval if needed)
- `/pause` / `/resume` — astronaut control files
- `/approve <token>` — one-shot permission grant

## Security

- Bot token in OS keychain only
- Read-only default; writes require explicit mode + approval
- No secrets, diffs, or API keys in outbound messages

## Dependencies

1. Phase 6 `prometheus daemon` with SQLite event tail
2. Stable TUI/setup (Layer 1 stabilization)
3. MCP template pattern (`mcp_templates.py`) reused for bridge config
