from __future__ import annotations


import httpx

from prometheus_cli.tools.web import (
    UNTRUSTED_END,
    UNTRUSTED_START,
    WebFetch,
)


class FakeClient:
    def __init__(self, url_to_response):
        self._urls = url_to_response
        self.requested: list[str] = []

    def get(self, url):
        self.requested.append(url)
        value = self._urls.get(url)
        if isinstance(value, Exception):
            raise value

        class R:
            status_code = value.get("status", 200)
            text = value.get("body", "")

        return R()

    def close(self):
        pass


def test_fetch_extracts_title_and_strips_html():
    client = FakeClient({"https://example.com/page": {
        "body": "<html><head><title>Example Page</title></head><body><p>Hello <b>world</b></p><script>bad()</script></body></html>"
    }})
    wf = WebFetch(allowed_domains=["example.com"])
    result = wf.fetch("https://example.com/page", client=client)
    assert result.status == 200
    assert result.title == "Example Page"
    assert "Hello world" in result.text
    assert "<script>" not in result.text
    assert "<b>" not in result.text


def test_citation_wraps_content_as_untrusted():
    client = FakeClient({"https://example.com/x": {"body": "<title>T</title>secret finding"}})
    wf = WebFetch()
    out = wf.fetch("https://example.com/x", client=client).with_citation()
    assert UNTRUSTED_START in out
    assert UNTRUSTED_END in out
    assert "secret finding" in out
    assert "https://example.com/x" in out


def test_domain_allowlist_blocks_unapproved_domain():
    wf = WebFetch(allowed_domains=["trusted.com"])
    result = wf.fetch("https://evil.example.com/x", client=FakeClient({}))
    assert result.status == 0
    assert "not permitted" in result.error


def test_subdomain_matches_allowlist():
    client = FakeClient({"https://docs.example.com/x": {"body": "ok"}})
    wf = WebFetch(allowed_domains=["example.com"])
    result = wf.fetch("https://docs.example.com/x", client=client)
    assert result.status == 200


def test_allow_network_false_blocks_all():
    wf = WebFetch(allow_network=False)
    result = wf.fetch("https://example.com/x", client=FakeClient({}))
    assert result.status == 0
    assert "policy" in result.error


def test_bounded_output_respects_max_chars():
    big = "<title>B</title>" + ("x" * 50000)
    client = FakeClient({"https://example.com/big": {"body": big}})
    wf = WebFetch(max_chars=1000)
    result = wf.fetch("https://example.com/big", client=client)
    assert len(result.text) <= 1000


def test_caches_repeated_fetch(tmp_path):
    body = "<title>C</title>cached body content"
    client = FakeClient({"https://example.com/c": {"body": body}})
    wf = WebFetch(cache_dir=tmp_path / ".artifacts")
    first = wf.fetch("https://example.com/c", client=client)
    assert first.cached is False
    cache_files = list((tmp_path / ".artifacts").glob("*.txt"))
    assert len(cache_files) == 1
    second_client = FakeClient({})
    second = wf.fetch("https://example.com/c", client=second_client)
    assert second.cached is True
    assert "cached body content" in second.text


def test_network_error_is_reported_not_raised():
    client = FakeClient({"https://example.com/x": httpx.ConnectError("refused", request=httpx.Request("GET", "x"))})
    wf = WebFetch()
    result = wf.fetch("https://example.com/x", client=client)
    assert result.status == 0
    assert "refused" in result.error
    assert "refused" in result.with_citation()


def test_relative_url_without_scheme_rejected():
    wf = WebFetch()
    result = wf.fetch("not-a-url", client=FakeClient({}))
    assert result.status == 0


def test_cache_dir_excluded_from_git_is_safe(tmp_path):
    cache = tmp_path / ".artifacts"
    client = FakeClient({"https://example.com/x": {"body": "data"}})
    WebFetch(cache_dir=cache).fetch("https://example.com/x", client=client)
    assert cache.exists()
    assert cache.name == ".artifacts"
