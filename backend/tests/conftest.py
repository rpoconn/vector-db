from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.features.products.repository import ProductRepository
from app.main import create_app
from app.shared.config import Settings
from app.shared.database import Database

from .catalog import CATALOG_SIZE, make_product


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        env="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        images_dir=tmp_path / "images",
        embedder="hashing",
        vector_store="numpy",
        _env_file=None,
    )


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


@pytest.fixture
def database(app: FastAPI) -> Database:
    db: Database = app.state.database
    return db


@pytest.fixture
async def catalog(database: Database) -> list[str]:
    """Seed CATALOG_SIZE products into the app database; returns their ids."""
    products = [make_product(i) for i in range(CATALOG_SIZE)]
    async with database.session_factory() as session:
        await ProductRepository(session).replace_all(products)
        await session.commit()
    return [product.id for product in products]
