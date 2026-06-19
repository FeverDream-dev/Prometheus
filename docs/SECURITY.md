# Security and permissions

## Threat model

Defend against prompt injection, malicious repositories, poisoned MCP results, dependency scripts,
path traversal, symlink escapes, secret leakage, command injection, destructive model behavior,
runaway costs, compromised bundles, and unattended-session drift.

## Capability envelope

Every session receives explicit scopes:

- allowed workspace roots;
- read/write path patterns;
- command families and timeouts;
- network domains and methods;
- MCP servers;
- secret names (never secret values in prompts);
- package installers;
- external side effects;
- time/token/cost/storage budgets.

Astronaut mode removes routine prompts only inside this envelope. The following always require a
specific user grant: privilege escalation, writes outside roots, destructive disk/Git operations,
credential changes, purchases, production deployment, public publishing, and contacting people.

## Sandbox tiers

1. Native restricted process: fast baseline, no shell by default.
2. Container: isolated filesystem/network with explicit mounts.
3. Platform sandbox: bubblewrap/landlock on Linux, sandbox-exec successor strategy on macOS, and
   Windows Sandbox/Job Objects/AppContainer strategy on Windows/WSL.
4. Unsandboxed: explicit warning, persistent visual indicator, logged grant.

The onboarding test must prove the chosen sandbox blocks path escape and unauthorized network.

## Secrets

Use Keychain, Credential Manager, or Secret Service/keyring. Redact values and common token forms
from prompts, logs, diffs, terminal output, screenshots, and crash reports. Environment variables
are compatibility inputs, not the preferred storage mechanism.

## Supply chain

- Pin and verify installer artifacts and model hashes.
- Generate SBOMs and third-party license inventories.
- Sign releases and bundle registries.
- Require bundle manifests and show capabilities before install.
- Never execute install hooks from community bundles.
- Run dependency vulnerability and secret scans in CI.

## Provider terms

Provider adapters must not imply that a subscription plan permits arbitrary API use. For example,
Z.AI Coding Plan requires its dedicated endpoint and is limited to supported coding tools/terms.
The production team must confirm PROMETHEUS eligibility before advertising plan-quota support;
otherwise expose the general Z.AI API and label Coding Plan support experimental/unverified.

## Logging and telemetry

Default telemetry is off. Local audit logs are on, user-readable, redactable, and deletable. Opt-in
telemetry must describe every collected field and never include source code, prompts, file paths,
secrets, model responses, or command output by default.

