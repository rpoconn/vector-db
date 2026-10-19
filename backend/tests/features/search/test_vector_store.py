import uuid
from collections.abc import Callable

import numpy as np
import pytest

from app.features.search.vector_store import (
    ChromaVectorStore,
    Metadata,
    NumpyVectorStore,
    VectorStore,
    create_vector_store,
)
from app.features.search.vectors import Vectors
from app.shared.config import Settings

DIMENSION = 3
IDS = ["x", "y", "xy", "neg"]
VECTORS = np.array([[1, 0, 0], [0, 1, 0], [1, 1, 0], [-1, 0, 0]], dtype=np.float32)
METADATAS: list[Metadata] = [
    {"category": "A", "price": 1.0},
    {"category": "B", "price": 2.0},
    {"category": "A", "price": 3.0, "brand": "Acme"},
    {"category": "B", "price": 4.0},
]


def _numpy() -> VectorStore:
    return NumpyVectorStore(DIMENSION)


def _chroma() -> VectorStore:
    # In-memory Chroma clients share state per process: isolate each test's collection.
    return ChromaVectorStore(collection_name=f"test-{uuid.uuid4().hex}")


@pytest.fixture(params=[_numpy, _chroma], ids=["numpy", "chroma"])
def store(request: pytest.FixtureRequest) -> VectorStore:
    factory: Callable[[], VectorStore] = request.param
    return factory()


@pytest.fixture
async def filled(store: VectorStore) -> VectorStore:
    await store.upsert(IDS, VECTORS, METADATAS)
    return store


def _vector(x: float, y: float, z: float = 0.0) -> Vectors:
    return np.array([x, y, z], dtype=np.float32)


async def test_empty_store_returns_no_matches(store: VectorStore) -> None:
    assert await store.query(_vector(1, 0), k=5) == []
    assert await store.count() == 0
    assert await store.ids() == set()


async def test_query_ranks_by_cosine_similarity(filled: VectorStore) -> None:
    matches = await filled.query(_vector(1, 0.1), k=3)

    assert [match.id for match in matches] == ["x", "xy", "y"]
    assert matches[0].score == pytest.approx(0.995, abs=1e-3)
    assert matches[1].score == pytest.approx(0.774, abs=1e-3)


async def test_query_caps_k_at_store_size(filled: VectorStore) -> None:
    matches = await filled.query(_vector(1, 0), k=50)

    assert len(matches) == len(IDS)
    assert matches[-1].id == "neg"
    assert matches[-1].score == pytest.approx(-1.0, abs=1e-5)


async def test_query_filters_on_metadata(filled: VectorStore) -> None:
    by_category = await filled.query(_vector(0, 1), k=5, where={"category": "A"})
    by_two_fields = await filled.query(_vector(0, 1), k=5, where={"category": "A", "brand": "Acme"})
    no_match = await filled.query(_vector(0, 1), k=5, where={"category": "Z"})

    assert [match.id for match in by_category] == ["xy", "x"]
    assert [match.id for match in by_two_fields] == ["xy"]
    assert no_match == []


async def test_upsert_replaces_existing_vectors_and_metadata(filled: VectorStore) -> None:
    await filled.upsert(["x"], np.array([[0, 0, 1]], dtype=np.float32), [{"category": "C"}])

    matches = await filled.query(_vector(0, 0, 1), k=1, where={"category": "C"})
    assert [match.id for match in matches] == ["x"]
    assert matches[0].score == pytest.approx(1.0, abs=1e-5)
    assert await filled.count() == len(IDS)


async def test_delete_removes_ids_and_ignores_unknown(filled: VectorStore) -> None:
    await filled.delete(["x", "unknown"])

    assert await filled.ids() == {"y", "xy", "neg"}
    assert "x" not in {match.id for match in await filled.query(_vector(1, 0), k=5)}


async def test_upsert_rejects_mismatched_lengths(store: VectorStore) -> None:
    with pytest.raises(ValueError, match="same length"):
        await store.upsert(["a", "b"], VECTORS[:1], METADATAS[:2])


async def test_numpy_store_keeps_last_of_repeated_ids_in_one_upsert() -> None:
    store = NumpyVectorStore(DIMENSION)
    await store.upsert(["a", "a"], VECTORS[:2], [{"n": 1}, {"n": 2}])

    assert await store.count() == 1
    assert [match.id for match in await store.query(_vector(0, 1), k=1, where={"n": 2})] == ["a"]


def test_create_vector_store_follows_settings() -> None:
    numpy_store = create_vector_store(Settings(vector_store="numpy", _env_file=None), DIMENSION)
    chroma_store = create_vector_store(Settings(vector_store="chroma", _env_file=None), DIMENSION)

    assert isinstance(numpy_store, NumpyVectorStore)
    assert isinstance(chroma_store, ChromaVectorStore)
