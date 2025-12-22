import numpy as np

from retrieval.engines.faiss_ip import build_ip_index, search_ip


def test_faiss_ip_search_returns_best_match() -> None:
    vectors = np.asarray(
        [
            [1.0, 0.0],
            [0.0, 1.0],
            [0.5, 0.5],
        ],
        dtype=np.float32,
    )
    index = build_ip_index(vectors)

    scores, indices = search_ip(index, np.asarray([1.0, 0.0], dtype=np.float32), top_n=2)

    assert scores.shape == (1, 2)
    assert indices.shape == (1, 2)
    assert indices[0, 0] == 0
    assert scores[0, 0] >= scores[0, 1]

