"""Readers for the Amazon Berkeley Objects (ABO) archives (CC BY 4.0, Amazon.com).

Archives are read in place with `tarfile`; nothing is fully extracted.
See https://amazon-berkeley-objects.s3.amazonaws.com/index.html
"""

import csv
import gzip
import logging
import tarfile
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import TracebackType
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)

ARCHIVE_BASE_URL = "https://amazon-berkeley-objects.s3.amazonaws.com/archives"
LISTINGS_ARCHIVE = "abo-listings.tar"
IMAGES_ARCHIVE = "abo-images-small.tar"

LISTINGS_PREFIX = "listings/metadata/listings_"
IMAGES_METADATA_MEMBER = "images/metadata/images.csv.gz"
SMALL_IMAGES_PREFIX = "images/small/"
SMALL_IMAGE_MAX_SIDE = 256


class LocalizedValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    language_tag: str | None = None
    value: str


class UntaggedValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: str


class AboListing(BaseModel):
    """The subset of an ABO listing record the storefront uses."""

    model_config = ConfigDict(extra="ignore")

    item_id: str
    domain_name: str
    item_name: list[LocalizedValue] = Field(default_factory=list)
    brand: list[LocalizedValue] = Field(default_factory=list)
    bullet_point: list[LocalizedValue] = Field(default_factory=list)
    product_description: list[LocalizedValue] = Field(default_factory=list)
    color: list[LocalizedValue] = Field(default_factory=list)
    product_type: list[UntaggedValue] = Field(default_factory=list)
    main_image_id: str | None = None
    other_image_id: list[str] = Field(default_factory=list)


class AboImage(BaseModel):
    """One row of `images.csv.gz`. Height and width are of the original image."""

    image_id: str
    height: int
    width: int
    path: str

    @property
    def member_name(self) -> str:
        return f"{SMALL_IMAGES_PREFIX}{self.path}"

    @property
    def extension(self) -> str:
        return Path(self.path).suffix

    def small_size(self) -> tuple[int, int]:
        """(width, height) of the downscaled copy in the `small` archive."""
        scale = min(1.0, SMALL_IMAGE_MAX_SIDE / max(self.width, self.height, 1))
        return max(1, round(self.width * scale)), max(1, round(self.height * scale))


def iter_listings(archive: Path) -> Iterator[AboListing]:
    """Stream every listing from `abo-listings.tar`, skipping malformed records."""
    with tarfile.open(archive) as tar:
        for member in tar:
            if not (member.isfile() and member.name.startswith(LISTINGS_PREFIX)):
                continue
            file = tar.extractfile(member)
            if file is None:
                continue
            with gzip.open(file) as lines:
                for line_number, line in enumerate(lines, start=1):
                    try:
                        yield AboListing.model_validate_json(line)
                    except ValidationError as exc:
                        logger.warning(
                            "Skipping malformed listing %s:%d (%d errors)",
                            member.name,
                            line_number,
                            exc.error_count(),
                        )


class AboImagesArchive:
    """Random access to `abo-images-small.tar`: image metadata plus selective extraction."""

    def __init__(self, archive: Path) -> None:
        self._archive = archive
        self._tar: tarfile.TarFile | None = None

    def __enter__(self) -> Self:
        self._tar = tarfile.open(self._archive)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._tar is not None:
            self._tar.close()
            self._tar = None

    @property
    def tar(self) -> tarfile.TarFile:
        if self._tar is None:
            raise RuntimeError("AboImagesArchive must be used as a context manager")
        return self._tar

    def read_index(self) -> dict[str, AboImage]:
        """Image metadata keyed by image id."""
        file = self.tar.extractfile(IMAGES_METADATA_MEMBER)
        if file is None:
            raise FileNotFoundError(f"{IMAGES_METADATA_MEMBER} missing from {self._archive}")
        with gzip.open(file, "rt", encoding="utf-8", newline="") as text:
            rows = csv.DictReader(text)
            images = (AboImage.model_validate(row) for row in rows)
            return {image.image_id: image for image in images}

    def extract(self, targets: Mapping[str, Path]) -> int:
        """Copy archive members (by member name) to the given paths; returns files written."""
        written = 0
        for member in self.tar.getmembers():
            destination = targets.get(member.name)
            if destination is None or not member.isfile():
                continue
            source = self.tar.extractfile(member)
            if source is None:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source, destination.open("wb") as target:
                target.write(source.read())
            written += 1
        missing = len(targets) - written
        if missing:
            logger.warning("%d requested images were not found in %s", missing, self._archive)
        return written
