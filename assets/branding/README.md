# PROMETHEUS branding assets

Source brand assets for the PROMETHEUS coding agent. Used by the TUI splash,
the `prometheus logo` command family, and the README/website visuals.

## Files

| File | Purpose |
|---|---|
| `feverducation.png` | Company logo (1024×1024 RGBA). Source for `prometheus logo generate`. |

## Usage

The logo is consumed in two ways:

1. **At runtime**: `prometheus_cli/logo.py` ships a brand-derived ASCII art
   (circular ring + central eye + name + tagline) that does NOT require this
   PNG. The PNG is only used when `prometheus logo generate --source ...` is
   invoked to regenerate a high-fidelity ASCII version of the source image.
2. **In docs/website**: referenced by `docs/IMAGE_PROMPTS.md` and the GitHub
   Pages site under the `website/` directory.

## Regenerating the ASCII module

```sh
prometheus logo generate \
  --source assets/branding/feverducation.png \
  --out src/prometheus_cli/generated_logo.py
```

Requires Pillow (`pip install pillow`). If Pillow is absent, the command
writes a static brand-fallback module so downstream code still imports
`GENERATED_LOGO` successfully.

## Licensing

This logo is the property of FeverDream.dev and is provided here for use
within the PROMETHEUS project only. The broader project license is in
[`LICENSE.md`](../../LICENSE.md) (dual community + commercial). Do not
re-distribute the logo outside the PROMETHEUS project without explicit
written permission.

## Adding new brand assets

When adding new assets:

- Keep source files small (under ~1 MB each — this directory is committed).
- Add a row to the table above.
- Do NOT commit generated ASCII modules — they live under
  `src/prometheus_cli/generated_logo.py` and are regenerated on demand.
- Do NOT commit binary blobs like `.psd`, `.ai`, `.sketch` — keep those in
  the design source-of-truth outside this repo.
