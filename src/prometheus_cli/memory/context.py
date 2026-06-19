from __future__ import annotations

from dataclasses import dataclass, field

AVAILABLE_TOOLS = (
    "list_files(pattern), read_file(path), write_file(path, content), "
    "run_command(command: string array, timeout), git_checkpoint(message), "
    "git_diff(path), git_log(limit)"
)

DEFAULT_CHAR_BUDGET = 24000


@dataclass
class ContextSection:
    name: str
    content: str
    provenance: str = ""
    protected: bool = False


@dataclass
class ContextPacket:
    sections: list[ContextSection] = field(default_factory=list)

    def to_messages(self, system_contract: str) -> list[dict]:
        body = "\n\n".join(f"## {s.name}\n{s.content}".rstrip() for s in self.sections)
        body += "\n\n## Expected output\nReturn only an AgentTurn JSON object matching the provided schema."
        return [
            {"role": "system", "content": system_contract},
            {"role": "user", "content": body},
        ]

    @property
    def chars(self) -> int:
        return sum(len(s.content) for s in self.sections)

    def names(self) -> list[str]:
        return [s.name for s in self.sections]


def _trim_to_budget(sections: list[ContextSection], budget: int) -> list[ContextSection]:
    protected = [s for s in sections if s.protected]
    flexible = [s for s in sections if not s.protected]
    total = sum(len(s.content) for s in sections)
    if total <= budget:
        return sections
    while flexible and total > budget:
        cut = flexible.pop(0)
        total -= len(cut.content)
    return protected + flexible


def build_context_packet(
    store,
    seat,
    micro_step=None,
    *,
    char_budget: int = DEFAULT_CHAR_BUDGET,
) -> ContextPacket:
    sections: list[ContextSection] = []
    intent = store.get_intent()
    if intent:
        sections.append(ContextSection(
            name="Immutable intent",
            content=intent.objective
            + ("\n\nSuccess criteria:\n- " + "\n- ".join(intent.success_criteria) if intent.success_criteria else "")
            + ("\n\nConstraints:\n- " + "\n- ".join(c.statement for c in intent.constraints if c.active) if intent.constraints else ""),
            provenance="layer-0 intent", protected=True,
        ))
    working = store.get_working_memory()
    if working:
        sections.append(ContextSection(
            name="Working memory (<=1024 words)",
            content=working, provenance="layer-1 working memory", protected=True,
        ))
    active = micro_step or store.active_micro_step()
    if active:
        sections.append(ContextSection(
            name="Active micro-step",
            content=f"{active.id}: {active.description}\nacceptance: {active.acceptance}",
            provenance="layer-2 task graph", protected=True,
        ))
    facts = [f for f in store.list_facts() if f.is_certain and not f.superseded_by]
    if facts:
        sections.append(ContextSection(
            name="Verified facts",
            content="\n".join(f"- {f.summary} [{f.id}]" for f in facts[-10:]),
            provenance="layer-2 facts",
        ))
    decisions = store.list_decisions()
    if decisions:
        sections.append(ContextSection(
            name="Recent decisions",
            content="\n".join(f"- {d.choice}" for d in decisions[-6:]),
            provenance="layer-2 decisions",
        ))
    sections.append(ContextSection(
        name="Available tools", content=AVAILABLE_TOOLS, provenance="tool broker",
    ))
    return ContextPacket(sections=_trim_to_budget(sections, char_budget))


__all__ = [
    "AVAILABLE_TOOLS",
    "ContextPacket",
    "ContextSection",
    "DEFAULT_CHAR_BUDGET",
    "build_context_packet",
]
