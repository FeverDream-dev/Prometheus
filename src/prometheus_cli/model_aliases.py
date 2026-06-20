from __future__ import annotations

MODEL_ALIASES: dict[str, str] = {
    "vibethinker-q2": "hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K",
    "vibethinker-q4": "hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q4_K_M",
    "vibethinker-q4-m": "hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q4_K_M",
}


def resolve_alias(name: str) -> str:
    return MODEL_ALIASES.get(name.strip().lower(), name)


def is_alias(name: str) -> bool:
    return name.strip().lower() in MODEL_ALIASES


__all__ = ["MODEL_ALIASES", "is_alias", "resolve_alias"]
