"""Text embedders: a real ONNX model (fastembed) and a deterministic hashing stand-in."""

import asyncio
import hashlib
import logging
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import numpy as np
from fastembed import TextEmbedding

from app.features.search.vectors import Vectors, normalize_rows
from app.shared.config import Settings
from app.shared.retry import retrying

logger = logging.getLogger(__name__)

# Small batches of similar-length texts minimize padding; ~2.5x faster than 64 unsorted on CPU.
DEFAULT_BATCH_SIZE = 16
HASHING_DIMENSION = 256
_TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    """Turns text into L2-normalized float32 vectors."""

    @property
    def model_name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    async def load(self) -> None:
        """Get ready to embed (e.g. fetch and load model files) so the first call is fast."""
        ...

    async def embed_documents(self, texts: Sequence[str]) -> Vectors:
        """One row per text, shape `(len(texts), dimension)`."""
        ...

    async def embed_query(self, text: str) -> Vectors:
        """A single vector, shape `(dimension,)`."""
        ...


def is_transient_model_error(exc: BaseException) -> bool:
    """Network failures while fetching model files (fastembed wraps them in a ValueError)."""
    if isinstance(exc, OSError):
        return True
    return isinstance(exc, ValueError) and str(exc).startswith("Could not load model")


class FastEmbedEmbedder:
    """ONNX sentence-embedding model, downloaded once into `cache_dir`.

    The model is loaded by `load()`, or lazily by the first embedding call.
    """

    def __init__(
        self,
        model_name: str,
        cache_dir: Path,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        download_attempts: int = 5,
        retry_min_wait: float = 1.0,
    ) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._batch_size = batch_size
        self._download_attempts = download_attempts
        self._retry_min_wait = retry_min_wait
        self._model: TextEmbedding | None = None
        self._load_lock = asyncio.Lock()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return TextEmbedding.get_embedding_size(self._model_name)

    async def load(self) -> None:
        await self._get_model()

    async def _get_model(self) -> TextEmbedding:
        async with self._load_lock:
            if self._model is None:
                self._model = await asyncio.to_thread(self._load)
            return self._model

    def _load(self) -> TextEmbedding:
        logger.info("Loading embedding model %s (cache: %s)", self._model_name, self._cache_dir)
        policy = retrying(
            is_transient_model_error,
            attempts=self._download_attempts,
            min_wait=self._retry_min_wait,
        )
        return policy(TextEmbedding, self._model_name, cache_dir=str(self._cache_dir))

    async def embed_documents(self, texts: Sequence[str]) -> Vectors:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        model = await self._get_model()

        def run() -> Vectors:
            order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
            rows = model.passage_embed([texts[i] for i in order], batch_size=self._batch_size)
            embedded = np.asarray(list(rows), dtype=np.float32)
            result = np.empty_like(embedded)
            result[order] = embedded
            return normalize_rows(result)

        return await asyncio.to_thread(run)

    async def embed_query(self, text: str) -> Vectors:
        model = await self._get_model()

        def run() -> Vectors:
            (row,) = model.query_embed(text)
            return normalize_rows(np.asarray(row, dtype=np.float32))

        return await asyncio.to_thread(run)


class HashingEmbedder:
    """Bag-of-words feature hashing: deterministic, instant, lexical rather than semantic.

    Texts that share words get similar vectors, which is enough for tests and e2e runs.
    """

    def __init__(self, dimension: int = HASHING_DIMENSION) -> None:
        self._dimension = dimension

    @property
    def model_name(self) -> str:
        return f"hashing-{self._dimension}"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def load(self) -> None:
        pass

    def _embed(self, text: str) -> Vectors:
        vector = np.zeros(self._dimension, dtype=np.float32)
        for token in _TOKEN.findall(text.lower()):
            digest = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest())
            vector[digest % self._dimension] += 1.0 if digest >> 63 else -1.0
        return normalize_rows(vector)

    async def embed_documents(self, texts: Sequence[str]) -> Vectors:
        matrix = np.empty((len(texts), self._dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            matrix[row] = self._embed(text)
        return matrix

    async def embed_query(self, text: str) -> Vectors:
        return self._embed(text)


def create_embedder(settings: Settings) -> Embedder:
    if settings.embedder == "hashing":
        return HashingEmbedder()
    return FastEmbedEmbedder(settings.embedding_model, settings.embedding_cache_dir)
