# BundleForge

BundleForge lets users create, adapt, validate, share, and install custom model
bundles for PROMETHEUS. Users describe what they want to build in natural
language, and BundleForge recommends a template, validates it against the model
catalog and hardware, and installs it.

## Quick start

```sh
# Natural-language recommendation
prometheus bundleforge recommend "I want to build a 2D game with sprites"

# Interactive wizard
prometheus bundleforge wizard

# Create from template
prometheus bundleforge create --template game-dev-lite --out .prometheus/bundles

# Validate a bundle
prometheus bundleforge validate game-dev-lite

# Install into ~/.prometheus/bundles/
prometheus bundleforge install game-dev-lite

# Export as shareable folder
prometheus bundleforge export game-dev-lite --out ./exported

# Search templates
prometheus bundleforge search "rag"
```

## Commands

| Command | Description |
|---|---|
| `recommend <request>` | Recommend a bundle from a natural-language request |
| `wizard` | Interactive bundle creation wizard (10 questions) |
| `create --template <id>` | Create a bundle from a template |
| `inspect <id\|path>` | Show full details of a bundle or template |
| `validate <id\|path>` | Validate schema, licenses, and hardware fit |
| `install <id\|path>` | Install a bundle into `~/.prometheus/bundles/` |
| `export <id\|path>` | Export as a shareable folder |
| `search <query>` | Search templates by keyword |

## Templates

| Template | Use Case | Min Hardware |
|---|---|---|
| `webapp-local-lite` | Web development, CPU-only | 8 GB RAM, 0 GB VRAM |
| `webapp-12gb-quality` | Web development, higher quality | 16 GB RAM, 10 GB VRAM |
| `game-dev-lite` | Game development with sprites | 8 GB RAM, 6 GB VRAM |
| `game-dev-assetforge` | Game dev with full asset pipeline | 16 GB RAM, 8 GB VRAM |
| `whatsapp-mcp-assistant` | WhatsApp/chat automation via MCP | 8 GB RAM, 0 GB VRAM |
| `rag-docs-local` | RAG over local documents | 8 GB RAM, 0 GB VRAM |
| `qa-browser-vision` | Browser QA with vision | 16 GB RAM, 6 GB VRAM |
| `assetforge-icon-factory` | Image/icon generation | 8 GB RAM, 8 GB VRAM |
| `cpu-only-emergency` | Minimal CPU-only fallback | 4 GB RAM, 0 GB VRAM |
| `cloud-hybrid-max` | Maximum quality, hybrid | 32 GB RAM, 20 GB VRAM |

## How recommendation works

1. User request is matched against keyword groups (game, rag, mcp, cpu, etc.)
2. Best-matching use case maps to a template
3. Hardware is checked — if the template doesn't fit, a lighter alternative is selected
4. License compatibility is verified (commercial_safe enforcement)
5. The LLM cannot create unvalidated YAML — BundleForge validates deterministically

## Bundle format

```yaml
id: game-dev-lite
name: Game Dev Lite
description: Local game development bundle
version: "0.1.0"
use_case: game_development
roles:
  envoy:
    model: gemma3n:e2b
    provider: ollama
  builder:
    model: qwen2.5-coder:7b
    provider: ollama
  critic:
    model: granite-code:3b
    provider: ollama
optional:
  image_generator: black-forest-labs/FLUX.1-schnell
permissions:
  network: ask
  browser: allow
  assets: allow
  external_directory: deny
requirements:
  min_ram_gb: 8
  min_vram_gb: 6
  min_disk_gb: 30
commercial_safe: true
license_notes: "All models Apache-2.0 or Gemma-Terms."
```

When installed, ForgeBundle is converted to BundleV2 format and placed in
`~/.prometheus/bundles/` so `prometheus use <id>` can activate it.
