# PROMETHEUS — ALWAYS-ON BOUNDED MEMORY, MICRO-STEPS, AND THREE-SEAT ARENA

Repository: `https://github.com/FeverDream-dev/Prometheus`

## Implementation instruction

Implement this feature in the actual PROMETHEUS product. Do not answer by rewriting this document,
creating another proposal, or merely adding memory-related classes that are never used by the real
agent loop. Integrate it into sessions, model routing, TUI, tools, checkpoints, resume, tests, and
the model-bundle system.

The feature described here is a core runtime invariant. Users do not turn it off. They may inspect,
export, rebuild, or reset its data, but every PROMETHEUS task must use bounded project memory and
micro-step execution.

# 1. Problem

Local models often have less reliable long-context behavior and less usable context than the
maximum advertised by their model card. Large context also consumes substantial KV-cache memory,
reduces speed, and competes with model weights for VRAM. Continuously replaying the full chat,
repository, logs, tool output, plans, and previous attempts is wasteful even on large servers.

PROMETHEUS must therefore never depend on “remembering the whole conversation.” It must transform
work into a small operational memory plus a durable structured project ledger, and retrieve deeper
history only when needed.

The goal is not to delete history. The goal is layered memory:

```text
Current micro-step
      +
1,024-word working memory
      +
Relevant structured decisions/tasks/evidence
      +
On-demand retrieval from durable history
```

# 2. Core design: small memory, complete ledger

The 1,024-word memory is the fast briefing for the next model turn. It is not the database and is
not allowed to become the only record of the project.

Implement five layers:

## Layer 0 — Immutable intent

Preserve the user's original objectives, explicit constraints, approvals, rejected choices, and
definition of success. Never silently rewrite user intent during summarization.

Store normalized records with links to the original event IDs. When two requests conflict, mark a
conflict and ask or apply the latest explicit instruction according to deterministic rules. Never
blend contradictory requirements into a fabricated compromise.

## Layer 1 — Working memory, maximum 1,024 words

Maintain a concise human-readable briefing containing only:

- product/project objective;
- current verified state;
- architecture/stack currently selected;
- critical user constraints;
- active milestone;
- active micro-step;
- last successful action and evidence;
- present blocker/failure hypothesis;
- immediately next steps;
- files/components currently relevant;
- warnings and unresolved decisions.

The file must be at most 1,024 words. Enforce the limit in code. Prefer short factual statements and
stable identifiers over narrative. Do not include long logs, full diffs, source code, repeated chat,
or internal model reasoning.

## Layer 2 — Structured project state

Store machine-readable ledgers that are not subject to the 1,024-word limit:

- task graph with pending/active/passing/failing/blocked/superseded status;
- decisions with alternatives, rationale, evidence, author, and timestamp;
- requirements and acceptance criteria;
- file/component map;
- environment facts;
- tool/provider/model capabilities;
- attempts and normalized failure signatures;
- permissions and approvals;
- checkpoints and rollback references;
- test/build/browser evidence;
- unresolved questions;
- model handoffs.

These records should be compact JSON/SQLite data, schema-versioned, validated, and queryable.

## Layer 3 — Append-only event and evidence history

Keep the complete durable history outside the prompt:

- user messages;
- model final responses and action proposals;
- tool calls and bounded/redacted results;
- diffs and Git references;
- test results;
- browser traces/screenshots;
- MCP interactions;
- memory revisions;
- errors, retries, and recovery events.

Large artifacts belong in a content-addressed artifact store. Events link to hashes/paths instead of
copying huge contents into SQLite or every prompt.

## Layer 4 — Retrieval index

Use deterministic lexical retrieval first: file paths, symbols, task IDs, decision IDs, error
signatures, and ripgrep. Add optional local embeddings for semantic retrieval. Embeddings improve
recall but must never be the only way to recover critical intent or decisions.

# 3. Hidden project storage

Use a project-local hidden directory by default:

```text
.prometheus/
  memory/
    working.md
    intent.json
    tasks.json
    decisions.jsonl
    failures.jsonl
    handoffs/
    revisions/
  state/
    project.sqlite3
    schema-version
  evidence/
    manifests/
    artifacts/
  indexes/
  locks/
  recovery/
```

Add `.prometheus/` to the project `.gitignore` by default. Provide a separate explicitly sanitized
export for teams that want to share approved project rules/decisions. Never commit private chats,
secrets, absolute personal paths, model prompts, browser profiles, local database state, or raw
tool logs.

The folder is hidden but not secret. Users must be able to inspect what PROMETHEUS remembers.

Required commands:

- `/memory` — concise current memory and health;
- `/memory inspect` — browse intent, tasks, decisions, evidence, and revisions;
- `/memory why <fact>` — show provenance/evidence for a remembered claim;
- `/memory rebuild` — regenerate indexes/working memory from durable events;
- `/memory export` — sanitized user-approved export;
- `/memory reset` — checkpoint then clear/reinitialize after confirmation.

Do not provide `/memory off`. The agent loop requires this layer to remain reliable.

# 4. Memory update protocol

Update memory at deterministic boundaries:

- after every completed or failed micro-step;
- before switching model seats;
- before context truncation/compaction;
- when prompt usage reaches a configured threshold;
- after a user changes scope or corrects a fact;
- before session pause/exit;
- after crash recovery;
- after Git checkpoint/rollback.

Use this transaction:

1. Persist the raw event and evidence.
2. Redact secrets and sensitive values.
3. Extract candidate facts, decisions, task updates, failures, and next actions.
4. Compare candidates against existing structured state.
5. Reject unsupported claims and preserve conflicts explicitly.
6. Update structured records atomically.
7. Generate a new `working.md` of no more than 1,024 words.
8. Validate required sections, word limit, IDs, and provenance.
9. Write a versioned revision, checksum it, and atomically replace the active memory.
10. Verify it can be reloaded before acknowledging the micro-step as persisted.

The summarizing model may propose memory changes but deterministic code validates and commits them.
Never let a model directly overwrite durable intent or remove evidence.

## Fact confidence

Classify remembered statements:

- `user_explicit` — directly stated by the user;
- `observed` — verified by a tool/test/repository inspection;
- `decided` — selected and recorded with rationale;
- `inferred` — plausible but unverified;
- `stale` — once true but possibly outdated;
- `conflicted` — contradicted by another record.

Only explicit/observed/decided facts may be phrased as certain in working memory. Inferences must be
labeled and verified before they drive high-impact actions.

## Secret safety

Never store API keys, passwords, private tokens, cookies, authorization headers, `.env` values, or
secret file contents in working memory, events, embeddings, debug exports, or model handoffs. Store
only secret references such as `secret://openrouter/api-key`.

# 5. Micro-step execution engine

PROMETHEUS must work through tiny, verifiable increments rather than requesting one giant model
response for an entire project.

Use this state machine:

```text
UNDERSTAND
  -> SELECT ONE MICRO-STEP
  -> LOAD ONLY RELEVANT MEMORY/FILES
  -> PROPOSE ACTION
  -> APPLY WITH PERMISSION
  -> VERIFY
  -> REVIEW
  -> RECORD EVIDENCE
  -> UPDATE MEMORY
  -> GIT CHECKPOINT WHEN WARRANTED
  -> SELECT NEXT MICRO-STEP
```

## Micro-step requirements

Every micro-step must define:

- one specific outcome;
- reason it is the next dependency;
- inputs and relevant memory IDs;
- files/components expected to change;
- tool/permission needs;
- acceptance test;
- rollback method;
- time/action budget;
- completion evidence.

Prefer one concern and one to three files per step, but do not mechanically split an atomic change
into broken fragments. Database migration plus its model/test may be one coherent micro-step.

Examples:

- Detect the existing project framework and record evidence.
- Decide Docker vs native only after requirements and environment are known.
- Add one provider health check and its tests.
- Implement one settings screen action end to end.
- Repair one failing acceptance criterion.

Do not ask trivial questions that can be safely discovered. For example, inspect the repository and
deployment requirements before asking “which Linux?” or “Docker yes/no?” Choose a reversible default
when evidence supports it; ask the user only when the choice materially changes cost, risk, or
product direction.

## Guard against endless decomposition

Small steps must still produce progress. Prevent analysis loops:

- every planning step must produce either a verified fact, explicit decision, new test, or working
  code;
- limit consecutive planning-only steps;
- merge micro-steps that have no independently testable value;
- periodically verify progress against the top-level objective;
- mark obsolete tasks superseded rather than carrying them forever.

# 6. Context assembly for each model turn

Never send full history by default. Construct a bounded context packet:

1. system/role contract;
2. immutable user intent relevant to the step;
3. current 1,024-word working memory;
4. active micro-step record;
5. relevant decisions/requirements;
6. only the necessary file excerpts/symbols;
7. recent directly relevant evidence/failure signatures;
8. available tool schemas and permission limits;
9. expected structured output.

Attach provenance IDs to retrieved facts so the receiving agent can request deeper evidence. Apply
strict per-section token budgets. If the packet is too large, reduce file excerpts and retrieved
history—not immutable intent or the active acceptance criterion.

# 7. Three logical agent seats for 8 GB VRAM

Implement three persistent logical agents but do not keep three models in VRAM. On an 8 GB GPU,
load one seat at a time, persist a structured handoff, unload it, then load the next. System RAM/CPU
offload may be used when the runtime supports it, but PROMETHEUS must report when this occurs and
warn that performance can fall sharply.

## Seat A — Envoy: user-facing multimodal coordinator

Default candidate: `gemma4:e2b`.

Responsibilities:

- converse naturally with the user;
- interpret broad goals and clarify only material ambiguity;
- handle text, images, audio, and video represented as frames/audio where supported;
- research the web through permissioned tools and cite sources;
- translate requests into requirements and micro-step objectives;
- report progress, blockers, and results in understandable language;
- never claim a technical result without Builder/Verifier evidence.

Gemma does not browse or execute tools by magic. PROMETHEUS owns web, browser, media preprocessing,
and tool execution. The model proposes typed calls through the broker.

8 GB policy:

- default to a conservative context (approximately 4K–8K initially, dynamically measured);
- enable supported memory-saving runtime options only after capability checks;
- unload after creating the handoff;
- if Gemma 4 E2B cannot run reliably, fall back to `qwen3.5:4b` for text/image coordination and
  expose audio/video limitations honestly;
- never silently become cloud-backed.

## Seat B — Forge: coding builder

Default candidate: `qwen3.5:4b`.

Responsibilities:

- inspect code and relevant project context;
- propose typed file/tool operations;
- implement the active micro-step;
- produce small patches rather than whole-repository rewrites;
- run focused tests during implementation;
- explain changed behavior and expected evidence;
- stop and hand off rather than fabricating success.

This model must pass exact qualification tests for structured output, tool calls, file patches,
multi-turn tools, code repair, and repository navigation before being marked stable.

## Seat C — Argus: tester, critic, and alternate solver

Default candidate: `granite4.1:3b`.

Responsibilities:

- inspect the task, patch, diff, logs, tests, browser evidence, and acceptance criterion;
- run or request independent verification tools;
- identify false completion, regressions, placeholders, missing branches, and security problems;
- normalize the failure signature;
- accept with evidence, reject with exact reasons, or propose a materially different resolution;
- update the task/evidence ledger through validated events.

Optional specialist: VibeThinker-3B may be invoked for bounded algorithmic reasoning or failure
diagnosis, but it is not one of the direct tool seats and must never control tools.

# 8. Turn-based Arena protocol

The Builder and Tester must not merely agree with one another. Implement a turn-based arena that
uses objective evidence rather than model popularity.

## Normal loop

1. Envoy defines the micro-step and acceptance criterion.
2. Forge implements a candidate patch.
3. Argus reviews the diff and executes/requests verification.
4. If passing, the deterministic evaluator records evidence and advances.
5. If failing, Argus records a normalized failure and alternate hypothesis.
6. Forge receives only the relevant handoff and tries a revised approach.
7. After repeated same-signature failure, switch strategy/model or open a deeper arena round.

## Deep arena round

For a difficult/critical step:

- create isolated Git worktrees or patch candidates from the same clean checkpoint;
- have Forge and Argus independently propose solutions, using role-appropriate prompts;
- optionally ask VibeThinker for a non-tool reasoning critique;
- run the same tests, lint, build, security, and browser criteria against each candidate;
- score deterministically: critical tests first, regressions, correctness, scope, maintainability,
  performance, and patch size;
- select the passing candidate, merge carefully, and retain evidence;
- if neither passes, discard both worktrees and preserve failure knowledge.

Do not run deep arena for every trivial change. Trigger it for repeated failures, security-critical
work, architecture decisions, ambiguous repairs, or explicit user request. Three models debating
without tests is not an arena—it is extra text.

# 9. Model swapping and memory handoff

Before every seat change, create a compact typed handoff:

```json
{
  "task_id": "...",
  "from_seat": "envoy|forge|argus",
  "to_seat": "...",
  "objective": "...",
  "acceptance": ["..."],
  "verified_facts": [{"id": "...", "summary": "..."}],
  "changes": [{"path": "...", "diff_ref": "..."}],
  "evidence": [{"id": "...", "kind": "test|build|browser|tool"}],
  "failure_signature": null,
  "next_action": "...",
  "prohibited_actions": ["..."]
}
```

Persist and validate the handoff, then unload the current model using the runtime’s supported
mechanism. Measure free VRAM/RAM before loading the next model. Run a health/warmup probe. If load
fails, reduce context or fall back according to the active bundle; do not lose the micro-step.

The receiving seat loads `working.md`, the active task, and referenced facts/evidence—not the full
previous transcript.

# 10. Runtime memory policy for 8 GB GPUs

Implement measured behavior rather than promising “RAM and VRAM exchange easily.” CPU/RAM offload
is slower and varies by runtime, model architecture, driver, and platform.

Required behavior:

- detect total/free RAM and VRAM before every load;
- reserve headroom for OS, display, runtime buffers, and KV cache;
- estimate weights plus KV cache at the selected context;
- prefer quantized models qualified for the runtime;
- default to one loaded model;
- unload promptly at seat change (`keep_alive: 0` where appropriate);
- dynamically lower context before OOM;
- allow partial GPU/CPU execution only when supported and show actual placement/performance state;
- warn when a model spills substantially into CPU RAM;
- never rely on swap/pagefile as normal working memory;
- support Flash Attention/KV cache quantization only after runtime/platform qualification;
- record tokens/second, load time, RAM, VRAM, and context for future recommendations;
- provide a CPU-only fallback rather than crashing.

# 11. Always-on behavior and user controls

Bounded memory and micro-steps are always enabled. The user can configure:

- working-memory limit only within a safe product range, with 1,024 words as the default/maximum
  for the initial MVP;
- checkpoint cadence;
- local history retention duration/size;
- semantic embeddings on/off (structured memory remains on);
- privacy/redaction policies;
- deep arena triggers;
- model choices for each seat;
- how much evidence appears in the UI.

The user cannot disable durable task state, intent preservation, or the pre-swap handoff because the
agent cannot resume/reason safely without them.

# 12. TUI requirements

Show enough state to make this system understandable:

- active seat/model and loading/unloading status;
- active micro-step and acceptance criterion;
- top-level milestone progress;
- memory health, last compaction, and word count;
- current RAM/VRAM/model placement/context;
- current task/failure/checkpoint;
- Arena round and candidate status;
- pause/cancel/inspect-memory actions;
- a timeline of concise evidence, not raw hidden reasoning.

Do not expose private chain-of-thought. Show concise rationale, decisions, actions, tool evidence,
and final conclusions.

# 13. Required tests

## Memory correctness

- working memory never exceeds 1,024 words;
- explicit user constraints survive hundreds of events/compactions;
- superseded requirements are not treated as active;
- contradictions are flagged rather than blended;
- every remembered factual claim has provenance;
- secrets are redacted before persistence/indexing/handoff;
- atomic update survives process termination;
- corrupt active memory restores the last valid revision;
- rebuild from event history produces equivalent active tasks/decisions;
- reset/export behave safely;
- `.prometheus/` remains uncommitted.

## Micro-steps

- large objective becomes a dependency-aware task graph;
- exactly one micro-step is active per execution lane;
- acceptance criterion is present before mutation;
- failed verification does not mark completion;
- step budget prevents infinite tool loops;
- project-level objective remains visible after many small steps;
- crash/resume continues at the correct boundary without repeating side effects.

## Three seats and Arena

- one-model-at-a-time behavior under an enforced 8 GB budget;
- pre-swap handoff is persisted and validated;
- receiving seat can continue without full transcript;
- Gemma multimodal smoke tests for supported inputs;
- Qwen coding/tool/patch qualification;
- Granite log/test/review qualification;
- VibeThinker tool calls are rejected;
- reviewer detects a deliberately faulty but test-passing superficial patch through an added
  acceptance test;
- repeated failure triggers alternate hypothesis/deep arena;
- candidate worktrees cannot contaminate each other;
- deterministic tests, not model vote, select the winner;
- temporary worktrees and artifacts are cleaned and ignored.

## Real end-to-end scenario

Use a disposable SaaS fixture. Starting only from a product objective, prove that PROMETHEUS:

1. discovers/chooses a reversible initial stack decision;
2. records it with evidence;
3. creates one tiny vertical slice;
4. has Forge implement it;
5. has Argus test/reject or accept it;
6. updates the 1,024-word memory;
7. hot-swaps seats without losing state;
8. creates a Git checkpoint;
9. exits and resumes;
10. completes several more micro-steps without replaying the full history.

Record prompt-token/context size per turn to demonstrate that memory remains bounded as event
history grows.

# 14. Implementation order

1. Audit current session/context/memory code and tests.
2. Define versioned schemas for intent, tasks, decisions, events, evidence, handoffs, and revisions.
3. Build atomic hidden project store and Git-ignore protection.
4. Implement append-only events and deterministic provenance.
5. Implement 1,024-word working-memory generation/validation/recovery.
6. Integrate context packet construction into every model turn.
7. Replace broad one-shot orchestration with the micro-step state machine.
8. Implement logical seats and structured handoffs.
9. Implement measured sequential loading/unloading for the 8 GB bundle.
10. Implement normal Arena loop and deterministic reviewer gate.
11. Implement deep Arena in isolated worktrees.
12. Add TUI visibility and `/memory` controls.
13. Run unit, integration, crash-recovery, real-Ollama, and disposable SaaS E2E tests.
14. Update documentation only with verified behavior.

# 15. Completion gate

Do not call this complete because a summary file exists. Completion requires:

- every real agent turn uses bounded context construction;
- every step persists intent/tasks/evidence;
- working memory is enforced at 1,024 words;
- resume works after process death;
- three seats operate sequentially under the 8 GB policy;
- real model qualification has been run for at least the active bundle;
- Builder and Tester complete a real repair through the Arena loop;
- user can inspect/prove why important facts were remembered;
- no secret or hidden test artifact enters Git;
- tests demonstrate context remains bounded while history grows.

At handoff, report exact files, schemas, migrations, test commands/results, models/quantizations,
measured RAM/VRAM/context/load time/tokens per second, end-to-end evidence, Git status, remaining
limitations, and the shortest command sequence for the user to test the feature.

Begin by inspecting the current PROMETHEUS memory/session/orchestrator implementation. Then build
the hidden project store and one complete micro-step with a persisted 1,024-word handoff before
expanding the rest.
