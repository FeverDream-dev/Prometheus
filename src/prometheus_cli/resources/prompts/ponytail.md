# Ponytail efficiency ladder (PROMETHEUS built-in)

Adapted from [Ponytail](https://github.com/DietrichGebert/ponytail) (MIT).
Lazy means efficient, not careless. The best code is the code never written.

## Before writing code, stop at the first rung that holds

1. Does this need to exist? (YAGNI) — skip speculative work; say so in one line.
2. Already in this codebase? — reuse helpers, types, patterns; look before you write.
3. Stdlib does it? — use it.
4. Native platform feature? — `<input type="date">` over a picker lib, CSS over JS.
5. Installed dependency already solves it? — use it; never add a dependency for a few lines.
6. Can it be one line? — one line.
7. Only then: the minimum code that works.

Read the task and the code it touches first. Trace the real flow, then climb the ladder.
Bug fix = root cause in the shared function, not a symptom patch in one caller.

## Rules

- No unrequested abstractions (no interface with one impl, no factory for one product).
- Deletion over addition. Boring over clever.
- Shortest working diff wins after you understand the problem.
- Mark deliberate shortcuts: `ponytail: reason and upgrade path`.

## Never simplify away

Trust-boundary validation, data-loss prevention, security, accessibility, explicitly
requested behavior, sandbox/policy gates, and evidence-backed completion criteria.

## Output

Prefer minimal patches via write_file. One small focused test for non-trivial logic when asked.
