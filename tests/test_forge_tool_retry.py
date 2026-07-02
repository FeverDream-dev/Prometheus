from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from prometheus_cli.agent import ArenaLoop, MicroStepEngine
from prometheus_cli.agent_efficiency import narrates_tools_without_calls
from prometheus_cli.memory import Intent, ProjectMemoryStore, TaskNode
from prometheus_cli.models import AutonomyMode, Settings
from prometheus_cli.tools.workspace import WorkspaceTools

FIX = "<!DOCTYPE html><html><body>ok</body></html>"

narrated = json.dumps({"status": "working", "message": "write_file('./site/index.html', '...')", "calls": []})
fixed = json.dumps({
    "status": "working",
    "message": "write index",
    "calls": [{"tool": "write_file", "arguments": {"path": "site/index.html", "content": FIX}, "reason": "build"}],
})


class Scripted:
    def __init__(self, scripts):
        self._scripts = list(scripts)
        self.calls = 0

    def complete(self, messages, schema=None):
        self.calls += 1
        content = " ".join(str(m.get("content", "")) for m in messages if isinstance(m, dict))
        if "RETRY REQUIRED" in content and len(self._scripts) > 1:
            return self._scripts[1]
        return self._scripts[0]

    def unload(self):
        pass


def test_narrated_forge_retries_and_writes():
    scripts = [narrated, fixed]
    with TemporaryDirectory() as tmp:
        ws = Path(tmp)
        store = ProjectMemoryStore(ws)
        store.set_intent(Intent(objective="site", success_criteria=["file exists"]))
        store.upsert_task(TaskNode(id="t1", description="write html", status="active", acceptance="file"))
        tools = WorkspaceTools(ws)
        engine = MicroStepEngine(store=store, tools=tools, settings=Settings(mode=AutonomyMode.ASTRONAUT), approve=lambda _c, _r: True)
        forge = Scripted([narrated, fixed])
        out = engine.run_seat(
            __import__("prometheus_cli.agent.seats", fromlist=["SEATS"]).SEATS["forge"],
            forge,
        )
        assert narrates_tools_without_calls("write_file('x')", [])
        assert forge.calls >= 2
        assert any("SELF-CHECK OK" in line for line in out.tool_outputs)
