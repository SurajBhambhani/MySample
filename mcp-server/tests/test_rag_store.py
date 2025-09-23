from pathlib import Path

import pytest

from mcp_server.rag_store import (
    CompositeRAGStore,
    EmbeddingBackend,
    InMemoryRAGStore,
    SQLiteRAGStore,
)


class DummyEmbedder(EmbeddingBackend):
    async def embed(self, text: str):
        # deterministic embedding based on character ordinals
        return [float(len(text)), float(sum(ord(ch) for ch in text) % 1000)]


@pytest.mark.asyncio
async def test_upsert_and_query(tmp_path: Path):
    embedder = DummyEmbedder()
    store = SQLiteRAGStore(tmp_path / "rag.db", embedder)

    doc1 = await store.upsert(source="doc1", content="hello world")
    doc2 = await store.upsert(source="doc2", content="fast api relay")

    results = await store.query(text="hello", limit=2)

    assert [doc.id for doc in results] == [doc1, doc2]
    assert results[0].source == "doc1"
    assert results[0].score >= results[1].score


@pytest.mark.asyncio
async def test_query_limit(tmp_path: Path):
    embedder = DummyEmbedder()
    store = SQLiteRAGStore(tmp_path / "rag.db", embedder)
    for idx in range(5):
        await store.upsert(source=f"doc{idx}", content=f"content {idx}")

    results = await store.query(text="content", limit=3)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_composite_store_queries_all_sources(tmp_path: Path):
    embedder = DummyEmbedder()
    store_a = SQLiteRAGStore(tmp_path / "a.db", embedder, name="alpha")
    store_b = InMemoryRAGStore(embedder, name="beta")
    composite = CompositeRAGStore([store_a, store_b], embedder)

    await composite.upsert(source="docA", content="alpha content", store="alpha")
    await composite.upsert(source="docB", content="beta content", store="beta")

    results = await composite.query(text="content", limit=5)
    stores = {doc.store for doc in results}
    assert stores == {"alpha", "beta"}
    assert any(doc.source == "docA" for doc in results)
    assert any(doc.source == "docB" for doc in results)

    alpha_only = await composite.query(text="content", limit=5, stores=["alpha"])
    assert {doc.store for doc in alpha_only} == {"alpha"}
