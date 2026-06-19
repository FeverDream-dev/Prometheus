# Installation design

## Public entry points

Eventually provide:

- POSIX: `curl ... | sh` with a visible two-stage bootstrap and checksums;
- Windows/WSL: PowerShell bootstrap plus WSL instructions;
- Homebrew, `pipx`, standalone signed binaries, and container image;
- offline bundle with manifest and checksums.

The one-liner must remain a small auditable bootstrap. It downloads a versioned installer, verifies
its signature/hash, then runs it. A single opaque "huge script" is harder to audit and maintain.
The full installer may be comprehensive while the one-liner stays safe.

## Detection order

1. OS/architecture and WSL.
2. RAM, available disk, CPU instruction support.
3. NVIDIA CUDA, AMD ROCm/Vulkan, Intel Vulkan/oneAPI, Apple Metal.
4. Existing Ollama/llama.cpp/LM Studio/PowerInfer services.
5. Network availability and proxy.
6. Candidate bundles with predicted weights, KV cache, and headroom.
7. User confirmation of runtime, models, download sizes, licenses, and telemetry.
8. Download with resume, hash verification, health check, inference smoke test.
9. Sandbox escape test and first project wizard.

## PowerInfer

Offer only behind `--experimental-powerinfer`. Detect its supported platform/backend and model
format. Run a benchmark against the Ollama/default path and keep it only when it succeeds and
provides a measurable benefit. Never claim it generically improves tokens per second.

## Uninstall

Remove PROMETHEUS binaries/configuration while separately asking whether to preserve model caches,
sessions, plugins, and projects. Never remove shared Ollama models automatically.

