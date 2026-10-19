"""Persistence for the embedding cache. The only module that touches `product_embeddings`."""

from collections.abc import Collection, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.search.models import ProductEmbedding


class EmbeddingCacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, model: str) -> dict[str, ProductEmbedding]:
        """Cached embeddings for `model`, keyed by product id."""
        rows = await self._session.scalars(
            select(ProductEmbedding).where(ProductEmbedding.model == model)
        )
        return {row.product_id: row for row in rows}

    async def save(self, model: str, embeddings: Sequence[ProductEmbedding]) -> None:
        """Insert or replace `model`'s cache rows (caller commits)."""
        await self.delete(model, [embedding.product_id for embedding in embeddings])
        self._session.add_all(embeddings)
        await self._session.flush()

    async def delete(self, model: str, product_ids: Collection[str]) -> None:
        if product_ids:
            await self._session.execute(
                delete(ProductEmbedding).where(
                    ProductEmbedding.model == model,
                    ProductEmbedding.product_id.in_(product_ids),
                )
            )
