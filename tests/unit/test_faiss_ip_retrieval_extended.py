"""Unit tests for the FAISS IP retrieval module."""

import pytest
import numpy as np
from retrieval.engines.faiss_ip import build_ip_index, search_ip


def test_faiss_build_ip_index_basic():
    """Test basic FAISS IP index building."""
    dimension = 128
    vectors = np.random.rand(10, dimension).astype(np.float32)

    index = build_ip_index(vectors)

    # Index should be built successfully
    assert hasattr(index, "ntotal")
    assert index.ntotal == 10
    assert hasattr(index, "d")
    assert index.d == dimension


def test_faiss_search_ip_basic():
    """Test basic search functionality."""
    dimension = 64
    num_vectors = 5
    vectors = np.random.rand(num_vectors, dimension).astype(np.float32)

    index = build_ip_index(vectors)

    query_vector = np.random.rand(dimension).astype(np.float32)
    scores, indices = search_ip(index, query_vector, top_n=3)

    assert isinstance(scores, np.ndarray)
    assert isinstance(indices, np.ndarray)
    assert scores.shape[0] == 1  # 1 query
    assert indices.shape[0] == 1  # 1 query
    assert scores.shape[1] <= 3  # At most 3 results per query
    assert indices.shape[1] <= 3  # At most 3 results per query


def test_faiss_search_ip_multiple_queries():
    """Test search with multiple queries."""
    dimension = 32
    vectors = np.random.rand(10, dimension).astype(np.float32)

    index = build_ip_index(vectors)

    query_vectors = np.random.rand(3, dimension).astype(np.float32)  # 3 queries
    scores, indices = search_ip(index, query_vectors, top_n=5)

    assert scores.shape[0] == 3  # 3 queries
    assert indices.shape[0] == 3  # 3 queries
    assert scores.shape[1] <= 5  # At most 5 results per query
    assert indices.shape[1] <= 5  # At most 5 results per query


def test_faiss_search_ip_top_n_limit():
    """Test that search respects the top_n parameter."""
    dimension = 64
    vectors = np.random.rand(10, dimension).astype(np.float32)

    index = build_ip_index(vectors)

    query_vector = np.random.rand(dimension).astype(np.float32)
    scores, indices = search_ip(index, query_vector, top_n=2)

    assert scores.shape[1] <= 2
    assert indices.shape[1] <= 2


def test_faiss_search_ip_single_vector():
    """Test search with a single vector."""
    dimension = 16
    vectors = np.random.rand(1, dimension).astype(np.float32)

    index = build_ip_index(vectors)

    query = np.random.rand(dimension).astype(np.float32)
    scores, indices = search_ip(index, query, top_n=5)

    assert isinstance(scores, np.ndarray)
    assert isinstance(indices, np.ndarray)
    assert 0 <= scores.shape[1] <= 5
    assert 0 <= indices.shape[1] <= 5


def test_faiss_search_ip_normalized_vectors():
    """Test search with normalized vectors."""
    dimension = 64
    vectors = np.random.rand(5, dimension).astype(np.float32)
    # Normalize vectors
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / norms

    index = build_ip_index(vectors)

    query = np.random.rand(dimension).astype(np.float32)
    query = query / np.linalg.norm(query)  # Also normalize query
    scores, indices = search_ip(index, query, top_n=3)

    assert isinstance(scores, np.ndarray)
    assert isinstance(indices, np.ndarray)


def test_faiss_search_ip_large_dimensions():
    """Test search with larger dimensions."""
    dimension = 512  # Larger dimension
    vectors = np.random.rand(3, dimension).astype(np.float32)

    index = build_ip_index(vectors)

    query = np.random.rand(dimension).astype(np.float32)
    scores, indices = search_ip(index, query, top_n=2)

    assert isinstance(scores, np.ndarray)
    assert isinstance(indices, np.ndarray)


def test_faiss_search_ip_large_number_of_vectors():
    """Test search with a larger number of vectors."""
    dimension = 32
    num_vectors = 50
    vectors = np.random.rand(num_vectors, dimension).astype(np.float32)

    index = build_ip_index(vectors)

    query = np.random.rand(dimension).astype(np.float32)
    scores, indices = search_ip(index, query, top_n=10)

    assert isinstance(scores, np.ndarray)
    assert isinstance(indices, np.ndarray)
    assert scores.shape[1] <= 10
    assert indices.shape[1] <= 10


def test_faiss_search_ip_zero_top_n():
    """Test search with top_n=0 (should raise error)."""
    dimension = 32
    vectors = np.random.rand(5, dimension).astype(np.float32)

    index = build_ip_index(vectors)

    query = np.random.rand(dimension).astype(np.float32)

    with pytest.raises(ValueError, match="top_n must be >= 1"):
        search_ip(index, query, top_n=0)


def test_faiss_search_ip_query_wrong_dimension():
    """Test search with query vector of wrong dimension."""
    dimension = 64
    vectors = np.random.rand(5, dimension).astype(np.float32)

    index = build_ip_index(vectors)

    wrong_dimension_query = np.random.rand(dimension + 10).astype(
        np.float32
    )  # Wrong dimension

    with pytest.raises(ValueError, match="Query dim"):
        search_ip(index, wrong_dimension_query, top_n=5)


def test_faiss_search_ip_all_zeros_vector():
    """Test search with all zeros vectors."""
    dimension = 32
    vectors = np.zeros((2, dimension)).astype(np.float32)

    index = build_ip_index(vectors)

    query = np.zeros(dimension).astype(np.float32)
    scores, indices = search_ip(index, query, top_n=5)

    assert isinstance(scores, np.ndarray)
    assert isinstance(indices, np.ndarray)


def test_faiss_search_ip_single_query_vector():
    """Test search with single query vector (not reshaped)."""
    dimension = 32
    vectors = np.random.rand(5, dimension).astype(np.float32)

    index = build_ip_index(vectors)

    # Single dimensional query (should be reshaped internally)
    query = np.random.rand(dimension).astype(np.float32)  # 1D array
    scores, indices = search_ip(index, query, top_n=3)

    assert isinstance(scores, np.ndarray)
    assert isinstance(indices, np.ndarray)
    assert scores.shape[0] == 1  # Should be treated as 1 query
    assert indices.shape[0] == 1  # Should be treated as 1 query


def test_faiss_empty_vectors_error():
    """Test that building index with empty vectors raises error."""
    dimension = 64
    empty_vectors = np.array([]).reshape(0, dimension).astype(np.float32)

    with pytest.raises(ValueError, match="vectors must not be empty"):
        build_ip_index(empty_vectors)


def test_faiss_search_on_empty_index():
    """Test searching on an index with no vectors."""
    # Actually, this may not be possible since build_index will fail with empty vectors
    # But we can test the scenario with just 1 vector and see behavior
    dimension = 32
    vectors = np.random.rand(1, dimension).astype(np.float32)

    index = build_ip_index(vectors)

    query = np.random.rand(dimension).astype(np.float32)
    scores, indices = search_ip(index, query, top_n=1)

    # Should return results successfully
    assert isinstance(scores, np.ndarray)
    assert isinstance(indices, np.ndarray)
