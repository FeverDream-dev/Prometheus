# Installer proof — what is verified and what the release tag changed

## Full installed-product smoke (2026-06-23)

`bash scripts/full_installed_product_smoke.sh` against the live public installer:

```text
=== PROMETHEUS full installed-product smoke ===
[1/8] Installing from public installer... install OK
[2/8] prometheus doctor ... doctor OK
[3/8] prometheus bundles list ... found 10 bundles
[4/8] prometheus setup --dry-run ... setup --dry-run OK
[5/8] prometheus tui --demo --exit-after-render ... tui demo OK
[6/8] bundleforge recommend ... bundleforge OK
[7/8] sandbox test ... sandbox OK
[8/8] raw markup check ... no raw markup in artifacts/tui
=== PASS: full installed-product smoke ===
```

Unreleased main: `PROMETHEUS_REF=main bash scripts/full_installed_product_smoke.sh`

---

## Packaged defaults fix (Step 1 recovery)

The v0.1.0 wheel shipped without default bundles, causing `prometheus setup` to
report `No bundles found. Pass --bundles-dir.` after a clean install. This is
now fixed: default bundles (v1 + v2), prompts, schemas, i18n, and
default_config are packaged inside the wheel at
`prometheus_cli/resources/`.

Clean-install verification (`bash scripts/clean_install_defaults_smoke.sh`):

```text
=== PROMETHEUS clean-install defaults smoke ===
[1/5] Building wheel + sdist...
  wheel: prometheus_local_agent-0.1.0-py3-none-any.whl
[2/5] Creating clean venv...
[3/5] Testing: prometheus bundles list
  found 10 bundles
[4/5] Testing: prometheus setup --dry-run
  setup --dry-run shows bundles (no 'No bundles found' error)
[5/5] Testing: prometheus doctor
  doctor runs successfully
=== PASS: clean install includes defaults ===
```

Wheel resource count (was 0, now 27 data files):

| Resource | Count |
|---|---|
| V2 bundles (`bundles_v2/*.yaml`) | 10 |
| V1 bundles (`bundles_v1/*.yaml`) | 8 |
| Prompts (`prompts/*.md`) | 3 |
| Schemas (`schemas/*.json`) | 3 |
| i18n (`i18n/*.json`) | 2 |
| Default config (`default_config.yaml`) | 1 |
| **Total** | **27** |

The fix will be included in the next release tag. The current v0.1.0 release
artifacts on GitHub still have the old wheel without resources; users installing
from `main` source or the next tag get the fix.

---

## Summary

`v0.1.0` is **published** (tag pushed, GitHub Release live at
<https://github.com/FeverDream-dev/Prometheus/releases/tag/v0.1.0>, published
2026-06-21T04:27:42Z). Both installer paths were verified this session against
the live release:

| Path | When it activates | Checksum verified? | Tested this session? |
|---|---|---|---|
| **Release sdist (from GitHub Release)** | `v*` tag exists + release assets uploaded | **Yes** — SHA-256 sidecar, strict fail on mismatch/missing | **Yes — verified end-to-end against the live v0.1.0 release** |
| Source archive fallback | No release found, or `PROMETHEUS_VERSION=main` | No (GitHub generates dynamically) — warns loudly | Yes — verified this session |
| Local wheel install | Developer/CI path | Verified via `SHA256SUMS` | Yes — verified this session |

The installer prefers the release sdist whenever the resolved version starts
with `v`. With `v0.1.0` now published, the default resolution
(`api.github.com/.../releases/latest`) returns `v0.1.0`, so **the default
one-liner now installs the verified release sdist** — not the source archive.

## What is proven this session (real evidence)

### 1. Release sdist install with checksum verification (the default path now)

```sh
$ ISOLATED_HOME=/tmp/rel-install-home
$ rm -rf "$ISOLATED_HOME" && mkdir -p "$ISOLATED_HOME"
$ HOME="$ISOLATED_HOME" PROMETHEUS_VERSION=v0.1.0 \
    sh public/install.sh --yes --no-ollama --no-tui \
       --bin "$ISOLATED_HOME/.local/bin" \
       --prefix "$ISOLATED_HOME/.local/share/prometheus"
=== PROMETHEUS installer ===
repository : FeverDream-dev/Prometheus
version    : v0.1.0
install to : /tmp/rel-install-home/.local/share/prometheus/versions/v0.1.0
launcher   : /tmp/rel-install-home/.local/bin/prometheus
checksum verified: 84fa97575f43baa42dae4ae43fa8ff4bfaf6de59d7bb8d1b66dfac8f7a779ff7
=== Installation complete ===
```

The downloaded sdist's SHA-256 matches the published
`prometheus_local_agent-0.1.0.tar.gz.sha256` sidecar exactly
(`84fa97575f43baa42dae4ae43fa8ff4bfaf6de59d7bb8d1b66dfac8f7a779ff7`). The
installed entry point works:

```sh
$ "$ISOLATED_HOME/.local/bin/prometheus" --help          # PASS
$ "$ISOLATED_HOME/.local/bin/prometheus" doctor           # PASS — full hardware report
```

This is the **default path** for new users now that `v0.1.0` is published: the
GitHub Releases API returns `v0.1.0` as latest, so a plain
`curl ... | sh` with no `PROMETHEUS_VERSION` env resolves to this verified
release sdist.

### 2. Default resolution now picks the release (dry-run proof)

```sh
$ sh public/install.sh --dry-run
=== PROMETHEUS installer ===
version    : v0.1.0
DRY RUN — no changes will be made.
would download: https://github.com/FeverDream-dev/Prometheus/releases/download/v0.1.0/prometheus_local_agent-0.1.0.tar.gz
would verify  : https://github.com/FeverDream-dev/Prometheus/releases/download/v0.1.0/prometheus_local_agent-0.1.0.tar.gz.sha256
EXIT: 0
```

No `PROMETHEUS_VERSION` was set. The installer queried
`api.github.com/.../releases/latest`, got `tag_name: v0.1.0`, and selected the
release sdist + checksum path.

### 3. Explicit `PROMETHEUS_VERSION=v0.1.0` (release path)

```sh
$ PROMETHEUS_VERSION=v0.1.0 sh public/install.sh --dry-run
version    : v0.1.0
would download: https://github.com/FeverDream-dev/Prometheus/releases/download/v0.1.0/prometheus_local_agent-0.1.0.tar.gz
would verify  : https://github.com/FeverDream-dev/Prometheus/releases/download/v0.1.0/prometheus_local_agent-0.1.0.tar.gz.sha256
EXIT: 0
```

### 4. Source-archive fallback (`PROMETHEUS_VERSION=main`)

```sh
$ PROMETHEUS_VERSION=main sh public/install.sh --dry-run
version    : main  (unreleased)
would download: https://github.com/FeverDream-dev/Prometheus/archive/refs/heads/main.tar.gz
would verify  : (source archive — no checksum sidecar)
EXIT: 0
```

A real install through this path also succeeds and warns loudly about the
unverified checksum:

```sh
$ HOME="$ISOLATED_HOME" PROMETHEUS_VERSION=main sh public/install.sh --yes --no-ollama --no-tui ...
! Source archive: no stable checksum to verify against.
! Computed sha256: d6c8df4fe1cbc90e0b9ef37f8ecb023e2dd4547baed5923887f58f77aa4e226c
! For a verified install, pin a version:  PROMETHEUS_VERSION=v0.1.0 sh install.sh
=== Installation complete ===
```

### 5. Direct download of the source archive (manual fallback path)

The exact URL from the task —
`https://github.com/FeverDream-dev/Prometheus/archive/refs/heads/main.tar.gz` —
was downloaded, extracted, and installed into a clean venv:

```sh
$ curl -fsSL -o main.tar.gz \
    https://github.com/FeverDream-dev/Prometheus/archive/refs/heads/main.tar.gz
downloaded main.tar.gz (32971585 bytes)
$ tar -xzf main.tar.gz && ls -d Prometheus-main/
$ python3 -m venv clean_venv
$ clean_venv/bin/python -m pip install "Prometheus-main[tui]"
$ clean_venv/bin/prometheus --help     # PASS
$ clean_venv/bin/prometheus doctor     # PASS
```

This path works. Note the size difference: the **release sdist is 167 KB**
(Python source only, via `python -m build`), while the **GitHub source archive
is ~33 MB** (includes all git-tracked images and docs). The release sdist is the
smaller, cleaner, checksum-verifiable install path — which is why the installer
prefers it.

### 6. No placeholder URLs

```sh
$ grep -r 'prometheus/local-agent' install.sh public/install.sh install.ps1 public/install.ps1
# (no matches)
```

All installer scripts use the real repo `FeverDream-dev/Prometheus`.

### 7. install.ps1 (Windows → WSL delegate)

Static structure verified (PowerShell syntax is validated by the
`windows-latest` job in CI; `pwsh` is not installed in this Linux sandbox):

- `FeverDream-dev/Prometheus` is the repo (1 reference).
- Zero `raw.githubusercontent` references in `install.ps1` itself.
- Delegates to WSL (`wsl.exe` referenced 5×).
- Bootstrap URL is the GitHub Pages host:
  `https://feverdream-dev.github.io/Prometheus/install.sh`.
- If WSL is missing, prints exact `wsl --install` steps and exits non-zero
  rather than falling back to a placeholder.

## What the release tag changed

Before `v0.1.0` was pushed, the installer's default path resolved to `main` and
warned that release artifacts were not yet available. Now that `v0.1.0` is
published:

- **Default install is now checksum-verified.** The installer downloads the
  release sdist from `releases/download/v0.1.0/`, fetches the `.sha256` sidecar,
  and hard-fails on any mismatch or missing sidecar. It no longer falls back to
  the source archive for the default path.
- **The source-archive fallback still exists** for `PROMETHEUS_VERSION=main`
  and for the (now-impossible) case where a `v*` tag exists but the release
  assets 404. It remains explicitly unverified and warns about it.
- **`prometheus update`** and the installer's auto-update path now resolve to a
  real release rather than `main`.

## Installer checksum logic (how it works)

| Scenario | `VERIFY_CHECKSUM` | `SHA_URL` | Behavior |
|---|---|---|---|
| Release sdist available (default now) | 1 | Set (`releases/download/`) | Hard-fail if sidecar missing; verify strictly |
| Release sdist 404 → source archive fallback | 0 | Empty | Warn loudly; compute + display hash |
| `main` branch install | 0 | Empty | Warn loudly; compute + display hash |

Consequences:
- Release installs are checksum-verified (hard-fail on mismatch/missing).
- Source archive installs are honest about being unverified.
- The installer never silently installs an unverified release artifact.

## Published release checksums (for manual verification)

```
# From https://github.com/FeverDream-dev/Prometheus/releases/download/v0.1.0/SHA256SUMS
f8065326d8c3808fcb8db74dd28b1bd51f4a9270595388da137fdebf255b404d  prometheus_local_agent-0.1.0-py3-none-any.whl
84fa97575f43baa42dae4ae43fa8ff4bfaf6de59d7bb8d1b66dfac8f7a779ff7  prometheus_local_agent-0.1.0.tar.gz
```

```sh
# Manual verification a user can run after download:
sha256sum -c SHA256SUMS
```

## Exact commands for the next release (v0.1.1)

`v0.1.0` is shipped and must not be deleted or re-tagged. The next release is
`v0.1.1`, which has **not** been tagged yet. A human runs, when ready:

```sh
# 1. Bump version and push main.
$EDITOR pyproject.toml           # version = "0.1.1"
git add pyproject.toml
git commit -m "release: bump version to 0.1.1"
git push origin main

# 2. Tag and push (triggers release.yml).
git tag v0.1.1
git push origin v0.1.1

# 3. After release.yml completes, verify the installer finds the new assets:
PROMETHEUS_VERSION=v0.1.1 sh install.sh --dry-run
# Expected: would download .../releases/download/v0.1.1/prometheus_local_agent-0.1.1.tar.gz

# 4. Run the manual release smoke workflow:
#    Actions → install-release-smoke → Run workflow → v0.1.1
```
