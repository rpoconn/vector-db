import pytest

from app.features.products.repository import ProductRepository
from app.features.products.service import ProductNotFoundError, ProductService
from app.shared.database import Database


async def test_get_by_ids_returns_summaries_in_requested_order(
    database: Database, catalog: list[str]
) -> None:
    async with database.session_factory() as session:
        service = ProductService(ProductRepository(session))
        summaries = await service.get_by_ids([catalog[3], catalog[0]])

    assert [summary.id for summary in summaries] == [catalog[3], catalog[0]]
    assert summaries[0].thumbnail is not None
    assert summaries[0].thumbnail.url == f"/images/{catalog[3]}/0.jpg"


async def test_get_product_raises_for_unknown_id(database: Database) -> None:
    async with database.session_factory() as session:
        service = ProductService(ProductRepository(session))
        with pytest.raises(ProductNotFoundError) as excinfo:
            await service.get_product("missing")

    assert excinfo.value.product_id == "missing"
