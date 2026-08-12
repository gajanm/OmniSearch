import logging
import os
import re
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable, List, Optional
from fastapi.middleware.cors import CORSMiddleware

import anyio
from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI
from pinecone import Pinecone
from pydantic import BaseModel, Field

logger = logging.getLogger("omnisearch")
logging.basicConfig(level=logging.INFO)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)


class SearchResult(BaseModel):
    id: str
    score: float
    title: str
    description: str
    category: str
    price: float


class SearchResponse(BaseModel):
    results: List[SearchResult]


def normalize_query(query: str) -> str:
    normalized = query.strip().lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


class EmbeddingCache:
    def __init__(self, max_size: int = 512) -> None:
        self.max_size = max_size
        self._store: OrderedDict[str, List[float]] = OrderedDict()

    def get(self, key: str) -> Optional[List[float]]:
        if key in self._store:
            self._store.move_to_end(key)
            return self._store[key]
        return None

    def set(self, key: str, value: List[float]) -> None:
        self._store[key] = value
        self._store.move_to_end(key)
        if len(self._store) > self.max_size:
            self._store.popitem(last=False)


class EmbeddingService:
    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        cache: EmbeddingCache,
        fetch_embedding: Optional[Callable[[str], Awaitable[List[float]]]] = None,
    ) -> None:
        self.client = client
        self.model = model
        self.cache = cache
        self._fetch_embedding = fetch_embedding or self._fetch_from_openai

    async def _fetch_from_openai(self, text: str) -> List[float]:
        response = await self.client.embeddings.create(model=self.model, input=text)
        return response.data[0].embedding

    async def get_embedding(self, text: str) -> List[float]:
        cached = self.cache.get(text)
        if cached is not None:
            return cached
        embedding = await self._fetch_embedding(text)
        self.cache.set(text, embedding)
        return embedding


class SearchPipeline:
    def __init__(self, embedding_service: EmbeddingService, pinecone_index: Any) -> None:
        self.embedding_service = embedding_service
        self.pinecone_index = pinecone_index

    async def run(self, query: str, top_k: int) -> List[SearchResult]:
        started = time.perf_counter()
        normalized = normalize_query(query)
        normalize_time = time.perf_counter()

        embedding = await self.embedding_service.get_embedding(normalized)
        embed_time = time.perf_counter()

        response = await anyio.to_thread.run_sync(
            self.pinecone_index.query,
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
        )
        pinecone_time = time.perf_counter()

        results: List[SearchResult] = []
        for match in response.get("matches", []):
            metadata = match.get("metadata", {}) or {}
            results.append(
                SearchResult(
                    id=str(match.get("id")),
                    score=float(match.get("score", 0.0)),
                    title=str(metadata.get("title", "")),
                    description=str(metadata.get("description", "")),
                    category=str(metadata.get("category", "")),
                    price=float(metadata.get("price", 0.0)),
                )
            )

        total_time = time.perf_counter() - started
        logger.info(
            "search timing total=%.3fs normalize=%.3fs embed=%.3fs pinecone=%.3fs",
            total_time,
            normalize_time - started,
            embed_time - normalize_time,
            pinecone_time - embed_time,
        )
        return results


def _create_openai_client() -> AsyncOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    return AsyncOpenAI(api_key=api_key)


def _create_pinecone_index() -> Any:
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME")
    if not api_key or not index_name:
        raise RuntimeError("PINECONE_API_KEY and PINECONE_INDEX_NAME are required")
    pinecone = Pinecone(api_key=api_key)
    return pinecone.Index(index_name)


def create_app() -> FastAPI:
    app = FastAPI(title="OmniSearch API")
    app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

    openai_model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    app.state.embedding_service = EmbeddingService(
        client=_create_openai_client(),
        model=openai_model,
        cache=EmbeddingCache(max_size=512),
    )
    app.state.pinecone_index = _create_pinecone_index()
    app.state.search_pipeline = SearchPipeline(
        embedding_service=app.state.embedding_service,
        pinecone_index=app.state.pinecone_index,
    )

    @app.post("/search", response_model=SearchResponse)
    async def search(request: SearchRequest) -> SearchResponse:
        try:
            results = await app.state.search_pipeline.run(request.query, request.top_k)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail="Search failed") from exc

        return SearchResponse(results=results)

    return app


app = create_app()
