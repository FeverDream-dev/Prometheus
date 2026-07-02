from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightError = Exception

_browsers_ready: bool | None = None


def browsers_ready() -> bool:
    """True when Playwright is installed and Chromium binaries are present."""
    global _browsers_ready
    if _browsers_ready is not None:
        return _browsers_ready
    if not PLAYWRIGHT_AVAILABLE:
        _browsers_ready = False
        return False
    try:
        pw = sync_playwright().start()
        try:
            browser = pw.chromium.launch(headless=True)
            browser.close()
            _browsers_ready = True
        finally:
            pw.stop()
    except Exception:
        _browsers_ready = False
    return _browsers_ready


@dataclass
class BrowserEvidence:
    url: str = ""
    title: str = ""
    console_errors: list[str] = field(default_factory=list)
    network_failures: list[dict] = field(default_factory=list)
    screenshot_b64: str = ""

    def summary(self) -> str:
        lines = [f"URL: {self.url}", f"Title: {self.title}"]
        if self.console_errors:
            lines.append(f"Console errors ({len(self.console_errors)}):")
            for err in self.console_errors[:5]:
                lines.append(f"  ! {err}")
        if self.network_failures:
            lines.append(f"Network failures ({len(self.network_failures)}):")
            for fail in self.network_failures[:5]:
                lines.append(f"  ! {fail.get('method','')} {fail.get('url','')} → {fail.get('status','?')}")
        return "\n".join(lines)


class BrowserTools:
    def __init__(self, headless: bool = True):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is not installed. Install with: "
                "pip install 'prometheus-local-agent[browser]' && playwright install chromium"
            )
        self._headless = headless
        self._pw = None
        self._browser = None
        self._page = None
        self._console_errors: list[str] = []
        self._network_failures: list[dict] = []

    def _ensure_browser(self) -> None:
        if self._page is not None:
            return
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self._headless)
        self._page = self._browser.new_page()
        self._page.on("console", lambda msg: (
            self._console_errors.append(f"[{msg.type}] {msg.text}")
            if msg.type in ("error", "warning") else None
        ))
        self._page.on("requestfailed", lambda req: (
            self._network_failures.append({
                "method": req.method,
                "url": req.url,
                "status": "failed",
                "failure": req.failure,
            })
        ))

    def navigate(self, url: str, wait_until: str = "networkidle") -> str:
        self._ensure_browser()
        self._console_errors.clear()
        self._network_failures.clear()
        self._page.goto(url, wait_until=wait_until, timeout=30000)
        return f"Navigated to {url}\nTitle: {self._page.title()}"

    def screenshot(self, full_page: bool = True) -> str:
        self._ensure_browser()
        png_bytes = self._page.screenshot(full_page=full_page)
        b64 = base64.b64encode(png_bytes).decode("ascii")
        return f"screenshot:{len(png_bytes)} bytes (base64 {len(b64)} chars)"

    def click(self, selector: str) -> str:
        self._ensure_browser()
        self._page.click(selector, timeout=10000)
        return f"Clicked: {selector}"

    def fill(self, selector: str, value: str) -> str:
        self._ensure_browser()
        self._page.fill(selector, value, timeout=10000)
        return f"Filled {selector} with {len(value)} chars"

    def text(self, selector: str = "body") -> str:
        self._ensure_browser()
        return self._page.inner_text(selector)[:10000]

    def evaluate(self, expression: str) -> str:
        self._ensure_browser()
        result = self._page.evaluate(expression)
        return json.dumps(result, default=str)[:10000]

    def collect_evidence(self) -> BrowserEvidence:
        self._ensure_browser()
        return BrowserEvidence(
            url=self._page.url,
            title=self._page.title(),
            console_errors=list(self._console_errors),
            network_failures=list(self._network_failures),
        )

    def close(self) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._page = None
        self._browser = None
        self._pw = None
