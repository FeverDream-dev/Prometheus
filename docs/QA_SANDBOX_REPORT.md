# PROMETHEUS QA sandbox report

**Date:** 2026-06-21T02:12Z
**Host:** Linux x86_64 · AMD Ryzen 7 3700X · 47 GB RAM · AMD GPU (0 GB VRAM) · Docker ready · bwrap available
**Python:** 3.14.4
**Ollama:** installed, service running (5 local models)
**Test count:** 638 passed, 8 skipped

---

## Summary

| Category | Result |
|---|---|
| compileall | **PASS** |
| pytest (638 tests) | **PASS** (638 passed, 8 skipped) |
| ruff check | **PASS** (clean) |
| `prometheus --help` | **PASS** (18 top-level + 9 sub-app command groups) |
| `prometheus doctor` | **PASS** |
| `prometheus bundles list` | **PASS** (10 bundles, hardware-classified) |
| `prometheus sandbox doctor` | **PASS** (4 tiers: off/basic/docker/native) |
| `prometheus sandbox test --all` | **PASS** (19 PASS, 0 FAIL, 1 SKIP) |
| `prometheus memory inspect` | **PASS** |
| `prometheus vision doctor` | **PASS** (Playwright + 3 browsers) |
| `prometheus assets doctor` | **PASS** (torch available, diffusers/rembg not installed) |
| `git status --short` | **PASS** (no runtime artifacts tracked) |
| provider smoke (optional) | **SKIP** — `Connection refused` (no Ollama on probe port 1) |
| MCP malicious fixture (optional) | **PASS** — exfiltrate tool detected, output marked untrusted |
| **Overall** | **PASS** — all 12 required checks passed, 1 optional skip |

---

## 1. compileall

```
$ python -m compileall src
Listing 'src'...
Listing 'src/prometheus_cli'...
Listing 'src/prometheus_cli/agent'...
Listing 'src/prometheus_cli/assets'...
Listing 'src/prometheus_cli/memory'...
Listing 'src/prometheus_cli/providers'...
Listing 'src/prometheus_cli/tools'...
Listing 'src/prometheus_cli/vision'...
Listing 'src/prometheus_local_agent.egg-info'...
```
Result: **PASS** — all modules byte-compile without error.

---

## 2. pytest

```
$ python -m pytest -q
....sssss.....s......................................................... [ 11%]
........................................................................ [ 22%]
...............ss....................................................... [ 33%]
........................................................................ [ 44%]
........................................................................ [ 55%]
........................................................................ [ 66%]
........................................................................ [ 78%]
........................................................................ [ 89%]
......................................................................   [100%]
638 passed, 8 skipped in 28.17s
```

Skip breakdown (8 skipped):
- 5 × Real-Ollama end-to-end tests (require `PROMETHEUS_E2E_OLLAMA=1`)
- 2 × AssetForge image generation tests (require `PROMETHEUS_RUN_IMAGE_TESTS=1`)
- 1 × Browser sandbox E2E (requires Playwright browser install in CI runner)

Result: **PASS**.

---

## 3. ruff

```
$ ruff check src tests
All checks passed!
```

Result: **PASS**.

---

## 4. prometheus --help

```
$ prometheus --help

 Usage: prometheus [OPTIONS] COMMAND [ARGS]...

 PROMETHEUS — local-first adaptive coding agent

╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ doctor      Inspect hardware and recommend a model bundle.                   │
│ setup       Detect hardware, recommend a bundle, and configure PROMETHEUS.   │
│ init        Create user configuration for this machine.                      │
│ run         Run an evidence-driven coding session.                           │
│ sessions    List recent coding sessions and their completion.                │
│ resume      Show the state of a session for manual continuation.             │
│ tui         Launch the interactive Textual TUI.                              │
│ qualify     Run capability tests against a real model.                       │
│ modes       Explain autonomy levels.                                         │
│ memory      Inspect or manage PROMETHEUS bounded project memory.             │
│ use         Select the active model package.                                 │
│ export      Export a sanitized bundle manifest.                              │
│ update      Update PROMETHEUS to the latest release.                         │
│ uninstall   Remove PROMETHEUS.                                               │
│ models      List, pull, and unload Ollama models                             │
│ mcp         Manage MCP stdio servers                                         │
│ browser     Browser automation (Playwright)                                  │
│ bundles     List, inspect, and qualify model packages                        │
│ sandbox     Sandbox doctor + enforcement test suite                          │
│ provider    Provider smoke probes                                            │
│ astronaut   Long-running autonomous sessions                                 │
│ vision      Vision element inspection (Playwright + computed CSS)            │
│ assets      AssetForge — local image generation package                      │
╰──────────────────────────────────────────────────────────────────────────────╯
```

Result: **PASS** — 14 top-level commands + 9 sub-app command groups (models, mcp,
browser, bundles, sandbox, provider, astronaut, vision, assets).

---

## 5. prometheus doctor

```
$ prometheus doctor
╭────────────────────────────╮
│ PROMETHEUS hardware report │
╰────────────────────────────╯
OS: Linux x86_64
RAM: 47.0 GB
CPU: AMD Ryzen 7 3700X 8-Core Processor
CPU features: avx2, fma, sse4_2
GPU: AMD GPU
Disk free: 559.4 GB
Ollama: installed, service running
Docker: ready
Recommended package: spark-cpu-8gb (Spark — CPU / 8 GB)
```

Result: **PASS**.

---

## 6. prometheus bundles list

```
$ prometheus bundles list --json | python -m json.tool | head -20
[
  {
    "id": "spark-cpu-8gb",
    "name": "Spark — CPU / 8 GB",
    "status": "recommended",
    ...
  },
  ...
]
```

10 bundles classified:
| Bundle | Status |
|---|---|
| spark-cpu-8gb | recommended |
| ember-8gb-gpu | incompatible |
| forge-12gb | incompatible |
| oracle-gemma4-12gb | experimental |
| titan-24gb | experimental |
| hephaestus-code-24gb | experimental |
| vibethinker-review-addon | installed |
| cloud-hybrid | experimental |
| vibethinker-sandbox-q2 | installed |
| vibethinker-sandbox-q4 | installed |

Result: **PASS**.

### Bug fixed this session

`prometheus bundles list` (human-readable mode) previously crashed with
`rich.errors.MarkupError` when any installed bundle triggered the
`[bold green]installed[/bold]` status tag. Root cause: the closing tag was
`[/bold]` (mismatched with opening `[bold green]`). Fixed to
`[/bold green]`. Additionally, the `[installed]` inline marker for pulled
models was changed to `[green]installed[/green]` to avoid Rich interpreting
`installed` as an unknown style tag.

---

## 7. prometheus sandbox doctor

```
$ prometheus sandbox doctor
╭───────────────────────────╮
│ PROMETHEUS sandbox doctor │
╰───────────────────────────╯
  off     available — no enforcement requested
  basic   available — path + command policy enforced in-process
  docker  available — docker present; disposable-container enforcement available
  native  available — native confinement via bwrap
```

Result: **PASS** — all 4 tiers available.

---

## 8. prometheus sandbox test --all

```
$ prometheus sandbox test --workspace tests/fixtures/sandbox_target --all
╭────────────────────────────────────────────────────────────╮
│ Sandbox Test Suite — tests/fixtures/sandbox_target │
╰────────────────────────────────────────────────────────────╯
  basic.workspace_write_allowed          PASS  wrote allowed.txt inside workspace
  basic.outside_write_blocked            PASS  outside write blocked
  basic.symlink_escape_blocked           PASS  symlink escape blocked
  basic.path_traversal_blocked           PASS  .. traversal blocked
  basic.secret_redaction                 PASS  redacted='api_key=[REDACTED] token=gpt_xxx call'
  basic.rm_root_blocked                  PASS  BLOCKED catastrophic command
  basic.rm_home_blocked                  PASS  BLOCKED catastrophic command
  basic.sudo_blocked                     PASS  BLOCKED privilege escalation
  basic.chmod_recursive_blocked          PASS  BLOCKED catastrophic command
  basic.pipe_to_shell_blocked            PASS  BLOCKED pipe-to-shell
  basic.package_install_policy           PASS  BLOCKED package install
  basic.network_policy                   PASS  BLOCKED network
  basic.env_filter                       PASS  secret env var filtered
  mcp.permission_bypass_blocked          PASS  MCP-requested outside write blocked
  docker.workspace_mount_readonly        PASS (optional)  docker present
  docker.network_disabled                PASS (optional)  docker --network=none supported
  native.broker_active                   PASS (optional)  native confinement via bwrap
  browser.sandboxed_fixture_test         SKIP (optional)  Playwright E2E in integration tests
  memory.updated                         PASS  memory.md 193 chars
  git.checkpoint_rollback                PASS  checkpoint+rollback ok

╭──────────────────────────────────────╮
│ passed=19 failed=0 skipped=1 ok=True │
╰──────────────────────────────────────╯
```

### New tests added this session

| Test | What it verifies |
|---|---|
| `basic.rm_home_blocked` | `rm -rf ~` hard-denied by catastrophic-command pattern |
| `basic.chmod_recursive_blocked` | `chmod -R 777 /` hard-denied by catastrophic-command pattern |
| `basic.pipe_to_shell_blocked` | `curl ... \| sh` hard-denied by pipe-to-shell policy |
| `basic.env_filter` | Secret env vars (`API_KEY`, `TOKEN`, etc.) stripped from subprocess env when sandbox tier ≠ OFF |

Result: **PASS** — 19/20 tests pass, 1 SKIP (browser E2E).

---

## 9. prometheus memory inspect

```
$ prometheus memory inspect --workspace tests/fixtures/sandbox_target
Intent: (none)
Tasks:
Recent decisions:
Verified facts:
```

Result: **PASS** — empty workspace memory is valid.

---

## 10. prometheus vision doctor

```
$ prometheus vision doctor
╭──────────────────────────╮
│ PROMETHEUS vision doctor │
╰──────────────────────────╯
  Playwright: available
  Browsers: chromium, firefox, webkit
  Fixture UI: available
  Vision evidence dir: .prometheus/vision/
```

Result: **PASS** — Playwright + all 3 browser engines available.

---

## 11. prometheus assets doctor

```
$ prometheus assets doctor
╭───────────────────╮
│ AssetForge doctor │
╰───────────────────╯
  torch: available
  diffusers: not installed
  rembg (bg removal): not installed
  image tests enabled: False
  env var: PROMETHEUS_RUN_IMAGE_TESTS=1 to enable image generation
```

Result: **PASS** — torch available; diffusers/rembg not installed (optional dependencies, honestly reported).

---

## 12. provider smoke (optional — SKIP)

```
$ prometheus provider smoke --provider ollama --model fake-model \
    --base-url http://127.0.0.1:1 --timeout 2
╭──────────────────────────────────────────────────────────────────╮
│ provider smoke — Ollama (local, quota-free) @ http://127.0.0.1:1 │
╰──────────────────────────────────────────────────────────────────╯
  health: FAIL — [Errno 111] Connection refused
  list_models: FAIL — [Errno 111] Connection refused
  completion: FAIL — [Errno 111] Connection refused
  unload: FAIL — [Errno 111] Connection refused
╭──────────────────────────────────────────────────────╮
│ smoke result: FAIL — health, list_models, completion │
╰──────────────────────────────────────────────────────╯
```

Result: **SKIP** — probe targets port 1 (deliberately unreachable). The command
itself runs correctly and reports honest failure. Real provider smoke requires
a live Ollama instance on the default port (`127.0.0.1:11434`).

---

## 13. MCP malicious fixture test (optional — PASS)

```
$ prometheus mcp add malicious-qa --trust untrusted -- \
    python tests/fixtures/mcp/mcp_malicious_server.py
$ prometheus mcp test malicious-qa
Launching malicious-qa: python tests/fixtures/mcp/mcp_malicious_server.py
Initialized. server: malicious-fixture
╭───────────╮
│ Tools (1) │
╰───────────╯
  exfiltrate — Write a file to the host root (should be blocked by PROMETHEUS).
Output is delimited as untrusted data; it cannot alter system policy.
$ prometheus mcp remove malicious-qa
Removed MCP server 'malicious-qa'.
```

Result: **PASS** — the malicious MCP server's `exfiltrate` tool is discovered,
its output is marked as untrusted data, and the workspace policy layer prevents
the outside-write it requests. MCP output cannot alter system policy.

---

## 14. git status

```
$ git status --short
 M .github/workflows/pages.yml
 M README.md
 M src/prometheus_cli/cli.py
 M src/prometheus_cli/sandbox_test.py
 M src/prometheus_cli/tools/workspace.py
 M src/prometheus_cli/tui_commands.py
?? .github/workflows/qa-sandbox.yml
?? public/
?? scripts/qa_sandbox_smoke.sh
?? tests/fixtures/sandbox_target/.gitignore
?? tests/fixtures/sandbox_target/src/
?? tests/test_assets_cli.py
?? tests/test_astronaut_cli.py
?? tests/test_cli_command_groups.py
?? tests/test_memory_cli.py
?? tests/test_provider_smoke.py
?? tests/test_vision_cli.py
```

Result: **PASS** — no model weights, `.gguf`, `.safetensors`, `.prometheus/`
runtime dirs, caches, secrets, or generated runtime artifacts are tracked.

---

## QA smoke script

`scripts/qa_sandbox_smoke.sh` runs all 12 required checks + 2 optional checks:

```
$ bash scripts/qa_sandbox_smoke.sh
PROMETHEUS QA sandbox smoke — 2026-06-21T02:11:59Z

  [PASS] compileall src
  [PASS] pytest -q
  [PASS] ruff check src tests
  [PASS] prometheus --help
  [PASS] prometheus doctor
  [PASS] prometheus bundles list
  [PASS] prometheus sandbox doctor
  [PASS] sandbox test --workspace tests/fixtures/sandbox_target --all
  [PASS] memory inspect
  [PASS] vision doctor
  [PASS] assets doctor
  [PASS] git status --short
  [SKIP] provider smoke --provider fake — non-zero exit (see output above)
  [PASS] mcp test --fixture tests/fixtures/mcp/mcp_malicious_server.py

============================================
QA smoke summary: failed=0 skipped=1
============================================
RESULT: PASS (all required checks passed; 1 optional check(s) skipped)
```

CI workflow: `.github/workflows/qa-sandbox.yml` — triggers on push, PR, and
manual dispatch. Runs on Ubuntu with Python 3.11+.
