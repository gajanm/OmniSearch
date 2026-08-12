import asyncio
import json
import os
from pathlib import Path
from typing import List

from openai import AsyncOpenAI
from pinecone import Pinecone

DATA_PATH = Path(__file__).parent / "data" / "sample_products.json"


def load_products() -> List[dict]:
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


async def embed_batch(client: AsyncOpenAI, model: str, texts: List[str]) -> List[List[float]]:
    response = await client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


async def main() -> None:
    openai_key = os.environ.get("OPENAI_API_KEY")
    pinecone_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME")

    if not openai_key or not pinecone_key or not index_name:
        raise RuntimeError("Missing OPENAI_API_KEY, PINECONE_API_KEY, or PINECONE_INDEX_NAME")

    openai_model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    client = AsyncOpenAI(api_key=openai_key)
    pinecone = Pinecone(api_key=pinecone_key)
    index = pinecone.Index(index_name)

    products = load_products()
    batch_size = 25

    for start in range(0, len(products), batch_size):
        batch = products[start : start + batch_size]
        texts = [f"{item['title']}. {item['description']}" for item in batch]
        embeddings = await embed_batch(client, openai_model, texts)

        vectors = []
        for product, embedding in zip(batch, embeddings):
            vectors.append(
                {
                    "id": str(product["id"]),
                    "values": embedding,
                    "metadata": {
                        "title": product["title"],
                        "description": product["description"],
                        "category": product["category"],
                        "price": product["price"],
                    },
                }
            )

        index.upsert(vectors=vectors)
        print(f"Seeded {start + len(batch)} / {len(products)} products")


if __name__ == "__main__":
    asyncio.run(main())
