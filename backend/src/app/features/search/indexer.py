"""Builds the in-memory search index from the catalog, reusing cached embeddings."""

import hashlib
import logging
import time
from dataclasses import dataclass

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.products.schemas import ProductIndexEntry
from app.features.products.service import build_product_service
from app.features.search.embedding import Embedder, create_embedder
from app.features.search.models import ProductEmbedding
from app.features.search.repository import EmbeddingCacheRepository
from app.features.search.vector_store import (
    Metadata,
    VectorMatch,
    VectorStore,
    create_vector_store,
)
from app.features.search.vectors import from_blob, to_blob
from app.shared.config import Settings

logger = logging.getLogger(__name__)

EMBED_CHUNK_SIZE = 512
"""Products embedded (and cached) per step, so progress is logged and survives interruption."""


def document_text(entry: ProductIndexEntry) -> str:
    """The text embedded for a product."""
    parts = [entry.name, entry.brand, entry.category, entry.color, entry.description]
    return "\n".join(part for part in parts if part)


def document_metadata(entry: ProductIndexEntry) -> Metadata:
    """Filterable fields stored next to each vector."""
    metadata: dict[str, str | float] = {
        "category": entry.category,
        "price": entry.price_cents / 100,
    }
    if entry.brand:
        metadata["brand"] = entry.brand
    return metadata


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class IndexStats:
    indexed: int
    embedded: int
    seconds: float


class SearchIndex:
    """An embedder paired with the vector store holding the catalog's document vectors."""

    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self.embedder = embedder
        self.store = store

    async def query(self, text: str, k: int, where: Metadata | None = None) -> list[VectorMatch]:
        vector = await self.embedder.embed_query(text)
        return await self.store.query(vector, k, where)

    async def rebuild(self, session: AsyncSession) -> IndexStats:
        """Sync the store with the catalog, embedding only products missing from the cache."""
        started = time.perf_counter()
        await self.embedder.load()
        model = self.embedder.model_name
        entries = await build_product_service(session).list_index_entries()
        texts = {entry.id: document_text(entry) for entry in entries}
        hashes = {item_id: text_hash(text) for item_id, text in texts.items()}
        cache = EmbeddingCacheRepository(session)
        cached = await cache.load(model)

        await cache.delete(model, cached.keys() - texts.keys())
        stale = [
            entry
            for entry in entries
            if entry.id not in cached or cached[entry.id].text_hash != hashes[entry.id]
        ]
        if stale:
            logger.info("Embedding %d of %d products with %s", len(stale), len(entries), model)
        for start in range(0, len(stale), EMBED_CHUNK_SIZE):
            chunk = stale[start : start + EMBED_CHUNK_SIZE]
            vectors = await self.embedder.embed_documents([texts[entry.id] for entry in chunk])
            rows = [
                ProductEmbedding(
                    product_id=entry.id,
                    model=model,
                    text_hash=hashes[entry.id],
                    vector=to_blob(vector),
                )
                for entry, vector in zip(chunk, vectors, strict=True)
            ]
            await cache.save(model, rows)
            await session.commit()
            cached.update((row.product_id, row) for row in rows)
            logger.info("Embedded %d/%d products", start + len(chunk), len(stale))
        await session.commit()

        ids = [entry.id for entry in entries]
        await self.store.delete(sorted(await self.store.ids() - set(ids)))
        if entries:
            matrix = np.stack([from_blob(cached[item_id].vector) for item_id in ids])
            await self.store.upsert(ids, matrix, [document_metadata(entry) for entry in entries])

        stats = IndexStats(len(entries), len(stale), time.perf_counter() - started)
        if stats.indexed:
            logger.info(
                "Indexed %d products (%d newly embedded) in %.2fs",
                stats.indexed,
                stats.embedded,
                stats.seconds,
            )
        else:
            logger.warning("Search index is empty: no products; run scripts/seed_products.py")
        return stats


def create_search_index(settings: Settings) -> SearchIndex:
    embedder = create_embedder(settings)
    return SearchIndex(embedder, create_vector_store(settings, embedder.dimension))
