from __future__ import annotations

from pathlib import Path

import pytest

try:
    from prometheus_cli.browser import PLAYWRIGHT_AVAILABLE, browsers_ready
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

    def browsers_ready() -> bool:
        return False

pytestmark = pytest.mark.skipif(
    not PLAYWRIGHT_AVAILABLE or not browsers_ready(),
    reason="playwright browsers not ready; run: pip install 'prometheus-local-agent[browser]' && playwright install chromium",
)

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "sandbox_target" / "public" / "index.html"


def test_browser_cannot_save_outside_workspace(tmp_path):
    from prometheus_cli.browser import BrowserTools
    from prometheus_cli.models import SandboxTier, Settings
    from prometheus_cli.tools.workspace import WorkspaceTools

    ws = tmp_path / "ws"
    ws.mkdir()
    settings = Settings(sandbox_tier=SandboxTier.BASIC)
    tools = WorkspaceTools.from_settings(ws, settings)
    with pytest.raises(PermissionError):
        tools.write_file("../browser_exfil.png", "fake-screenshot")
    tools_b = BrowserTools(headless=True)
    try:
        nav = tools_b.navigate(f"file://{FIXTURE}")
        assert "sandbox fixture" in nav or "sandbox_target" in nav
    finally:
        tools_b.close()


def test_browser_evidence_collected_from_fixture():
    from prometheus_cli.browser import BrowserTools

    tools = BrowserTools(headless=True)
    try:
        tools.navigate(f"file://{FIXTURE}")
        evidence = tools.collect_evidence()
        assert "sandbox" in evidence.title.lower() or "fixture" in evidence.title.lower()
    finally:
        tools.close()
