from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx

UNTRUSTED_START = "--- UNTRUSTED WEB CONTENT START ---"
UNTRUSTED_END = "--- UNTRUSTED WEB CONTENT END ---"
DEFAULT_MAX_CHARS = 8000
DEFAULT_TIMEOUT = 15.0


@dataclass
class WebResult:
    url: str
    status: int
    title: str = ""
    text: str = ""
    fetched_at: str = ""
    cached: bool = False
    error: str = ""

    def with_citation(self) -> str:
        header = (f"[fetched {self.fetched_at}] {self.url} (HTTP {self.status})"
                  + (f" — {self.title}" if self.title else ""))
        if self.error:
            return f"{header}\nERROR: {self.error}"
        return f"{header}\n{UNTRUSTED_START}\n{self.text}\n{UNTRUSTED_END}"


@dataclass
class WebFetch:
    allowed_domains: list[str] = field(default_factory=list)
    allow_network: bool = True
    cache_dir: Path | None = None
    max_chars: int = DEFAULT_MAX_CHARS
    user_agent: str = "PROMETHEUS/0.1 (+local-first coding agent)"

    def _domain_allowed(self, url: str) -> bool:
        if not self.allow_network:
            return False
        host = urlparse(url).hostname or ""
        if not host:
            return False
        if not self.allowed_domains:
            return True
        return any(host == d or host.endswith("." + d) for d in self.allowed_domains)

    def _cache_key(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{key}.txt"

    def _read_cache(self, url: str) -> str | None:
        path = self._cache_key(url)
        if path and path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")
        return None

    def _write_cache(self, url: str, content: str) -> None:
        path = self._cache_key(url)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def fetch(self, url: str, client: httpx.Client | None = None, max_chars: int | None = None) -> WebResult:
        if not self._domain_allowed(url):
            return WebResult(url=url, status=0, error="domain not permitted (network/domain policy)")
        limit = max_chars or self.max_chars
        cached = self._read_cache(url)
        if cached is not None:
            return WebResult(
                url=url, status=200, text=cached[:limit],
                fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                cached=True,
            )
        own = client is None
        cl = client or httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True,
                                    headers={"User-Agent": self.user_agent})
        try:
            resp = cl.get(url)
            body = resp.text
        except httpx.HTTPError as exc:
            return WebResult(url=url, status=0, error=str(exc))
        finally:
            if own:
                cl.close()
        title = _extract_title(body)
        text = _html_to_text(body)[:limit]
        self._write_cache(url, text)
        return WebResult(
            url=url, status=resp.status_code, title=title, text=text,
            fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return _WS_RE.sub(" ", m.group(1)).strip()[:200] if m else ""


def _html_to_text(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.IGNORECASE | re.DOTALL)
    text = _TAG_RE.sub(" ", html)
    return _WS_RE.sub(" ", text).strip()


__all__ = ["DEFAULT_MAX_CHARS", "UNTRUSTED_END", "UNTRUSTED_START", "WebFetch", "WebResult"]
