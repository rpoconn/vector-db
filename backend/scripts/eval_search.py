"""Sanity-check semantic search quality against the seeded catalog.

    uv run python scripts/eval_search.py [--top 5] ["custom query" ...]

Builds the search index exactly as the app does (reusing cached embeddings) and logs the
top hits for a set of hand-written queries.
"""

import argparse
import asyncio
import logging
import time

from app.features.products.service import build_product_service
from app.features.search.indexer import create_search_index
from app.shared.config import get_settings
from app.shared.database import Database
from app.shared.logging import configure_logging

logger = logging.getLogger("app.scripts.eval_search")

DEFAULT_QUERIES = (
    "something to keep coffee hot",
    "desk lamp for reading",
    "cozy blanket",
    "warm winter jacket",
    "comfortable running shoes",
    "phone case",
    "gift for a gardener",
    "healthy snack",
    "office chair with back support",
    "earrings for a wedding",
    "rug for the living room",
    "kitchen knife",
)


async def run(queries: list[str], top: int) -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    index = create_search_index(settings)
    try:
        await database.create_all()
        async with database.session_factory() as session:
            await index.rebuild(session)
            products = build_product_service(session)
            for query in queries:
                started = time.perf_counter()
                matches = await index.query(query, top)
                elapsed_ms = (time.perf_counter() - started) * 1000
                hits = await products.get_by_ids([match.id for match in matches])
                lines = [
                    f"  {match.score:.3f}  [{hit.category}] {hit.name[:90]}"
                    for match, hit in zip(matches, hits, strict=True)
                ]
                logger.info("%r (%.1f ms)\n%s", query, elapsed_ms, "\n".join(lines))
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Log top search hits for sample queries.")
    parser.add_argument("queries", nargs="*", help="queries to run instead of the defaults")
    parser.add_argument("--top", type=int, default=5, help="hits per query")
    args = parser.parse_args()
    configure_logging(get_settings().log_level)
    asyncio.run(run(args.queries or list(DEFAULT_QUERIES), args.top))


if __name__ == "__main__":
    main()
