from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
MAX_FILE_SIZE = 1024 * 1024
SUPPORTED_EXTS = {".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".rst", ".html", ".csv"}


@dataclass
class RagChunk:
    chunk_id: str
    source: str
    text: str
    offset: int
    keywords: list[str] = field(default_factory=list)


@dataclass
class RagStatus:
    initialized: bool
    sources: int
    chunks: int
    total_chars: int
    index_path: str

    def as_dict(self) -> dict:
        return {
            "initialized": self.initialized,
            "sources": self.sources,
            "chunks": self.chunks,
            "total_chars": self.total_chars,
            "index_path": self.index_path,
        }


@dataclass
class RagResult:
    source: str
    text: str
    score: float
    chunk_id: str

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "text": self.text,
            "score": round(self.score, 4),
            "chunk_id": self.chunk_id,
        }


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text)]


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[tuple[int, str]]:
    chunks: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append((start, chunk))
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def _make_id(source: str, offset: int) -> str:
    raw = f"{source}:{offset}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class RagStore:
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.rag_dir = self.workspace / ".prometheus" / "rag"
        self.index_dir = self.rag_dir / "index"
        self.sources_file = self.rag_dir / "sources.jsonl"
        self.chunks_file = self.rag_dir / "chunks.jsonl"
        self.manifest_file = self.rag_dir / "manifest.json"

    def init(self) -> Path:
        self.rag_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(exist_ok=True)
        if not self.manifest_file.exists():
            manifest = {
                "created": datetime.now(timezone.utc).isoformat(),
                "version": 1,
                "embedding_model": None,
            }
            self.manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if not self.sources_file.exists():
            self.sources_file.write_text("", encoding="utf-8")
        if not self.chunks_file.exists():
            self.chunks_file.write_text("", encoding="utf-8")
        return self.rag_dir

    def is_initialized(self) -> bool:
        return self.rag_dir.is_dir() and self.manifest_file.is_file()

    def _read_chunks(self) -> list[RagChunk]:
        if not self.chunks_file.exists():
            return []
        chunks: list[RagChunk] = []
        for line in self.chunks_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                chunks.append(RagChunk(
                    chunk_id=data["chunk_id"],
                    source=data["source"],
                    text=data["text"],
                    offset=data["offset"],
                    keywords=data.get("keywords", []),
                ))
            except (json.JSONDecodeError, KeyError):
                continue
        return chunks

    def _read_sources(self) -> list[dict]:
        if not self.sources_file.exists():
            return []
        sources = []
        for line in self.sources_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                sources.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return sources

    def ingest(self, path: Path) -> dict:
        path = Path(path)
        if not self.is_initialized():
            self.init()

        if path.is_file():
            files = [path]
        elif path.is_dir():
            files = [
                f for f in sorted(path.rglob("*"))
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS and f.stat().st_size < MAX_FILE_SIZE
            ]
        else:
            return {"error": f"path not found: {path}", "ingested": 0, "chunks": 0}

        existing_sources = {s["path"] for s in self._read_sources()}
        new_sources: list[dict] = []
        new_chunks: list[RagChunk] = []

        for f in files:
            fpath = str(f.resolve())
            if fpath in existing_sources:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            chunks = _chunk_text(text)
            source_entry = {
                "path": fpath,
                "name": f.name,
                "size": f.stat().st_size,
                "chunks": len(chunks),
                "ingested": datetime.now(timezone.utc).isoformat(),
            }
            new_sources.append(source_entry)
            for offset, chunk_text in chunks:
                keywords = list(set(_tokenize(chunk_text)))[:20]
                new_chunks.append(RagChunk(
                    chunk_id=_make_id(fpath, offset),
                    source=fpath,
                    text=chunk_text,
                    offset=offset,
                    keywords=keywords,
                ))

        with open(self.sources_file, "a", encoding="utf-8") as sf:
            for s in new_sources:
                sf.write(json.dumps(s) + "\n")

        with open(self.chunks_file, "a", encoding="utf-8") as cf:
            for c in new_chunks:
                cf.write(json.dumps({
                    "chunk_id": c.chunk_id,
                    "source": c.source,
                    "text": c.text,
                    "offset": c.offset,
                    "keywords": c.keywords,
                }) + "\n")

        return {
            "ingested": len(new_sources),
            "chunks": len(new_chunks),
            "skipped": len(files) - len(new_sources),
        }

    def query(self, text: str, limit: int = 5) -> list[RagResult]:
        chunks = self._read_chunks()
        if not chunks:
            return []
        query_keywords = set(_tokenize(text))
        if not query_keywords:
            return []
        scored: list[tuple[float, RagChunk]] = []
        for chunk in chunks:
            chunk_kw = set(chunk.keywords) if chunk.keywords else set(_tokenize(chunk.text))
            if not chunk_kw:
                continue
            overlap = len(query_keywords & chunk_kw)
            if overlap == 0:
                continue
            score = overlap / len(query_keywords)
            scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        results: list[RagResult] = []
        seen_sources: set[str] = set()
        for score, chunk in scored[:limit * 2]:
            if len(results) >= limit:
                break
            results.append(RagResult(
                source=chunk.source,
                text=chunk.text[:300],
                score=score,
                chunk_id=chunk.chunk_id,
            ))
            seen_sources.add(chunk.source)
        return results

    def status(self) -> RagStatus:
        sources = self._read_sources()
        chunks = self._read_chunks()
        total_chars = sum(len(c.text) for c in chunks)
        return RagStatus(
            initialized=self.is_initialized(),
            sources=len(sources),
            chunks=len(chunks),
            total_chars=total_chars,
            index_path=str(self.rag_dir),
        )

    def reset(self) -> bool:
        if not self.rag_dir.is_dir():
            return False
        import shutil
        shutil.rmtree(self.rag_dir)
        return True


__all__ = [
    "RagChunk",
    "RagResult",
    "RagStatus",
    "RagStore",
]
