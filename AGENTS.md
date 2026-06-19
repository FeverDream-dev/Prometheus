# Instructions for every implementation agent

1. Read `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, and
   `docs/ACCEPTANCE_TESTS.md` before editing.
2. Preserve existing user changes. Use small commits and never erase unrelated work.
3. Implement vertical slices. A slice is not complete without automated tests and real CLI/TUI
   evidence.
4. Never label a placeholder, mock, fake provider, simulated browser, or unexecuted test as done.
5. A placeholder is permitted only to demonstrate planned UX. Mark it `PLACEHOLDER`, add its
   replacement acceptance test, and keep the containing milestone incomplete.
6. Use deterministic code for permissions, budgets, process management, parsing, checkpoints,
   and completion decisions. Models may advise but may not override these controls.
7. Never expose API keys in prompts, logs, Git, crash reports, or subprocess arguments.
8. Never use VibeThinker as the tool-calling controller. It is a reasoner/reviewer only.
9. Five repeated failures on the same hypothesis must trigger a different model/persona and a
   newly stated hypothesis, not five cosmetic retries.
10. Run unit, integration, security, packaging, and browser tests appropriate to every change.
11. A reported 95% completion requires the objective traceability matrix to prove at least 95%
    of weighted acceptance criteria, with no critical safety criterion incomplete.
12. Stop only for a genuine user decision, exhausted configured budget/time, or an external
    dependency that cannot be replaced. Persist state before stopping.

