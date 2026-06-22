# Model Catalog

PROMETHEUS ships a versioned local model catalog at
`src/prometheus_cli/resources/model_catalog/catalog.yaml`. The catalog is
advisory — it helps BundleForge pick appropriate models, but all model names are
validated at runtime against the actual Ollama/provider registry before use.

## Catalog schema

Each entry:

```yaml
- id: qwen2.5-coder:7b
  provider: ollama
  family: qwen2.5-coder
  roles: [builder, controller]
  strengths: [code, tools, structured_output]
  limits: [text_only]
  approx_download_size_mb: 4700
  min_ram_gb: 8
  min_vram_gb: 6
  context_window: 32768
  license: apache-2.0
  commercial_safe: true
  source_url: https://ollama.com/library/qwen2.5-coder
  aliases: []
```

## Model families included (23 entries)

| Family | Models | Primary Use |
|---|---|---|
| qwen2.5-coder | 0.5b, 1.5b, 3b, 7b, 14b, 32b | Coding (tiny to max) |
| granite / granite-code | granite4.1:3b, granite-code:3b, 8b | Coding + structured output |
| vibethinker | Q2_K, Q4_K_M | Reasoning/review add-on |
| gemma3n | e2b, e4b | General/multilingual/planning |
| llama3 | llama3.2:3b | General-purpose |
| deepseek-coder | v2:16b | Stronger coding |
| devstral | 24b | Stronger coding (24 GB) |
| nomic-embed | nomic-embed-text | RAG embeddings |
| mxbai-embed | mxbai-embed-large | RAG embeddings |
| bge | bge-m3 | Multilingual embeddings |
| sdxl | sdxl-turbo | Image generation (non-commercial) |
| flux | FLUX.1-schnell | Image generation (Apache-2.0) |
| rembg | u2netp, silueta | Background removal |

## Commercial safety

Models marked `commercial_safe: false` (e.g. SDXL Turbo) are never included in
bundles that claim `commercial_safe: true`. The validation engine enforces this
deterministically.

## Runtime validation

The catalog is advisory. At runtime, PROMETHEUS verifies:
- `ollama list` (model actually installed)
- Provider health
- Disk free space
- RAM/VRAM availability
- License compliance

## API

```python
from prometheus_cli.bundleforge import load_catalog

catalog = load_catalog()
model = catalog.by_id("qwen2.5-coder:7b")
fits = catalog.fits_hardware(ram_gb=16, vram_gb=8)
recommended = catalog.recommend_for_role("builder", ram_gb=16, vram_gb=8)
```
