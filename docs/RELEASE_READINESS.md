# PROMETHEUS release readiness

**Generated:** 2026-06-21T03:35:42Z by `scripts/release_smoke.sh`

**Result:** 17 passed / 0 failed

| Check | Status | Detail |
|---|---|---|
| compileall | PASS |  |
| pytest | PASS | 648 passed, 8 skipped in 29.55s |
| ruff check | PASS | All checks passed! |
| prometheus --help | PASS | ╰──────────────────────────────────────────────────────────────────────────────╯ |
| prometheus doctor | PASS | Recommended package: spark-cpu-8gb (Spark — CPU / 8 GB) |
| sandbox test (19/19) | PASS | report -> tests/fixtures/sandbox_target/.prometheus/sandbox-test-report.json |
| bash -n install.sh | PASS |  |
| bash -n public/install.sh | PASS |  |
| install.sh --dry-run | PASS | exit 0 |
| no placeholder URLs | PASS | clean |
| git status | PASS | 14 modified files (expected during dev) |
| wheel build | PASS | dist/prometheus_local_agent-0.1.0-py3-none-any.whl |
| sdist build | PASS | dist/prometheus_local_agent-0.1.0.tar.gz |
| checksums | PASS | SHA256SUMS + sidecars |
| SBOM (CycloneDX) | PASS | dist/sbom.cyclonedx.json |
| clean wheel install | PASS | pip install succeeded |
| installed CLI --help | PASS | exit 0 |

## How to reproduce

```sh
bash scripts/release_smoke.sh --build
```

## Next human step

```sh
git tag v0.1.0
git push origin v0.1.0
```

This triggers `.github/workflows/release.yml` which builds wheel + sdist +
SHA256SUMS + SBOM + release manifest, creates the GitHub Release, and runs the
smoke job.
