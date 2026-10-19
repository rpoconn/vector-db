from typing import Self

from pydantic import BaseModel, Field

from app.features.products.models import Product, ProductImage
from app.shared.pagination import PageParams

IMAGES_URL_PATH = "/images"
"""Where the seeded image directory is served, relative to the API root."""


class ProductListParams(PageParams):
    category: str | None = Field(default=None, min_length=1)


class ProductImageOut(BaseModel):
    position: int
    url: str
    width: int
    height: int

    @classmethod
    def from_model(cls, image: ProductImage) -> Self:
        return cls(
            position=image.position,
            url=f"{IMAGES_URL_PATH}/{image.path}",
            width=image.width,
            height=image.height,
        )


class ProductSummary(BaseModel):
    id: str
    name: str
    brand: str | None
    category: str
    color: str | None
    price_cents: int
    thumbnail: ProductImageOut | None

    @classmethod
    def from_model(cls, product: Product) -> Self:
        return cls(
            id=product.id,
            name=product.name,
            brand=product.brand,
            category=product.category,
            color=product.color,
            price_cents=product.price_cents,
            thumbnail=ProductImageOut.from_model(product.images[0]) if product.images else None,
        )


class ProductDetail(ProductSummary):
    description: str
    source_url: str
    images: list[ProductImageOut]

    @classmethod
    def from_model(cls, product: Product) -> Self:
        return cls(
            **ProductSummary.from_model(product).model_dump(),
            description=product.description,
            source_url=product.source_url,
            images=[ProductImageOut.from_model(image) for image in product.images],
        )


class CategoryOut(BaseModel):
    name: str
    product_count: int
