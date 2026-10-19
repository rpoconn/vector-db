from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pytest

from app.features.search import embedding as embedding_module
from app.features.search.embedding import (
    FastEmbedEmbedder,
    HashingEmbedder,
    create_embedder,
    is_transient_model_error,
)
from app.shared.config import Settings


async def test_hashing_embedder_is_deterministic_and_normalized() -> None:
    embedder = HashingEmbedder(dimension=64)

    documents = await embedder.embed_documents(["Brass desk lamp", "Wool rug", ""])
    query = await embedder.embed_query("Brass desk lamp")

    assert documents.shape == (3, 64)
    assert documents.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(documents[:2], axis=1), 1.0, rtol=1e-6)
    assert not documents[2].any()
    np.testing.assert_array_equal(documents[0], query)
    assert embedder.model_name == "hashing-64"
    assert embedder.dimension == 64


async def test_hashing_embedder_scores_shared_words_higher() -> None:
    embedder = HashingEmbedder()
    lamp, rug = await embedder.embed_documents(["brass desk LAMP", "wool area rug"])
    query = await embedder.embed_query("lamp for my desk")

    assert float(query @ lamp) > float(query @ rug)


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (ConnectionError("refused"), True),
        (TimeoutError(), True),
        (ValueError("Could not load model BAAI/x from any source."), True),
        (ValueError("Model x is not supported"), False),
        (RuntimeError("boom"), False),
    ],
)
def test_is_transient_model_error(exc: BaseException, expected: bool) -> None:
    assert is_transient_model_error(exc) is expected


class _FakeTextEmbedding:
    """Stands in for fastembed.TextEmbedding; fails to load `failures` times first."""

    failures: ClassVar[int] = 0
    loads: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, model_name: str, **kwargs: Any) -> None:
        if _FakeTextEmbedding.failures:
            _FakeTextEmbedding.failures -= 1
            raise ValueError(f"Could not load model {model_name} from any source.")
        _FakeTextEmbedding.loads.append({"model_name": model_name, **kwargs})

    @staticmethod
    def get_embedding_size(model_name: str) -> int:
        return 3

    def passage_embed(self, texts: list[str], batch_size: int) -> list[list[float]]:
        """Encodes each text's length so tests can check rows come back in input order."""
        return [[float(len(text)), 0.0, 1.0] for text in texts]

    def query_embed(self, query: str) -> list[list[float]]:
        return [[0.0, 0.0, 2.0]]


@pytest.fixture
def fake_text_embedding(monkeypatch: pytest.MonkeyPatch) -> type[_FakeTextEmbedding]:
    _FakeTextEmbedding.failures = 0
    _FakeTextEmbedding.loads = []
    monkeypatch.setattr(embedding_module, "TextEmbedding", _FakeTextEmbedding)
    return _FakeTextEmbedding


async def test_fastembed_embedder_retries_model_download_and_loads_once(
    fake_text_embedding: type[_FakeTextEmbedding], tmp_path: Path
) -> None:
    fake_text_embedding.failures = 2
    embedder = FastEmbedEmbedder("some/model", tmp_path, retry_min_wait=0)

    documents = await embedder.embed_documents(["long text", "", "mid"])
    query = await embedder.embed_query("q")

    expected = np.array([[9, 0, 1], [0, 0, 1], [3, 0, 1]], dtype=np.float32)
    np.testing.assert_allclose(documents, expected / np.linalg.norm(expected, axis=1)[:, None])
    np.testing.assert_allclose(query, [0.0, 0.0, 1.0])
    assert fake_text_embedding.loads == [{"model_name": "some/model", "cache_dir": str(tmp_path)}]
    assert embedder.dimension == 3


async def test_fastembed_embedder_load_loads_model_eagerly(
    fake_text_embedding: type[_FakeTextEmbedding], tmp_path: Path
) -> None:
    embedder = FastEmbedEmbedder("some/model", tmp_path)

    await embedder.load()
    await embedder.load()

    assert len(fake_text_embedding.loads) == 1


async def test_fastembed_embedder_gives_up_after_max_attempts(
    fake_text_embedding: type[_FakeTextEmbedding], tmp_path: Path
) -> None:
    fake_text_embedding.failures = 5
    embedder = FastEmbedEmbedder("some/model", tmp_path, download_attempts=2, retry_min_wait=0)

    with pytest.raises(ValueError, match="Could not load model"):
        await embedder.embed_query("q")
    assert fake_text_embedding.failures == 3


async def test_fastembed_embedder_skips_model_for_no_documents(
    fake_text_embedding: type[_FakeTextEmbedding], tmp_path: Path
) -> None:
    embedder = FastEmbedEmbedder("some/model", tmp_path)

    assert (await embedder.embed_documents([])).shape == (0, 3)
    assert fake_text_embedding.loads == []


def test_create_embedder_follows_settings(tmp_path: Path) -> None:
    hashing = create_embedder(Settings(embedder="hashing", _env_file=None))
    real = create_embedder(
        Settings(embedder="fastembed", embedding_cache_dir=tmp_path, _env_file=None)
    )

    assert isinstance(hashing, HashingEmbedder)
    assert isinstance(real, FastEmbedEmbedder)
    assert (real.model_name, real.dimension) == ("BAAI/bge-small-en-v1.5", 384)


@pytest.mark.slow
async def test_fastembed_embedder_captures_meaning() -> None:
    """Downloads the real model (~70 MB) into the data dir on first run."""
    embedder = create_embedder(Settings(embedder="fastembed", _env_file=None))
    blanket, drill = await embedder.embed_documents(
        ["Soft fleece throw blanket for the couch", "Cordless power drill with two batteries"]
    )
    query = await embedder.embed_query("something cozy to keep warm")

    assert float(query @ blanket) > float(query @ drill)
