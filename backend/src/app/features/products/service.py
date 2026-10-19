"""Catalog use cases. Other features read products only through this module."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.products.repository import ProductRepository
from app.features.products.schemas import (
    CategoryOut,
    ProductDetail,
    ProductIndexEntry,
    ProductListParams,
    ProductSummary,
)
from app.shared.database import get_session
from app.shared.pagination import Page


class ProductNotFoundError(Exception):
    def __init__(self, product_id: str) -> None:
        super().__init__(f"Product {product_id!r} not found")
        self.product_id = product_id


class ProductService:
    def __init__(self, repository: ProductRepository) -> None:
        self._repository = repository

    async def list_products(self, params: ProductListParams) -> Page[ProductSummary]:
        products, total = await self._repository.list_page(
            category=params.category, limit=params.limit, offset=params.offset
        )
        return Page[ProductSummary](
            items=[ProductSummary.from_model(product) for product in products],
            total=total,
            limit=params.limit,
            offset=params.offset,
        )

    async def get_product(self, product_id: str) -> ProductDetail:
        product = await self._repository.get(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        return ProductDetail.from_model(product)

    async def get_by_ids(self, product_ids: Sequence[str]) -> list[ProductSummary]:
        """Summaries in the order of `product_ids` (e.g. search ranking); unknown ids skipped."""
        products = await self._repository.get_by_ids(product_ids)
        return [ProductSummary.from_model(product) for product in products]

    async def list_index_entries(self) -> list[ProductIndexEntry]:
        """Searchable fields of the whole catalog, ordered by id."""
        return [ProductIndexEntry.from_model(p) for p in await self._repository.list_all()]

    async def list_categories(self) -> list[CategoryOut]:
        return [
            CategoryOut(name=name, product_count=count)
            for name, count in await self._repository.categories()
        ]


def build_product_service(session: AsyncSession) -> ProductService:
    return ProductService(ProductRepository(session))


def get_product_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ProductService:
    return build_product_service(session)
