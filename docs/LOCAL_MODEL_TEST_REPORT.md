# Local model test report

Generated: 2026-06-23T20:00:05Z

## Environment

- PROMETHEUS_RUN_OLLAMA_TESTS: `0`
- Python: `Python 3.11.14`

## Ollama status

Ollama: **not reachable** (skipped live qualification)

```
```

## Packaged bundles

Count: **10**

## Bundle qualification

### ember-8gb

Result: **SKIP/FAIL**

```
Ollama service not responding at http://127.0.0.1:11434.
```

### forge-12gb

Result: **SKIP/FAIL**

```
Ollama service not responding at http://127.0.0.1:11434.
```

## Provider smoke

Result: **SKIP/FAIL**

```
Usage: prometheus provider smoke [OPTIONS]
Try 'prometheus provider smoke --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ Missing option '--model'.                                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Tiny model pull (qwen2.5-coder:0.5b)

Result: **SKIPPED — PROMETHEUS_RUN_OLLAMA_TESTS not set**

```
(skipped)
```
