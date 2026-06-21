from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Any

from .background_removal import is_available as rembg_available, remove_background
from .manifest import AssetManifest, VALID_KINDS, VALID_SIZES, can_use_commercially, write_manifest
from .questions import ask_missing, build_prompt


IMAGE_TESTS_ENABLED = "PROMETHEUS_RUN_IMAGE_TESTS"


def is_image_gen_enabled() -> bool:
    return os.environ.get(IMAGE_TESTS_ENABLED, "") == "1"


def generate(
    name: str,
    kind: str = "icon",
    size: str = "512x512",
    transparent: bool = False,
    model: str = "stabilityai/sdxl-turbo",
    style: str = "",
    colors: str = "",
    seed: int = 0,
    steps: int = 4,
    output_dir: Path | None = None,
    answers: dict[str, str] | None = None,
    prompt_fn=None,
) -> dict[str, Any]:
    if kind not in VALID_KINDS:
        return {"error": f"invalid kind '{kind}'; valid: {', '.join(VALID_KINDS)}"}
    if size not in VALID_SIZES:
        return {"error": f"invalid size '{size}'; valid: {', '.join(VALID_SIZES)}"}
    if seed == 0:
        seed = random.randint(1, 2**31 - 1)

    resolved_answers = ask_missing(
        existing={**(answers or {}),
                  "kind": kind, "size": size,
                  "transparent": "yes" if transparent else "no"},
        prompt_fn=prompt_fn,
    )

    prompt, negative_prompt = build_prompt(resolved_answers, name)
    commercial = resolved_answers.get("commercial", "no")

    manifest = AssetManifest(
        name=name, kind=kind, model=model,
        prompt=prompt, negative_prompt=negative_prompt,
        seed=seed, size=size, steps=steps,
        transparent=transparent,
        commercial_use="allowed" if commercial == "yes" else "restricted",
    )

    out_dir = output_dir or Path("assets/generated")
    asset_dir = out_dir / name

    result: dict[str, Any] = {
        "name": name,
        "kind": kind,
        "model": model,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": seed,
        "manifest": manifest.to_dict(),
        "answers_warnings": resolved_answers.warnings,
        "image_generated": False,
        "transparent_processed": False,
    }

    if is_image_gen_enabled():
        try:
            img_bytes = _run_pipeline(model, prompt, negative_prompt, size, seed, steps)
            asset_dir.mkdir(parents=True, exist_ok=True)
            (asset_dir / "source.png").write_bytes(img_bytes)
            manifest.files.append("source.png")
            result["image_generated"] = True
            if transparent:
                rb_result = remove_background(
                    asset_dir / "source.png",
                    asset_dir / "transparent.png",
                )
                if rb_result["success"]:
                    manifest.background_removal_model = "rembg"
                    manifest.files.append("transparent.png")
                    manifest.post_processing.append("background_removal: rembg")
                    result["transparent_processed"] = True
                    result["background_removal"] = rb_result
                else:
                    result["background_removal"] = rb_result
                    manifest.warnings.append("background removal failed: " + rb_result.get("error", "?"))
            for res in ("512", "256", "128"):
                rp = asset_dir / f"web-{res}.png"
                rp.write_bytes(img_bytes)
                manifest.files.append(f"web-{res}.png")
        except Exception as exc:
            result["image_error"] = str(exc)
            manifest.warnings.append(f"image generation failed: {exc}")
    else:
        result["skip_reason"] = (
            f"image generation disabled; set {IMAGE_TESTS_ENABLED}=1 to run. "
            f"Manifest and provenance written; no image files generated."
        )

    manifest_path, readme_path = write_manifest(asset_dir, manifest)
    result["manifest_path"] = str(manifest_path)
    result["readme_path"] = str(readme_path)
    result["asset_dir"] = str(asset_dir)
    result["can_use_commercially"] = can_use_commercially(model)
    return result


def _run_pipeline(model: str, prompt: str, negative: str, size: str,
                  seed: int, steps: int) -> bytes:
    from diffusers import AutoPipelineForText2Image
    import torch
    width, height = (int(x) for x in size.split("x"))
    pipe = AutoPipelineForText2Image.from_pretrained(
        model, torch_dtype=torch.float16, variant="fp16",
    )
    if torch.cuda.is_available():
        pipe = pipe.to("cuda")
    img = pipe(
        prompt=prompt, negative_prompt=negative,
        width=width, height=height, num_inference_steps=steps,
        generator=torch.Generator().manual_seed(seed),
    ).images[0]
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def doctor() -> dict[str, Any]:
    return {
        "rembg_available": rembg_available(),
        "diffusers_available": _check_diffusers(),
        "torch_available": _check_torch(),
        "image_tests_enabled": is_image_gen_enabled(),
        "env_var": IMAGE_TESTS_ENABLED,
    }


def _check_diffusers() -> bool:
    try:
        import diffusers  # noqa
        return True
    except ImportError:
        return False


def _check_torch() -> bool:
    try:
        import torch  # noqa
        return True
    except ImportError:
        return False


def setup() -> dict[str, Any]:
    instructions = []
    if not _check_torch():
        instructions.append("pip install torch")
    if not _check_diffusers():
        instructions.append("pip install diffusers transformers accelerate")
    if not rembg_available():
        instructions.append("pip install rembg  # MIT-licensed background removal")
    if instructions:
        return {"ready": False, "commands": instructions}
    return {"ready": True, "commands": []}


__all__ = ["generate", "doctor", "setup", "is_image_gen_enabled"]
