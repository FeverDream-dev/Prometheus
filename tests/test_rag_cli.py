from __future__ import annotations


import pytest
from typer.testing import CliRunner

from prometheus_cli.cli import app


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "doc1.md").write_text("# JWT Auth\n\nThis document explains JWT token issuance and validation.", encoding="utf-8")
    (tmp_path / "doc2.md").write_text("# API Design\n\nREST API design patterns for scalable web applications.", encoding="utf-8")
    (tmp_path / "code.py").write_text("def hello():\n    print('hello world')\n", encoding="utf-8")
    return tmp_path


class TestRagInit:
    def test_init_creates_rag_directory(self, runner, workspace):
        result = runner.invoke(app, ["rag", "init", "--workspace", str(workspace)])
        assert result.exit_code == 0, result.stdout
        assert "RAG initialized" in result.stdout
        rag_dir = workspace / ".prometheus" / "rag"
        assert rag_dir.is_dir()
        assert (rag_dir / "manifest.json").is_file()

    def test_status_before_init(self, runner, tmp_path):
        result = runner.invoke(app, ["rag", "status", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "not initialized" in result.stdout.lower()


class TestRagIngest:
    def test_ingest_single_file(self, runner, workspace):
        runner.invoke(app, ["rag", "init", "--workspace", str(workspace)])
        result = runner.invoke(app, ["rag", "ingest", str(workspace / "doc1.md"), "--workspace", str(workspace)])
        assert result.exit_code == 0, result.stdout
        assert "Ingested" in result.stdout

    def test_ingest_directory(self, runner, workspace):
        runner.invoke(app, ["rag", "init", "--workspace", str(workspace)])
        result = runner.invoke(app, ["rag", "ingest", str(workspace), "--workspace", str(workspace)])
        assert result.exit_code == 0
        assert "Ingested" in result.stdout

    def test_status_after_ingest(self, runner, workspace):
        runner.invoke(app, ["rag", "init", "--workspace", str(workspace)])
        runner.invoke(app, ["rag", "ingest", str(workspace), "--workspace", str(workspace)])
        result = runner.invoke(app, ["rag", "status", "--workspace", str(workspace)])
        assert result.exit_code == 0
        assert "Sources:" in result.stdout
        assert "Chunks:" in result.stdout

    def test_status_json(self, runner, workspace):
        runner.invoke(app, ["rag", "init", "--workspace", str(workspace)])
        runner.invoke(app, ["rag", "ingest", str(workspace / "doc1.md"), "--workspace", str(workspace)])
        result = runner.invoke(app, ["rag", "status", "--workspace", str(workspace), "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.stdout)
        assert data["sources"] >= 1
        assert data["chunks"] >= 1


class TestRagQuery:
    def test_query_returns_results(self, runner, workspace):
        runner.invoke(app, ["rag", "init", "--workspace", str(workspace)])
        runner.invoke(app, ["rag", "ingest", str(workspace), "--workspace", str(workspace)])
        result = runner.invoke(app, ["rag", "query", "JWT authentication", "--workspace", str(workspace)])
        assert result.exit_code == 0
        assert "JWT" in result.stdout or "jwt" in result.stdout.lower()

    def test_query_no_results(self, runner, workspace):
        runner.invoke(app, ["rag", "init", "--workspace", str(workspace)])
        runner.invoke(app, ["rag", "ingest", str(workspace), "--workspace", str(workspace)])
        result = runner.invoke(app, ["rag", "query", "quantum physics xyzzy", "--workspace", str(workspace)])
        assert result.exit_code == 0
        assert "No matching" in result.stdout or "no results" in result.stdout.lower()

    def test_query_json(self, runner, workspace):
        runner.invoke(app, ["rag", "init", "--workspace", str(workspace)])
        runner.invoke(app, ["rag", "ingest", str(workspace / "doc1.md"), "--workspace", str(workspace)])
        result = runner.invoke(app, ["rag", "query", "JWT", "--workspace", str(workspace), "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.stdout)
        assert len(data) >= 1
        assert "source" in data[0]
        assert "score" in data[0]


class TestRagReset:
    def test_reset_requires_confirm(self, runner, workspace):
        runner.invoke(app, ["rag", "init", "--workspace", str(workspace)])
        result = runner.invoke(app, ["rag", "reset", "--workspace", str(workspace)])
        assert result.exit_code == 1

    def test_reset_with_confirm(self, runner, workspace):
        runner.invoke(app, ["rag", "init", "--workspace", str(workspace)])
        result = runner.invoke(app, ["rag", "reset", "--workspace", str(workspace), "--confirm"])
        assert result.exit_code == 0
        assert "cleared" in result.stdout.lower()

    def test_reset_when_not_initialized(self, runner, tmp_path):
        result = runner.invoke(app, ["rag", "reset", "--workspace", str(tmp_path), "--confirm"])
        assert result.exit_code == 0
