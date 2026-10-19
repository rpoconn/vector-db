"""Persistence queries for products. The only module that touches the product tables."""

from collections.abc import Sequence

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.products.models import Product, ProductImage


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _with_images() -> Select[tuple[Product]]:
        return select(Product).options(selectinload(Product.images))

    async def list_page(
        self, *, category: str | None, limit: int, offset: int
    ) -> tuple[Sequence[Product], int]:
        """One page of products ordered by id, plus the total matching count."""
        filters = [Product.category == category] if category is not None else []
        total = await self._session.scalar(select(func.count(Product.id)).where(*filters))
        rows = await self._session.scalars(
            self._with_images().where(*filters).order_by(Product.id).limit(limit).offset(offset)
        )
        return rows.all(), total or 0

    async def list_all(self) -> Sequence[Product]:
        """Every product ordered by id, without images."""
        rows = await self._session.scalars(select(Product).order_by(Product.id))
        return rows.all()

    async def get(self, product_id: str) -> Product | None:
        rows = await self._session.scalars(self._with_images().where(Product.id == product_id))
        return rows.one_or_none()

    async def get_by_ids(self, product_ids: Sequence[str]) -> list[Product]:
        """Products for `product_ids` in the given order; unknown ids are skipped."""
        if not product_ids:
            return []
        rows = await self._session.scalars(self._with_images().where(Product.id.in_(product_ids)))
        by_id = {product.id: product for product in rows}
        return [by_id[product_id] for product_id in product_ids if product_id in by_id]

    async def categories(self) -> list[tuple[str, int]]:
        """Distinct categories with their product counts, alphabetically."""
        rows = await self._session.execute(
            select(Product.category, func.count(Product.id))
            .group_by(Product.category)
            .order_by(Product.category)
        )
        return [(category, count) for category, count in rows.tuples()]

    async def replace_all(self, products: Sequence[Product]) -> None:
        """Swap the whole catalog for `products` (caller commits)."""
        await self._session.execute(delete(ProductImage))
        await self._session.execute(delete(Product))
        self._session.add_all(products)
        await self._session.flush()
