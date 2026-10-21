"""A small synthetic catalog with generated images, for end-to-end tests and quick demos.

No dataset download is needed: products are built from word lists per category, and each
gets a few solid-colour PNG "angles" so the gallery has something to switch between.
Everything is deterministic, so specs can rely on names and categories.
"""

import logging
import struct
import zlib
from pathlib import Path

from pydantic import BaseModel

from app.features.products.models import Product, ProductImage
from app.features.products.repository import ProductRepository
from app.shared.database import Database

logger = logging.getLogger(__name__)

DEFAULT_DEMO_COUNT = 48
DEMO_IMAGE_COUNT = 3
DEMO_IMAGE_SIZE = 64
DEMO_ID_PREFIX = "DEMO"

type Rgb = tuple[int, int, int]


class DemoCategory(BaseModel):
    name: str
    brand: str
    styles: list[str]
    kinds: list[str]
    blurb: str
    base_price_cents: int
    rgb: Rgb


DEMO_CATEGORIES = [
    DemoCategory(
        name="Lamp",
        brand="Lumen & Co",
        styles=["Brass", "Walnut", "Matte Black", "Ceramic", "Copper", "Rattan"],
        kinds=["Desk Lamp", "Floor Lamp", "Reading Lamp", "Table Lamp"],
        blurb="A lamp with a warm, dimmable bulb for reading at a desk or beside the bed.",
        base_price_cents=5999,
        rgb=(240, 196, 80),
    ),
    DemoCategory(
        name="Rug",
        brand="Loomworks",
        styles=["Wool", "Jute", "Shag", "Flatweave", "Persian", "Moroccan"],
        kinds=["Area Rug", "Runner", "Doormat", "Round Rug"],
        blurb="A soft rug that anchors a living room or hallway and is easy to vacuum.",
        base_price_cents=12999,
        rgb=(176, 96, 64),
    ),
    DemoCategory(
        name="Sofa",
        brand="Settle",
        styles=["Velvet", "Linen", "Leather", "Boucle", "Corduroy", "Tweed"],
        kinds=["Loveseat", "Sectional Sofa", "Sleeper Sofa", "Chaise"],
        blurb="A deep, comfortable sofa to sink into for movie nights and afternoon naps.",
        base_price_cents=79999,
        rgb=(80, 120, 176),
    ),
    DemoCategory(
        name="Coffee",
        brand="Morning Ridge",
        styles=["Ethiopian", "Colombian", "Sumatran", "Kenyan", "Guatemalan", "Brazilian"],
        kinds=["Whole Bean Coffee", "Ground Coffee", "Espresso Roast", "Decaf Coffee"],
        blurb="Freshly roasted coffee beans with notes of chocolate and citrus for the morning.",
        base_price_cents=1499,
        rgb=(96, 64, 48),
    ),
    DemoCategory(
        name="Shoes",
        brand="Stride",
        styles=["Trail", "Road", "Canvas", "Suede", "Waterproof", "Knit"],
        kinds=["Running Shoes", "Hiking Boots", "Sneakers", "Sandals"],
        blurb="Lightweight shoes with a cushioned sole and grippy tread for walking and running.",
        base_price_cents=8999,
        rgb=(72, 160, 112),
    ),
    DemoCategory(
        name="Blanket",
        brand="Hearthside",
        styles=["Fleece", "Knit", "Sherpa", "Weighted", "Cotton", "Cashmere"],
        kinds=["Throw Blanket", "Quilt", "Electric Blanket", "Picnic Blanket"],
        blurb="A cozy, warm blanket for cold winter evenings on the couch.",
        base_price_cents=3999,
        rgb=(168, 104, 176),
    ),
]


def png_bytes(width: int, height: int, rgb: Rgb) -> bytes:
    """A minimal solid-colour, 8-bit RGB PNG (no image library needed)."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)

    row = b"\x00" + bytes(rgb) * width  # filter type 0, then the pixels
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def demo_image_colour(category: DemoCategory, index: int, position: int) -> Rgb:
    """A shade of the category colour, distinct per product and per angle."""
    shift = (index * 23 + position * 40) % 120 - 60
    red, green, blue = (max(0, min(255, c + shift)) for c in category.rgb)
    return red, green, blue


def build_demo_catalog(count: int = DEFAULT_DEMO_COUNT) -> list[Product]:
    """`count` products spread round-robin over the demo categories."""
    products: list[Product] = []
    for index in range(count):
        category = DEMO_CATEGORIES[index % len(DEMO_CATEGORIES)]
        rank = index // len(DEMO_CATEGORIES)
        style = category.styles[rank % len(category.styles)]
        kind = category.kinds[rank % len(category.kinds)]
        product_id = f"{DEMO_ID_PREFIX}{index + 1:04d}"
        products.append(
            Product(
                id=product_id,
                name=f"{style} {kind}",
                brand=category.brand,
                category=category.name,
                description=f"{category.blurb}\nStyle: {style.lower()}. Type: {kind.lower()}.",
                color=style,
                price_cents=category.base_price_cents + rank * 500,
                source_url=f"https://example.com/products/{product_id}",
                images=[
                    ProductImage(
                        position=position,
                        path=f"{product_id}/{position}.png",
                        width=DEMO_IMAGE_SIZE,
                        height=DEMO_IMAGE_SIZE,
                    )
                    for position in range(DEMO_IMAGE_COUNT)
                ],
            )
        )
    return products


def write_demo_images(images_dir: Path, products: list[Product]) -> int:
    """Write every product's PNG angles under `images_dir`; returns the file count."""
    written = 0
    for index, product in enumerate(products):
        category = DEMO_CATEGORIES[index % len(DEMO_CATEGORIES)]
        for image in product.images:
            target = images_dir / image.path
            target.parent.mkdir(parents=True, exist_ok=True)
            colour = demo_image_colour(category, index, image.position)
            target.write_bytes(png_bytes(image.width, image.height, colour))
            written += 1
    return written


async def seed_demo_catalog(
    database: Database, images_dir: Path, *, count: int = DEFAULT_DEMO_COUNT
) -> int:
    """Replace the catalog with the synthetic one and write its images. Returns product count."""
    products = build_demo_catalog(count)
    written = write_demo_images(images_dir, products)
    async with database.session_factory() as session:
        await ProductRepository(session).replace_all(products)
        await session.commit()
    logger.info("Seeded %d demo products with %d images", len(products), written)
    return len(products)
