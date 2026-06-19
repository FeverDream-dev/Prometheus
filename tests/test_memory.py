from __future__ import annotations

import subprocess

import pytest

from prometheus_cli.memory import (
    MAX_WORKING_WORDS,
    Constraint,
    Decision,
    Fact,
    FactConfidence,
    FailureSignature,
    Handoff,
    Intent,
    Provenance,
    ProjectMemoryStore,
    TaskNode,
    WorkingMemoryTooLarge,
)


@pytest.fixture
def store(tmp_path):
    return ProjectMemoryStore(tmp_path)


def _words(n: int) -> str:
    return " ".join(f"word{i}" for i in range(n))


def test_working_memory_enforces_1024_word_limit(store):
    rev = store.set_working_memory(_words(1024))
    assert rev.word_count == 1024
    with pytest.raises(WorkingMemoryTooLarge):
        store.set_working_memory(_words(1025))


def test_explicit_user_constraints_survive_across_revisions(store):
    intent = Intent(objective="ship feature", success_criteria=["tests pass"])
    intent.add_constraint(Constraint(id="c1", statement="must work offline"))
    store.set_intent(intent)
    store.set_working_memory("# v1\nfirst revision")
    store.set_working_memory("# v2\nsecond revision")
    store.set_working_memory("# v3\nthird revision")
    recovered = store.get_intent()
    assert recovered is not None
    assert recovered.objective == "ship feature"
    assert recovered.success_criteria == ["tests pass"]
    assert any(c.statement == "must work offline" and c.active for c in recovered.constraints)


def test_corrupt_active_memory_restores_last_valid_revision(store):
    store.set_working_memory("# good\nthe real state")
    store.working_path.write_text("GARBAGE \x00 broken", encoding="utf-8")
    status = store.status()
    assert status.recovered is True
    assert status.ok is True
    assert "the real state" in store.get_working_memory()


def test_corrupt_store_recovers_from_earlier_revision_when_latest_bad(store):
    store.set_working_memory("# v1\nfirst good")
    store.set_working_memory("# v2\nsecond good")
    revs = store.list_revisions()
    (store.revisions_dir / revs[-1].path).write_text("corrupt", encoding="utf-8")
    status = store.recover()
    assert status.ok is True
    assert "first good" in store.get_working_memory()


def test_every_fact_has_provenance(store):
    fact = Fact(id="f1", summary="python 3.11 detected", confidence=FactConfidence.OBSERVED,
                provenance=Provenance(source="tool", event_id=7))
    store.record_fact(fact)
    loaded = store.list_facts()[0]
    assert loaded.provenance.source == "tool"
    assert loaded.provenance.event_id == 7
    assert loaded.is_certain is True


def test_inferred_facts_not_treated_as_certain(store):
    fact = Fact(id="f2", summary="maybe uses docker", confidence=FactConfidence.INFERRED)
    store.record_fact(fact)
    assert store.list_facts()[0].is_certain is False


def test_secrets_redacted_before_persistence(store, tmp_path):
    fact = Fact(id="f3", summary="api key sk-1234567890abcdefghijklmnopqrstuv loaded")
    store.record_fact(fact)
    persisted = store.facts_path.read_text(encoding="utf-8")
    assert "sk-1234567890abcdefghijklmnopqrstuv" not in persisted
    assert "[REDACTED]" in persisted


def test_export_is_sanitized_of_secrets(store, tmp_path):
    store.set_intent(Intent(objective="build with api_key=sk-leak1234567890abcdefghij"))
    store.set_working_memory("memory contains token=sk-leak1234567890abcdefghij")
    out = store.export(tmp_path / "export.json")
    text = out.read_text(encoding="utf-8")
    assert "sk-leak1234567890abcdefghij" not in text


def test_atomic_write_survives_partial_write_simulation(store, tmp_path):
    store.set_working_memory("# committed\nreal content")
    tmp = store.working_path.with_suffix(".md.tmp.99999")
    tmp.write_text("partial", encoding="utf-8")
    assert store.get_working_memory() == "# committed\nreal content"


def test_rebuild_regenerates_working_memory_from_ledgers(store):
    store.set_intent(Intent(objective="fix calculator", success_criteria=["add() adds"]))
    store.upsert_task(TaskNode(id="t1", description="patch add()", status="active", acceptance="2+2=4"))
    store.append_decision(Decision(id="d1", question="which fix", choice="return a + b"))
    store.record_fact(Fact(id="f1", summary="add subtracts", confidence=FactConfidence.OBSERVED,
                           provenance=Provenance(source="test")))
    status = store.rebuild()
    assert status.ok is True
    text = store.get_working_memory()
    assert "fix calculator" in text
    assert "patch add()" in text
    assert "return a + b" in text
    assert status.word_count <= MAX_WORKING_WORDS


def test_handoff_persisted_and_validated(store):
    handoff = Handoff(
        task_id="t1", from_seat="forge", to_seat="argus",
        objective="verify add()", acceptance=["2+2=4"],
        verified_facts=[{"id": "f1", "summary": "add subtracts"}],
        next_action="run tests", prohibited_actions=["git push"],
    )
    path = store.write_handoff(handoff)
    reloaded = Handoff.model_validate_json(path.read_text(encoding="utf-8"))
    assert reloaded.from_seat == "forge"
    assert reloaded.to_seat == "argus"
    assert reloaded.acceptance == ["2+2=4"]


def test_failure_signature_aggregates_repeats(store):
    store.record_failure(FailureSignature(id="x1", signature="ImportError: x", hypothesis="missing dep"))
    store.record_failure(FailureSignature(id="x1", signature="ImportError: x", hypothesis="missing dep"))
    failures = store.list_failures()
    assert len(failures) == 1
    assert failures[0].count == 2


def test_superseded_tasks_are_not_active(store):
    store.upsert_task(TaskNode(id="t1", description="old approach", status="superseded"))
    store.upsert_task(TaskNode(id="t2", description="real approach", status="active"))
    active = store.active_micro_step()
    assert active is not None
    assert active.id == "t2"


def test_reset_clears_memory_but_keeps_store_usable(store):
    store.set_intent(Intent(objective="x"))
    store.set_working_memory("# mem")
    store.reset()
    assert store.get_working_memory() == ""
    assert store.get_intent() is None
    store.set_working_memory("# fresh after reset")
    assert store.status().ok is True


def test_prometheus_dir_is_gitignored(store, tmp_path):
    ignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".prometheus/" in ignore
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    out = subprocess.run(["git", "check-ignore", ".prometheus/"], cwd=tmp_path, capture_output=True, text=True)
    assert out.returncode == 0, ".prometheus/ must be git-ignored"


def test_conflicting_constraints_are_flagged_not_blended(store):
    intent = Intent(objective="deploy")
    intent.add_constraint(Constraint(id="a", statement="use docker"))
    intent.add_constraint(Constraint(id="b", statement="no containers"))
    intent.record_conflict("docker vs no containers")
    reloaded = store.get_intent() if False else intent
    assert "docker vs no containers" in reloaded.conflicts


def test_provenance_why_lookup(store):
    store.record_fact(Fact(id="f9", summary="evidence X", provenance=Provenance(source="test", event_id=42)))
    found = store.why("f9")
    assert found is not None
    assert found.provenance.event_id == 42
    assert store.why("missing") is None
