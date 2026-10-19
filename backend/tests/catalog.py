"""Fixture catalog shared by feature tests."""

from app.features.products.models import Product, ProductImage

CATEGORIES = ("Lamp", "Rug", "Sofa", "Grocery")
CATALOG_SIZE = 20


def make_product(index: int, *, image_count: int = 3) -> Product:
    product_id = f"P{index:04d}"
    return Product(
        id=product_id,
        name=f"Product {index}",
        brand="Acme" if index % 2 else None,
        category=CATEGORIES[index % len(CATEGORIES)],
        description=f"Description of product {index}",
        color="Blue",
        price_cents=1000 + index,
        source_url=f"https://www.amazon.com/dp/{product_id}",
        images=[
            ProductImage(position=p, path=f"{product_id}/{p}.jpg", width=256, height=200)
            for p in reversed(range(image_count))  # inserted out of order on purpose
        ],
    )
