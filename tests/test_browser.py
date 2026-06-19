from __future__ import annotations

import json
from unittest import mock

import pytest

from prometheus_cli.browser import BrowserTools, BrowserEvidence, PLAYWRIGHT_AVAILABLE


@pytest.fixture
def mock_page():
    page = mock.MagicMock()
    page.url = "http://localhost:3000"
    page.title.return_value = "Test Page"
    page.screenshot.return_value = b"\x89PNG fake screenshot"
    page.inner_text.return_value = "Hello World"
    page.evaluate.return_value = {"result": 42}
    page.on = mock.MagicMock()
    return page


@pytest.fixture
def mock_playwright_ctx(mock_page):
    pw_instance = mock.MagicMock()
    pw_instance.chromium.launch.return_value.new_page.return_value = mock_page
    pw_context = mock.MagicMock()
    pw_context.start.return_value = pw_instance
    return pw_context, mock_page


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestBrowserNavigation:
    def test_navigate_returns_url_and_title(self, mock_playwright_ctx):
        pw_ctx, page = mock_playwright_ctx
        with mock.patch("prometheus_cli.browser.sync_playwright", return_value=pw_ctx):
            tools = BrowserTools()
            result = tools.navigate("http://localhost:3000")
            assert "http://localhost:3000" in result
            assert "Test Page" in result
            page.goto.assert_called_once()

    def test_navigate_clears_previous_evidence(self, mock_playwright_ctx):
        pw_ctx, page = mock_playwright_ctx
        with mock.patch("prometheus_cli.browser.sync_playwright", return_value=pw_ctx):
            tools = BrowserTools()
            tools._console_errors.append("old error")
            tools.navigate("http://localhost:3000")
            assert len(tools._console_errors) == 0


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestBrowserInteraction:
    def test_click_calls_page_click(self, mock_playwright_ctx):
        pw_ctx, page = mock_playwright_ctx
        with mock.patch("prometheus_cli.browser.sync_playwright", return_value=pw_ctx):
            tools = BrowserTools()
            result = tools.click("#submit-btn")
            page.click.assert_called_once_with("#submit-btn", timeout=10000)
            assert "submit-btn" in result

    def test_fill_calls_page_fill(self, mock_playwright_ctx):
        pw_ctx, page = mock_playwright_ctx
        with mock.patch("prometheus_cli.browser.sync_playwright", return_value=pw_ctx):
            tools = BrowserTools()
            result = tools.fill("#email", "user@example.com")
            page.fill.assert_called_once()
            assert "email" in result

    def test_text_returns_inner_text(self, mock_playwright_ctx):
        pw_ctx, page = mock_playwright_ctx
        with mock.patch("prometheus_cli.browser.sync_playwright", return_value=pw_ctx):
            tools = BrowserTools()
            result = tools.text("h1")
            assert result == "Hello World"

    def test_evaluate_returns_json_result(self, mock_playwright_ctx):
        pw_ctx, page = mock_playwright_ctx
        with mock.patch("prometheus_cli.browser.sync_playwright", return_value=pw_ctx):
            tools = BrowserTools()
            result = tools.evaluate("document.title")
            data = json.loads(result)
            assert data["result"] == 42


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestScreenshot:
    def test_screenshot_returns_size_info(self, mock_playwright_ctx):
        pw_ctx, page = mock_playwright_ctx
        with mock.patch("prometheus_cli.browser.sync_playwright", return_value=pw_ctx):
            tools = BrowserTools()
            result = tools.screenshot()
            assert "screenshot:" in result
            page.screenshot.assert_called_once()


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestEvidenceCollection:
    def test_collect_evidence_captures_url_and_title(self, mock_playwright_ctx):
        pw_ctx, page = mock_playwright_ctx
        with mock.patch("prometheus_cli.browser.sync_playwright", return_value=pw_ctx):
            tools = BrowserTools()
            tools.navigate("http://localhost:3000")
            evidence = tools.collect_evidence()
            assert evidence.url == "http://localhost:3000"
            assert evidence.title == "Test Page"

    def test_console_handler_captures_errors(self, mock_playwright_ctx):
        pw_ctx, page = mock_playwright_ctx
        with mock.patch("prometheus_cli.browser.sync_playwright", return_value=pw_ctx):
            tools = BrowserTools()
            tools.navigate("http://localhost:3000")
            handlers = {call.args[0]: call.args[1] for call in page.on.call_args_list}
            console_handler = handlers.get("console")
            if console_handler:
                msg = mock.MagicMock(type="error", text="Uncaught TypeError")
                console_handler(msg)
                assert any("TypeError" in e for e in tools._console_errors)

    def test_network_handler_captures_failures(self, mock_playwright_ctx):
        pw_ctx, page = mock_playwright_ctx
        with mock.patch("prometheus_cli.browser.sync_playwright", return_value=pw_ctx):
            tools = BrowserTools()
            tools.navigate("http://localhost:3000")
            handlers = {call.args[0]: call.args[1] for call in page.on.call_args_list}
            fail_handler = handlers.get("requestfailed")
            if fail_handler:
                req = mock.MagicMock(method="GET", url="http://broken.api/v1", failure="net::ERR_FAILED")
                fail_handler(req)
                assert any("broken.api" in f["url"] for f in tools._network_failures)

    def test_evidence_summary_format(self):
        evidence = BrowserEvidence(
            url="http://test",
            title="Test",
            console_errors=["Error: bad thing"],
            network_failures=[{"method": "GET", "url": "http://x", "status": "failed"}],
        )
        summary = evidence.summary()
        assert "http://test" in summary
        assert "Console errors" in summary
        assert "Network failures" in summary


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestBrowserLifecycle:
    def test_close_stops_playwright(self, mock_playwright_ctx):
        pw_ctx, page = mock_playwright_ctx
        with mock.patch("prometheus_cli.browser.sync_playwright", return_value=pw_ctx):
            tools = BrowserTools()
            tools.navigate("http://localhost:3000")
            tools.close()
            assert tools._page is None
            assert tools._browser is None
