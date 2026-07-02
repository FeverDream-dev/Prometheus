from __future__ import annotations

import socket
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

from prometheus_cli.browser import PLAYWRIGHT_AVAILABLE, BrowserTools, browsers_ready

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "web"


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def server_url():
    def handler(*a, **kw):
        return SimpleHTTPRequestHandler(*a, directory=str(FIXTURE_DIR), **kw)

    httpd = HTTPServer(("127.0.0.1", _free_port()), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/index.html"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def browser():
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("playwright not installed")
    if not browsers_ready():
        pytest.skip("playwright browsers not installed; run: playwright install chromium")
    bt = BrowserTools(headless=True)
    yield bt
    bt.close()


pytestmark = pytest.mark.skipif(
    not PLAYWRIGHT_AVAILABLE or not browsers_ready(),
    reason="playwright browsers not ready; run: pip install 'prometheus-local-agent[browser]' && playwright install chromium",
)


def test_navigate_and_read_title(server_url, browser):
    browser.navigate(server_url)
    evidence = browser.collect_evidence()
    assert evidence.title == "PROMETHEUS Web Fixture"
    assert evidence.url == server_url


def test_real_click_increments_counter(server_url, browser):
    browser.navigate(server_url)
    assert browser.text("#count") == "0"
    browser.click("#inc")
    browser.click("#inc")
    assert browser.text("#count") == "2"


def test_fill_and_greet(server_url, browser):
    browser.navigate(server_url)
    browser.fill("#name", "Prometheus")
    browser.click("#greet")
    assert "Hello, Prometheus" in browser.text("#out")


def test_console_error_captured_as_evidence(server_url, browser):
    browser.navigate(server_url)
    evidence = browser.collect_evidence()
    assert any("fixture diagnostic error" in msg for msg in evidence.console_errors)


def test_screenshot_returns_byte_marker(server_url, browser):
    browser.navigate(server_url)
    out = browser.screenshot()
    assert out.startswith("screenshot:")
    assert "bytes" in out


def test_collect_evidence_summary_is_human_readable(server_url, browser):
    browser.navigate(server_url)
    summary = browser.collect_evidence().summary()
    assert "URL:" in summary
    assert "PROMETHEUS Web Fixture" in summary
