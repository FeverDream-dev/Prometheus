from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

from ..redaction import redact
from .schemas import (
    SCHEMA_VERSION,
    Decision,
    Fact,
    FailureSignature,
    Handoff,
    Intent,
    MAX_WORKING_WORDS,
    MemoryRevision,
    TaskNode,
    WorkingMemoryStatus,
)

_SCHEMA_FILE = "schema-version"
_GITIGNORE_MARKER = ".prometheus/"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class WorkingMemoryTooLarge(ValueError):
    pass


class ProjectMemoryStore:
    def __init__(self, workspace: Path, *, ensure: bool = True):
        self.workspace = Path(workspace).resolve()
        self.root = self.workspace / ".prometheus"
        self.memory_dir = self.root / "memory"
        self.state_dir = self.root / "state"
        self.revisions_dir = self.memory_dir / "revisions"
        self.handoffs_dir = self.memory_dir / "handoffs"
        self.working_path = self.memory_dir / "working.md"
        self.intent_path = self.memory_dir / "intent.json"
        self.tasks_path = self.memory_dir / "tasks.json"
        self.decisions_path = self.memory_dir / "decisions.jsonl"
        self.facts_path = self.memory_dir / "facts.jsonl"
        self.failures_path = self.memory_dir / "failures.jsonl"
        self.revisions_index = self.revisions_dir / "index.json"
        if ensure:
            self._ensure()

    def _ensure(self) -> None:
        for d in (self.memory_dir, self.state_dir, self.revisions_dir, self.handoffs_dir):
            d.mkdir(parents=True, exist_ok=True)
        sv = self.state_dir / _SCHEMA_FILE
        if not sv.exists():
            sv.write_text(f"{SCHEMA_VERSION}\n", encoding="utf-8")
        self._ensure_gitignored()

    def _ensure_gitignored(self) -> None:
        ignore = self.workspace / ".gitignore"
        try:
            existing = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
        except OSError:
            existing = ""
        lines = {ln.strip() for ln in existing.splitlines() if ln.strip()}
        if _GITIGNORE_MARKER not in lines and f"/{_GITIGNORE_MARKER}" not in lines:
            entry = existing + ("" if existing.endswith("\n") or not existing else "\n") + _GITIGNORE_MARKER + "\n"
            self._atomic_write(ignore, entry)

    def _atomic_write(self, path: Path, data: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)

    @property
    def schema_version(self) -> int:
        try:
            return int((self.state_dir / _SCHEMA_FILE).read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return SCHEMA_VERSION

    def set_intent(self, intent: Intent) -> None:
        intent.updated_at = _now()
        if not intent.created_at:
            intent.created_at = intent.updated_at
        self._atomic_write(self.intent_path, intent.model_dump_json(indent=2))

    def get_intent(self) -> Intent | None:
        if not self.intent_path.exists():
            return None
        return Intent.model_validate_json(self.intent_path.read_text(encoding="utf-8"))

    def get_tasks(self) -> list[TaskNode]:
        if not self.tasks_path.exists():
            return []
        return [TaskNode.model_validate(t) for t in json.loads(self.tasks_path.read_text(encoding="utf-8"))]

    def upsert_task(self, task: TaskNode) -> None:
        tasks = {t.id: t for t in self.get_tasks()}
        tasks[task.id] = task
        self._atomic_write(self.tasks_path, json.dumps([t.model_dump(mode="json") for t in tasks.values()], indent=2))

    def active_micro_step(self) -> TaskNode | None:
        for t in self.get_tasks():
            if t.status == "active":
                return t
        return None

    def append_decision(self, decision: Decision) -> None:
        if not decision.created_at:
            decision.created_at = _now()
        with self.decisions_path.open("a", encoding="utf-8") as fh:
            fh.write(decision.model_dump_json() + "\n")

    def list_decisions(self) -> list[Decision]:
        if not self.decisions_path.exists():
            return []
        return [Decision.model_validate_json(line) for line in self.decisions_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def record_fact(self, fact: Fact) -> None:
        fact.summary = redact(fact.summary)
        if not fact.created_at:
            fact.created_at = _now()
        with self.facts_path.open("a", encoding="utf-8") as fh:
            fh.write(fact.model_dump_json() + "\n")

    def list_facts(self) -> list[Fact]:
        if not self.facts_path.exists():
            return []
        return [Fact.model_validate_json(line) for line in self.facts_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def why(self, fact_id: str) -> Fact | None:
        for f in self.list_facts():
            if f.id == fact_id:
                return f
        return None

    def record_failure(self, failure: FailureSignature) -> None:
        existing = {f.signature: f for f in self.list_failures()}
        if failure.signature in existing:
            prev = existing[failure.signature]
            prev.count += 1
            prev.last_seen = _now()
            failure = prev
        else:
            failure.count = max(failure.count, 1)
            if not failure.last_seen:
                failure.last_seen = _now()
        all_failures = [f for s, f in existing.items() if s != failure.signature] + [failure]
        lines = "\n".join(f.model_dump_json() for f in all_failures) + ("\n" if all_failures else "")
        self._atomic_write(self.failures_path, lines)

    def list_failures(self) -> list[FailureSignature]:
        if not self.failures_path.exists():
            return []
        return [FailureSignature.model_validate_json(line) for line in self.failures_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def write_handoff(self, handoff: Handoff) -> Path:
        if not handoff.created_at:
            handoff.created_at = _now()
        path = self.handoffs_dir / f"{handoff.from_seat}-to-{handoff.to_seat}-{_checksum(handoff.model_dump_json())}.json"
        self._atomic_write(path, handoff.model_dump_json(indent=2))
        return path

    def set_working_memory(self, markdown: str, *, force: bool = False) -> MemoryRevision:
        words = _word_count(markdown)
        if words > MAX_WORKING_WORDS and not force:
            raise WorkingMemoryTooLarge(
                f"working memory is {words} words; limit is {MAX_WORKING_WORDS}"
            )
        revisions = self._read_revisions()
        version = (revisions[-1].version + 1) if revisions else 1
        checksum = _checksum(markdown)
        rev_path = self.revisions_dir / f"working-v{version}-{checksum}.md"
        self._atomic_write(rev_path, markdown)
        revision = MemoryRevision(version=version, checksum=checksum, word_count=words, created_at=_now(), path=rev_path.name)
        revisions.append(revision)
        self._atomic_write(self.revisions_index, json.dumps([r.model_dump(mode="json") for r in revisions], indent=2))
        self._atomic_write(self.working_path, markdown)
        return revision

    def get_working_memory(self) -> str:
        return self.working_path.read_text(encoding="utf-8") if self.working_path.exists() else ""

    def status(self) -> WorkingMemoryStatus:
        revisions = self._read_revisions()
        text = self.get_working_memory()
        if not text:
            return WorkingMemoryStatus(ok=False, word_count=0, version=0, checksum="", error="no working memory yet")
        recovered = False
        actual = _checksum(text)
        last = revisions[-1] if revisions else None
        if last is None or last.checksum != actual:
            fixed = self.recover()
            return WorkingMemoryStatus(
                ok=fixed.ok, word_count=fixed.word_count, version=fixed.version,
                checksum=fixed.checksum, last_updated=fixed.last_updated, recovered=True,
                error="" if fixed.ok else "corrupt; recovered last revision",
            )
        return WorkingMemoryStatus(
            ok=True, word_count=last.word_count, version=last.version,
            checksum=last.checksum, last_updated=last.created_at, recovered=recovered,
        )

    def recover(self) -> WorkingMemoryStatus:
        revisions = self._read_revisions()
        for rev in reversed(revisions):
            rev_path = self.revisions_dir / rev.path
            if rev_path.exists():
                content = rev_path.read_text(encoding="utf-8")
                if _checksum(content) == rev.checksum:
                    self._atomic_write(self.working_path, content)
                    return WorkingMemoryStatus(
                        ok=True, word_count=rev.word_count, version=rev.version,
                        checksum=rev.checksum, last_updated=rev.created_at, recovered=True,
                    )
        self.working_path.unlink(missing_ok=True)
        return WorkingMemoryStatus(ok=False, word_count=0, version=0, checksum="", error="no valid revision to recover")

    def rebuild(self) -> WorkingMemoryStatus:
        intent = self.get_intent()
        tasks = self.get_tasks()
        decisions = self.list_decisions()
        facts = [f for f in self.list_facts() if f.is_certain and not f.superseded_by]
        active = self.active_micro_step() or (tasks[0] if tasks else None)
        self.set_working_memory(self._draft_working(intent, tasks, decisions, facts, active))
        return self.status()

    def _draft_working(self, intent, tasks, decisions, facts, active) -> str:
        lines = ["# Working memory", ""]
        if intent:
            lines += ["## Objective", intent.objective, ""]
            if intent.success_criteria:
                lines += ["## Success criteria"]
                lines += [f"- {c}" for c in intent.success_criteria]
                lines.append("")
            if intent.constraints:
                lines += ["## Active constraints"]
                lines += [f"- {c.statement}" for c in intent.constraints if c.active]
                lines.append("")
        if active:
            lines += ["## Active micro-step", f"{active.id}: {active.description}", f"acceptance: {active.acceptance}", ""]
        if facts:
            lines += ["## Verified facts"]
            lines += [f"- {f.summary} ({f.confidence.value}, {f.provenance.source})" for f in facts[-12:]]
            lines.append("")
        if decisions:
            lines += ["## Recent decisions"]
            lines += [f"- {d.choice}" for d in decisions[-6:]]
            lines.append("")
        lines += ["## Next", "continue the active micro-step", ""]
        return "\n".join(lines)

    def _read_revisions(self) -> list[MemoryRevision]:
        if not self.revisions_index.exists():
            return []
        return [MemoryRevision.model_validate(r) for r in json.loads(self.revisions_index.read_text(encoding="utf-8"))]

    def list_revisions(self) -> list[MemoryRevision]:
        return self._read_revisions()

    def export(self, dest: Path) -> Path:
        export = {
            "schema_version": SCHEMA_VERSION,
            "exported_at": _now(),
            "intent": redact(self.intent_path.read_text(encoding="utf-8")) if self.intent_path.exists() else None,
            "tasks": json.loads(self.tasks_path.read_text(encoding="utf-8")) if self.tasks_path.exists() else [],
            "decisions": [d.model_dump(mode="json") for d in self.list_decisions()],
            "working_memory": redact(self.get_working_memory()),
        }
        dump = json.dumps(export, indent=2)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(dest, redact(dump))
        return dest

    def reset(self) -> None:
        for p in (self.working_path, self.intent_path, self.tasks_path, self.decisions_path,
                  self.facts_path, self.failures_path, self.revisions_index):
            p.unlink(missing_ok=True)
        for rev in self._read_revisions():
            (self.revisions_dir / rev.path).unlink(missing_ok=True)
        self._atomic_write(self.revisions_index, "[]")


__all__ = [
    "ProjectMemoryStore",
    "WorkingMemoryTooLarge",
]
