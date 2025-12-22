"""FAISS helpers for inner-product search."""

from __future__ import annotations

import os
import sys
from typing import Tuple

import numpy as np


def build_ip_index(vectors: np.ndarray):
    """Build a FAISS IndexFlatIP over the provided vectors."""
    try:
        if sys.platform == "darwin":
            os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
        import faiss  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "faiss is required for FAISS indexing. Install faiss-cpu."
        ) from exc

    from typing import Any, cast

    faiss_any = cast(Any, faiss)
    dense = _as_float32_matrix(vectors)
    if dense.size == 0:
        raise ValueError("vectors must not be empty")

    index = faiss_any.IndexFlatIP(dense.shape[1])
    index.add(dense)
    return index


def search_ip(
    index,
    queries: np.ndarray,
    *,
    top_n: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Search a FAISS inner-product index.

    Returns:
        (scores, indices) with shapes (n_queries, top_n).
    """
    if top_n < 1:
        raise ValueError("top_n must be >= 1")

    dense = _as_float32_matrix(queries)
    if getattr(index, "ntotal", 0) == 0:
        return np.zeros((dense.shape[0], 0), dtype=np.float32), np.zeros(
            (dense.shape[0], 0), dtype=np.int64
        )

    dim = getattr(index, "d", None)
    if dim is None:
        raise ValueError("Unsupported FAISS index (missing 'd').")
    if dense.shape[1] != int(dim):
        raise ValueError(f"Query dim {dense.shape[1]} != index dim {dim}")

    k = min(int(top_n), int(getattr(index, "ntotal", top_n)))
    scores, indices = index.search(dense, k)
    return scores, indices


def _as_float32_matrix(array: np.ndarray) -> np.ndarray:
    dense = np.asarray(array, dtype=np.float32)
    if dense.ndim == 1:
        dense = dense.reshape(1, -1)
    if dense.ndim != 2:
        raise ValueError("Expected a 2D matrix")
    return np.ascontiguousarray(dense)


__all__ = ["build_ip_index", "search_ip"]
