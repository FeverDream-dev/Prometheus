from __future__ import annotations

from .models import AutonomyMode, Risk, Settings


ALWAYS_DENY_WITHOUT_EXPLICIT_APPROVAL = {Risk.DESTRUCTIVE}


def requires_approval(settings: Settings, risk: Risk) -> bool:
    if risk in ALWAYS_DENY_WITHOUT_EXPLICIT_APPROVAL:
        return True
    if settings.mode == AutonomyMode.COPILOT:
        return risk != Risk.READ
    if settings.mode == AutonomyMode.PILOT:
        return risk in {Risk.EXECUTE, Risk.NETWORK}
    return False


def mode_description(mode: AutonomyMode) -> str:
    return {
        AutonomyMode.COPILOT: "Suggestive: approves writes and commands.",
        AutonomyMode.PILOT: "Balanced: edits automatically; approves risky execution/network.",
        AutonomyMode.ASTRONAUT: "Autonomous: continues within declared scope and hard guardrails.",
    }[mode]

