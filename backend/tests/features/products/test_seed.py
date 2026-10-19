from collections import Counter
from pathlib import Path

import pytest

from app.features.products.abo import AboImage, AboImagesArchive, AboListing, iter_listings
from app.features.products.repository import ProductRepository
from app.features.products.seed import (
    humanize_product_type,
    is_eligible,
    seed_catalog,
    stratified_order,
    synthetic_price_cents,
    to_seed_product,
)
from app.shared.database import Database

from .conftest import ArchiveBuilder, ListingFactory


def _image_ids(*item_ids: str) -> list[str]:
    return [f"{i}-{angle}" for i in item_ids for angle in ("main", "side", "back")]


def test_iter_listings_parses_records_and_skips_malformed(
    abo_archives: ArchiveBuilder, listing: ListingFactory
) -> None:
    listings_tar, _ = abo_archives([listing("A1"), {"item_id": "BROKEN"}, listing("A2")], [])

    assert [item.item_id for item in iter_listings(listings_tar)] == ["A1", "A2"]


def test_images_archive_reads_index_and_extracts_selected_members(
    abo_archives: ArchiveBuilder, tmp_path: Path
) -> None:
    _, images_tar = abo_archives([], ["img-a", "img-b"])

    with AboImagesArchive(images_tar) as archive:
        index = archive.read_index()
        written = archive.extract({index["img-b"].member_name: tmp_path / "out" / "b.jpg"})

    assert index["img-a"] == AboImage(
        image_id="img-a", height=250, width=500, path="00/00000000.jpg"
    )
    assert index["img-a"].small_size() == (256, 128)
    assert written == 1
    assert (tmp_path / "out" / "b.jpg").read_bytes() == b"img-b"


def test_images_archive_requires_context_manager(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        AboImagesArchive(tmp_path / "x.tar").read_index()


@pytest.mark.parametrize(
    ("overrides", "eligible"),
    [
        ({}, True),
        ({"item_name": [{"language_tag": "de_DE", "value": "Nur Deutsch"}]}, False),
        ({"main_image_id": None}, False),
        ({"other_image_id": []}, False),
        ({"product_type": []}, False),
        ({"item_id": "../escape"}, False),
    ],
)
def test_is_eligible(listing: ListingFactory, overrides: dict[str, object], eligible: bool) -> None:
    record = listing("A1") | overrides

    assert is_eligible(AboListing.model_validate(record)) is eligible


def test_stratified_order_interleaves_types_and_dedupes(listing: ListingFactory) -> None:
    raw = [listing(f"G{n}", "GROCERY") for n in range(10)]
    raw += [listing(f"L{n}", "LAMP") for n in range(2)]
    raw += [listing("G0", "GROCERY"), listing("X1", item_name=[])]
    listings = [AboListing.model_validate(record) for record in raw]

    ordered = stratified_order(listings, seed=7)

    assert len(ordered) == 12
    first_four = Counter(item.product_type[0].value for item in ordered[:4])
    assert first_four == {"GROCERY": 2, "LAMP": 2}
    assert [item.item_id for item in stratified_order(listings, seed=7)] == [
        item.item_id for item in ordered
    ]


@pytest.mark.parametrize(
    ("product_type", "expected"),
    [
        ("WALL_ART", "Wall Art"),
        ("LAMP", "Lamp"),
        ("FINENECKLACEBRACELETANKLET", "Fine Necklaces & Bracelets"),
        ("ABIS_BEAUTY", "Beauty"),
    ],
)
def test_humanize_product_type(product_type: str, expected: str) -> None:
    assert humanize_product_type(product_type) == expected


def test_synthetic_price_is_deterministic_and_ends_in_99() -> None:
    price = synthetic_price_cents("SOFA", "B01", seed=1)

    assert price == synthetic_price_cents("SOFA", "B01", seed=1)
    assert price % 100 == 99
    assert price > 0
    prices = {synthetic_price_cents("SOFA", f"B{n}") for n in range(20)}
    assert len(prices) > 1


def test_to_seed_product_maps_english_fields_and_images(listing: ListingFactory) -> None:
    abo = AboListing.model_validate(listing("A1"))
    index = {
        image_id: AboImage(image_id=image_id, height=250, width=500, path=f"aa/{n}.png")
        for n, image_id in enumerate(_image_ids("A1"))
    }

    product = to_seed_product(abo, index, max_images=2)

    assert product is not None
    assert product.name == "Lamp A1"
    assert product.brand == "Rivet"  # no English brand: falls back to any language
    assert product.category == "Lamp"
    assert product.description == "Bright\nDimmable"
    assert product.color == "Brass"
    assert product.source_url == "https://www.amazon.com/dp/A1"
    assert [(i.position, i.path, i.archive_member) for i in product.images] == [
        (0, "A1/0.png", "images/small/aa/0.png"),
        (1, "A1/1.png", "images/small/aa/1.png"),
    ]


def test_to_seed_product_needs_two_resolvable_images(listing: ListingFactory) -> None:
    abo = AboListing.model_validate(listing("A1"))
    index = {"A1-main": AboImage(image_id="A1-main", height=1, width=1, path="aa/0.jpg")}

    assert to_seed_product(abo, index) is None


async def test_seed_catalog_writes_products_and_images(
    abo_archives: ArchiveBuilder,
    listing: ListingFactory,
    database: Database,
    tmp_path: Path,
) -> None:
    records = [listing(f"L{n}", "LAMP") for n in range(4)]
    records += [listing(f"R{n}", "RUG") for n in range(4)]
    records.append(listing("NOIMG", "RUG"))  # images absent from the archive
    listings_tar, images_tar = abo_archives(
        records, _image_ids(*(f"L{n}" for n in range(4)), *(f"R{n}" for n in range(4)))
    )
    images_dir = tmp_path / "catalog-images"
    stale = images_dir / "OLD" / "0.jpg"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old")

    written = await seed_catalog(
        database, listings_tar, images_tar, images_dir, count=4, seed=3, max_images=2
    )

    assert written == 4
    async with database.session_factory() as session:
        repository = ProductRepository(session)
        assert await repository.categories() == [("Lamp", 2), ("Rug", 2)]
        products, _ = await repository.list_page(category=None, limit=10, offset=0)
    for product in products:
        assert [image.path for image in product.images] == [
            f"{product.id}/0.jpg",
            f"{product.id}/1.jpg",
        ]
        assert (images_dir / product.id / "0.jpg").read_bytes() == f"{product.id}-main".encode()
        assert (images_dir / product.id / "1.jpg").read_bytes() == f"{product.id}-side".encode()
    assert not stale.parent.exists()
