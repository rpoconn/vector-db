from pathlib import Path

import pytest
from httpx import AsyncClient

from app.shared.config import Settings

from .conftest import CATALOG_SIZE


async def test_list_products_returns_a_page_of_summaries(
    client: AsyncClient, catalog: list[str]
) -> None:
    response = await client.get("/products", params={"limit": 3, "offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == CATALOG_SIZE
    assert (body["limit"], body["offset"]) == (3, 2)
    assert [item["id"] for item in body["items"]] == sorted(catalog)[2:5]
    first = body["items"][0]
    assert first["thumbnail"] == {
        "position": 0,
        "url": f"/images/{first['id']}/0.jpg",
        "width": 256,
        "height": 200,
    }
    assert "description" not in first


async def test_list_products_defaults_to_24_per_page(
    client: AsyncClient, catalog: list[str]
) -> None:
    body = (await client.get("/products")).json()

    assert (body["limit"], body["offset"]) == (24, 0)
    assert len(body["items"]) == CATALOG_SIZE


async def test_list_products_filters_by_category(client: AsyncClient, catalog: list[str]) -> None:
    body = (await client.get("/products", params={"category": "Sofa"})).json()

    assert body["total"] == CATALOG_SIZE // 4
    assert {item["category"] for item in body["items"]} == {"Sofa"}


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"category": ""}],
)
async def test_list_products_rejects_invalid_params(
    client: AsyncClient, params: dict[str, int | str]
) -> None:
    response = await client.get("/products", params=params)

    assert response.status_code == 422


async def test_get_product_returns_detail_with_all_images(
    client: AsyncClient, catalog: list[str]
) -> None:
    response = await client.get(f"/products/{catalog[1]}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == catalog[1]
    assert body["description"] == "Description of product 1"
    assert body["source_url"].endswith(catalog[1])
    assert [image["url"] for image in body["images"]] == [
        f"/images/{catalog[1]}/{position}.jpg" for position in range(3)
    ]
    assert body["thumbnail"] == body["images"][0]


async def test_get_unknown_product_is_404(client: AsyncClient) -> None:
    response = await client.get("/products/nope")

    assert response.status_code == 404
    assert response.json() == {"detail": "Product 'nope' not found"}


async def test_list_categories(client: AsyncClient, catalog: list[str]) -> None:
    response = await client.get("/categories")

    assert response.status_code == 200
    assert response.json() == [
        {"name": name, "product_count": 5} for name in ("Grocery", "Lamp", "Rug", "Sofa")
    ]


async def test_images_are_served_from_images_dir(client: AsyncClient, settings: Settings) -> None:
    image = Path(settings.images_dir) / "P0001" / "0.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"jpeg-bytes")

    response = await client.get("/images/P0001/0.jpg")

    assert response.status_code == 200
    assert response.content == b"jpeg-bytes"
    assert response.headers["content-type"] == "image/jpeg"


async def test_openapi_documents_catalog_endpoints(client: AsyncClient) -> None:
    spec = (await client.get("/openapi.json")).json()

    assert {"/products", "/products/{product_id}", "/categories"} <= spec["paths"].keys()
    parameters = spec["paths"]["/products"]["get"]["parameters"]
    assert [parameter["name"] for parameter in parameters] == ["limit", "offset", "category"]
