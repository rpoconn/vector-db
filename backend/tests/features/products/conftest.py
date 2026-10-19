import gzip
import io
import json
import tarfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

type ListingFactory = Callable[..., dict[str, Any]]
type ArchiveBuilder = Callable[[Sequence[dict[str, Any]], Sequence[str]], tuple[Path, Path]]


@pytest.fixture
def listing() -> ListingFactory:
    """Builds a raw ABO listing record; keyword arguments override fields."""

    def build(item_id: str, product_type: str = "LAMP", **overrides: Any) -> dict[str, Any]:
        record: dict[str, Any] = {
            "item_id": item_id,
            "domain_name": "amazon.com",
            "item_name": [
                {"language_tag": "de_DE", "value": f"Lampe {item_id}"},
                {"language_tag": "en_US", "value": f"Lamp {item_id}"},
            ],
            "brand": [{"language_tag": "de_DE", "value": "Rivet"}],
            "bullet_point": [
                {"language_tag": "en_US", "value": "Bright"},
                {"language_tag": "fr_FR", "value": "Lumineux"},
                {"language_tag": "en_US", "value": "Dimmable"},
            ],
            "color": [{"language_tag": "en_US", "value": "Brass", "standardized_values": ["Gold"]}],
            "product_type": [{"value": product_type}],
            "main_image_id": f"{item_id}-main",
            "other_image_id": [f"{item_id}-side", f"{item_id}-back"],
            "model_year": [{"value": 2019}],
        }
        record.update(overrides)
        return record

    return build


def _add_member(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


@pytest.fixture
def abo_archives(tmp_path: Path) -> ArchiveBuilder:
    """Writes tiny ABO-shaped listings and images tars; returns their paths.

    Every image id listed in `image_ids` gets a 500x250 original and a file in `small/`.
    """

    def build(listings: Sequence[dict[str, Any]], image_ids: Sequence[str]) -> tuple[Path, Path]:
        listings_tar = tmp_path / "abo-listings.tar"
        with tarfile.open(listings_tar, "w") as tar:
            lines = "\n".join(json.dumps(record) for record in listings) + "\n"
            _add_member(tar, "listings/README.md", b"readme")
            _add_member(tar, "listings/metadata/listings_0.json.gz", gzip.compress(lines.encode()))

        images_tar = tmp_path / "abo-images-small.tar"
        rows = ["image_id,height,width,path"]
        with tarfile.open(images_tar, "w") as tar:
            for n, image_id in enumerate(image_ids):
                path = f"{n:02x}/{n:08x}.jpg"
                rows.append(f"{image_id},250,500,{path}")
                _add_member(tar, f"images/small/{path}", image_id.encode())
            csv_bytes = gzip.compress(("\r\n".join(rows) + "\r\n").encode())
            _add_member(tar, "images/metadata/images.csv.gz", csv_bytes)
        return listings_tar, images_tar

    return build
