"""Seed the product catalog from the downloaded ABO archives.

    uv run python scripts/seed_products.py [--count 3000] [--seed 42]

Replaces all products in the database and copies their images into the images directory.
"""

import argparse
import asyncio
import logging
from pathlib import Path

from app.features.products.abo import IMAGES_ARCHIVE, LISTINGS_ARCHIVE
from app.features.products.seed import DEFAULT_MAX_IMAGES, DEFAULT_SEED, seed_catalog
from app.shared.config import Settings, get_settings
from app.shared.database import Database
from app.shared.logging import configure_logging

logger = logging.getLogger("app.scripts.seed_products")


async def run(settings: Settings, args: argparse.Namespace) -> None:
    abo_dir: Path = args.abo_dir
    listings_archive, images_archive = abo_dir / LISTINGS_ARCHIVE, abo_dir / IMAGES_ARCHIVE
    missing = [a.name for a in (listings_archive, images_archive) if not a.is_file()]
    if missing:
        raise SystemExit(f"Missing {', '.join(missing)}; run scripts/download_abo.py first")

    database = Database(settings.database_url)
    try:
        await database.create_all()
        await seed_catalog(
            database,
            listings_archive,
            images_archive,
            settings.images_dir,
            count=args.count,
            seed=args.seed,
            max_images=args.max_images,
        )
    finally:
        await database.dispose()


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Seed the product catalog from the ABO archives.")
    parser.add_argument("--count", type=int, default=3000, help="number of products")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="sampling/price seed")
    parser.add_argument(
        "--max-images", type=int, default=DEFAULT_MAX_IMAGES, help="images kept per product"
    )
    parser.add_argument("--abo-dir", type=Path, default=settings.abo_dir)
    args = parser.parse_args()
    configure_logging(settings.log_level)
    asyncio.run(run(settings, args))


if __name__ == "__main__":
    main()
