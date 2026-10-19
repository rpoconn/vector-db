import numpy as np
import pytest
from httpx import AsyncClient

from app.features.products.service import build_product_service
from app.features.search.indexer import SearchIndex
from app.features.search.schemas import SearchParams
from app.features.search.service import SearchService
from app.shared.database import Database

from ...catalog import CATALOG_SIZE


async def test_search_ranks_matching_products_first(
    client: AsyncClient, indexed_catalog: list[str]
) -> None:
    response = await client.get("/search", params={"q": "lamp"})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "lamp"
    hits = body["hits"]
    assert len(hits) == CATALOG_SIZE
    lamps = CATALOG_SIZE // 4
    assert {hit["product"]["category"] for hit in hits[:lamps]} == {"Lamp"}
    assert "Lamp" not in {hit["product"]["category"] for hit in hits[lamps:]}
    scores = [hit["score"] for hit in hits]
    assert scores == sorted(scores, reverse=True)
    assert hits[0]["product"]["thumbnail"]["url"].startswith("/images/")


async def test_search_respects_limit_and_category(
    client: AsyncClient, indexed_catalog: list[str]
) -> None:
    body = (
        await client.get("/search", params={"q": "  lamp  ", "category": "Rug", "limit": 3})
    ).json()

    assert body["query"] == "lamp"
    assert len(body["hits"]) == 3
    assert {hit["product"]["category"] for hit in body["hits"]} == {"Rug"}


async def test_search_on_empty_index_returns_no_hits(client: AsyncClient) -> None:
    response = await client.get("/search", params={"q": "lamp"})

    assert response.status_code == 200
    assert response.json() == {"query": "lamp", "hits": []}


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"q": ""},
        {"q": "   "},
        {"q": "x" * 501},
        {"q": "lamp", "limit": 0},
        {"q": "lamp", "limit": 101},
    ],
)
async def test_search_rejects_invalid_params(
    client: AsyncClient, params: dict[str, str | int]
) -> None:
    response = await client.get("/search", params=params)

    assert response.status_code == 422


async def test_search_skips_vectors_without_a_product(
    database: Database, search_index: SearchIndex, indexed_catalog: list[str]
) -> None:
    vector = await search_index.embedder.embed_query("lamp")
    await search_index.store.upsert(["ghost"], np.stack([vector]), [{"category": "Lamp"}])

    async with database.session_factory() as session:
        service = SearchService(search_index, build_product_service(session))
        response = await service.search(SearchParams(q="lamp", limit=3))

    assert len(response.hits) == 2
    assert "ghost" not in {hit.product.id for hit in response.hits}


async def test_openapi_documents_search(client: AsyncClient) -> None:
    spec = (await client.get("/openapi.json")).json()

    operation = spec["paths"]["/search"]["get"]
    assert [parameter["name"] for parameter in operation["parameters"]] == [
        "q",
        "category",
        "limit",
    ]
    assert "SearchResponse" in spec["components"]["schemas"]
