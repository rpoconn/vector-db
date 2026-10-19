from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.shared.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        env="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        images_dir=tmp_path / "images",
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
