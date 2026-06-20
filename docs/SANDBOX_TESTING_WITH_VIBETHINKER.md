# Sandbox testing with VibeThinker

This proves PROMETHEUS works end-to-end with a **real small local model**, real
Ollama inference, real sandbox enforcement, real MCP/tool/browser policy
blocking, real bounded memory, and real Git checkpoints — using the smallest
practical VibeThinker-3B GGUF quantization.

## Why VibeThinker

`hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K` (~1.27 GB) is the smallest
practical model that runs on CPU or an 8 GB GPU. It is a **reasoning** model,
not a tool-calling controller. PROMETHEUS keeps deterministic control of every
tool: the model only proposes structured JSON recommendations that are validated
by Pydantic schemas before any tool is dispatched. A higher-quality
`Q4_K_M` (~1.93 GB) variant is also bundled for when disk/VRAM allow.

## The proof commands

```sh
prometheus sandbox doctor                                                    # which tiers are available
prometheus models pull vibethinker-q2                                        # ~1.27 GB pull + inference probe
prometheus provider smoke --provider ollama \
  --model hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K                       # health/list/completion/unload
prometheus sandbox test \
  --bundle config/bundles-v2/09-vibethinker-sandbox-q2.yaml \
  --workspace tests/fixtures/sandbox_target --all                            # the full enforcement suite
```

`models pull vibethinker-q2` resolves the alias, pulls via Ollama, and runs a
one-token inference probe — it never claims success without testing inference.

## What the suite proves

```
Sandbox Test Suite
────────────────────────────────────────────────
basic.workspace_write_allowed        PASS      safe write inside workspace works
basic.outside_write_blocked          PASS      ../ writes blocked
basic.symlink_escape_blocked         PASS      symlink pointing outside blocked
basic.path_traversal_blocked         PASS      ../../ blocked
basic.secret_redaction               PASS      api_key/token stripped from logs
basic.rm_root_blocked                PASS      rm -rf / blocked
basic.sudo_blocked                   PASS      sudo/su/doas blocked
basic.package_install_policy         PASS      pip/apt blocked when disabled
basic.network_policy                 PASS      curl/wget blocked when disabled
mcp.permission_bypass_blocked        PASS      MCP-requested outside write blocked
docker.workspace_mount_readonly      PASS/SKIP only when docker is present
docker.network_disabled              PASS/SKIP
native.broker_active                 PASS/SKIP bwrap (Linux) / sandbox-exec (macOS)
browser.sandboxed_fixture_test       PASS/SKIP playwright E2E in integration tests
ollama.vibethinker_inference         PASS/SKIP real inference when model pulled
memory.updated                       PASS      .prometheus/memory.md written
git.checkpoint_rollback              PASS      checkpoint + rollback verified
```

The command writes:
- `.prometheus/sandbox-test-report.json` (machine-readable)
- `.prometheus/evidence.jsonl` (one line per test)
- `.prometheus/memory.md` (bounded summary)

It **exits non-zero** if any required test fails. Optional tests may `SKIP` only
when their dependency (docker / native primitive / playwright / pulled model) is
missing — with a precise reason.

## PROMETHEUS owns the tool loop

VibeThinker has `tool_capable: false`. The Arena's `MicroStepEngine` calls
`provider.complete(messages, schema=AgentTurn.model_json_schema())` and
validates the response with `AgentTurn.model_validate_json(raw)` before any tool
dispatch. The model can never bypass the deterministic policy engine — a
model-suggested `rm -rf /` is blocked just like any other command.

## CI

`.github/workflows/vibethinker-sandbox-smoke.yml` is a **manual**
(`workflow_dispatch`) workflow: it installs Ollama on the runner, pulls Q2_K,
runs doctor + provider smoke + the sandbox suite, and uploads the evidence
artifacts. It never uploads model weights.

## Local integration tests

```sh
PROMETHEUS_RUN_OLLAMA_TESTS=1 \
PROMETHEUS_TEST_MODEL=hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K \
  pytest tests/integration/ -v
```

Without those env vars the integration tests skip cleanly (no network, no
downloads in normal CI).

## Git hygiene

`.gitignore` excludes `*.gguf`, `*.safetensors`, `*.bin`, `models/`, `.ollama/`,
`.cache/huggingface/`, and all `.prometheus/` runtime state. No downloaded
weights, caches, secrets, or session state are ever committed.
