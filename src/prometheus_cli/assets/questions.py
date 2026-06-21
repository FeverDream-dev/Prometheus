from __future__ import annotations

from dataclasses import dataclass, field

from .manifest import VALID_KINDS, VALID_SIZES

QUESTIONS = [
    {"id": "usage", "text": "Where will the asset be used?", "default": "web"},
    {"id": "kind", "text": "What kind of asset is it: icon, hero, illustration, logo, dashboard, mockup, background?",
     "default": "icon", "valid": VALID_KINDS},
    {"id": "style", "text": "What style should it follow?", "default": "flat, modern"},
    {"id": "colors", "text": "What colors should it use?", "default": ""},
    {"id": "transparent", "text": "Should it have transparency?", "default": "no", "valid": ("yes", "no")},
    {"id": "size", "text": "What size/aspect ratio?", "default": "512x512", "valid": VALID_SIZES},
    {"id": "text", "text": "Should text be included?", "default": "no", "valid": ("yes", "no")},
    {"id": "commercial", "text": "Is it for commercial use?", "default": "no", "valid": ("yes", "no")},
    {"id": "format", "text": "Raster PNG/WebP only, or also SVG vector-style?", "default": "png", "valid": ("png", "webp", "svg")},
]


@dataclass
class AssetAnswers:
    answers: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def get(self, key: str, default: str = "") -> str:
        return self.answers.get(key, default)


def ask_missing(existing: dict[str, str] | None = None,
                 prompt_fn=None) -> AssetAnswers:
    """Ask only the questions whose answers are missing from ``existing``.

    ``prompt_fn`` is a callable(text, default) -> str for interactive use.
    In non-interactive mode (prompt_fn=None), all defaults are used.
    """
    existing = existing or {}
    result = AssetAnswers(answers=dict(existing))

    for q in QUESTIONS:
        qid = q["id"]
        if qid in existing and existing[qid]:
            raw = existing[qid]
            if "valid" in q and raw not in q["valid"]:
                result.warnings.append(f"'{raw}' is not a valid option for {qid}; using default '{q['default']}'")
                raw = q["default"]
            result.answers[qid] = raw
            continue
        if prompt_fn is not None:
            raw = prompt_fn(q["text"], q["default"])
        else:
            raw = q["default"]
        if "valid" in q and raw not in q["valid"]:
            result.warnings.append(f"'{raw}' is not a valid option for {qid}; using default '{q['default']}'")
            raw = q["default"]
        result.answers[qid] = raw

    if result.get("text") == "yes":
        result.warnings.append(
            "Image models are bad at legible text; consider rendering text in HTML/SVG instead."
        )
    if result.get("commercial") == "yes":
        result.warnings.append(
            "Commercial use requires checking the model's license terms."
        )
    return result


def build_prompt(answers: AssetAnswers, name: str) -> tuple[str, str]:
    kind = answers.get("kind", "icon")
    style = answers.get("style", "flat, modern")
    colors = answers.get("colors", "")
    text_ok = answers.get("text", "no") == "yes"

    parts = [f"{kind} named {name}"]
    if style:
        parts.append(f"style: {style}")
    if colors:
        parts.append(f"colors: {colors}")
    if not text_ok:
        parts.append("no text")
    prompt = ", ".join(parts) + f", high quality, {kind} for web use"

    negative = "blurry, low quality, distorted, watermark, signature, extra digits, deformed"
    if not text_ok:
        negative += ", text, letters, words"
    return prompt, negative


__all__ = ["AssetAnswers", "QUESTIONS", "ask_missing", "build_prompt"]
