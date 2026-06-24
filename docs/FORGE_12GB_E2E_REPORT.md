# Forge-12GB end-to-end report

Generated: 2026-06-24T01:15:00Z  
Test dir: `/mnt/projects-ssd/test`

## Summary

| Check | Result | Notes |
|---|---|---|
| Installed package has TUI fixes (`_log_user`, thread-safe session) | **PASS** | Rebuilt wheel installed to `~/.local/share/prometheus/versions/v0.1.2` |
| `prometheus use forge-12gb` | **PASS** | Bundle materialized under `~/.prometheus/bundles/` |
| `prometheus bundles qualify forge-12gb` | **SKIP** | `qwen3.5:9b` not installed locally (404) |
| `prometheus provider smoke --model granite4.1:3b` | **PASS** | Inference OK |
| `prometheus models inspect granite4.1:3b` | **PASS** | Installed + inference OK |
| TUI pytest suite (32 tests) | **PASS** | No SQLite thread failures |
| Full test-folder TUI smoke (13 checks) | **12/13 PASS** | `doctor` check intermittent in sandbox |
| Website via `prometheus run --classic` | **PARTIAL** | Model ran 50 steps; granite/llama returned empty AgentTurn tool loops; no files written |
| Workspace tool chain (`write_file`) | **PASS** | Direct `WorkspaceTools.write_file` created `site/index.html` |
| Chat user/agent distinction | **PASS** | Blue **You** block + gold **◆ PROMETHEUS** lines |
| No-bundle objective block | **PASS** | Setup card, no SQLite error |

## Installed models (Ollama)

```
granite4.1:3b, qwen2.5:0.5b, VibeThinker Q2/Q4, gemma4:e2b, gemma4:latest, llama3.2:latest
```

`forge-12gb` controller `qwen3.5:9b` is **not** installed. Pull manually:

```bash
prometheus models pull --bundle forge-12gb --yes
# or: ollama pull qwen3.5:9b
```

## Website creation attempt

Used local test bundle `forge-12gb-local-test.yaml` (granite4.1:3b controller) and
`llama-local-test.yaml` (llama3.2:latest). Both completed 50 orchestrator steps but
models returned empty structured turns without successful `write_file` execution.

**Workaround verified:** workspace write path works; a starter page exists at
`/mnt/projects-ssd/test/site/index.html` (created via `WorkspaceTools`).

**Next step for full agent website build:** install `qwen3.5:9b` or use a stronger
tool-calling model, then:

```bash
cd /mnt/projects-ssd/test
prometheus use forge-12gb
prometheus run "Create a gaming website in ./site/" --classic --yes
```

## TUI screenshot bug (fixed)

The SQLite error in the TUI screenshot came from **stale installed code** (v0.1.2 wheel
before commits `9bffb6f` / `0453e62`). After rebuilding and reinstalling the wheel:

- SessionStore uses per-thread connections + `check_same_thread=False`
- Objectives without `active_bundle_id` show setup card (no orchestrator)
- User/agent chat styling is distinct

**Restart the TUI** after reinstall: `prometheus tui` in `/mnt/projects-ssd/test`.

## Docs acceptance spot-check

- `scripts/test_folder_full_tui.sh` → 12/13 PASS
- `scripts/clean_install_defaults_smoke.sh` → PASS (when `python -m build` available)
- No raw markup in `artifacts/tui/` → PASS
- `docs/ACCEPTANCE_TESTS.md` critical gates → see `docs/IMPLEMENTATION_STATUS.md` matrix
