# Agent reliability engineering plan

Status: **in progress** (2026-07-02)

## Problems found (E2E console)

| # | Problem | Fix | Status |
|---|---|---|---|
| 1 | Arena `git diff HEAD` misses untracked files on fresh repos | `verify_workspace_progress()` counts non-empty artifacts + porcelain | **done** |
| 2 | `write_file` accepted 0-byte files | Reject empty content; `SELF-CHECK` read-back | **done** |
| 3 | Classic orchestrator loops on empty model turns | Stop after 3 consecutive empty turns | **done** |
| 4 | Model marks `complete` with no files | Block complete until `verify_workspace_progress` passes | **done** |
| 5 | Bloated tool context on local models | Embedded **Ponytail** (minimal code) + **Cavecrew** (compress results) | **done** |
| 6 | Ollama duplicate/stale serve | `doctor` should warn (TODO) | planned |
| 7 | `git_rollback` undoes good work with `--yes` | Pilot: rollback needs explicit approval even with `--yes` (TODO) | planned |
| 8 | Telegram / phone bridge | `docs/BRIDGES.md` Phase 8 | deferred |

## Embedded efficiency stack

- **Ponytail** (`ponytail_mode`): minimal-code ladder — https://github.com/DietrichGebert/ponytail
- **Caveman** (`caveman_mode`): terse messages, tools in calls[] — https://github.com/JuliusBrussee/caveman
- **Cavecrew** (`cavecrew_mode`): compress tool results before next turn
- **Low VRAM**: `arena_char_budget` auto 12k for spark/ember bundles
- **Error decode**: `prometheus decode-error "<log line>"`
- **Self-check**: every `write_file` → automatic `read_file` verification line in tool results

## Self-check loop (deterministic)

```
write_file → SELF-CHECK OK/FAIL in tool result
Arena verify → nonempty artifacts OR pytest OR git diff
Orchestrator complete → verify_workspace_progress must pass
```

## Next validation

```bash
ollama serve &
cd _e2e_website_test && export PROMETHEUS_HOME=/tmp/prometheus-e2e-home
prometheus use spark-cpu-8gb
prometheus run "Create ./site/index.html + styles.css ..." --classic --yes --workspace .
```

## Competitive target

Match OpenCode/Codex on: first-run UX, reliable file writes, visible errors.  
Beat them on: local/offline, weighted completion %, Ponytail+Cavecrew token budget on 8 GB RAM.
