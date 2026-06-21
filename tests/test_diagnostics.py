from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from prometheus_cli.diagnostics import (
    _fallback_redact,
    _safe,
    _parse_since,
    collect_diagnostics,
    collect_python_env,
    export_zip,
    render_diagnostics_lines,
)


SECRET_FIXTURES = [
    "sk-abc123def456ghi789jkl012mno345pqr678",
    "Bearer abcdefABCDEF1234567890abcdef",
    "password=supersecret_value123",
    "api_key=sk-live-9384571039845",
    "ghp_abc123def456ghi789jkl012mno345pqr678",
    "token: xoxb-1234567890-abcdefghij",
    "Authorization: Bearer really-long-secret-token-value-here",
]


@pytest.mark.parametrize("secret", SECRET_FIXTURES)
def test_redact_strips_known_secret_patterns(secret):
    redacted = _fallback_redact(secret)
    assert "[REDACTED]" in redacted, f"secret not redacted: {secret!r} -> {redacted!r}"
    for fragment in (
        "supersecret_value123",
        "sk-live-9384571039845",
        "abc123def456ghi789jkl012mno345pqr678",
        "really-long-secret-token-value-here",
        "xoxb-1234567890-abcdefghij",
    ):
        if fragment in secret:
            assert fragment not in redacted, f"leaked fragment {fragment!r}"


def test_parse_since_supports_mh_dw():
    import datetime
    base = datetime.datetime.now(datetime.timezone.utc)

    def _minutes(s):
        delta = base - _parse_since(s)
        return round(delta.total_seconds() / 60.0)

    assert abs(_minutes("30m") - 30) <= 1
    assert abs(_minutes("2h") - 120) <= 1
    assert abs(_minutes("1d") - 1440) <= 2
    assert abs(_minutes("1w") - 10080) <= 5


def test_parse_since_returns_none_on_garbage():
    assert _parse_since(None) is None
    assert _parse_since("garbage") is None
    assert _parse_since("") is None


def test_safe_blocks_secret_files():
    assert _safe(Path(".env")) is False
    assert _safe(Path(".env.local")) is False
    assert _safe(Path("secrets.yaml")) is False
    assert _safe(Path("id_rsa")) is False


def test_safe_blocks_model_weights():
    assert _safe(Path("model.gguf")) is False
    assert _safe(Path("weights.safetensors")) is False
    assert _safe(Path("model.bin")) is False


def test_safe_allows_normal_logs():
    assert _safe(Path("install.log")) is True
    assert _safe(Path("events.jsonl")) is True
    assert _safe(Path("prometheus.log")) is True


def test_collect_python_env_has_required_fields():
    env = collect_python_env()
    assert "python_version" in env
    assert "platform" in env
    assert "architecture" in env


def test_collect_diagnostics_full_schema():
    diag = collect_diagnostics(since_str="1h")
    for key in (
        "collected_at", "since", "python_env", "prometheus", "config",
        "recent_sessions", "recent_output_logs", "installer_logs",
        "ollama", "git", "test_hints", "secret_redaction",
    ):
        assert key in diag, f"diagnostics missing {key}"
    assert diag["secret_redaction"]
    assert "applied" in diag["secret_redaction"].lower()


def test_render_diagnostics_lines_returns_nonempty():
    diag = collect_diagnostics()
    lines = render_diagnostics_lines(diag)
    assert len(lines) > 5
    joined = "\n".join(lines)
    assert "Prometheus:" in joined
    assert "Try:" in joined


def test_render_diagnostics_lines_redacts_secrets():
    diag = collect_diagnostics()
    diag["recent_output_logs"] = ["api_key=sk-leaked-1234567890abcdefghij"]
    lines = render_diagnostics_lines(diag)
    rendered = "\n".join(lines)
    assert "sk-leaked-1234567890abcdefghij" not in rendered


def test_export_zip_creates_zip_with_json_and_readme(tmp_path):
    diag = {"collected_at": "2026-06-21T00:00:00+00:00", "secret_redaction": "applied"}
    out = export_zip(diag, tmp_path / "diag.zip")
    assert out.exists()
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "diagnostics.json" in names
        assert "README.txt" in names
        payload = json.loads(zf.read("diagnostics.json"))
        assert payload["collected_at"] == "2026-06-21T00:00:00+00:00"


def test_export_zip_redacts_secrets_in_payload(tmp_path):
    diag = {
        "recent_output_logs": ["Bearer abcdef1234567890abcdef1234567890"],
        "config": {"error": "password=hunter2_supersecret"},
    }
    out = export_zip(diag, tmp_path / "diag.zip")
    with zipfile.ZipFile(out) as zf:
        body = zf.read("diagnostics.json").decode("utf-8")
    assert "abcdef1234567890abcdef1234567890" not in body
    assert "hunter2_supersecret" not in body


def test_diagnostics_does_not_read_secret_env_files(tmp_path, monkeypatch):
    secret_env = tmp_path / ".env"
    secret_env.write_text("API_KEY=sk-supersecret-1234567890abcdef", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    diag = collect_diagnostics()
    serialized = json.dumps(diag, default=str)
    assert "sk-supersecret" not in serialized
    assert ".env" not in serialized or "[REDACTED]" in serialized


def test_test_hints_include_required_commands():
    diag = collect_diagnostics()
    commands = [h["command"] for h in diag["test_hints"]]
    assert "pytest -q" in commands
    assert "ruff check src tests" in commands
    assert "prometheus sandbox test --workspace <dir> --all" in commands


def test_collect_diagnostics_handles_no_git(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    diag = collect_diagnostics()
    assert diag["git"]["available"] is False
