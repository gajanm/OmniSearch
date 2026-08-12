import asyncio
import os

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("PINECONE_API_KEY", "test")
os.environ.setdefault("PINECONE_INDEX_NAME", "test-index")

from fastapi.testclient import TestClient

from app.main import (
    EmbeddingCache,
    EmbeddingService,
    SearchPipeline,
    create_app,
    normalize_query,
)


def test_normalize_query() -> None:
    assert normalize_query("  Hello,   World!! ") == "hello world"


def test_search_response_schema() -> None:
    app = create_app()

    class DummyEmbedding:
        async def get_embedding(self, text: str) -> list[float]:
            return [0.1, 0.2, 0.3]

    class DummyIndex:
        def query(self, vector: list[float], top_k: int, include_metadata: bool) -> dict:
            return {
                "matches": [
                    {
                        "id": "42",
                        "score": 0.87,
                        "metadata": {
                            "title": "Trail Backpack",
                            "description": "Lightweight pack",
                            "category": "outdoors",
                            "price": 79.99,
                        },
                    }
                ]
            }

    app.state.embedding_service = DummyEmbedding()
    app.state.pinecone_index = DummyIndex()
    app.state.search_pipeline = SearchPipeline(
        embedding_service=app.state.embedding_service,
        pinecone_index=app.state.pinecone_index,
    )

    client = TestClient(app)
    response = client.post("/search", json={"query": "backpack", "top_k": 1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["id"] == "42"
    assert payload["results"][0]["score"] == 0.87
    assert payload["results"][0]["title"] == "Trail Backpack"


def test_embedding_cache_behavior() -> None:
    calls = {"count": 0}

    async def fake_fetch(text: str) -> list[float]:
        calls["count"] += 1
        return [0.1, 0.2]

    service = EmbeddingService(
        client=None,
        model="test",
        cache=EmbeddingCache(max_size=2),
        fetch_embedding=fake_fetch,
    )

    async def run() -> None:
        await service.get_embedding("test")
        await service.get_embedding("test")

    asyncio.run(run())
    assert calls["count"] == 1
