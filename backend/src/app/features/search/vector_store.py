"""Vector stores: in-process Chroma (HNSW) and an exact NumPy scan used as a test double."""

import asyncio
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import chromadb
import numpy as np
from chromadb.api.collection_configuration import CreateCollectionConfiguration
from chromadb.config import Settings as ChromaSettings

from app.features.search.vectors import Vectors, normalize_rows
from app.shared.config import Settings

logger = logging.getLogger(__name__)

type MetadataValue = str | int | float | bool
type Metadata = Mapping[str, MetadataValue]

DEFAULT_COLLECTION = "products"
# Sized for a few thousand to ~10k items: favor recall, the build cost is negligible.
HNSW_CONFIGURATION: CreateCollectionConfiguration = {
    "hnsw": {"space": "cosine", "max_neighbors": 16, "ef_construction": 200, "ef_search": 100}
}
_CHROMA_UPSERT_BATCH = 1000
_CHROMA_SETTINGS = ChromaSettings(anonymized_telemetry=False)


@dataclass(frozen=True, slots=True)
class VectorMatch:
    id: str
    score: float
    """Cosine similarity: 1.0 is identical, 0.0 unrelated."""


class VectorStore(Protocol):
    async def upsert(
        self, ids: Sequence[str], vectors: Vectors, metadatas: Sequence[Metadata]
    ) -> None: ...

    async def delete(self, ids: Sequence[str]) -> None: ...

    async def ids(self) -> set[str]: ...

    async def count(self) -> int: ...

    async def query(
        self, vector: Vectors, k: int, where: Metadata | None = None
    ) -> list[VectorMatch]:
        """The `k` most similar vectors, best first; `where` keeps exact metadata matches."""
        ...


class NumpyVectorStore:
    """Brute-force cosine search over a normalized matrix. Exact; fine for thousands of rows."""

    def __init__(self, dimension: int) -> None:
        self._ids: list[str] = []
        self._rows: dict[str, int] = {}
        self._matrix: Vectors = np.empty((0, dimension), dtype=np.float32)
        self._metadatas: list[Metadata] = []

    async def upsert(
        self, ids: Sequence[str], vectors: Vectors, metadatas: Sequence[Metadata]
    ) -> None:
        _check_lengths(ids, vectors, metadatas)
        vectors = normalize_rows(np.asarray(vectors, dtype=np.float32))
        new_rows: list[Vectors] = []
        for item_id, vector, metadata in zip(ids, vectors, metadatas, strict=True):
            row = self._rows.get(item_id)
            if row is None:
                self._rows[item_id] = len(self._ids)
                self._ids.append(item_id)
                self._metadatas.append(metadata)
                new_rows.append(vector)
            elif row < len(self._matrix):
                self._matrix[row] = vector
                self._metadatas[row] = metadata
            else:  # Repeated id within this call: overwrite the pending row.
                new_rows[row - len(self._matrix)] = vector
                self._metadatas[row] = metadata
        if new_rows:
            self._matrix = np.vstack([self._matrix, *new_rows])

    async def delete(self, ids: Sequence[str]) -> None:
        doomed = {self._rows[item_id] for item_id in ids if item_id in self._rows}
        if not doomed:
            return
        keep = [row for row in range(len(self._ids)) if row not in doomed]
        self._ids = [self._ids[row] for row in keep]
        self._metadatas = [self._metadatas[row] for row in keep]
        self._matrix = self._matrix[keep]
        self._rows = {item_id: row for row, item_id in enumerate(self._ids)}

    async def ids(self) -> set[str]:
        return set(self._ids)

    async def count(self) -> int:
        return len(self._ids)

    async def query(
        self, vector: Vectors, k: int, where: Metadata | None = None
    ) -> list[VectorMatch]:
        candidates = np.arange(len(self._ids))
        if where:
            candidates = np.array(
                [
                    row
                    for row in candidates
                    if all(self._metadatas[row].get(key) == value for key, value in where.items())
                ],
                dtype=np.intp,
            )
        if k <= 0 or candidates.size == 0:
            return []
        scores = self._matrix[candidates] @ normalize_rows(np.asarray(vector, dtype=np.float32))
        k = min(k, candidates.size)
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top], kind="stable")]
        return [VectorMatch(self._ids[candidates[i]], float(scores[i])) for i in top]


class ChromaVectorStore:
    """Chroma collection with a cosine HNSW index; in-memory unless `persist_dir` is given.

    In-memory Chroma clients share one store per process, so distinct indexes in the same
    process need distinct `collection_name`s.
    """

    def __init__(
        self, *, persist_dir: Path | None = None, collection_name: str = DEFAULT_COLLECTION
    ) -> None:
        client = (
            chromadb.PersistentClient(path=str(persist_dir), settings=_CHROMA_SETTINGS)
            if persist_dir is not None
            else chromadb.EphemeralClient(settings=_CHROMA_SETTINGS)
        )
        self._collection = client.get_or_create_collection(
            collection_name, configuration=HNSW_CONFIGURATION, embedding_function=None
        )

    async def upsert(
        self, ids: Sequence[str], vectors: Vectors, metadatas: Sequence[Metadata]
    ) -> None:
        _check_lengths(ids, vectors, metadatas)

        def run() -> None:
            for start in range(0, len(ids), _CHROMA_UPSERT_BATCH):
                end = start + _CHROMA_UPSERT_BATCH
                self._collection.upsert(
                    ids=list(ids[start:end]),
                    embeddings=np.asarray(vectors[start:end], dtype=np.float32),
                    metadatas=[dict(metadata) for metadata in metadatas[start:end]],
                )

        if ids:
            await asyncio.to_thread(run)

    async def delete(self, ids: Sequence[str]) -> None:
        if ids:
            await asyncio.to_thread(self._collection.delete, ids=list(ids))

    async def ids(self) -> set[str]:
        result = await asyncio.to_thread(self._collection.get, include=[])
        return set(result["ids"])

    async def count(self) -> int:
        return await asyncio.to_thread(self._collection.count)

    async def query(
        self, vector: Vectors, k: int, where: Metadata | None = None
    ) -> list[VectorMatch]:
        def run() -> list[VectorMatch]:
            n_results = min(k, self._collection.count())
            if n_results <= 0:
                return []
            result = self._collection.query(
                query_embeddings=np.asarray(vector, dtype=np.float32).reshape(1, -1),
                n_results=n_results,
                where=_chroma_where(where),
                include=["distances"],
            )
            distances = result["distances"]
            assert distances is not None  # requested via `include`
            return [
                VectorMatch(item_id, 1.0 - distance)
                for item_id, distance in zip(result["ids"][0], distances[0], strict=True)
            ]

        return await asyncio.to_thread(run)


def _chroma_where(where: Metadata | None) -> Any:
    if not where:
        return None
    clauses = [{key: value} for key, value in where.items()]
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def _check_lengths(ids: Sequence[str], vectors: Vectors, metadatas: Sequence[Metadata]) -> None:
    if not len(ids) == len(vectors) == len(metadatas):
        raise ValueError(
            f"ids ({len(ids)}), vectors ({len(vectors)}) and metadatas ({len(metadatas)}) "
            "must have the same length"
        )


def create_vector_store(settings: Settings, dimension: int) -> VectorStore:
    if settings.vector_store == "numpy":
        return NumpyVectorStore(dimension)
    return ChromaVectorStore(persist_dir=settings.vector_store_persist_dir)
