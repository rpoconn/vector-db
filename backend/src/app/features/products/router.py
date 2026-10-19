from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles

from app.features.products.schemas import (
    IMAGES_URL_PATH,
    CategoryOut,
    ProductDetail,
    ProductListParams,
    ProductSummary,
)
from app.features.products.service import (
    ProductNotFoundError,
    ProductService,
    get_product_service,
)
from app.shared.pagination import Page

router = APIRouter(tags=["products"])

ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]


@router.get("/products", response_model=Page[ProductSummary])
async def list_products(
    service: ProductServiceDep, params: Annotated[ProductListParams, Query()]
) -> Page[ProductSummary]:
    return await service.list_products(params)


@router.get(
    "/products/{product_id}",
    response_model=ProductDetail,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Product not found"}},
)
async def get_product(product_id: str, service: ProductServiceDep) -> ProductDetail:
    try:
        return await service.get_product(product_id)
    except ProductNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(service: ProductServiceDep) -> list[CategoryOut]:
    return await service.list_categories()


def mount_product_images(app: FastAPI, images_dir: Path) -> None:
    """Serve seeded product images. The directory may be created after startup."""
    app.mount(
        IMAGES_URL_PATH,
        StaticFiles(directory=images_dir, check_dir=False),
        name="product-images",
    )
