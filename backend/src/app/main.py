"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.features.health.router import router as health_router
from app.features.products.router import mount_product_images
from app.features.products.router import router as products_router
from app.shared.config import Settings, get_settings
from app.shared.database import Database
from app.shared.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.images_dir.mkdir(parents=True, exist_ok=True)
        database = Database(settings.database_url)
        await database.create_all()
        app.state.settings = settings
        app.state.database = database
        logger.info("Application started (env=%s)", settings.env)
        try:
            yield
        finally:
            await database.dispose()
            logger.info("Application stopped")

    app = FastAPI(title="Storefront API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(products_router)
    mount_product_images(app, settings.images_dir)
    return app


app = create_app()
