# Caveman terse output (PROMETHEUS built-in)

Adapted from [Caveman](https://github.com/JuliusBrussee/caveman) (MIT).
Terse agent messages and tool context — ~65–75% fewer prose tokens on local models.

## Rules for AgentTurn JSON

- `message` field: short. No filler, no tool-call narration in prose.
- Put actions in `calls[]` only — never describe `write_file(...)` inside `message` without `calls`.
- Quote exact error lines when reporting failures; do not dump full stack traces.
- Code in `write_file` content: full and correct — compression applies to messages, not file bodies.

## Intensity (configured via caveman_mode)

| Level | Behavior |
|---|---|
| **lite** | Professional but tight; keep grammar |
| **full** | Drop articles; fragments OK; short synonyms |
| **ultra** | Maximum compression; code symbols never abbreviated |

## Auto-clarity exceptions

Use full sentences for: security warnings, destructive confirmations, multi-step order ambiguity.

## Tool discipline (critical for small models)

WRONG: message = "I will write_file('index.html', ...)" with empty calls[]
RIGHT: calls = [{tool: write_file, arguments: {path, content}, reason: ...}]

After write_file, read_file same path to confirm (SELF-CHECK in tool results).
