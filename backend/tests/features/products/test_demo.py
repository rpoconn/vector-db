import struct
import zlib
from collections import Counter

from fastapi import FastAPI
from httpx import AsyncClient

from app.features.products.demo import (
    DEMO_CATEGORIES,
    DEMO_IMAGE_COUNT,
    build_demo_catalog,
    png_bytes,
    seed_demo_catalog,
    write_demo_images,
)
from app.shared.config import Settings
from app.shared.database import Database


def test_catalog_is_deterministic_and_spread_across_categories() -> None:
    products = build_demo_catalog(14)

    assert [p.id for p in products] == [p.id for p in build_demo_catalog(14)]
    assert len({p.id for p in products}) == 14
    assert Counter(p.category for p in products) == {
        category.name: 3 if i < 2 else 2 for i, category in enumerate(DEMO_CATEGORIES)
    }
    assert all(len(p.images) == DEMO_IMAGE_COUNT for p in products)
    assert all(p.category.lower() in p.description.lower() for p in products)


def test_png_bytes_is_a_valid_png() -> None:
    data = png_bytes(4, 2, (10, 20, 30))

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    width, height, depth, colour_type = struct.unpack(">IIBB", data[16:26])
    assert (width, height, depth, colour_type) == (4, 2, 8, 2)
    idat_length = struct.unpack(">I", data[33:37])[0]
    pixels = zlib.decompress(data[41 : 41 + idat_length])
    assert pixels == (b"\x00" + bytes((10, 20, 30)) * 4) * 2


def test_write_demo_images_gives_each_angle_a_different_colour(settings: Settings) -> None:
    products = build_demo_catalog(2)

    assert write_demo_images(settings.images_dir, products) == 2 * DEMO_IMAGE_COUNT
    files = [(settings.images_dir / image.path).read_bytes() for image in products[0].images]
    assert all(f.startswith(b"\x89PNG") for f in files)
    assert len(set(files)) == DEMO_IMAGE_COUNT


async def test_seed_demo_catalog_serves_products_and_images(
    app: FastAPI, database: Database, client: AsyncClient
) -> None:
    settings: Settings = app.state.settings
    assert await seed_demo_catalog(database, settings.images_dir, count=7) == 7

    listing = await client.get("/products", params={"limit": 3})
    assert listing.json()["total"] == 7
    product = await client.get(f"/products/{listing.json()['items'][0]['id']}")
    image_url = product.json()["images"][1]["url"]
    image = await client.get(image_url)
    assert image.status_code == 200
    assert image.content.startswith(b"\x89PNG")
