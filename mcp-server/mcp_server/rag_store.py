"""RAG store infrastructure with pluggable backends."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Iterable, List, Optional, Sequence
import uuid

import httpx


class RAGError(RuntimeError):
    """Raised when the RAG store or embedding backend cannot fulfil a request."""


@dataclass
class RAGDocument:
    """Result returned by a RAG store query."""

    id: str
    content: str
    score: float
    source: Optional[str] = None
    store: Optional[str] = None


class EmbeddingBackend(ABC):
    """Abstraction around an embedding provider."""

    @abstractmethod
    async def embed(self, text: str) -> List[float]:  # pragma: no cover - interface hook
        raise NotImplementedError


@dataclass
class OllamaEmbeddingBackend(EmbeddingBackend):
    endpoint: str
    model: str
    timeout: float = 30.0

    async def embed(self, text: str) -> List[float]:
        payload = {"model": self.model, "prompt": text}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.endpoint.rstrip('/')}/api/embeddings", json=payload)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:  # pragma: no cover - network failure best-effort
                raise RAGError(str(exc)) from exc
            data = resp.json()
        embedding = data.get("embedding")
        if not embedding:
            raise RAGError("Ollama embeddings response missing 'embedding'")
        return [float(x) for x in embedding]


class BaseRAGStore(ABC):
    """Interface for storage backends that support upsert and similarity query."""

    def __init__(self, embedder: EmbeddingBackend, name: str) -> None:
        self._embedder = embedder
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    async def upsert(
        self,
        *,
        source: Optional[str],
        content: str,
        store: Optional[str] = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def query(
        self,
        *,
        text: str,
        limit: int = 3,
        embedding: Optional[List[float]] = None,
        stores: Optional[Sequence[str]] = None,
    ) -> List[RAGDocument]:
        raise NotImplementedError


class SQLiteRAGStore(BaseRAGStore):
    """SQLite-backed persistent store."""

    def __init__(self, db_path: Path, embedder: EmbeddingBackend, *, name: Optional[str] = None) -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        super().__init__(embedder, name or f"sqlite:{path}")
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = RLock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT,
                    content TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._conn.commit()

    async def upsert(
        self,
        *,
        source: Optional[str],
        content: str,
        store: Optional[str] = None,
    ) -> str:
        embedding = await self._embedder.embed(content)
        doc_id = await asyncio.to_thread(self._insert_document, source, content, embedding)
        return str(doc_id)

    def _insert_document(self, source: Optional[str], content: str, embedding: Iterable[float]) -> int:
        vector_json = json.dumps(list(embedding))
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO rag_documents (source, content, embedding) VALUES (?, ?, ?)",
                (source, content, vector_json),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    async def query(
        self,
        *,
        text: str,
        limit: int = 3,
        embedding: Optional[List[float]] = None,
        stores: Optional[Sequence[str]] = None,
    ) -> List[RAGDocument]:
        query_vec = embedding or await self._embedder.embed(text)
        rows = await asyncio.to_thread(self._fetch_rows)
        docs: List[RAGDocument] = []
        for row in rows:
            doc_vec = json.loads(row["embedding"])
            score = _cosine_similarity(query_vec, doc_vec)
            docs.append(
                RAGDocument(
                    id=str(row["id"]),
                    source=row["source"],
                    content=row["content"],
                    score=score,
                    store=self.name,
                )
            )
        docs.sort(key=lambda item: item.score, reverse=True)
        return docs[: max(0, limit)]

    def _fetch_rows(self) -> List[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute("SELECT id, source, content, embedding FROM rag_documents")
            return cur.fetchall()


class InMemoryRAGStore(BaseRAGStore):
    """Ephemeral in-memory store useful for transient or file based docs."""

    def __init__(self, embedder: EmbeddingBackend, *, name: str = "memory") -> None:
        super().__init__(embedder, name)
        self._lock = RLock()
        self._docs: dict[str, dict[str, Iterable[float] | str | None]] = {}

    async def upsert(
        self,
        *,
        source: Optional[str],
        content: str,
        store: Optional[str] = None,
    ) -> str:
        embedding = await self._embedder.embed(content)
        doc_id = str(uuid.uuid4())
        with self._lock:
            self._docs[doc_id] = {
                "source": source,
                "content": content,
                "embedding": list(embedding),
            }
        return doc_id

    async def query(
        self,
        *,
        text: str,
        limit: int = 3,
        embedding: Optional[List[float]] = None,
        stores: Optional[Sequence[str]] = None,
    ) -> List[RAGDocument]:
        query_vec = embedding or await self._embedder.embed(text)
        with self._lock:
            items = list(self._docs.items())
        docs: List[RAGDocument] = []
        for doc_id, payload in items:
            doc_vec = payload["embedding"]
            score = _cosine_similarity(query_vec, doc_vec)
            docs.append(
                RAGDocument(
                    id=doc_id,
                    source=payload["source"],
                    content=payload["content"],
                    score=score,
                    store=self.name,
                )
            )
        docs.sort(key=lambda item: item.score, reverse=True)
        return docs[: max(0, limit)]


class CompositeRAGStore(BaseRAGStore):
    """Aggregate multiple stores into a single entry point."""

    def __init__(
        self,
        stores: Sequence[BaseRAGStore],
        embedder: EmbeddingBackend,
        *,
        name: str = "composite",
    ) -> None:
        if not stores:
            raise RAGError("CompositeRAGStore requires at least one store")
        super().__init__(embedder, name)
        self._stores = {store.name: store for store in stores}
        self._default = stores[0]

    @property
    def store_names(self) -> List[str]:
        return list(self._stores.keys())

    async def upsert(
        self,
        *,
        source: Optional[str],
        content: str,
        store: Optional[str] = None,
    ) -> str:
        target = self._default if store is None else self._stores.get(store)
        if target is None:
            raise RAGError(f"Unknown store '{store}'")
        doc_id = await target.upsert(source=source, content=content)
        return f"{target.name}:{doc_id}"

    async def query(
        self,
        *,
        text: str,
        limit: int = 3,
        embedding: Optional[List[float]] = None,
        stores: Optional[Sequence[str]] = None,
    ) -> List[RAGDocument]:
        selected: List[BaseRAGStore]
        if stores:
            selected = []
            for name in stores:
                store = self._stores.get(name)
                if store is None:
                    raise RAGError(f"Unknown store '{name}'")
                selected.append(store)
        else:
            selected = list(self._stores.values())

        query_vec = embedding or await self._embedder.embed(text)
        docs: List[RAGDocument] = []
        for store in selected:
            results = await store.query(text=text, limit=limit, embedding=query_vec)
            for doc in results:
                docs.append(
                    RAGDocument(
                        id=f"{store.name}:{doc.id}",
                        source=doc.source,
                        content=doc.content,
                        score=doc.score,
                        store=store.name,
                    )
                )
        docs.sort(key=lambda item: item.score, reverse=True)
        return docs[: max(0, limit)]


def _cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    a_list = list(a)
    b_list = list(b)
    if not a_list or not b_list:
        return 0.0
    if len(a_list) != len(b_list):
        raise RAGError("Embedding dimensionality mismatch")
    dot = sum(x * y for x, y in zip(a_list, b_list))
    norm_a = sum(x * x for x in a_list) ** 0.5
    norm_b = sum(y * y for y in b_list) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_default_store() -> BaseRAGStore:
    endpoint = os.getenv("OLLAMA_ENDPOINT")
    if not endpoint:
        raise RAGError("OLLAMA_ENDPOINT is required to use RAG embeddings")
    model = os.getenv("RAG_EMBED_MODEL") or os.getenv("OLLAMA_MODEL") or "llama3"
    embedder = OllamaEmbeddingBackend(endpoint=endpoint, model=model)

    raw_sources = os.getenv("RAG_SOURCES")
    if raw_sources:
        try:
            config = json.loads(raw_sources)
        except json.JSONDecodeError as exc:
            raise RAGError("RAG_SOURCES must be valid JSON") from exc
        if not isinstance(config, list):
            raise RAGError("RAG_SOURCES must be a JSON array")
        stores: List[BaseRAGStore] = []
        for idx, entry in enumerate(config):
            if not isinstance(entry, dict):
                raise RAGError("Each RAG source must be an object")
            kind = entry.get("type", "sqlite").lower()
            name = entry.get("name")
            if kind == "sqlite":
                path = entry.get("path")
                if not path:
                    raise RAGError("sqlite RAG source requires 'path'")
                stores.append(SQLiteRAGStore(Path(path), embedder, name=name))
            elif kind == "memory":
                stores.append(InMemoryRAGStore(embedder, name=name or f"memory:{idx}"))
            else:
                raise RAGError(f"Unsupported RAG source type '{kind}'")
        if not stores:
            raise RAGError("RAG_SOURCES did not yield any stores")
        if len(stores) == 1:
            return stores[0]
        return CompositeRAGStore(stores=stores, embedder=embedder)

    db_path = Path(os.getenv("RAG_DB_PATH", "rag_store.db"))
    return SQLiteRAGStore(db_path, embedder)


__all__ = [
    "BaseRAGStore",
    "CompositeRAGStore",
    "EmbeddingBackend",
    "InMemoryRAGStore",
    "OllamaEmbeddingBackend",
    "RAGDocument",
    "RAGError",
    "SQLiteRAGStore",
    "build_default_store",
]
