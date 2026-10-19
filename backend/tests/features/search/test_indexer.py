import numpy as np
from sqlalchemy import select, update

from app.features.products.models import Product
from app.features.products.schemas import ProductIndexEntry
from app.features.search.indexer import (
    SearchIndex,
    document_metadata,
    document_text,
)
from app.features.search.models import ProductEmbedding
from app.features.search.vector_store import NumpyVectorStore
from app.shared.database import Database

from ...catalog import CATALOG_SIZE
from .conftest import CountingEmbedder

ENTRY = ProductIndexEntry(
    id="P1",
    name="Brass Lamp",
    brand=None,
    category="Lamp",
    color="Gold",
    description="Bright\nDimmable",
    price_cents=4999,
)


def _index() -> tuple[SearchIndex, CountingEmbedder, NumpyVectorStore]:
    embedder = CountingEmbedder()
    store = NumpyVectorStore(embedder.dimension)
    return SearchIndex(embedder, store), embedder, store


def test_document_text_joins_present_fields() -> None:
    assert document_text(ENTRY) == "Brass Lamp\nLamp\nGold\nBright\nDimmable"


def test_document_metadata_omits_missing_brand() -> None:
    assert document_metadata(ENTRY) == {"category": "Lamp", "price": 49.99}
    assert document_metadata(ENTRY.model_copy(update={"brand": "Rivet"}))["brand"] == "Rivet"


async def test_rebuild_embeds_and_indexes_whole_catalog(
    database: Database, catalog: list[str]
) -> None:
    index, embedder, store = _index()

    async with database.session_factory() as session:
        stats = await index.rebuild(session)
        cached = (await session.scalars(select(ProductEmbedding))).all()

    assert (stats.indexed, stats.embedded) == (CATALOG_SIZE, CATALOG_SIZE)
    assert len(embedder.embedded) == CATALOG_SIZE
    assert await store.ids() == set(catalog)
    assert {row.product_id for row in cached} == set(catalog)
    assert {row.model for row in cached} == {embedder.model_name}


async def test_rebuild_reuses_cached_embeddings(database: Database, catalog: list[str]) -> None:
    async with database.session_factory() as session:
        await _index()[0].rebuild(session)

    index, embedder, store = _index()  # e.g. after a restart: empty store, warm cache
    async with database.session_factory() as session:
        stats = await index.rebuild(session)

    assert (stats.indexed, stats.embedded) == (CATALOG_SIZE, 0)
    assert embedder.embedded == []
    assert await store.count() == CATALOG_SIZE
    matches = await index.query("Lamp", k=1)
    assert matches[0].score > 0


async def test_rebuild_reembeds_only_changed_products(
    database: Database, catalog: list[str]
) -> None:
    index, embedder, _ = _index()
    async with database.session_factory() as session:
        await index.rebuild(session)
        await session.execute(
            update(Product).where(Product.id == catalog[0]).values(name="Velvet sofa")
        )
        await session.commit()
        embedder.embedded.clear()

        stats = await index.rebuild(session)

    assert stats.embedded == 1
    assert len(embedder.embedded) == 1
    assert embedder.embedded[0].startswith("Velvet sofa")


async def test_rebuild_drops_removed_products_from_store_and_cache(
    database: Database, catalog: list[str]
) -> None:
    index, _, store = _index()
    async with database.session_factory() as session:
        await index.rebuild(session)
        await session.delete(await session.get_one(Product, catalog[0]))
        await session.commit()

        stats = await index.rebuild(session)
        cached_ids = set(await session.scalars(select(ProductEmbedding.product_id)))

    assert stats.indexed == CATALOG_SIZE - 1
    assert catalog[0] not in await store.ids()
    assert catalog[0] not in cached_ids


async def test_rebuild_of_empty_catalog_empties_store(database: Database) -> None:
    index, _, store = _index()
    stale_vector = np.ones((1, index.embedder.dimension), dtype=np.float32)
    await store.upsert(["stale"], stale_vector, [{"category": "X"}])

    async with database.session_factory() as session:
        stats = await index.rebuild(session)

    assert (stats.indexed, stats.embedded) == (0, 0)
    assert await store.count() == 0
