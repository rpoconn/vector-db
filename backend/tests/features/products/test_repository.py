from app.features.products.repository import ProductRepository
from app.shared.database import Database

from ...catalog import CATALOG_SIZE, make_product


async def test_list_page_orders_by_id_and_counts_total(
    database: Database, catalog: list[str]
) -> None:
    async with database.session_factory() as session:
        products, total = await ProductRepository(session).list_page(
            category=None, limit=5, offset=5
        )

    assert total == CATALOG_SIZE
    assert [p.id for p in products] == sorted(catalog)[5:10]


async def test_list_page_filters_by_category(database: Database, catalog: list[str]) -> None:
    async with database.session_factory() as session:
        products, total = await ProductRepository(session).list_page(
            category="Rug", limit=100, offset=0
        )

    assert total == CATALOG_SIZE // 4
    assert {p.category for p in products} == {"Rug"}


async def test_get_loads_images_in_position_order(database: Database, catalog: list[str]) -> None:
    async with database.session_factory() as session:
        product = await ProductRepository(session).get(catalog[0])

    assert product is not None
    assert [image.position for image in product.images] == [0, 1, 2]


async def test_get_unknown_id_returns_none(database: Database, catalog: list[str]) -> None:
    async with database.session_factory() as session:
        assert await ProductRepository(session).get("missing") is None


async def test_get_by_ids_preserves_requested_order_and_skips_unknown(
    database: Database, catalog: list[str]
) -> None:
    requested = [catalog[7], "missing", catalog[2], catalog[11]]

    async with database.session_factory() as session:
        products = await ProductRepository(session).get_by_ids(requested)

    assert [p.id for p in products] == [catalog[7], catalog[2], catalog[11]]


async def test_get_by_ids_with_no_ids(database: Database) -> None:
    async with database.session_factory() as session:
        assert await ProductRepository(session).get_by_ids([]) == []


async def test_categories_are_counted_alphabetically(
    database: Database, catalog: list[str]
) -> None:
    async with database.session_factory() as session:
        categories = await ProductRepository(session).categories()

    assert categories == [("Grocery", 5), ("Lamp", 5), ("Rug", 5), ("Sofa", 5)]


async def test_replace_all_drops_previous_catalog(database: Database, catalog: list[str]) -> None:
    async with database.session_factory() as session:
        await ProductRepository(session).replace_all([make_product(500, image_count=2)])
        await session.commit()

    async with database.session_factory() as session:
        repository = ProductRepository(session)
        products, total = await repository.list_page(category=None, limit=100, offset=0)
        assert total == 1
        assert [image.path for image in products[0].images] == ["P0500/0.jpg", "P0500/1.jpg"]
