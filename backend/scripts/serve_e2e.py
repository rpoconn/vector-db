"""Seed a fresh synthetic catalog and serve the API for end-to-end tests.

    uv run python scripts/serve_e2e.py [--port 8001] [--frontend-url http://localhost:5174]

Runs with `APP_ENV=test` semantics: the model-free hashing embedder and NumPy vector store,
an in-memory mailbox at `/_test/mailbox` for e-mailed links, and a throwaway database under
`data/e2e/`. Nothing here touches the real catalog in `data/`.
"""

import argparse
import asyncio
import logging
import shutil
from pathlib import Path

import uvicorn

from app.features.products.demo import DEFAULT_DEMO_COUNT, seed_demo_catalog
from app.main import create_app
from app.shared.config import DATA_DIR, Settings
from app.shared.database import Database
from app.shared.logging import configure_logging

logger = logging.getLogger("app.scripts.serve_e2e")

DEFAULT_PORT = 8001
DEFAULT_FRONTEND_URL = "http://localhost:5174"


def build_settings(data_dir: Path, frontend_url: str) -> Settings:
    return Settings(
        env="test",
        database_url=f"sqlite+aiosqlite:///{(data_dir / 'storefront.db').as_posix()}",
        images_dir=data_dir / "images",
        frontend_url=frontend_url,
        embedder="hashing",
        vector_store="numpy",
        _env_file=None,
    )


async def seed(settings: Settings, count: int) -> None:
    database = Database(settings.database_url)
    try:
        await database.create_all()
        await seed_demo_catalog(database, settings.images_dir, count=count)
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed and serve the API for e2e tests.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL)
    parser.add_argument("--count", type=int, default=DEFAULT_DEMO_COUNT, help="products to seed")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR / "e2e")
    args = parser.parse_args()

    configure_logging("INFO")
    data_dir: Path = args.data_dir.resolve()
    shutil.rmtree(data_dir, ignore_errors=True)
    settings = build_settings(data_dir, args.frontend_url)
    asyncio.run(seed(settings, args.count))
    logger.info("Serving the e2e catalog from %s on port %d", data_dir, args.port)
    uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port, log_config=None)


if __name__ == "__main__":
    main()
