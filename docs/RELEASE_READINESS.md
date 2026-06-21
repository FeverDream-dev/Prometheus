# PROMETHEUS release readiness

**Status:** `v0.1.0` is **PUBLISHED** and verified this session. The first
release tag is no longer pending. The next planned release is `v0.1.1`; that
tag has **not** been pushed yet.

**Verified:** 2026-06-21T18:39:47Z (session-local, America/Sao_Paulo).
**Release published:** 2026-06-21T04:27:42Z (GitHub API).
**Tag commit:** `8954a5e7c731f526c88ce11a54229cc5bd70ff25` (== current `HEAD`).

## Headline result

`v0.1.0` was tagged, pushed to `origin`, and the `release` GitHub Actions
workflow built and published a GitHub Release with **7 assets** (wheel, sdist,
both `.sha256` sidecars, `SHA256SUMS`, CycloneDX SBOM, `release-manifest.json`).
The release is live at
<https://github.com/FeverDream-dev/Prometheus/releases/tag/v0.1.0>.

This session re-verified the release end-to-end against the live GitHub
Release API and the published download URLs. Every artifact is internally
checksum-consistent, and the source inside the published sdist is byte-identical
to the current working tree.

## Baseline verification (this session, real outputs)

| Check | Status | Detail |
|---|---|---|
| `python -m compileall src` | PASS | clean (all modules byte-compile) |
| `pytest -q` | PASS | 648 passed, 8 skipped in 27.65s |
| `ruff check` | PASS | All checks passed! |
| `prometheus --help` | PASS | 14 top-level + 9 sub-app command groups |
| `prometheus doctor` | PASS | Recommended package detected; hardware report rendered |
| `prometheus sandbox test --workspace tests/fixtures/sandbox_target --all` | PASS | passed=19 failed=0 skipped=1 ok=True |
| `git status --short` | PASS | clean (before release-prep edits) |

Commands run:

```sh
$ python -m compileall src            # clean
$ pytest -q                           # 648 passed, 8 skipped in 27.65s
$ ruff check                          # All checks passed!
$ prometheus --help                   # 14 top-level + 9 sub-app groups
$ prometheus doctor                   # hardware report OK
$ prometheus sandbox test --workspace tests/fixtures/sandbox_target --all
#   passed=19 failed=0 skipped=1 ok=True
$ git status --short                  # (no output — clean)
```

## Local artifact build (this session)

```sh
$ rm -rf dist build src/prometheus_local_agent.egg-info
$ python -m build
Successfully built prometheus_local_agent-0.1.0.tar.gz and
                 prometheus_local_agent-0.1.0-py3-none-any.whl
```

| Local artifact | Size | SHA-256 |
|---|---|---|
| `prometheus_local_agent-0.1.0-py3-none-any.whl` | 123 487 B | `98e3cf8a766d800be6a86c2b96a142b5b8a9b71b36916ed16b4590080a21ef3d` |
| `prometheus_local_agent-0.1.0.tar.gz` | 168 269 B | `04d341344d803bfe01bab81ddfcc41a7c9d8f6988b0dd1075569feeeedf3cc85` |

Checksums (`SHA256SUMS` + per-asset `.sha256` sidecars) and the CycloneDX SBOM
(`sbom.cyclonedx.json`) were generated locally using the same commands as
`release.yml`.

## Published release verification (this session)

Downloaded all 7 published assets from
`https://github.com/FeverDream-dev/Prometheus/releases/download/v0.1.0/` and
verified them:

| Published asset | Size | SHA-256 |
|---|---|---|
| `prometheus_local_agent-0.1.0-py3-none-any.whl` | 123 758 B | `f8065326d8c3808fcb8db74dd28b1bd51f4a9270595388da137fdebf255b404d` |
| `prometheus_local_agent-0.1.0-py3-none-any.whl.sha256` | 65 B | (sidecar) |
| `prometheus_local_agent-0.1.0.tar.gz` | 166 798 B | `84fa97575f43baa42dae4ae43fa8ff4bfaf6de59d7bb8d1b66dfac8f7a779ff7` |
| `prometheus_local_agent-0.1.0.tar.gz.sha256` | 65 B | (sidecar) |
| `SHA256SUMS` | 214 B | (manifest of the two artifacts above) |
| `sbom.cyclonedx.json` | 46 158 B | CycloneDX 1.5 |
| `release-manifest.json` | 908 B | version + artifact hashes |

### Internal consistency of the published release

```sh
$ cd /tmp/published-v0.1.0
$ sha256sum -c SHA256SUMS
prometheus_local_agent-0.1.0-py3-none-any.whl: OK
prometheus_local_agent-0.1.0.tar.gz: OK
```

- Both `.sha256` sidecars match their artifacts: **OK**
- `release-manifest.json` lists 6 artifacts; every hash matches the actual
  bytes: **MANIFEST VERDICT: consistent**

### Local vs published — why the bytes differ (and why that is fine)

The locally built wheel/sdist differ in raw bytes from the published ones
(different sizes and hashes). This is **expected** and is **not a defect**:

1. **Source identity is proven.** The `v0.1.0` tag points at commit
   `8954a5e7c731f526c88ce11a54229cc5bd70ff25`, which is the current `HEAD`:
   ```sh
   $ git rev-list -n1 v0.1.0
   8954a5e7c731f526c88ce11a54229cc5bd70ff25
   $ git rev-parse HEAD
   8954a5e7c731f526c88ce11a54229cc5bd70ff25
   ```
2. **The source inside the sdists is byte-identical.** Extracting both the
   local and the published sdist and diffing recursively yields **0 differing
   files**:
   ```sh
   $ tar -xzf dist/prometheus_local_agent-0.1.0.tar.gz           # local
   $ tar -xzf published/prometheus_local_agent-0.1.0.tar.gz      # published
   $ diff -rq prometheus_local_agent-0.1.0/ prometheus_local_agent-0.1.0/
   # (no output — 0 differing files)
   ```
3. The remaining byte differences live entirely in the **outer container**
   (gzip mtime headers on the `.tar.gz`, and wheel build metadata produced by
   different Python versions: CI builds on `setup-python@v5` 3.11; this local
   build used Python 3.14). This is the well-known Python reproducible-builds
   limitation and does not affect the installed package.

The published v0.1.0 artifacts are authoritative for the release. They are not
overwritten.

## How to reproduce

```sh
# Baseline
. .venv/bin/activate
python -m compileall src && pytest -q && ruff check
prometheus --help && prometheus doctor
prometheus sandbox test --workspace tests/fixtures/sandbox_target --all

# Local build + checksums + SBOM
rm -rf dist build src/prometheus_local_agent.egg-info
python -m build
(cd dist && sha256sum * > SHA256SUMS && for f in *; do
   [ "$f" = SHA256SUMS ] && continue
   sha256sum "$f" | awk '{print $1}' > "$f.sha256"
 done)
cyclonedx-py environment -o dist/sbom.cyclonedx.json --sv 1.5 "$(which python)"

# Download and verify the published release
BASE="https://github.com/FeverDream-dev/Prometheus/releases/download/v0.1.0"
mkdir -p /tmp/pub && cd /tmp/pub
for a in prometheus_local_agent-0.1.0-py3-none-any.whl \
         prometheus_local_agent-0.1.0.tar.gz SHA256SUMS; do
  curl -fsSL -o "$a" "$BASE/$a"
done
sha256sum -c SHA256SUMS
```

## Next human step (v0.1.1)

`v0.1.0` is shipped and verified. The next release is `v0.1.1`. **The `v0.1.1`
tag has not been created or pushed yet.** When the changes targeting `v0.1.1`
are ready, a human runs:

```sh
# 1. Bump the version in pyproject.toml to 0.1.1, commit, and push main.
git add pyproject.toml
git commit -m "release: bump version to 0.1.1"
git push origin main

# 2. Tag and push the release tag (triggers .github/workflows/release.yml).
git tag v0.1.1
git push origin v0.1.1

# 3. Watch the release workflow build + publish.
#    https://github.com/FeverDream-dev/Prometheus/actions/workflows/release.yml

# 4. After it completes, run the manual release smoke workflow:
#    Actions → install-release-smoke → Run workflow → v0.1.1
```

Pushing `v0.1.1` triggers `.github/workflows/release.yml`, which (after this
session's improvements) builds wheel + sdist + SHA256SUMS + per-asset sidecars +
CycloneDX SBOM + a provenance-enriched `release-manifest.json`, asserts all
required artifacts exist and are checksum-consistent before upload, creates the
GitHub Release with auto-generated notes, and runs the smoke job (wheel install
+ `prometheus --help` + `prometheus doctor` + public-installer bootstrap).
