from collections.abc import Sequence

import pytest
from fastapi import FastAPI

from app.features.search.embedding import HashingEmbedder
from app.features.search.indexer import SearchIndex
from app.features.search.vectors import Vectors
from app.shared.database import Database


class CountingEmbedder(HashingEmbedder):
    """HashingEmbedder that records every document text it embeds."""

    def __init__(self) -> None:
        super().__init__()
        self.embedded: list[str] = []

    async def embed_documents(self, texts: Sequence[str]) -> Vectors:
        self.embedded.extend(texts)
        return await super().embed_documents(texts)


@pytest.fixture
def search_index(app: FastAPI) -> SearchIndex:
    index: SearchIndex = app.state.search_index
    return index


@pytest.fixture
async def indexed_catalog(
    database: Database, catalog: list[str], search_index: SearchIndex
) -> list[str]:
    """The fixture catalog, seeded after startup and then indexed."""
    async with database.session_factory() as session:
        await search_index.rebuild(session)
    return catalog
