"""Vector array type and helpers shared by embedders and vector stores."""

import numpy as np
from numpy.typing import NDArray

type Vectors = NDArray[np.float32]


def normalize_rows(vectors: Vectors) -> Vectors:
    """Scale each vector (the last axis) to unit length; zero vectors stay zero."""
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)


def to_blob(vector: Vectors) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def from_blob(blob: bytes) -> Vectors:
    return np.frombuffer(blob, dtype=np.float32)
