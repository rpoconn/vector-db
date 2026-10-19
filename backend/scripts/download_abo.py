"""Download the Amazon Berkeley Objects archives used to seed the catalog.

    uv run python scripts/download_abo.py [--skip-images]

Resumable and idempotent: re-running finishes partial downloads and skips complete ones.
"""

import argparse
import logging
from pathlib import Path

import httpx

from app.features.products.abo import ARCHIVE_BASE_URL, IMAGES_ARCHIVE, LISTINGS_ARCHIVE
from app.shared.config import get_settings
from app.shared.download import download_file
from app.shared.logging import configure_logging

logger = logging.getLogger("app.scripts.download_abo")


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Download the Amazon Berkeley Objects archives.")
    parser.add_argument("--dest", type=Path, default=settings.abo_dir, help="output directory")
    parser.add_argument(
        "--skip-images", action="store_true", help="only fetch listings (83 MB, not 3 GB)"
    )
    args = parser.parse_args()
    configure_logging(settings.log_level)

    archives = [LISTINGS_ARCHIVE] if args.skip_images else [LISTINGS_ARCHIVE, IMAGES_ARCHIVE]
    timeout = httpx.Timeout(30.0, read=120.0)
    with httpx.Client(timeout=timeout) as client:
        for archive in archives:
            logger.info("Fetching %s", archive)
            download_file(client, f"{ARCHIVE_BASE_URL}/{archive}", args.dest / archive)
    logger.info("Archives ready in %s", args.dest)


if __name__ == "__main__":
    main()
