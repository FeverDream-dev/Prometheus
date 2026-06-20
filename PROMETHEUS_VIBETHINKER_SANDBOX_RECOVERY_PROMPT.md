# PROMETHEUS VibeThinker Sandbox Recovery + Real-Model Test Prompt

Repository: `https://github.com/FeverDream-dev/Prometheus`

You are OpenCode working inside the existing PROMETHEUS repository. Do **not** rewrite this prompt as another document. Do **not** make a plan-only PR. Audit the repository, then implement the missing real sandbox/model-test features directly in source code, tests, CI/manual workflows, docs, and the GitHub Pages site.

The user’s specific goal for this session:

> Use a small local VibeThinker-3B model to prove that PROMETHEUS really works end-to-end with sandboxing, Ollama/local inference, model downloading, tool execution, permission enforcement, Git checkpoints, bounded memory, and evidence-based completion.

This must become a real product feature, not a local-only experiment on the current computer.

---

## 0. Current known problem

The repo still is not the full original PROMETHEUS idea.

Known issues to verify again before coding:

1. The README still describes install as “one-liner from a fresh clone,” which is not the public copy-paste installer we wanted.
2. GitHub currently shows no published releases, so any installer depending on release artifacts is not proven.
3. The POSIX installer still uses the PyPI package name `prometheus-local-agent` when not installing from local source. Do not rely on an unpublished/fake package.
4. The Windows installer still contains placeholder URLs such as `prometheus/local-agent`.
5. `docs/IMPLEMENTATION_STATUS.md` still lists sandbox enforcement, provider conformance tests, and failure-signature tracking as blockers.
6. The README admits browser automation, full MCP transport, native sandboxes, sound playback, provider OAuth, signed bundle ecosystem, daemon recovery, and desktop client are unfinished.

Re-check these facts from the repo before making changes. Update `docs/ORIGINAL_IDEA_GAP_AUDIT.md` with evidence.

---

## 1. Non-negotiable outcome

At the end of this session, a developer must be able to run a real test like:

```sh
prometheus sandbox doctor
prometheus models pull vibethinker-q2
prometheus sandbox test --bundle config/bundles/vibethinker-sandbox-q2.yaml --workspace tests/fixtures/sandbox_target --all
```

And get evidence that:

1. the small model was actually available through Ollama or a supported local backend;
2. PROMETHEUS actually called the model;
3. sandbox mode actually blocked unsafe operations;
4. sandbox mode allowed safe workspace operations;
5. MCP/tools/browser/package-install policies cannot bypass the sandbox;
6. `.prometheus/memory.md` was created/updated;
7. Git checkpoint/rollback worked;
8. the session produced evidence logs;
9. no model weights, caches, secrets, `.ollama`, or `.prometheus` state were committed.

If this cannot be fully completed, implement the most useful vertical slice and add failing or skipped tests that clearly show exactly what remains.

---

## 2. Model choice: use the smallest practical VibeThinker first

The original VibeThinker repo is:

```text
WeiboAI/VibeThinker-3B
https://huggingface.co/WeiboAI/VibeThinker-3B/tree/main
```

The original repository uses safetensors and is about 6.19 GB total. That is acceptable as a full-model fallback, but not ideal for a small sandbox smoke test.

For the small MVP sandbox test, use the GGUF quantized VibeThinker package first:

```text
hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
```

This is the smallest practical test model, around 1.27 GB, and should run on CPU or 8 GB GPU. It is lower quality, but good enough to prove real local inference, sandboxing, and orchestration. For better quality when disk/VRAM allows, also support:

```text
hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q4_K_M
```

around 1.93 GB.

Add both as explicit test bundles, with Q2_K as the default sandbox smoke-test bundle.

Do **not** commit downloaded model files. Ollama/llama.cpp/Hugging Face caches must stay outside the repo and must be gitignored.

---

## 3. Implement model download/qualification commands

Implement or fix these commands:

```sh
prometheus models list
prometheus models pull vibethinker-q2
prometheus models pull vibethinker-q4
prometheus models inspect vibethinker-q2
prometheus models unload
prometheus provider smoke --provider ollama --model hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
```

Expected behavior:

### `prometheus models pull vibethinker-q2`

1. Detect Ollama.
2. If Ollama is missing, print clear install instructions and offer setup through `prometheus setup`.
3. If Ollama is installed but not running, try to start it or print exact instructions.
4. Pull or run the model through Ollama using:

```sh
ollama run hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
```

or the equivalent non-interactive API/CLI pull flow.

5. Verify it is listed locally.
6. Run a tiny inference prompt:
   - prompt: `Reply with exactly: PROMETHEUS_SANDBOX_READY`
   - pass condition: output contains `PROMETHEUS_SANDBOX_READY` or an accepted near-match with logged raw output.
7. Store model evidence in the session/evidence ledger.
8. Never assume success without testing inference.

### `prometheus provider smoke`

Must test:

- health;
- list models;
- one completion;
- timeout/cancellation;
- unload/keep_alive where supported;
- redaction of secrets from logs.

Use small timeouts so the command cannot hang forever.

---

## 4. Add bundle manifests

Create or update these files:

```text
config/bundles/vibethinker-sandbox-q2.yaml
config/bundles/vibethinker-sandbox-q4.yaml
```

Example structure:

```yaml
id: vibethinker-sandbox-q2
name: VibeThinker Sandbox Q2
description: Small local reasoning model used to prove PROMETHEUS sandbox and tool execution with real inference.
backend: ollama
models:
  controller:
    id: hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
    role: reviewer_reasoner
    required_capabilities:
      - chat
      - reasoning
    tool_calling: false
  builder:
    id: hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
    role: small_test_builder
    tool_calling: false
  critic:
    id: hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
    role: sandbox_critic
    tool_calling: false
limits:
  min_ram_gb: 8
  min_vram_gb: 0
  recommended_context: 4096
  sequential_loading: true
  keep_alive: 0
safety:
  sandbox_required: true
  network_default: false
  install_packages_default: false
notes:
  - VibeThinker is not a tool-calling controller. PROMETHEUS must keep deterministic control of tools.
  - This bundle is for smoke testing and reasoning/review, not high-quality production coding.
```

Important: If the controller role in the current architecture requires tool-calling, do **not** lie by using VibeThinker as a real tool-calling controller. Instead implement an engine mode where PROMETHEUS owns the tool loop deterministically and asks VibeThinker for structured JSON recommendations that are validated by Pydantic schemas before any tool call.

---

## 5. Implement real sandbox test command

Implement:

```sh
prometheus sandbox doctor
prometheus sandbox test --bundle config/bundles/vibethinker-sandbox-q2.yaml --workspace tests/fixtures/sandbox_target --all
```

The test command must run a complete suite and print a clear result table:

```text
Sandbox Test Suite
────────────────────────────────────
basic.workspace_write_allowed        PASS
basic.outside_write_blocked          PASS
basic.symlink_escape_blocked         PASS
basic.secret_redaction               PASS
basic.rm_root_blocked                PASS
basic.package_install_policy         PASS
basic.network_policy                 PASS
docker.workspace_mount_readonly      PASS/SKIP
docker.network_disabled              PASS/SKIP
docker.env_filter                    PASS/SKIP
mcp.permission_bypass_blocked        PASS
browser.sandboxed_fixture_test       PASS/SKIP
ollama.vibethinker_inference         PASS
memory.updated                       PASS
git.checkpoint_rollback              PASS
```

Also write machine-readable output:

```text
.prometheus/sandbox-test-report.json
.prometheus/evidence.jsonl
.prometheus/memory.md
```

The command must exit non-zero if required tests fail. Optional tests may be `SKIP` only when the dependency is missing, with a precise reason.

---

## 6. Sandbox features that must be tested

### Required `basic` sandbox tests

These must pass on every OS supported by the MVP:

1. Safe write inside workspace is allowed.
2. Read/write outside workspace is blocked.
3. Symlink escape is blocked.
4. `..` path traversal is blocked.
5. Dangerous command patterns are blocked:
   - `rm -rf /`
   - `rm -rf ~`
   - `sudo`
   - `curl | sh` unless network/install policy is explicitly enabled
   - `chmod -R 777 /`
6. Environment variables are filtered.
7. Secrets are redacted from command output and evidence logs.
8. Package install is blocked unless policy allows it.
9. Network commands are blocked unless policy allows it.
10. Destructive Git operations require approval.

### Required `docker` sandbox tests

Run if Docker is available; otherwise mark `SKIP`.

1. Workspace is mounted only as configured.
2. Command runs inside the container, not the host.
3. Network disabled mode actually blocks outbound network.
4. Secrets from host env are not exposed.
5. Container is disposed after test.
6. Timeout kills long-running commands.

### Required `native` sandbox tests

Run if the OS has supported primitives; otherwise mark `SKIP`.

- Linux: bubblewrap/landlock if installed/supported.
- macOS: sandbox-exec if available.
- Windows/WSL: WSL basic mode and Docker mode for now.

Do not claim native sandbox support if the OS primitive is missing.

---

## 7. MCP/tools/browser must not bypass sandbox

Add tests proving:

1. A normal tool cannot write outside workspace.
2. An MCP tool cannot write outside workspace.
3. Browser automation cannot save files outside workspace.
4. Package installer cannot install packages if policy disables it.
5. Web fetch/search cannot run if network policy disables it.
6. A model-suggested command cannot bypass the deterministic policy engine.

Create fixtures:

```text
tests/fixtures/sandbox_target/
  README.md
  package.json or pyproject.toml
  tests/
  public/index.html

tests/fixtures/mcp_malicious_server.py
```

The malicious MCP fixture should attempt to request a write outside the workspace. PROMETHEUS must block it and log evidence.

---

## 8. Use VibeThinker in a real model-driven sandbox task

Add an integration test/manual test that asks VibeThinker to perform a tiny coding task through PROMETHEUS:

Objective:

```text
Inside the sandbox fixture, create a function add(a, b), add tests for it, run the tests, and report evidence. Do not touch files outside the workspace.
```

Expected steps:

1. PROMETHEUS loads bounded memory.
2. VibeThinker proposes a structured next action or patch.
3. PROMETHEUS validates the proposed action against schema.
4. PROMETHEUS applies the patch only inside workspace.
5. PROMETHEUS runs tests inside sandbox.
6. PROMETHEUS creates a Git checkpoint.
7. PROMETHEUS updates `.prometheus/memory.md`.
8. PROMETHEUS records evidence.
9. Argus/tester pass checks that no outside files were touched.
10. Completion is computed from evidence, not model self-report.

Do not depend on VibeThinker tool-calling. PROMETHEUS must own the tool execution.

---

## 9. Add test files

Add at minimum:

```text
tests/test_sandbox_enforcement.py
tests/test_sandbox_cli.py
tests/test_vibethinker_bundle.py
tests/integration/test_vibethinker_ollama_smoke.py
tests/integration/test_sandbox_vibethinker_task.py
tests/integration/test_mcp_sandbox_block.py
tests/integration/test_browser_sandbox_policy.py
```

Integration tests that require Ollama/model download must be skipped by default unless:

```sh
PROMETHEUS_RUN_OLLAMA_TESTS=1
```

is set.

When enabled, they must use the small Q2_K model by default:

```sh
PROMETHEUS_TEST_MODEL=hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
```

Do not download the full 6.19 GB WeiboAI safetensors model in normal CI.

---

## 10. Add manual GitHub Actions workflow

Create:

```text
.github/workflows/vibethinker-sandbox-smoke.yml
```

Use `workflow_dispatch`, not automatic push, because model download can be slow/large.

The workflow must:

1. checkout repo;
2. install Python;
3. install package in editable mode;
4. install/start Ollama if practical on the runner, or clearly skip with explanation;
5. pull `hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K`;
6. run:

```sh
prometheus doctor
prometheus sandbox doctor
prometheus models pull vibethinker-q2
prometheus provider smoke --provider ollama --model hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
prometheus sandbox test --bundle config/bundles/vibethinker-sandbox-q2.yaml --workspace tests/fixtures/sandbox_target --all
```

7. upload `.prometheus/sandbox-test-report.json` and logs as artifacts;
8. never upload model weights.

---

## 11. Update public docs and website

Update:

```text
README.md
docs/SANDBOX_TESTING_WITH_VIBETHINKER.md
docs/IMPLEMENTATION_STATUS.md
docs/ORIGINAL_IDEA_GAP_AUDIT.md
site/
```

The website must include a serious “Local sandbox proof” section:

- show the Q2_K VibeThinker smoke command;
- explain that VibeThinker is a local small reasoning model;
- explain that PROMETHEUS, not the model, controls tools;
- show the sandbox test table;
- explain what is blocked;
- explain what is skipped when Docker/native sandbox dependencies are missing;
- do not claim 100% support unless all tests pass on Linux/macOS/Windows/WSL.

---

## 12. Git hygiene

Before final response, run:

```sh
git status --short
find . -name '*.gguf' -o -name '*.safetensors' -o -name '.ollama' -o -path '*/.prometheus/*'
```

No downloaded model weights, caches, secrets, or runtime `.prometheus` state may be staged.

Update `.gitignore` with:

```gitignore
.prometheus/
**/.prometheus/
*.gguf
*.safetensors
*.bin
models/
.ollama/
.cache/huggingface/
sandbox-test-report.json
```

---

## 13. Required commands to run before claiming success

Run these commands and paste the evidence into `docs/IMPLEMENTATION_STATUS.md`:

```sh
python -m compileall src
python -m pytest -q
ruff check src tests
bash -n scripts/install.sh
pwsh -NoProfile -File scripts/install.ps1 -WhatIf || true
prometheus doctor
prometheus sandbox doctor
prometheus bundles list
prometheus bundles inspect vibethinker-sandbox-q2
prometheus models inspect vibethinker-q2
PROMETHEUS_RUN_OLLAMA_TESTS=1 prometheus models pull vibethinker-q2
PROMETHEUS_RUN_OLLAMA_TESTS=1 prometheus provider smoke --provider ollama --model hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K
PROMETHEUS_RUN_OLLAMA_TESTS=1 prometheus sandbox test --bundle config/bundles/vibethinker-sandbox-q2.yaml --workspace tests/fixtures/sandbox_target --all
```

If Ollama or internet is unavailable in the development environment, do not fake success. Instead:

1. run all offline tests;
2. add the manual workflow;
3. mark the real-model smoke test as pending with exact command;
4. include a clear reason.

---

## 14. Final acceptance criteria

Do not stop until these are true:

1. `prometheus sandbox doctor` exists and works.
2. `prometheus sandbox test` exists and runs a real test suite.
3. VibeThinker Q2_K bundle exists.
4. VibeThinker Q4_K_M bundle exists.
5. `prometheus models pull vibethinker-q2` exists.
6. A real Ollama smoke path exists.
7. Sandbox policy blocks unsafe file writes.
8. Sandbox policy blocks dangerous commands.
9. MCP cannot bypass sandbox.
10. Browser automation cannot bypass sandbox.
11. Git checkpoint/rollback is included in the sandbox test.
12. Bounded memory is included in the sandbox test.
13. Integration tests are skipped safely unless enabled.
14. Manual GitHub Actions workflow exists for real VibeThinker sandbox proof.
15. README and website clearly show how to run the proof.
16. No model weights or local runtime state are committed.
17. Implementation status includes actual commands and results.

Start by auditing the repository, then implement the VibeThinker Q2_K sandbox proof as the highest-priority vertical slice.
