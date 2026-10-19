"""Build the storefront catalog from the ABO archives: sample, copy images, write SQLite."""

import asyncio
import logging
import math
import random
import re
import shutil
from collections import Counter, defaultdict
from collections.abc import Iterable
from itertools import zip_longest
from pathlib import Path

from pydantic import BaseModel

from app.features.products.abo import (
    AboImage,
    AboImagesArchive,
    AboListing,
    LocalizedValue,
    iter_listings,
)
from app.features.products.models import Product, ProductImage
from app.features.products.repository import ProductRepository
from app.shared.database import Database

logger = logging.getLogger(__name__)

ENGLISH = "en_US"
DEFAULT_SEED = 42
DEFAULT_MAX_IMAGES = 8
_SAFE_ITEM_ID = re.compile(r"^[A-Za-z0-9]+$")
# ABO's internal "ABIS_" types duplicate public ones (ABIS_BEAUTY ~ BEAUTY).
_INTERNAL_TYPE_PREFIX = "ABIS_"

_CATEGORY_NAMES = {
    "FINEEARRING": "Fine Earrings",
    "FINENECKLACEBRACELETANKLET": "Fine Necklaces & Bracelets",
    "FINERING": "Fine Rings",
    "FINEOTHER": "Fine Jewelry",
    "FASHIONEARRING": "Fashion Earrings",
    "FASHIONNECKLACEBRACELETANKLET": "Fashion Necklaces & Bracelets",
    "FASHIONRING": "Fashion Rings",
    "FASHIONOTHER": "Fashion Jewelry",
}

# Median synthetic price (USD) per ABO product type; ABO has no prices.
_MEDIAN_PRICE = {
    "GROCERY": 9.0,
    "COFFEE": 14.0,
    "VITAMIN": 18.0,
    "HEALTH_PERSONAL_CARE": 15.0,
    "BEAUTY": 20.0,
    "SHOES": 65.0,
    "BOOT": 90.0,
    "SANDAL": 40.0,
    "CHAIR": 180.0,
    "SOFA": 800.0,
    "TABLE": 250.0,
    "BED": 450.0,
    "HEADBOARD": 200.0,
    "RUG": 140.0,
    "WALL_ART": 60.0,
    "LAMP": 70.0,
    "LIGHT_FIXTURE": 110.0,
    "FINERING": 300.0,
    "FINEEARRING": 220.0,
    "FINENECKLACEBRACELETANKLET": 260.0,
}
_DEFAULT_MEDIAN_PRICE = 35.0


class SeedImage(BaseModel):
    position: int
    archive_member: str
    path: str
    width: int
    height: int


class SeedProduct(BaseModel):
    id: str
    name: str
    brand: str | None
    category: str
    description: str
    color: str | None
    price_cents: int
    source_url: str
    images: list[SeedImage]

    def to_model(self) -> Product:
        return Product(
            id=self.id,
            name=self.name,
            brand=self.brand,
            category=self.category,
            description=self.description,
            color=self.color,
            price_cents=self.price_cents,
            source_url=self.source_url,
            images=[
                ProductImage(
                    position=image.position, path=image.path, width=image.width, height=image.height
                )
                for image in self.images
            ],
        )


def _english(values: list[LocalizedValue]) -> list[str]:
    return [v.value.strip() for v in values if v.language_tag == ENGLISH and v.value.strip()]


def is_eligible(listing: AboListing) -> bool:
    """English name, a product type, a main image and at least one alternate angle."""
    return bool(
        _SAFE_ITEM_ID.match(listing.item_id)
        and _english(listing.item_name)
        and listing.product_type
        and listing.main_image_id
        and listing.other_image_id
    )


def stratified_order(listings: Iterable[AboListing], seed: int) -> list[AboListing]:
    """Eligible, de-duplicated listings interleaved round-robin across product types.

    Any prefix of the result is a stratified sample: each type contributes equally until it
    runs out, so large types (e.g. GROCERY) cannot dominate the catalog.
    """
    by_type: defaultdict[str, list[AboListing]] = defaultdict(list)
    seen: set[str] = set()
    for listing in listings:
        if listing.item_id in seen or not is_eligible(listing):
            continue
        seen.add(listing.item_id)
        by_type[listing.product_type[0].value].append(listing)

    rng = random.Random(seed)
    groups = [by_type[product_type] for product_type in sorted(by_type)]
    for group in groups:
        rng.shuffle(group)
    rng.shuffle(groups)
    return [listing for row in zip_longest(*groups) for listing in row if listing is not None]


def humanize_product_type(product_type: str) -> str:
    product_type = product_type.removeprefix(_INTERNAL_TYPE_PREFIX)
    if product_type in _CATEGORY_NAMES:
        return _CATEGORY_NAMES[product_type]
    return product_type.replace("_", " ").title()


def synthetic_price_cents(product_type: str, item_id: str, seed: int = DEFAULT_SEED) -> int:
    """Deterministic, plausible price ending in .99, log-normally spread around a median."""
    rng = random.Random(f"{seed}:{item_id}")
    median = _MEDIAN_PRICE.get(product_type, _DEFAULT_MEDIAN_PRICE)
    dollars = max(1, math.ceil(median * rng.lognormvariate(0.0, 0.45)))
    return dollars * 100 - 1


def to_seed_product(
    listing: AboListing,
    image_index: dict[str, AboImage],
    *,
    seed: int = DEFAULT_SEED,
    max_images: int = DEFAULT_MAX_IMAGES,
) -> SeedProduct | None:
    """Map a listing to a catalog row, or None if fewer than two of its images exist."""
    image_ids = [listing.main_image_id, *listing.other_image_id][:max_images]
    found = [image_index[i] for i in image_ids if i is not None and i in image_index]
    if len(found) < 2:
        return None

    images = []
    for position, image in enumerate(found):
        width, height = image.small_size()
        images.append(
            SeedImage(
                position=position,
                archive_member=image.member_name,
                path=f"{listing.item_id}/{position}{image.extension}",
                width=width,
                height=height,
            )
        )

    product_type = listing.product_type[0].value
    brands = _english(listing.brand) or [b.value.strip() for b in listing.brand if b.value.strip()]
    colors = _english(listing.color)
    return SeedProduct(
        id=listing.item_id,
        name=_english(listing.item_name)[0],
        brand=brands[0] if brands else None,
        category=humanize_product_type(product_type),
        description="\n".join(
            _english(listing.bullet_point) + _english(listing.product_description)
        ),
        color=colors[0] if colors else None,
        price_cents=synthetic_price_cents(product_type, listing.item_id, seed),
        source_url=f"https://www.{listing.domain_name}/dp/{listing.item_id}",
        images=images,
    )


def build_catalog(
    listings_archive: Path,
    images_archive: Path,
    images_dir: Path,
    *,
    count: int,
    seed: int = DEFAULT_SEED,
    max_images: int = DEFAULT_MAX_IMAGES,
) -> list[SeedProduct]:
    """Select `count` products and copy their images into `images_dir` (blocking I/O)."""
    candidates = stratified_order(iter_listings(listings_archive), seed)
    logger.info("Found %d eligible listings", len(candidates))

    with AboImagesArchive(images_archive) as archive:
        image_index = archive.read_index()
        catalog: list[SeedProduct] = []
        for listing in candidates:
            product = to_seed_product(listing, image_index, seed=seed, max_images=max_images)
            if product is not None:
                catalog.append(product)
                if len(catalog) == count:
                    break
        if len(catalog) < count:
            logger.warning("Only %d of %d requested products available", len(catalog), count)

        _remove_stale_image_dirs(images_dir, keep={product.id for product in catalog})
        targets = {
            image.archive_member: images_dir / image.path
            for product in catalog
            for image in product.images
        }
        written = archive.extract(targets)

    categories = Counter(product.category for product in catalog)
    logger.info(
        "Selected %d products across %d categories (largest: %s); copied %d images",
        len(catalog),
        len(categories),
        ", ".join(f"{name}={n}" for name, n in categories.most_common(3)),
        written,
    )
    return catalog


def _remove_stale_image_dirs(images_dir: Path, keep: set[str]) -> None:
    if not images_dir.is_dir():
        return
    for child in images_dir.iterdir():
        if child.is_dir() and child.name not in keep:
            shutil.rmtree(child)


async def seed_catalog(
    database: Database,
    listings_archive: Path,
    images_archive: Path,
    images_dir: Path,
    *,
    count: int,
    seed: int = DEFAULT_SEED,
    max_images: int = DEFAULT_MAX_IMAGES,
) -> int:
    """Replace the catalog with a fresh sample from the ABO archives. Returns product count."""
    catalog = await asyncio.to_thread(
        build_catalog,
        listings_archive,
        images_archive,
        images_dir,
        count=count,
        seed=seed,
        max_images=max_images,
    )
    async with database.session_factory() as session:
        await ProductRepository(session).replace_all([product.to_model() for product in catalog])
        await session.commit()
    logger.info("Wrote %d products to the database", len(catalog))
    return len(catalog)
