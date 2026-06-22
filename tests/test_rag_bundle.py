from __future__ import annotations


import pytest

from prometheus_cli.rag import RagStore


@pytest.fixture
def store(tmp_path):
    (tmp_path / "doc1.md").write_text("# JWT Auth\n\nJWT token issuance and validation for REST APIs.", encoding="utf-8")
    (tmp_path / "doc2.md").write_text("# API Design\n\nREST API design patterns with pagination and caching.", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("Project notes about deployment and CI/CD pipelines.", encoding="utf-8")
    s = RagStore(tmp_path)
    s.init()
    return s


class TestRagStoreInit:
    def test_init_creates_directory(self, tmp_path):
        store = RagStore(tmp_path)
        path = store.init()
        assert path.is_dir()
        assert (path / "manifest.json").is_file()
        assert (path / "sources.jsonl").is_file()
        assert (path / "chunks.jsonl").is_file()

    def test_is_initialized_false_before_init(self, tmp_path):
        store = RagStore(tmp_path)
        assert store.is_initialized() is False

    def test_is_initialized_true_after_init(self, tmp_path):
        store = RagStore(tmp_path)
        store.init()
        assert store.is_initialized() is True


class TestRagStoreIngest:
    def test_ingest_single_file(self, store, tmp_path):
        result = store.ingest(tmp_path / "doc1.md")
        assert result["ingested"] == 1
        assert result["chunks"] >= 1

    def test_ingest_directory(self, store, tmp_path):
        result = store.ingest(tmp_path)
        assert result["ingested"] >= 2

    def test_ingest_skips_duplicates(self, store, tmp_path):
        store.ingest(tmp_path / "doc1.md")
        result = store.ingest(tmp_path / "doc1.md")
        assert result["ingested"] == 0

    def test_ingest_nonexistent_path(self, store, tmp_path):
        result = store.ingest(tmp_path / "nonexistent")
        assert "error" in result


class TestRagStoreQuery:
    def test_query_returns_matching_results(self, store, tmp_path):
        store.ingest(tmp_path)
        results = store.query("JWT authentication")
        assert len(results) >= 1
        assert any("jwt" in r.text.lower() or "auth" in r.text.lower() for r in results)

    def test_query_returns_score(self, store, tmp_path):
        store.ingest(tmp_path / "doc1.md")
        results = store.query("JWT token")
        for r in results:
            assert 0 < r.score <= 1.0

    def test_query_no_match_returns_empty(self, store, tmp_path):
        store.ingest(tmp_path)
        results = store.query("quantum physics xyzzy nonexistent")
        assert results == []

    def test_query_respects_limit(self, store, tmp_path):
        store.ingest(tmp_path)
        results = store.query("API design REST", limit=1)
        assert len(results) <= 1

    def test_query_empty_store(self, tmp_path):
        store = RagStore(tmp_path)
        store.init()
        results = store.query("anything")
        assert results == []


class TestRagStoreStatus:
    def test_status_after_ingest(self, store, tmp_path):
        store.ingest(tmp_path)
        st = store.status()
        assert st.initialized is True
        assert st.sources >= 2
        assert st.chunks >= 2
        assert st.total_chars > 0

    def test_status_before_ingest(self, tmp_path):
        store = RagStore(tmp_path)
        store.init()
        st = store.status()
        assert st.sources == 0
        assert st.chunks == 0


class TestRagStoreReset:
    def test_reset_removes_directory(self, store, tmp_path):
        store.ingest(tmp_path / "doc1.md")
        assert store.reset() is True
        assert not (tmp_path / ".prometheus" / "rag").is_dir()

    def test_reset_when_not_initialized(self, tmp_path):
        store = RagStore(tmp_path)
        assert store.reset() is False


class TestRagStorage:
    def test_rag_files_in_prometheus_dir(self, tmp_path):
        store = RagStore(tmp_path)
        store.init()
        rag_dir = tmp_path / ".prometheus" / "rag"
        assert rag_dir.is_dir()
        assert (rag_dir / "index").is_dir()
        assert (rag_dir / "sources.jsonl").is_file()
        assert (rag_dir / "chunks.jsonl").is_file()
        assert (rag_dir / "manifest.json").is_file()

    def test_chunks_have_keywords(self, store, tmp_path):
        store.ingest(tmp_path / "doc1.md")
        chunks = store._read_chunks()
        assert len(chunks) >= 1
        for chunk in chunks:
            assert isinstance(chunk.keywords, list)
