from __future__ import annotations

from typing import Any

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightError = Exception


def is_available() -> bool:
    return PLAYWRIGHT_AVAILABLE


def driver_info() -> dict[str, Any]:
    if not PLAYWRIGHT_AVAILABLE:
        return {"available": False, "reason": "playwright not installed"}
    try:
        import playwright
        return {
            "available": True,
            "version": getattr(playwright, "__version__", "unknown"),
            "browsers": _detect_browsers(),
        }
    except Exception as exc:
        return {"available": True, "version": "?", "error": str(exc)}


def _detect_browsers() -> list[str]:
    found: list[str] = []
    try:
        pw = sync_playwright().start()
        for name, meth in (("chromium", pw.chromium), ("firefox", pw.firefox), ("webkit", pw.webkit)):
            try:
                if meth.executable_path:
                    found.append(name)
            except Exception:
                pass
        pw.stop()
    except Exception:
        pass
    return found


class PlaywrightDriver:
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

    def start(self, browser: str = "chromium") -> "PlaywrightDriver":
        self._pw = sync_playwright().start()
        launcher = getattr(self._pw, browser)
        self._browser = launcher.launch(headless=self._headless)
        self._page = self._browser.new_page()
        return self

    def navigate(self, url: str, wait_until: str = "networkidle") -> None:
        self._page.goto(url, wait_until=wait_until, timeout=30000)

    @property
    def page(self):
        return self._page

    def close(self) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._page = None
        self._browser = None
        self._pw = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()


__all__ = ["PlaywrightDriver", "driver_info", "is_available"]
